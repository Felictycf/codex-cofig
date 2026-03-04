import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

function parseArgs(argv) {
  const args = {
    port: 9333,
    ws: null,
    state: "x-auth-state.json",
    out: "for_you_20.json",
    maxRounds: 30,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--port") args.port = Number(argv[++i]);
    else if (a === "--ws") args.ws = argv[++i];
    else if (a === "--state") args.state = argv[++i];
    else if (a === "--out") args.out = argv[++i];
    else if (a === "--max-rounds") args.maxRounds = Number(argv[++i]);
    else if (a === "--help" || a === "-h") args.help = true;
  }
  return args;
}

const args = parseArgs(process.argv);
if (args.help) {
  console.log(
    [
      "Usage:",
      "  node tools/x_for_you_20.mjs --port 9333 [--ws ws://...] --state x-auth-state.json --out for_you_20.json",
      "",
      "Notes:",
      "  - Requires Chrome started with --remote-debugging-port (CDP).",
      "  - Uses Playwright storageState (x-auth-state.json) to avoid manual login.",
    ].join("\n")
  );
  process.exit(0);
}

let playwright;
try {
  playwright = require("playwright-core");
} catch {
  playwright = require(
    "/Users/felicity/.nvm/versions/node/v20.19.2/lib/node_modules/agent-browser/node_modules/playwright-core"
  );
}

const { chromium } = playwright;

async function getWsDebuggerUrl(port) {
  const res = await fetch(`http://127.0.0.1:${port}/json/version`);
  if (!res.ok) throw new Error(`CDP port ${port} not responding: HTTP ${res.status}`);
  const data = await res.json();
  if (!data.webSocketDebuggerUrl) throw new Error(`CDP /json/version missing webSocketDebuggerUrl`);
  return data.webSocketDebuggerUrl;
}

function normalizeText(text) {
  return (text ?? "").replace(/\s+/g, " ").trim();
}

async function ensureForYouTab(page) {
  const candidates = [
    page.getByRole("tab", { name: /For you/i }),
    page.getByRole("tab", { name: /为你/ }),
    page.getByRole("tab", { name: /推荐/ }),
  ];
  for (const loc of candidates) {
    try {
      if (await loc.first().isVisible({ timeout: 1500 })) {
        await loc.first().click({ timeout: 3000 }).catch(() => {});
        return;
      }
    } catch {}
  }
}

async function extractFromArticle(article) {
  const urlPath =
    (await article
      .locator('a[href*="/status/"]')
      .first()
      .getAttribute("href", { timeout: 1500 })
      .catch(() => null)) ?? null;
  if (!urlPath) return null;

  const time =
    (await article
      .locator("time")
      .first()
      .getAttribute("datetime", { timeout: 1500 })
      .catch(() => null)) ??
    normalizeText(await article.locator("time").first().innerText({ timeout: 1500 }).catch(() => ""));

  const authorBlock = await article
    .locator('[data-testid="User-Name"]')
    .first()
    .innerText({ timeout: 1500 })
    .catch(() => "");
  const author = normalizeText(authorBlock);

  const handle =
    normalizeText(
      await article
        .locator('a[href^="/"][role="link"] span')
        .filter({ hasText: "@" })
        .first()
        .innerText({ timeout: 800 })
        .catch(() => "")
    ) || null;

  const text =
    normalizeText(
      await article
        .locator('[data-testid="tweetText"]')
        .first()
        .innerText({ timeout: 1500 })
        .catch(() => "")
    ) || null;

  const promoted =
    (await article
      .getByText(/Promoted|推广|赞助/i)
      .first()
      .isVisible({ timeout: 300 })
      .catch(() => false)) || false;

  const mediaCount = await article.locator('div[data-testid="tweetPhoto"], video').count().catch(() => 0);

  const quoteStatus =
    (await article
      .locator('a[href*="/status/"]')
      .nth(1)
      .getAttribute("href", { timeout: 800 })
      .catch(() => null)) ?? null;

  return {
    url: `https://x.com${urlPath}`,
    time: time || null,
    author: author || null,
    handle,
    text,
    mediaCount,
    quoteUrl: quoteStatus ? `https://x.com${quoteStatus}` : null,
    promoted,
  };
}

async function collect20(page, maxRounds) {
  const items = [];
  const seen = new Set();
  let rounds = 0;

  while (items.length < 20 && rounds < maxRounds) {
    rounds++;
    const articles = page.locator("article");
    const count = Math.min(await articles.count(), 40);
    for (let i = 0; i < count; i++) {
      const article = articles.nth(i);
      const data = await extractFromArticle(article);
      if (!data) continue;
      if (data.promoted) continue;
      if (seen.has(data.url)) continue;
      seen.add(data.url);
      items.push(data);
      if (items.length >= 20) break;
    }
    if (items.length >= 20) break;
    await page.mouse.wheel(0, 1400).catch(async () => {
      await page.evaluate(() => window.scrollBy(0, 1400));
    });
    await page.waitForTimeout(1200);
  }
  return items.slice(0, 20);
}

async function main() {
  const ws = args.ws || (await getWsDebuggerUrl(args.port));
  const browser = await chromium.connectOverCDP(ws);
  let context;
  try {
    context = await browser.newContext({ storageState: args.state, locale: "zh-CN" });
    context.setDefaultTimeout(15000);

    const page = await context.newPage();
    await page.goto("https://x.com/home", { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.locator("article").first().waitFor({ timeout: 30000 }).catch(() => {});

    if (!page.url().includes("/home")) {
      throw new Error(`Not on /home (got: ${page.url()}). storageState may be invalid/expired.`);
    }

    await ensureForYouTab(page);
    await page.waitForTimeout(1500);

    const items = await collect20(page, args.maxRounds);
    await fs.writeFile(args.out, JSON.stringify({ items }, null, 2), "utf-8");
    console.log(JSON.stringify({ ok: true, count: items.length, out: args.out }, null, 2));
  } finally {
    await context?.close().catch(() => {});
    await browser.close().catch(() => {});
  }

  process.exit(0);
}

main().catch((err) => {
  console.error(String(err?.stack || err));
  process.exit(1);
});
