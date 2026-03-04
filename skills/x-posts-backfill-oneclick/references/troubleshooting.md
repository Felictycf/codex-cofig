# Troubleshooting

## 1) `Daemon failed to start`
- Do not rely on `agent-browser` daemon for this skill's core capture.
- Prefer CDP + Playwright script workflow in `scripts/capture_x_posts.mjs`.

## 2) Redirected to login
- Re-import storageState into the target profile/port:
  - `node /Users/felicity/.codex/resource/agent_browser/tools/x_import_state_to_user_data_dir.mjs --port <PORT> --state /Users/felicity/.codex/resource/agent_browser/x-auth-state.json`
- Verify returns `verifyUrl: https://x.com/home`.

## 3) Local CDP endpoint unavailable
- Launch isolated Chrome profile with remote debugging:
  - `open -na "Google Chrome" --args --remote-debugging-port=<PORT> --user-data-dir=/tmp/chrome-cdp<PORT>`
- Check:
  - `curl --noproxy '*' -fsS http://127.0.0.1:<PORT>/json/version`

## 4) Count lower than profile `statuses_count`
- `statuses_count` and timeline APIs can differ due to deleted/hidden/protected tweets and timeline policy.
- Run both modes and compare:
  - `--timeline tweets --mode self`
  - `--timeline tweets_replies --mode self`
- If needed, run on fresh profile/port to avoid stale cache.

## 5) Excel export dependency error
- Script auto-falls back from `pandas` to `openpyxl`.
- Ensure at least `openpyxl` is available.
