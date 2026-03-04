#!/usr/bin/env python3
"""Persist Insight Architect report and append an entry to the MOC file."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import unicodedata
from pathlib import Path


DEFAULT_ROOT = Path("/Users/felicity/work/obsidian-ai/20_Areas/Personal/Explore")
DEFAULT_MOC_FILE = "MOC-Insight-Architect.md"


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).strip().lower()
    normalized = normalized.replace("_", "-")
    slug = re.sub(r"[^\w\-]+", "-", normalized, flags=re.UNICODE).strip("-")
    return slug or "untitled"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for i in range(1, 1000):
        candidate = path.with_name(f"{stem}-{i:02d}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"unable to allocate unique filename for {path}")


def extract_moc_block(report_text: str, title: str, date_str: str, source: str, report_rel: str) -> str:
    pattern = re.compile(
        r"##\s*7\)\s*MOC[^\n]*\n(?:.*?\n)?```markdown\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(report_text)
    if match:
        return match.group(1).strip()

    return (
        f"## {title}\n"
        f"- 日期：{date_str}\n"
        f"- 来源：{source or 'N/A'}\n"
        f"- 报告：[[{report_rel}|查看完整报告]]"
    )


def ensure_moc_header(moc_path: Path) -> None:
    if moc_path.exists():
        return
    header = (
        "# MOC Insight Architect\n\n"
        "> Auto-generated index of saved Insight Architect reports.\n\n"
        "## Entries\n"
    )
    moc_path.write_text(header, encoding="utf-8")


def append_moc_entry(
    moc_path: Path,
    date_str: str,
    title: str,
    source: str,
    report_rel: str,
    moc_block: str,
) -> None:
    entry = (
        "\n---\n\n"
        f"### {date_str} | {title}\n"
        f"- Source: {source or 'N/A'}\n"
        f"- Report: [[{report_rel}|{title}]]\n\n"
        f"{moc_block.strip()}\n"
    )
    with moc_path.open("a", encoding="utf-8") as f:
        f.write(entry)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Save report and append MOC entry.")
    parser.add_argument("--title", required=True, help="Analysis title.")
    parser.add_argument("--source", default="", help="Source URL or label.")
    parser.add_argument("--report-md", required=True, help="Path to generated report markdown.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Obsidian Explore root path.")
    parser.add_argument("--moc-file", default=DEFAULT_MOC_FILE, help="MOC filename under root.")
    parser.add_argument(
        "--date",
        default=dt.date.today().isoformat(),
        help="Date in YYYY-MM-DD format.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser()
    report_src = Path(args.report_md).expanduser()
    if not report_src.exists():
        raise FileNotFoundError(f"report markdown not found: {report_src}")

    try:
        report_date = dt.datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("date must be in YYYY-MM-DD format") from exc

    year = f"{report_date.year:04d}"
    month = f"{report_date.month:02d}"
    report_dir = root / "reports" / year / month
    report_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{args.date}-{slugify(args.title)}-insight.md"
    report_dest = unique_path(report_dir / filename)
    shutil.copy2(report_src, report_dest)

    report_text = report_src.read_text(encoding="utf-8")
    report_rel = report_dest.relative_to(root).as_posix()
    moc_block = extract_moc_block(report_text, args.title, args.date, args.source, report_rel)

    moc_path = root / args.moc_file
    ensure_moc_header(moc_path)
    append_moc_entry(
        moc_path=moc_path,
        date_str=args.date,
        title=args.title,
        source=args.source,
        report_rel=report_rel,
        moc_block=moc_block,
    )

    output = {
        "root": str(root),
        "report_saved_to": str(report_dest),
        "moc_updated": str(moc_path),
        "report_link": report_rel,
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
