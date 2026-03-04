#!/usr/bin/env node
import fs from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import readline from 'node:readline';

const require = createRequire(import.meta.url);
let playwright;
try {
  playwright = require('playwright');
} catch {
  try {
    playwright = require('playwright-core');
  } catch {
    playwright = require('/Users/felicity/.nvm/versions/node/v20.19.2/lib/node_modules/agent-browser/node_modules/playwright-core');
  }
}

const { chromium } = playwright;

function parseArgs(argv) {
  const args = {
    out: path.resolve(process.cwd(), 'x-auth-state.json'),
    force: false,
    timeoutMs: 15 * 60 * 1000,
  };

  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out') args.out = path.resolve(argv[++i]);
    else if (a === '--force') args.force = true;
    else if (a === '--timeout-ms') args.timeoutMs = Number(argv[++i]);
    else if (a === '--help' || a === '-h') args.help = true;
  }
  return args;
}

function usage() {
  console.log([
    'Usage:',
    '  node scripts/export_x_auth_state.mjs --out /path/x-auth-state.json [--force]',
    '',
    'Behavior:',
    '  - If file exists and --force is not set: skip generation.',
    '  - Otherwise launch browser for manual X login and export Playwright storageState.',
  ].join('\n'));
}

async function exists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

function waitForEnter(promptText) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(promptText, () => {
      rl.close();
      resolve();
    });
  });
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    usage();
    return;
  }

  const already = await exists(args.out);
  if (already && !args.force) {
    console.log(JSON.stringify({ ok: true, skipped: true, reason: 'state_exists', out: args.out }, null, 2));
    return;
  }

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ locale: 'en-US' });
  const page = await context.newPage();

  try {
    await page.goto('https://x.com/home', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await waitForEnter('Please finish logging into X in the opened browser, then press Enter here to export storageState... ');

    await fs.mkdir(path.dirname(args.out), { recursive: true });
    await context.storageState({ path: args.out });

    console.log(JSON.stringify({ ok: true, skipped: false, out: args.out }, null, 2));
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch((e) => {
  console.error(e?.stack || String(e));
  process.exit(1);
});
