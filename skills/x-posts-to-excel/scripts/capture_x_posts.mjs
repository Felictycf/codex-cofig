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
    user: null,
    state: '/Users/felicity/.codex/resource/agent_browser/x-auth-state.json',
    timeline: 'tweets_replies',
    mode: 'self',
    out: null,
    maxRounds: 2600,
    idleRounds: 180,
  };

  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--port') args.port = Number(argv[++i]);
    else if (a === '--ws') args.ws = argv[++i];
    else if (a === '--user') args.user = (argv[++i] || '').replace(/^@/, '');
    else if (a === '--state') args.state = argv[++i];
    else if (a === '--timeline') args.timeline = argv[++i];
    else if (a === '--mode') args.mode = argv[++i];
    else if (a === '--out') args.out = argv[++i];
    else if (a === '--max-rounds') args.maxRounds = Number(argv[++i]);
    else if (a === '--idle-rounds') args.idleRounds = Number(argv[++i]);
    else if (a === '--help' || a === '-h') args.help = true;
  }

  if (!args.user && !args.help) throw new Error('Missing required argument --user <screen_name>');
  if (!args.out) args.out = `${args.user}_posts_${args.timeline}_${args.mode}.json`;
  return args;
}

function usage() {
  console.log([
    'Usage:',
    '  node scripts/capture_x_posts.mjs --port 9555 --user yourQuantGuy --timeline tweets_replies --mode self --out yourQuantGuy_full.json',
    '',
    'Options:',
    '  --port <n>             CDP port (default 9444)',
    '  --ws <url>             CDP websocket URL (optional)',
    '  --user <name>          X screen name (without @)',
    '  --state <path>         Playwright storageState JSON path',
    '  --timeline <kind>      tweets | tweets_replies (default tweets_replies)',
    '  --mode <kind>          self | all (default self)',
    '  --out <path>           Output JSON path',
    '  --max-rounds <n>       Max scroll rounds',
    '  --idle-rounds <n>      Stop after no-growth rounds',
  ].join('\n'));
}

async function getWsDebuggerUrl(port) {
  const res = await fetch(`http://127.0.0.1:${port}/json/version`);
  if (!res.ok) throw new Error(`CDP port ${port} not responding: HTTP ${res.status}`);
  const data = await res.json();
  if (!data.webSocketDebuggerUrl) throw new Error('Missing webSocketDebuggerUrl');
  return data.webSocketDebuggerUrl;
}

function findInstructions(obj) {
  const paths = [
    obj?.data?.user?.result?.timeline_v2?.timeline?.instructions,
    obj?.data?.user?.result?.timeline?.timeline?.instructions,
    obj?.data?.user?.result?.timeline_response?.timeline?.instructions,
    obj?.data?.user?.result?.timeline?.instructions,
  ];
  return paths.find((x) => Array.isArray(x)) || [];
}

function getEntriesFromInstruction(ins) {
  if (!ins) return [];
  if (Array.isArray(ins.entries)) return ins.entries;
  if (ins.entry) return [ins.entry];
  return [];
}

function extractTweetFromTweetResult(result) {
  if (!result) return null;
  if (result?.__typename === 'TweetWithVisibilityResults') result = result.tweet;
  const restId = result?.rest_id;
  const legacy = result?.legacy;
  if (!restId || !legacy) return null;

  const userResult = result?.core?.user_results?.result;
  const userLegacy = userResult?.legacy || {};
  const coreUser = userResult?.core || {};
  const screenName = userLegacy?.screen_name || coreUser?.screen_name || null;
  const userId = userResult?.rest_id || userLegacy?.id_str || legacy?.user_id_str || null;
  // For long-form posts, note_tweet contains the full body while legacy.full_text may be truncated.
  const fullText = legacy?.note_tweet?.note_tweet_results?.result?.text || legacy?.full_text || '';

  return {
    tweet_id: restId,
    url: screenName ? `https://x.com/${screenName}/status/${restId}` : `https://x.com/i/web/status/${restId}`,
    created_at: legacy?.created_at || null,
    text: fullText,
    lang: legacy?.lang || null,
    favorite_count: legacy?.favorite_count ?? null,
    retweet_count: legacy?.retweet_count ?? null,
    reply_count: legacy?.reply_count ?? null,
    quote_count: legacy?.quote_count ?? null,
    bookmark_count: legacy?.bookmark_count ?? null,
    view_count: result?.views?.count ?? null,
    author_name: userLegacy?.name || null,
    author_screen_name: screenName,
    author_user_id: userId,
    is_reply: Boolean(legacy?.in_reply_to_status_id_str),
    in_reply_to_status_id: legacy?.in_reply_to_status_id_str || null,
    in_reply_to_screen_name: legacy?.in_reply_to_screen_name || null,
    is_quote: Boolean(legacy?.is_quote_status),
    source: legacy?.source || null,
  };
}

function extractTweetsFromPayload(payload) {
  const out = [];
  const instructions = findInstructions(payload);
  for (const ins of instructions) {
    const entries = getEntriesFromInstruction(ins);
    for (const e of entries) {
      const direct = extractTweetFromTweetResult(e?.content?.itemContent?.tweet_results?.result);
      if (direct) out.push(direct);
      const modItems = e?.content?.items;
      if (Array.isArray(modItems)) {
        for (const mi of modItems) {
          const m = extractTweetFromTweetResult(mi?.item?.itemContent?.tweet_results?.result);
          if (m) out.push(m);
        }
      }
    }
  }
  return out;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    usage();
    return;
  }

  const endpointNeedle = args.timeline === 'tweets' ? '/UserTweets' : '/UserTweetsAndReplies';
  const ws = args.ws || (await getWsDebuggerUrl(args.port));

  const browser = await chromium.connectOverCDP(ws);
  let context;
  try {
    context = await browser.newContext({ storageState: args.state, locale: 'en-US' });
    context.setDefaultTimeout(20000);
    const page = await context.newPage();

    const seen = new Set();
    const items = [];
    let apiHits = 0;
    let rounds = 0;
    let idle = 0;

    page.on('response', async (resp) => {
      try {
        const url = resp.url();
        if (!url.includes('/i/api/graphql/') || !url.includes(endpointNeedle)) return;
        apiHits += 1;
        if (!resp.ok()) return;

        const j = await resp.json().catch(() => null);
        if (!j) return;

        const tweets = extractTweetsFromPayload(j);
        for (const t of tweets) {
          if (args.mode === 'self' && (t.author_screen_name || '').toLowerCase() !== args.user.toLowerCase()) {
            continue;
          }
          if (seen.has(t.tweet_id)) continue;
          seen.add(t.tweet_id);
          items.push(t);
        }
      } catch {}
    });

    await page.goto(`https://x.com/${args.user}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(2500);

    if (page.url().includes('/i/flow/login')) {
      throw new Error(`Redirected to login: ${page.url()}`);
    }

    const tab = args.timeline === 'tweets'
      ? page.getByRole('tab', { name: /^Posts$/i }).first()
      : page.getByRole('tab', { name: /Replies|回复|回覆/i }).first();

    if (await tab.isVisible().catch(() => false)) {
      await tab.click({ timeout: 5000 }).catch(() => {});
      await page.waitForTimeout(1800);
    }

    let prevCount = 0;
    let prevHits = 0;

    while (rounds < args.maxRounds && idle < args.idleRounds) {
      rounds += 1;

      await page.mouse.wheel(0, 2400).catch(async () => {
        await page.evaluate(() => window.scrollBy(0, 2400));
      });
      await sleep(900);

      const noMore = await page
        .getByText(/You’re all caught up|You've reached the end|没有更多|已显示全部/i)
        .first()
        .isVisible({ timeout: 200 })
        .catch(() => false);

      const noGrowth = items.length === prevCount && apiHits === prevHits;
      if (noMore) break;
      if (noGrowth) idle += 1;
      else idle = 0;

      prevCount = items.length;
      prevHits = apiHits;

      if (rounds % 50 === 0) {
        console.error(`progress: rounds=${rounds} apiHits=${apiHits} items=${items.length} idle=${idle}`);
      }
    }

    items.sort((a, b) => {
      const ta = Date.parse(a.created_at || '') || 0;
      const tb = Date.parse(b.created_at || '') || 0;
      return tb - ta;
    });

    const payload = {
      ok: true,
      user: args.user,
      timeline: args.timeline,
      mode: args.mode,
      endpoint: endpointNeedle,
      collected: items.length,
      apiHits,
      rounds,
      idleRounds: idle,
      generatedAt: new Date().toISOString(),
      items,
    };

    await fs.writeFile(args.out, JSON.stringify(payload, null, 2), 'utf-8');
    console.log(JSON.stringify({ ok: true, user: args.user, timeline: args.timeline, mode: args.mode, count: items.length, out: args.out }, null, 2));
  } finally {
    await context?.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch((e) => {
  console.error(e?.stack || String(e));
  process.exit(1);
});
