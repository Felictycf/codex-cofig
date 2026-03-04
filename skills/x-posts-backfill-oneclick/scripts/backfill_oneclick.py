#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import urlopen


def run(cmd, cwd=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def wait_cdp(port, timeout=30):
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            with urlopen(f'http://127.0.0.1:{port}/json/version', timeout=2) as r:
                data = json.loads(r.read().decode('utf-8'))
                if data.get('webSocketDebuggerUrl'):
                    return data
        except Exception as e:
            last_err = e
        time.sleep(0.25)
    raise RuntimeError(f'CDP port {port} not ready: {last_err}')


def score(item):
    s = len(item.get('text') or '')
    for k in [
        'favorite_count', 'retweet_count', 'reply_count', 'quote_count',
        'bookmark_count', 'view_count', 'author_name', 'author_screen_name',
        'author_user_id', 'source', 'created_at'
    ]:
        if item.get(k) not in (None, ''):
            s += 5
    return s


def ts(item):
    try:
        return parsedate_to_datetime(item.get('created_at') or '').timestamp()
    except Exception:
        return 0


def merge_json_files(files):
    union_seen = set()
    progress = []
    best = {}

    for file in files:
        data = json.loads(Path(file).read_text(encoding='utf-8'))
        items = data.get('items', [])
        before = len(union_seen)
        for it in items:
            tid = str(it.get('tweet_id') or '')
            if not tid:
                continue
            union_seen.add(tid)
            prev = best.get(tid)
            if prev is None or score(it) > score(prev):
                best[tid] = it
        after = len(union_seen)
        progress.append({
            'file': str(file),
            'input_count': len(items),
            'union_after': after,
            'new_added': after - before,
        })

    merged = sorted(best.values(), key=ts, reverse=True)
    return merged, progress


def main():
    p = argparse.ArgumentParser(description='One-click multi-round X backfill + merge + excel/csv export')
    p.add_argument('--user', required=True, help='Target X screen name, without @')
    p.add_argument('--state', default='/Users/felicity/x-auth-state.json', help='Path to x-auth-state.json')
    p.add_argument('--ports', default='9777,9888', help='Comma-separated CDP ports for rounds')
    p.add_argument('--max-rounds-replies', type=int, default=3400)
    p.add_argument('--idle-rounds-replies', type=int, default=260)
    p.add_argument('--max-rounds-tweets', type=int, default=2200)
    p.add_argument('--idle-rounds-tweets', type=int, default=220)
    p.add_argument('--skip-repair', action='store_true', help='Skip full TweetDetail text repair (faster, lower completeness)')
    p.add_argument('--repair-max-candidates', type=int, default=5000, help='Max tweets to repair when repair is enabled')
    p.add_argument('--out-dir', default=None, help='Output directory (default: ~/x_backfill_<user>_<yyyymmdd>)')
    args = p.parse_args()

    script_dir = Path(__file__).resolve().parent
    import_script = script_dir / 'x_import_state_to_user_data_dir.mjs'
    capture_script = script_dir / 'capture_x_posts.mjs'
    repair_script = script_dir / 'repair_note_texts.mjs'
    to_excel = script_dir / 'json_to_excel.py'
    to_csv = script_dir / 'json_to_csv.py'

    state = Path(args.state).expanduser().resolve()
    if not state.exists():
        raise FileNotFoundError(f'state file not found: {state}')

    today = datetime.now().strftime('%Y%m%d')
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else Path.home() / f'x_backfill_{args.user}_{today}'
    out_dir.mkdir(parents=True, exist_ok=True)

    ports = [int(x.strip()) for x in args.ports.split(',') if x.strip()]
    run_files = []

    for idx, port in enumerate(ports, start=1):
        profile_dir = f'/tmp/chrome-cdp{port}'
        run(['open', '-na', 'Google Chrome', '--args', f'--remote-debugging-port={port}', f'--user-data-dir={profile_dir}'])
        wait_cdp(port)

        run(['node', str(import_script), '--port', str(port), '--state', str(state)])

        replies_out = out_dir / f'r{idx}_tweets_replies_self.json'
        tweets_out = out_dir / f'r{idx}_tweets_self.json'

        run([
            'node', str(capture_script), '--port', str(port), '--user', args.user,
            '--timeline', 'tweets_replies', '--mode', 'self', '--out', str(replies_out),
            '--max-rounds', str(args.max_rounds_replies), '--idle-rounds', str(args.idle_rounds_replies),
        ])

        run([
            'node', str(capture_script), '--port', str(port), '--user', args.user,
            '--timeline', 'tweets', '--mode', 'self', '--out', str(tweets_out),
            '--max-rounds', str(args.max_rounds_tweets), '--idle-rounds', str(args.idle_rounds_tweets),
        ])

        run_files.extend([replies_out, tweets_out])

    merged, progress = merge_json_files(run_files)

    merged_json = out_dir / 'merged_self_all.json'
    merged_xlsx = out_dir / 'merged_self_all.xlsx'
    merged_csv = out_dir / 'merged_self_all.csv'
    report_json = out_dir / 'merge_report.json'

    merged_payload = {
        'ok': True,
        'user': args.user,
        'state': str(state),
        'ports': ports,
        'runs': progress,
        'merged_count': len(merged),
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'items': merged,
    }
    merged_json.write_text(json.dumps(merged_payload, ensure_ascii=False, indent=2), encoding='utf-8')
    report_json.write_text(json.dumps({'runs': progress, 'merged_count': len(merged)}, ensure_ascii=False, indent=2), encoding='utf-8')

    # Heavy mode by default: repair full text via TweetDetail/note_tweet for maximum completeness.
    if not args.skip_repair:
        run([
            'node', str(repair_script),
            '--port', str(ports[0] if ports else 9444),
            '--state', str(state),
            '--in', str(merged_json),
            '--out', str(merged_json),
            '--repair-all',
            '--max-candidates', str(args.repair_max_candidates),
            '--min-gain', '1',
        ])

    run(['python3', str(to_excel), '--in', str(merged_json), '--out', str(merged_xlsx)])
    run(['python3', str(to_csv), '--in', str(merged_json), '--out', str(merged_csv)])

    print(json.dumps({
        'ok': True,
        'user': args.user,
        'merged_count': len(merged),
        'out_dir': str(out_dir),
        'merged_json': str(merged_json),
        'merged_xlsx': str(merged_xlsx),
        'merged_csv': str(merged_csv),
        'report_json': str(report_json),
        'repair_applied': not args.skip_repair,
        'repair_max_candidates': args.repair_max_candidates,
        'runs': progress,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
