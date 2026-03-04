#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description='Convert captured X posts JSON to CSV without truncation')
    p.add_argument('--in', dest='input_json', required=True, help='Input JSON path from capture_x_posts.mjs')
    p.add_argument('--out', dest='output_csv', required=False, help='Output .csv path')
    p.add_argument('--flatten-newlines', action='store_true', help='Replace line breaks in text fields with literal \\n')
    return p.parse_args()


def build_rows(items, flatten_newlines=False):
    rows = []
    for i, it in enumerate(items, 1):
        text = it.get('text')
        source = it.get('source')
        if flatten_newlines:
            if isinstance(text, str):
                text = text.replace('\r\n', '\\n').replace('\n', '\\n')
            if isinstance(source, str):
                source = source.replace('\r\n', '\\n').replace('\n', '\\n')

        rows.append(
            {
                'index': i,
                'tweet_id': it.get('tweet_id'),
                'url': it.get('url'),
                'created_at': it.get('created_at'),
                'author_name': it.get('author_name'),
                'author_screen_name': it.get('author_screen_name'),
                'author_user_id': it.get('author_user_id'),
                'text': text,
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
                'source': source,
            }
        )
    return rows


def write_csv(rows, out_path):
    headers = [
        'index', 'tweet_id', 'url', 'created_at', 'author_name', 'author_screen_name', 'author_user_id',
        'text', 'lang', 'is_reply', 'in_reply_to_status_id', 'in_reply_to_screen_name', 'is_quote',
        'favorite_count', 'retweet_count', 'reply_count', 'quote_count', 'bookmark_count', 'view_count', 'source'
    ]

    # utf-8-sig improves Excel compatibility for Chinese text.
    with out_path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    args = parse_args()
    in_path = Path(args.input_json).expanduser().resolve()
    if not in_path.exists():
        raise FileNotFoundError(f'Input not found: {in_path}')

    data = json.loads(in_path.read_text(encoding='utf-8'))
    items = data.get('items', [])

    out_path = Path(args.output_csv).expanduser().resolve() if args.output_csv else in_path.with_suffix('.csv')
    rows = build_rows(items, flatten_newlines=args.flatten_newlines)
    write_csv(rows, out_path)

    print(json.dumps({'ok': True, 'input': str(in_path), 'rows': len(rows), 'out': str(out_path), 'flatten_newlines': args.flatten_newlines}, ensure_ascii=False))


if __name__ == '__main__':
    main()
