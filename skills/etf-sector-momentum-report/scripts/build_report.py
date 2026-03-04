#!/usr/bin/env python3
"""Build a short/mid/long ETF sector trend report from a Google Sheet."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1_xv9pPrxhx9A4OyhrvyTTJuKNXk8rn0m-eAWvnbdXWI/edit?gid=878537610#gid=878537610"
)
DEFAULT_HISTORY_DIR = "artifacts/etf-sector-momentum-report"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet-url", default=DEFAULT_SHEET_URL, help="Google Sheets URL")
    parser.add_argument(
        "--history-dir",
        default=DEFAULT_HISTORY_DIR,
        help="Directory for raw CSV, snapshots, and reports",
    )
    parser.add_argument("--output", help="Optional markdown output path")
    return parser.parse_args()


def extract_sheet_ids(sheet_url: str) -> tuple[str, str]:
    sheet_match = re.search(r"/d/([a-zA-Z0-9_-]+)", sheet_url)
    gid_match = re.search(r"gid=(\d+)", sheet_url)
    if not sheet_match or not gid_match:
        raise ValueError("Could not parse sheet id and gid from the Google Sheets URL.")
    return sheet_match.group(1), gid_match.group(1)


def build_export_url(sheet_url: str) -> str:
    sheet_id, gid = extract_sheet_ids(sheet_url)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def fetch_csv_text(sheet_url: str) -> str:
    export_url = build_export_url(sheet_url)
    request = urllib.request.Request(
        export_url,
        headers={"User-Agent": "Mozilla/5.0 Codex ETF Sector Momentum Report"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read().decode("utf-8-sig")
    if "text/csv" not in content_type and "," not in body:
        raise RuntimeError("The Google Sheet did not return CSV data. Check sharing permissions.")
    return body


def parse_rows(csv_text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(csv_text)))


def parse_percent(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    return float(value.rstrip("%"))


def parse_float(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    return float(value)


def mean(values: list[float | None]) -> float:
    filtered = [value for value in values if value is not None]
    return sum(filtered) / len(filtered) if filtered else 0.0


def scale_percent(value: float, lower: float, upper: float) -> float:
    if math.isclose(lower, upper):
        return 50.0
    clamped = min(max(value, lower), upper)
    return ((clamped - lower) / (upper - lower)) * 100.0


def parse_sheet(csv_text: str) -> tuple[str, list[dict[str, object]]]:
    rows = parse_rows(csv_text)
    header_index = None
    for index, row in enumerate(rows):
        if len(row) > 4 and row[2].strip() == "Ticker":
            header_index = index
            break
    if header_index is None:
        raise RuntimeError("Could not find the ETF table header row.")

    report_date = rows[2][2].strip() if len(rows) > 2 and len(rows[2]) > 2 else ""
    header = rows[header_index][2:18]
    sector = None
    items: list[dict[str, object]] = []

    for row in rows[header_index + 1 :]:
        cells = row[2:18]
        if not any(cell.strip() for cell in cells):
            continue
        ticker = cells[0].strip()
        name = cells[1].strip()
        if ticker and not name:
            sector = ticker
            continue
        if not ticker or sector is None:
            continue
        item = {header[i]: cells[i].strip() for i in range(len(header))}
        item["Sector"] = sector
        item["Price"] = parse_float(str(item["Price"]))
        for key in ("R20", "R60", "R120", "Rank"):
            item[key] = parse_float(str(item[key]))
        for key in ("1D%", "REL5", "REL20", "REL60", "REL120", "From 2025-12-31"):
            item[key] = parse_percent(str(item[key]))
        items.append(item)

    if not report_date:
        report_date = datetime.now().strftime("%Y-%m-%d")
    return report_date, items


def build_sector_metrics(items: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in items:
        grouped[str(item["Sector"])].append(item)

    sectors: list[dict[str, object]] = []
    for sector_name, sector_items in grouped.items():
        avg_rank = mean([item["Rank"] for item in sector_items])  # type: ignore[index]
        avg_rel5 = mean([item["REL5"] for item in sector_items])  # type: ignore[index]
        avg_rel20 = mean([item["REL20"] for item in sector_items])  # type: ignore[index]
        avg_rel60 = mean([item["REL60"] for item in sector_items])  # type: ignore[index]
        avg_rel120 = mean([item["REL120"] for item in sector_items])  # type: ignore[index]
        avg_1d = mean([item["1D%"] for item in sector_items])  # type: ignore[index]
        avg_r20 = mean([item["R20"] for item in sector_items])  # type: ignore[index]
        avg_r60 = mean([item["R60"] for item in sector_items])  # type: ignore[index]
        avg_r120 = mean([item["R120"] for item in sector_items])  # type: ignore[index]
        avg_ytd = mean([item["From 2025-12-31"] for item in sector_items])  # type: ignore[index]
        consistency = sum(
            1
            for item in sector_items
            if (item["Rank"] or 0) >= 60 or (item["REL20"] or -999) >= 0  # type: ignore[index]
        ) / len(sector_items)
        rel5_score = scale_percent(avg_rel5, -8.0, 8.0)
        rel20_score = scale_percent(avg_rel20, -10.0, 10.0)
        rel60_score = scale_percent(avg_rel60, -20.0, 20.0)
        rel120_score = scale_percent(avg_rel120, -25.0, 25.0)
        one_day_score = scale_percent(avg_1d, -3.0, 3.0)
        base_short_term_score = (
            (avg_rank * 0.30)
            + (rel5_score * 0.25)
            + (rel20_score * 0.20)
            + (one_day_score * 0.15)
            + (consistency * 100.0 * 0.10)
        )
        mid_term_score = (
            (avg_r20 * 0.30)
            + (avg_r60 * 0.25)
            + (rel20_score * 0.20)
            + (rel60_score * 0.15)
            + (consistency * 100.0 * 0.10)
        )
        long_term_score = (
            (avg_r60 * 0.30)
            + (avg_r120 * 0.30)
            + (rel60_score * 0.15)
            + (rel120_score * 0.15)
            + (consistency * 100.0 * 0.10)
        )
        leaders = sorted(
            sector_items,
            key=lambda item: ((item["Rank"] or 0), (item["REL20"] or -999)),  # type: ignore[index]
            reverse=True,
        )[:3]
        sectors.append(
            {
                "sector": sector_name,
                "count": len(sector_items),
                "avg_rank": round(avg_rank, 2),
                "avg_rel5": round(avg_rel5, 2),
                "avg_rel20": round(avg_rel20, 2),
                "avg_rel60": round(avg_rel60, 2),
                "avg_rel120": round(avg_rel120, 2),
                "avg_1d": round(avg_1d, 2),
                "avg_r20": round(avg_r20, 2),
                "avg_r60": round(avg_r60, 2),
                "avg_r120": round(avg_r120, 2),
                "avg_ytd": round(avg_ytd, 2),
                "consistency": round(consistency, 4),
                "base_short_term_score": round(base_short_term_score, 2),
                "short_term_score": round(base_short_term_score, 2),
                "current_score": round(base_short_term_score, 2),
                "mid_term_score": round(mid_term_score, 2),
                "long_term_score": round(long_term_score, 2),
                "leaders": [str(item["Ticker"]) for item in leaders],
            }
        )
    sectors.sort(key=lambda sector: sector["base_short_term_score"], reverse=True)
    return sectors


def load_previous_snapshots(snapshot_dir: Path, report_date: str) -> list[dict[str, object]]:
    snapshots: list[dict[str, object]] = []
    for path in sorted(snapshot_dir.glob("*.json")):
        if path.stem == report_date:
            continue
        snapshots.append(json.loads(path.read_text()))
    return snapshots[-2:]


def build_history_lookup(snapshots: list[dict[str, object]]) -> dict[str, list[float]]:
    history: dict[str, list[float]] = defaultdict(list)
    for snapshot in snapshots:
        for sector in snapshot.get("sector_metrics", []):
            history[str(sector["sector"])].append(
                float(
                    sector.get(
                        "base_short_term_score",
                        sector.get("short_term_score", sector.get("current_score", 0.0)),
                    )
                )
            )
    return history


def classify_state(score: float) -> str:
    if score >= 70:
        return "强势"
    if score >= 60:
        return "偏强"
    if score < 40:
        return "弱势"
    if score < 50:
        return "偏弱"
    return "震荡"


def classify_trade_action(short_term: str, mid_term: str, long_term: str) -> str:
    strong_states = {"强势", "偏强"}
    weak_states = {"偏弱", "弱势"}

    if short_term in strong_states:
        if mid_term in strong_states and long_term in strong_states:
            return "顺势做多"
        if mid_term in strong_states and long_term in weak_states:
            return "可做，但更偏反弹交易"
        if mid_term in weak_states and long_term in weak_states:
            return "只按反弹对待，快进快出"
        return "可做，但更偏反弹交易"
    if short_term in weak_states:
        if mid_term in strong_states and long_term in strong_states:
            return "等回踩，不追"
        if mid_term in weak_states and long_term in weak_states:
            return "回避"
        return "观察"
    if mid_term in strong_states and long_term in strong_states:
        return "等回踩，不追"
    if mid_term in weak_states and long_term in weak_states:
        return "回避"
    return "观察"


def enrich_with_history(sectors: list[dict[str, object]], history_lookup: dict[str, list[float]]) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for sector in sectors:
        base_short_term_score = float(sector["base_short_term_score"])
        series = history_lookup.get(str(sector["sector"]), [])[-2:] + [base_short_term_score]
        available = len(series)
        if available == 1:
            three_day_score = series[0]
        elif available == 2:
            three_day_score = (series[0] * 0.4) + (series[1] * 0.6)
        else:
            three_day_score = (series[0] * 0.2) + (series[1] * 0.3) + (series[2] * 0.5)
        slope = series[-1] - series[0]
        slope_adjustment = max(min(slope * 0.15, 5.0), -5.0)
        three_day_score = round(three_day_score + slope_adjustment, 2)
        trend_score = scale_percent(slope, -15.0, 15.0)
        short_term_score = round((base_short_term_score * 0.75) + (trend_score * 0.25), 2)
        short_term_conclusion = classify_state(short_term_score)
        mid_term_conclusion = classify_state(float(sector["mid_term_score"]))
        long_term_conclusion = classify_state(float(sector["long_term_score"]))
        action = classify_trade_action(short_term_conclusion, mid_term_conclusion, long_term_conclusion)
        enriched_sector = dict(sector)
        enriched_sector["short_term_score"] = short_term_score
        enriched_sector["three_day_score"] = three_day_score
        enriched_sector["history_points"] = available
        enriched_sector["slope"] = round(slope, 2)
        enriched_sector["short_term_conclusion"] = short_term_conclusion
        enriched_sector["mid_term_conclusion"] = mid_term_conclusion
        enriched_sector["long_term_conclusion"] = long_term_conclusion
        enriched_sector["action"] = action
        enriched.append(enriched_sector)
    enriched.sort(key=lambda sector: (sector["short_term_score"], sector["three_day_score"]), reverse=True)
    return enriched


def format_sector_row(index: int, sector: dict[str, object]) -> str:
    return (
        f"| {index} | {sector['sector']} | {sector['short_term_score']:.2f} | "
        f"{sector['three_day_score']:.2f} | {sector['short_term_conclusion']} | "
        f"{sector['mid_term_conclusion']} | {sector['long_term_conclusion']} | {sector['action']} |"
    )


def invalidation_text(sector: dict[str, object], is_top: bool) -> str:
    if is_top:
        return "若短线分数跌出板块前三，且中期或长期结论同步转弱，则顺势判断失效。"
    return "若短线重新回到前列，并且中期结论从偏弱修复到震荡以上，才考虑取消回避判断。"


def scenario_block(top_sector: dict[str, object]) -> str:
    name = str(top_sector["sector"])
    return "\n".join(
        [
            "## 五、未来1-3天推演",
            "",
            "### 情景A：延续",
            f"- 触发条件：`{name}` 继续保持短线第一，且中期、长期结论维持在`偏强`以上。",
            "- 交易含义：继续围绕主线做强，不切换到弱板块抄底。",
            "",
            "### 情景B：分化",
            f"- 触发条件：`{name}` 短线仍强，但中期或长期结论回落到`震荡`或以下，只剩少数龙头ETF维持强势。",
            "- 交易含义：从做板块切到做龙头，降低仓位扩张意愿。",
            "",
            "### 情景C：退潮",
            f"- 触发条件：`{name}` 短线分数和3日分数同步回落，且中期、长期最强板块开始切换。",
            "- 交易含义：停止追强，等待新的三日动能龙头出现。",
        ]
    )


def build_report(report_date: str, sectors: list[dict[str, object]]) -> str:
    top_sector = sectors[0]
    top_three_day = max(sectors, key=lambda sector: (sector["three_day_score"], sector["short_term_score"]))
    top_mid_term = max(sectors, key=lambda sector: (sector["mid_term_score"], sector["short_term_score"]))
    top_long_term = max(sectors, key=lambda sector: (sector["long_term_score"], sector["mid_term_score"]))
    top_names = [str(sector["sector"]) for sector in sectors[:3]]
    weakest = list(reversed(sectors[-2:]))
    weak_names = [str(sector["sector"]) for sector in weakest]
    observe_names = [str(sector["sector"]) for sector in sectors[2:4]]
    provisional = any(int(sector["history_points"]) < 3 for sector in sectors)

    lines = [
        "# ETF 板块动能日报",
        f"日期：{report_date}",
        "交易周期：1-3天",
        "",
        "## 一、首页结论",
        f"- 今日最强板块：`{top_sector['sector']}`",
        f"- 近3日最强板块：`{top_three_day['sector']}`",
        f"- 中期最强板块：`{top_mid_term['sector']}`",
        f"- 长期最强板块：`{top_long_term['sector']}`",
        f"- 当前主线方向：`{' / '.join(top_names[:2])}`",
        f"- 当前回避方向：`{' / '.join(weak_names)}`",
        (
            "- 说明：近3日结论为暂定值，历史快照不足 3 天。"
            if provisional
            else "- 说明：近3日结论基于最近 3 个交易日快照。"
        ),
        "",
        "一句话结论：",
        (
            f"`{top_sector['sector']}` 在短线仍最强，`{top_mid_term['sector']}` 的中期结构最好，"
            f"`{top_long_term['sector']}` 的60-120日趋势最稳；优先围绕 `{top_names[0]}` 和 `{top_names[1]}` 做顺势交易，"
            f"回避 `{weak_names[0]}` 与 `{weak_names[1]}`。"
        ),
        "",
        "## 二、板块强弱总表",
        "| 排名 | 板块 | 当日动能 | 3日动能 | 短线结论 | 中期结论 | 长期结论 | 交易结论 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, sector in enumerate(sectors, start=1):
        lines.append(format_sector_row(index, sector))

    strongest_focus = []
    strongest_names = []
    for candidate in (top_sector, top_mid_term, top_long_term):
        sector_name = str(candidate["sector"])
        if sector_name in strongest_names:
            continue
        strongest_names.append(sector_name)
        strongest_focus.append(candidate)

    lines.extend(["", "## 三、最强板块拆解", ""])
    for sector in strongest_focus:
        lines.extend(
            [
                f"### {sector['sector']}",
                f"- 短线结论：{sector['short_term_conclusion']}",
                f"- 中期结论：{sector['mid_term_conclusion']}",
                f"- 长期结论：{sector['long_term_conclusion']}",
                (
                    f"- 理由：当日分数 `{sector['short_term_score']:.2f}`，3日分数 `{sector['three_day_score']:.2f}`，"
                    f"中期分数 `{sector['mid_term_score']:.2f}`，长期分数 `{sector['long_term_score']:.2f}`，"
                    f"内部一致性 `{float(sector['consistency']) * 100:.0f}%`，代表ETF `{', '.join(sector['leaders'])}`。"
                ),
                f"- 交易动作：{sector['action']}",
                f"- 失效条件：{invalidation_text(sector, True)}",
                "",
            ]
        )

    lines.extend(["## 四、最弱板块拆解", ""])
    for sector in list(reversed(sectors[-2:])):
        lines.extend(
            [
                f"### {sector['sector']}",
                f"- 短线结论：{sector['short_term_conclusion']}",
                f"- 中期结论：{sector['mid_term_conclusion']}",
                f"- 长期结论：{sector['long_term_conclusion']}",
                (
                    f"- 理由：当日分数 `{sector['short_term_score']:.2f}`，3日分数 `{sector['three_day_score']:.2f}`，"
                    f"中期分数 `{sector['mid_term_score']:.2f}`，长期分数 `{sector['long_term_score']:.2f}`，"
                    f"内部一致性 `{float(sector['consistency']) * 100:.0f}%`。"
                ),
                f"- 交易动作：{sector['action']}",
                f"- 失效条件：{invalidation_text(sector, False)}",
                "",
            ]
        )

    lines.extend(["", scenario_block(top_sector), "", "## 六、执行摘要"])
    lines.extend(
        [
            f"- 最值得交易：`{top_names[0]}`",
            f"- 次优方向：`{top_names[1]}`",
            f"- 观察名单：`{' / '.join(observe_names)}`",
            f"- 回避名单：`{' / '.join(weak_names)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def save_outputs(
    history_dir: Path,
    report_date: str,
    csv_text: str,
    sectors: list[dict[str, object]],
    report_markdown: str,
    output_path: str | None,
    sheet_url: str,
) -> Path:
    raw_dir = history_dir / "raw"
    snapshot_dir = history_dir / "snapshots"
    report_dir = history_dir / "reports"
    for path in (raw_dir, snapshot_dir, report_dir):
        path.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / f"{report_date}.csv"
    raw_path.write_text(csv_text, encoding="utf-8")

    snapshot = {
        "report_date": report_date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sheet_url": sheet_url,
        "sector_metrics": sectors,
    }
    snapshot_path = snapshot_dir / f"{report_date}.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    final_output = Path(output_path) if output_path else report_dir / f"{report_date}-etf-sector-momentum.md"
    final_output.parent.mkdir(parents=True, exist_ok=True)
    final_output.write_text(report_markdown, encoding="utf-8")
    return final_output


def main() -> int:
    args = parse_args()
    history_dir = Path(args.history_dir)
    try:
        csv_text = fetch_csv_text(args.sheet_url)
        report_date, items = parse_sheet(csv_text)
        sectors = build_sector_metrics(items)
        previous_snapshots = load_previous_snapshots(history_dir / "snapshots", report_date)
        history_lookup = build_history_lookup(previous_snapshots)
        sectors = enrich_with_history(sectors, history_lookup)
        report_markdown = build_report(report_date, sectors)
        output_path = save_outputs(
            history_dir,
            report_date,
            csv_text,
            sectors,
            report_markdown,
            args.output,
            args.sheet_url,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
