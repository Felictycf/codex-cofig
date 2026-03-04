---
name: x-posts-backfill-oneclick
description: Run multi-round authenticated X timeline backfill and export merged datasets in JSON, CSV, and Excel with one command. Use when users need high-coverage X account history extraction, deduplicated merge across multiple browser rounds/ports, and convergence reporting.
---

# X Posts Backfill Oneclick

Use this skill when one-pass scraping is not enough and you need a higher-coverage merged result.

## One-Click Command

```bash
python3 scripts/backfill_oneclick.py \
  --user gch_enbsbxbs \
  --state /Users/felicity/x-auth-state.json
```

This command automatically:
1. Starts isolated Chrome sessions on multiple ports (`9777,9888` by default).
2. Imports login state into each session.
3. Captures both `tweets_replies + self` and `tweets + self` for each round.
4. Merges all rounds by `tweet_id`, keeps richer record when duplicates conflict.
5. Runs full text repair (`repair-all`) using `TweetDetail` to reduce long-text truncation.
6. Exports `merged_self_all.json`, `merged_self_all.csv`, `merged_self_all.xlsx`.
7. Writes `merge_report.json` showing per-round new additions.

## Key Options

```bash
python3 scripts/backfill_oneclick.py \
  --user gch_enbsbxbs \
  --state /Users/felicity/x-auth-state.json \
  --ports 9777,9888,9999 \
  --out-dir /Users/felicity/x_backfill_gch_custom
```

- `--ports`: more rounds for additional coverage.
- `--out-dir`: custom output folder.
- `--max-rounds-replies`, `--idle-rounds-replies`: tune deep capture behavior.
- `--max-rounds-tweets`, `--idle-rounds-tweets`: tune posts-only capture behavior.
- `--skip-repair`: skip heavy full-text repair (faster but less complete).
- `--repair-max-candidates`: cap heavy repair volume (default `5000`).

## Prerequisites

- `x-auth-state.json` exists (use `scripts/export_x_auth_state.mjs` from the related skill when needed).
- Chrome is installed.
- Node.js + Python3 available.
- `openpyxl` installed for xlsx export.

## Output Files

Under output directory:
- `r*_tweets_replies_self.json`
- `r*_tweets_self.json`
- `merged_self_all.json`
- `merged_self_all.csv`
- `merged_self_all.xlsx`
- `merge_report.json`

## Supporting Scripts

- `scripts/backfill_oneclick.py` (main orchestrator)
- `scripts/x_import_state_to_user_data_dir.mjs`
- `scripts/capture_x_posts.mjs`
- `scripts/repair_note_texts.mjs`
- `scripts/json_to_csv.py`
- `scripts/json_to_excel.py`
