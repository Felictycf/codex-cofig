#!/usr/bin/env python3
"""Contract checks for the ETF sector momentum report."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BUILD_SCRIPT = SCRIPT_DIR / "build_report.py"
ALLOWED_STATES = {"强势", "偏强", "震荡", "偏弱", "弱势"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-dir", required=True, help="Directory used by build_report.py")
    return parser.parse_args()


def run_report(history_dir: Path) -> Path:
    result = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--history-dir", str(history_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def read_table_rows(report_text: str) -> list[list[str]]:
    rows = []
    for line in report_text.splitlines():
        if not line.startswith("| ") or "---" in line:
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if parts and parts[0] == "排名":
            continue
        rows.append(parts)
    return rows


def extract_heading_sections(report_text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"^### (.+)$", report_text, re.MULTILINE))
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(report_text)
        sections[name] = report_text[start:end]
    return sections


def extract_homepage_leader(report_text: str, label: str) -> str:
    match = re.search(rf"- {label}：`([^`]+)`", report_text)
    if not match:
        raise SystemExit(f"missing homepage leader for {label}")
    return match.group(1)


def main() -> int:
    args = parse_args()
    history_dir = Path(args.history_dir)
    report_path = run_report(history_dir)
    report_text = report_path.read_text(encoding="utf-8")

    required_header = "| 排名 | 板块 | 当日动能 | 3日动能 | 短线结论 | 中期结论 | 长期结论 | 交易结论 |"
    if required_header not in report_text:
        raise SystemExit("missing strict three-layer table header")

    rows = read_table_rows(report_text)
    if not rows:
        raise SystemExit("missing board summary rows")

    short_leader = extract_homepage_leader(report_text, "今日最强板块")
    mid_leader = extract_homepage_leader(report_text, "中期最强板块")
    long_leader = extract_homepage_leader(report_text, "长期最强板块")
    strongest_sections = extract_heading_sections(report_text)

    for leader in {short_leader, mid_leader, long_leader}:
        if leader not in strongest_sections:
            raise SystemExit(f"missing strongest-sector breakdown for {leader}")

    for row in rows:
        short_state, mid_state, long_state = row[4], row[5], row[6]
        if short_state not in ALLOWED_STATES:
            raise SystemExit(f"short-term state {short_state!r} is not a pure state label")
        if mid_state not in ALLOWED_STATES:
            raise SystemExit(f"mid-term state {mid_state!r} is not a pure state label")
        if long_state not in ALLOWED_STATES:
            raise SystemExit(f"long-term state {long_state!r} is not a pure state label")

    for name, body in strongest_sections.items():
        if name not in {short_leader, mid_leader, long_leader}:
            continue
        for field in ("- 短线结论：", "- 中期结论：", "- 长期结论：", "- 交易动作：", "- 失效条件："):
            if field not in body:
                raise SystemExit(f"{name} strongest-sector block is missing {field}")

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
