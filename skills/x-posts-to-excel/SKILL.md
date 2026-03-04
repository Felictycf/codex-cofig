---
name: x-posts-to-excel
description: Capture X (Twitter) posts for a target account and export to Excel using an authenticated browser session. Use when the user asks to scrape X user timelines, collect all posts/replies, preserve metadata (time/url/engagement), or deliver `.xlsx` datasets from X profile content.
---

# X Posts To Excel

Use this skill to produce an `.xlsx` dataset from a target X account with high coverage.

## Workflow

1. Start isolated Chrome with CDP.
2. Import `storageState` so session is logged in.
3. Capture timeline API responses while scrolling (not DOM-only extraction).
4. Save structured JSON.
5. Convert JSON to Excel.
6. Report counts and paths.

## Inputs

Collect these from the user or defaults:
- `user`: target screen name, e.g. `yourQuantGuy`
- `timeline`: `tweets` or `tweets_replies` (default `tweets_replies`)
- `mode`: `self` (only target account posts) or `all` (includes conversation participants)
- `port`: CDP port, default `9555`
- `state`: storageState JSON path, default `/Users/felicity/.codex/resource/agent_browser/x-auth-state.json`
- `out`: output JSON/Excel paths

## Commands

### 0) Export `x-auth-state.json` only when missing

```bash
node scripts/export_x_auth_state.mjs \
  --out /Users/felicity/x-auth-state.json
```

If the file already exists, the script skips generation by default.  
Use `--force` only when you explicitly want to regenerate:

```bash
node scripts/export_x_auth_state.mjs \
  --out /Users/felicity/x-auth-state.json \
  --force
```

### 1) Launch isolated Chrome

```bash
open -na "Google Chrome" --args --remote-debugging-port=9555 --user-data-dir=/tmp/chrome-cdp9555
curl --noproxy '*' -fsS http://127.0.0.1:9555/json/version
```

### 2) Import login state (required)

```bash
node scripts/x_import_state_to_user_data_dir.mjs \
  --port 9555 \
  --state /Users/felicity/x-auth-state.json
```

Success criterion: output contains `"verifyUrl": "https://x.com/home"`.

### 3) Capture timeline data

Only target account posts/replies:

```bash
node scripts/capture_x_posts.mjs \
  --port 9555 \
  --user yourQuantGuy \
  --timeline tweets_replies \
  --mode self \
  --out /Users/felicity/yourQuantGuy_all_posts_full.json
```

Posts-only dataset:

```bash
node scripts/capture_x_posts.mjs \
  --port 9555 \
  --user yourQuantGuy \
  --timeline tweets \
  --mode self \
  --out /Users/felicity/yourQuantGuy_posts_only.json
```

### 4) Convert JSON to Excel

```bash
python3 scripts/json_to_excel.py \
  --in /Users/felicity/yourQuantGuy_all_posts_full.json \
  --out /Users/felicity/yourQuantGuy_all_posts_full.xlsx
```

### 5) Convert JSON to CSV (recommended, no xlsx re-conversion)

```bash
python3 scripts/json_to_csv.py \
  --in /Users/felicity/yourQuantGuy_all_posts_full.json \
  --out /Users/felicity/yourQuantGuy_all_posts_full.csv
```

If your downstream tool does not support multi-line CSV fields, add `--flatten-newlines`.

## Output Schema

JSON records include:
- `tweet_id`
- `url`
- `created_at`
- `text`
- `author_name`
- `author_screen_name`
- `author_user_id`
- `is_reply`
- `in_reply_to_status_id`
- `in_reply_to_screen_name`
- `is_quote`
- `favorite_count`
- `retweet_count`
- `reply_count`
- `quote_count`
- `bookmark_count`
- `view_count`
- `lang`
- `source`

Excel columns mirror these fields with an extra `index`.

## Quality Checks

After run, always verify:

```bash
python3 - <<'PY'
import json
p='/Users/felicity/yourQuantGuy_all_posts_full.json'
j=json.load(open(p,'r',encoding='utf-8'))
print('ok', j.get('ok'))
print('user', j.get('user'))
print('timeline', j.get('timeline'))
print('count', len(j.get('items',[])))
print('sample_ids', [x.get('tweet_id') for x in j.get('items',[])[:5]])
PY
```

And confirm Excel exists:

```bash
ls -lh /Users/felicity/yourQuantGuy_all_posts_full.xlsx
```

## Interpretation Notes

- `tweets_replies + mode=self` is usually closest to profile total activity.
- Profile `statuses_count` may still differ due to hidden/deleted/protected items and timeline policies.
- If output is unexpectedly low, rerun in a fresh profile/port and see `references/troubleshooting.md`.

## Resources

- Capture script: `scripts/capture_x_posts.mjs`
- Excel conversion script: `scripts/json_to_excel.py`
- Troubleshooting: `references/troubleshooting.md`


### 6) Heavy Mode: full TweetDetail text repair (slow)

```bash
node scripts/repair_note_texts.mjs \
  --port 9903 \
  --state /Users/felicity/x-auth-state.json \
  --in /Users/felicity/yourQuantGuy_all_posts_full.json \
  --out /Users/felicity/yourQuantGuy_all_posts_full.json \
  --repair-all \
  --max-candidates 5000 \
  --min-gain 1
```

Then re-export:

```bash
python3 scripts/json_to_excel.py --in /Users/felicity/yourQuantGuy_all_posts_full.json --out /Users/felicity/yourQuantGuy_all_posts_full.xlsx
python3 scripts/json_to_csv.py --in /Users/felicity/yourQuantGuy_all_posts_full.json --out /Users/felicity/yourQuantGuy_all_posts_full.csv
```
