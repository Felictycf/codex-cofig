#!/usr/bin/env node
import fs from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let playwright;
try {
  playwright = require('playwright-core');
} catch {
  playwright = require('/Users/felicity/.nvm/versions/node/v20.19.2/lib/node_modules/agent-browser/node_modules/playwright-core');
}
const { chromium } = playwright;

function parseArgs(argv) {
  const args = {
    port: 9444,
    ws: null,
    state: '/Users/felicity/x-auth-state.json',
    in: null,
    out: null,
    minLen: 140,
    maxLen: 160,
    maxCandidates: 120,
    minGain: 40,
    repairAll: false,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--port') args.port = Number(argv[++i]);
    else if (a === '--ws') args.ws = argv[++i];
    else if (a === '--state') args.state = argv[++i];
    else if (a === '--in') args.in = argv[++i];
    else if (a === '--out') args.out = argv[++i];
    else if (a === '--min-len') args.minLen = Number(argv[++i]);
    else if (a === '--max-len') args.maxLen = Number(argv[++i]);
    else if (a === '--max-candidates') args.maxCandidates = Number(argv[++i]);
    else if (a === '--min-gain') args.minGain = Number(argv[++i]);
    else if (a === '--repair-all') args.repairAll = true;
    else if (a === '--help' || a === '-h') args.help = true;
  }
  if (!args.in && !args.help) throw new Error('Missing --in <json>');
  if (!args.out) args.out = args.in;
  return args;
}

function usage() {
  console.log([
    'Usage:',
    '  node scripts/repair_note_texts.mjs --port 9899 --in /path/posts.json --out /path/posts_fixed.json',
    '',
    'Default candidate filter:',
    '  text length between 140 and 160, max 120 tweets',
    '',
    'Heavy mode:',
    '  add --repair-all to run TweetDetail repair on all tweets',
  ].join('\n'));
}

async function getWsDebuggerUrl(port) {
  const res = await fetch(`http://127.0.0.1:${port}/json/version`);
  if (!res.ok) throw new Error(`CDP port ${port} not responding: HTTP ${res.status}`);
  const data = await res.json();
  if (!data.webSocketDebuggerUrl) throw new Error('Missing webSocketDebuggerUrl');
  return data.webSocketDebuggerUrl;
}

function detailNoteText(found) {
  return (
    found?.note_tweet?.note_tweet_results?.result?.text ||
    found?.note_tweet?.note_tweet_results?.result?.note_tweet?.text ||
    null
  );
}

async function fetchNoteTextForTweet(page, url, tweetId) {
  return await new Promise(async (resolve) => {
    const timer = setTimeout(() => {
      page.off('response', onResp);
      resolve(null);
    }, 25000);

    const onResp = async (resp) => {
      try {
        const u = resp.url();
        if (!u.includes('/i/api/graphql/') || !u.includes('/TweetDetail')) return;
        const j = await resp.json().catch(() => null);
        if (!j) return;

        let found = null;
        const walk = (obj) => {
          if (!obj || typeof obj !== 'object' || found) return;
          if (obj.rest_id === tweetId && obj.legacy) {
            found = obj;
            return;
          }
          for (const k of Object.keys(obj)) walk(obj[k]);
        };
        walk(j);
        if (!found) return;

        const note = detailNoteText(found);
        clearTimeout(timer);
        page.off('response', onResp);
        resolve(note || null);
      } catch {
        clearTimeout(timer);
        page.off('response', onResp);
        resolve(null);
      }
    };

    page.on('response', onResp);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
    await page.waitForTimeout(800).catch(() => {});
  });
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    usage();
    return;
  }

  const raw = await fs.readFile(args.in, 'utf-8');
  const data = JSON.parse(raw);
  const items = Array.isArray(data.items) ? data.items : [];

  const candidates = items
    .map((it, idx) => ({ it, idx, len: (it.text || '').length }))
    .filter((x) => {
      if (!x.it?.tweet_id || !x.it?.url) return false;
      if (args.repairAll) return true;
      return x.len >= args.minLen && x.len <= args.maxLen;
    })
    .slice(0, args.maxCandidates);

  const ws = args.ws || (await getWsDebuggerUrl(args.port));
  const browser = await chromium.connectOverCDP(ws);
  let context;
  let updated = 0;
  try {
    context = await browser.newContext({ storageState: args.state, locale: 'en-US' });
    const page = await context.newPage();

    for (let i = 0; i < candidates.length; i++) {
      const c = candidates[i];
      const oldText = c.it.text || '';
      const note = await fetchNoteTextForTweet(page, c.it.url, String(c.it.tweet_id));
      if (note && note.length >= oldText.length + args.minGain) {
        items[c.idx].text = note;
        updated += 1;
      }
      if ((i + 1) % 10 === 0) {
        console.error(`repair progress: ${i + 1}/${candidates.length}, updated=${updated}`);
      }
      await page.waitForTimeout(250);
    }
  } finally {
    await context?.close().catch(() => {});
    await browser.close().catch(() => {});
  }

  data.items = items;
  data.repair = {
    appliedAt: new Date().toISOString(),
    candidateRange: [args.minLen, args.maxLen],
    candidates: candidates.length,
    updated,
    minGain: args.minGain,
    repairAll: args.repairAll,
  };

  await fs.writeFile(args.out, JSON.stringify(data, null, 2), 'utf-8');
  console.log(JSON.stringify({ ok: true, in: args.in, out: args.out, candidates: candidates.length, updated }, null, 2));
}

main().catch((e) => {
  console.error(e?.stack || String(e));
  process.exit(1);
});
