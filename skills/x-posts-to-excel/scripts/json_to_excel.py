#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description='Convert captured X posts JSON to Excel (.xlsx)')
    p.add_argument('--in', dest='input_json', required=True, help='Input JSON path from capture_x_posts.mjs')
    p.add_argument('--out', dest='output_xlsx', required=False, help='Output .xlsx path')
    return p.parse_args()


def build_rows(items):
    rows = []
    for i, it in enumerate(items, 1):
        rows.append(
            {
                'index': i,
                'tweet_id': it.get('tweet_id'),
                'url': it.get('url'),
                'created_at': it.get('created_at'),
                'author_name': it.get('author_name'),
                'author_screen_name': it.get('author_screen_name'),
                'author_user_id': it.get('author_user_id'),
                'text': it.get('text'),
                'lang': it.get('lang'),
                'is_reply': it.get('is_reply'),
                'in_reply_to_status_id': it.get('in_reply_to_status_id'),
                'in_reply_to_screen_name': it.get('in_reply_to_screen_name'),
                'is_quote': it.get('is_quote'),
                'favorite_count': it.get('favorite_count'),
                'retweet_count': it.get('retweet_count'),
                'reply_count': it.get('reply_count'),
                'quote_count': it.get('quote_count'),
                'bookmark_count': it.get('bookmark_count'),
                'view_count': it.get('view_count'),
                'source': it.get('source'),
            }
        )
    return rows


def write_xlsx(rows, out_path):
    try:
        import pandas as pd

        pd.DataFrame(rows).to_excel(out_path, index=False)
        return
    except Exception:
        pass

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    headers = list(rows[0].keys()) if rows else ['index']
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h) for h in headers])
    wb.save(out_path)


def main():
    args = parse_args()
    in_path = Path(args.input_json).expanduser().resolve()
    if not in_path.exists():
        raise FileNotFoundError(f'Input not found: {in_path}')

    data = json.loads(in_path.read_text(encoding='utf-8'))
    items = data.get('items', [])

    out_path = Path(args.output_xlsx).expanduser().resolve() if args.output_xlsx else in_path.with_suffix('.xlsx')
    rows = build_rows(items)
    write_xlsx(rows, out_path)

    print(json.dumps({'ok': True, 'input': str(in_path), 'rows': len(rows), 'out': str(out_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
