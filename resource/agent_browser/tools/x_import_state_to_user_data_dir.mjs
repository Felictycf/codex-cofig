import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

function parseArgs(argv) {
  const args = {
    port: 9333,
    ws: null,
    state: "x-auth-state.json",
    verify: true,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--port") args.port = Number(argv[++i]);
    else if (a === "--ws") args.ws = argv[++i];
    else if (a === "--state") args.state = argv[++i];
    else if (a === "--no-verify") args.verify = false;
    else if (a === "--help" || a === "-h") args.help = true;
  }
  return args;
}

const args = parseArgs(process.argv);
if (args.help) {
  console.log(
    [
      "Usage:",
      "  node tools/x_import_state_to_user_data_dir.mjs --port 9333 [--ws ws://...] --state x-auth-state.json",
      "",
      "What it does:",
      "  - Connects to an existing Chrome started with --remote-debugging-port.",
      "  - Injects cookies + localStorage from Playwright storageState into the *running* Chrome profile.",
      "  - This effectively 'writes' the login session into that Chrome user-data-dir, so future launches can reuse it.",
      "",
      "Security:",
      "  - The state file contains cookies; treat it like a password.",
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

function normalizeOrigin(origin) {
  if (!origin) return origin;
  return origin.endsWith("/") ? origin.slice(0, -1) : origin;
}

async function importOriginStorage(context, entry) {
  const origin = normalizeOrigin(entry.origin);
  if (!origin) return { origin: null, localStorage: 0, sessionStorage: 0 };

  const localStorageItems = Array.isArray(entry.localStorage) ? entry.localStorage : [];
  const sessionStorageItems = Array.isArray(entry.sessionStorage) ? entry.sessionStorage : [];

  const page = await context.newPage();

  // Avoid external network: fulfill navigations/resources under this origin with a tiny HTML document.
  const routeGlob = `${origin}/**`;
  await page.route(routeGlob, async (route) => {
    if (route.request().resourceType() === "document") {
      await route.fulfill({
        status: 200,
        contentType: "text/html; charset=utf-8",
        body: "<!doctype html><html><head><meta charset='utf-8'></head><body>ok</body></html>",
      });
      return;
    }
    await route.fulfill({ status: 204, body: "" });
  });

  await page.goto(origin, { waitUntil: "domcontentloaded", timeout: 30000 });

  await page.evaluate(
    ({ localStorageItems, sessionStorageItems }) => {
      for (const item of localStorageItems) {
        try {
          localStorage.setItem(item.name, item.value);
        } catch {}
      }
      for (const item of sessionStorageItems) {
        try {
          sessionStorage.setItem(item.name, item.value);
        } catch {}
      }
    },
    { localStorageItems, sessionStorageItems }
  );

  await page.close().catch(() => {});
  return { origin, localStorage: localStorageItems.length, sessionStorage: sessionStorageItems.length };
}

async function main() {
  const stateRaw = await fs.readFile(args.state, "utf-8");
  const storageState = JSON.parse(stateRaw);
  if (!storageState || typeof storageState !== "object") throw new Error("Invalid storageState JSON");

  const cookies = Array.isArray(storageState.cookies) ? storageState.cookies : [];
  const origins = Array.isArray(storageState.origins) ? storageState.origins : [];

  const ws = args.ws || (await getWsDebuggerUrl(args.port));
  const browser = await chromium.connectOverCDP(ws);

  try {
    const contexts = browser.contexts();
    if (!contexts.length) throw new Error("No browser context found. Make sure Chrome has an open window.");

    const context = contexts[0];
    await context.addCookies(cookies);

    const importedOrigins = [];
    for (const entry of origins) {
      importedOrigins.push(await importOriginStorage(context, entry));
    }

    const cookieCount = (await context.cookies().catch(() => [])).length;
    const xCookieCount = (await context.cookies(["https://x.com"]).catch(() => [])).length;

    let verifyUrl = null;
    if (args.verify) {
      const page = await context.newPage();
      await page.goto("https://x.com/home", { waitUntil: "domcontentloaded", timeout: 60000 });
      verifyUrl = page.url();
      await page.close().catch(() => {});
    }

    console.log(
      JSON.stringify(
        {
          ok: true,
          importedCookies: cookies.length,
          contextCookiesNow: cookieCount,
          contextCookiesForX: xCookieCount,
          importedOrigins,
          verifyUrl,
          note: "If verifyUrl is a login flow, your state may be expired/invalid.",
        },
        null,
        2
      )
    );
  } finally {
    await browser.close().catch(() => {});
  }

  process.exit(0);
}

main().catch((err) => {
  console.error(String(err?.stack || err));
  process.exit(1);
});

