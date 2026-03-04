---
name: etf-sector-momentum-report
description: Generate a daily ETF sector trend report from the provided Google Sheets watchlist by fetching the sheet, saving historical snapshots, ranking sectors, and writing a trading-oriented markdown report with separate short-term, mid-term, and long-term conclusions. Use when the user wants ETF板块趋势日报, 板块强弱排行, 当天最强动能, 近3天最强动能, 20-60日趋势, 60-120日趋势, or short-horizon trading suggestions based on this sheet structure.
---

# ETF Sector Momentum Report

## Overview

Generate a repeatable trading report from the Google Sheets ETF watchlist. Pull the latest sheet, normalize sector and ETF rows, save a dated snapshot, and write a markdown report with separate `短线 / 中期 / 长期` conclusions:

- `短线`: current session plus recent `1-3` trading days
- `中期`: `20-60` day structure
- `长期`: `60-120` day structure

## Workflow

1. Use the default Google Sheets URL unless the user gives another public sheet with the same structure.
2. Run `scripts/build_report.py` to fetch the CSV export, parse sectors, compute scores, and save outputs under `artifacts/etf-sector-momentum-report/` in the current workspace.
3. Read the generated markdown report and present the headline conclusions to the user.
4. If the user wants style changes, rewrite the generated markdown instead of recalculating the metrics by hand.

## Command

```bash
python /Users/felicity/.codex/skills/etf-sector-momentum-report/scripts/build_report.py
```

Useful options:

```bash
python /Users/felicity/.codex/skills/etf-sector-momentum-report/scripts/build_report.py \
  --sheet-url "https://docs.google.com/spreadsheets/d/..." \
  --history-dir "artifacts/etf-sector-momentum-report" \
  --output "artifacts/etf-sector-momentum-report/custom-report.md"
```

## Output Contract

The generated report must keep this structure:

1. `首页结论`
2. `板块强弱总表`
3. `最强板块拆解`
4. `最弱板块拆解`
5. `未来1-3天推演`
6. `执行摘要`

The report should stay trading-oriented:

- Prefer board-level conclusions over single-ETF commentary.
- Distinguish `当日最强` from `近3日最强`.
- Always output `短线结论`, `中期结论`, and `长期结论`.
- Use pure state labels for each layer: `强势 / 偏强 / 震荡 / 偏弱 / 弱势`.
- Use `长期` to mean `60-120` day structure, not just YTD.
- Give a separate `交易结论` that is informed by all three layers.
- Always include an invalidation condition.

## History Rules

- Save the raw CSV under `raw/`.
- Save normalized daily metrics under `snapshots/`.
- Save the finished markdown report under `reports/`.
- If fewer than `3` daily snapshots exist, explicitly say that the `近3日动能` conclusion is provisional.

## Sheet Assumptions

The parser expects the same structure as the provided watchlist:

- A header row with `Ticker`, `Name`, `Price`, `1D%`, `R20`, `R60`, `R120`, `Rank`, `REL5`, `REL20`, `REL60`, `REL120`, `From 2025-12-31`, and `Tradetime`
- Sector rows where column `Ticker` contains the sector name and `Name` is empty
- ETF rows immediately under each sector row

If the sheet is private or the structure changes, stop and report the mismatch instead of guessing.

## References

- Read `references/report-spec.md` when you need the scoring logic or the meaning of each report section.
