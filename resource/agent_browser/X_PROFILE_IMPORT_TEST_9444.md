# 新建 Chrome Profile（`/tmp/chrome-cdp9444`）并导入 `x-auth-state.json` 的完整流程（Runbook）

本文档记录一次完整可复现的流程：  
创建一个全新的 Chrome `--user-data-dir=/tmp/chrome-cdp9444`，用 CDP（Chrome DevTools Protocol）接管该浏览器，将 `x-auth-state.json`（Playwright storageState）导入并写入该 profile，从而实现 **无需手动登录** 也可直接打开 `https://x.com/home`。随后在该 profile 上抓取 X「For You」最近 20 条并输出 JSON。

相关文件：
- 登录态（Playwright storageState）：`x-auth-state.json`
- 导入脚本：`tools/x_import_state_to_user_data_dir.mjs`
- 抓取脚本：`tools/x_for_you_20.mjs`
- 抓取输出：`for_you_20_9444.json`
- 旧版通用 Runbook（含更多背景）：`X_FOR_YOU_20_RUNBOOK.md`

---

## 目标

1) 新建独立的 Chrome profile（避免与主浏览器冲突）
2) 将 `x-auth-state.json` 导入并写入该 profile（cookies + localStorage）
3) 验证在**不再传入 storageState** 的情况下也能直达 `https://x.com/home`
4) 抓取 For You 最近 20 条并保存为 `for_you_20_9444.json`

---

## 前置条件

### 必需
- macOS 本地可运行 Google Chrome
- 已有可用的 Playwright storageState：`x-auth-state.json`
- 本项目已包含脚本：
  - `tools/x_import_state_to_user_data_dir.mjs`
  - `tools/x_for_you_20.mjs`

### 可选（但强烈建议）
- 确认不会有其它 Chrome 实例同时占用同一个 `--user-data-dir`（避免 profile lock）

---

## Step 1：创建全新的 `user-data-dir` 并启动 Chrome（CDP 9444）

```bash
rm -rf /tmp/chrome-cdp9444
open -na "Google Chrome" --args --remote-debugging-port=9444 --user-data-dir=/tmp/chrome-cdp9444
```

说明：
- `rm -rf`：确保是干净的新 profile（测试时非常重要）。
- `--remote-debugging-port=9444`：开启 CDP 服务，后续脚本通过该端口接管浏览器。
- `--user-data-dir=/tmp/chrome-cdp9444`：把 cookies/localStorage 等写入这个目录。

---

## Step 2：确认 CDP 端口是否正常

### 方式 A：Node fetch（推荐，避免 shell 代理干扰）

```bash
node -e "fetch('http://127.0.0.1:9444/json/version').then(r=>r.json()).then(j=>console.log(j.webSocketDebuggerUrl)).catch(e=>{console.error(e); process.exit(1)})"
```

预期输出类似：
`ws://127.0.0.1:9444/devtools/browser/<id>`

### 方式 B：curl（如果你环境配置了 HTTP 代理，务必加 `--noproxy`）

```bash
curl --noproxy '*' -sS http://127.0.0.1:9444/json/version
```

---

## Step 3：将 `x-auth-state.json` 导入到正在运行的 Chrome（写入 profile）

执行导入脚本：

```bash
node tools/x_import_state_to_user_data_dir.mjs --port 9444 --state x-auth-state.json
```

导入脚本做了什么：
1) 读取 `x-auth-state.json` 的 `cookies` / `origins`
2) 通过 `http://127.0.0.1:9444/json/version` 获取 `webSocketDebuggerUrl`
3) `chromium.connectOverCDP(wsUrl)` 连接你刚打开的 Chrome
4) 向已有 context 注入 cookies：`context.addCookies(cookies)`
5) 对 `origins` 里的每个 origin（此处是 `https://x.com`）：
   - 新开页面并 route 拦截该 origin 的请求，返回本地 HTML（避免外部网络依赖）
   - 在页面中写入 localStorage/sessionStorage
6) 验证：打开 `https://x.com/home`，输出最终 `verifyUrl`

导入成功的判断标准：
- 输出 `verifyUrl` 为 `https://x.com/home`（而不是 `https://x.com/i/flow/login?...`）
- 输出 `contextCookiesForX` 有值（例如本次为 12）

本次执行结果（示例）：
```json
{
  "ok": true,
  "importedCookies": 26,
  "contextCookiesForX": 12,
  "verifyUrl": "https://x.com/home"
}
```

---

## Step 4：验证“确实写进 profile”——不再传入 storageState 也能直达 Home

导入成功后，需要验证它不是“仅在临时上下文有效”，而是确实写入到了 `/tmp/chrome-cdp9444` 的 profile。

验证方式：通过 CDP 连接 Chrome，新建一个**不带 `storageState`** 的 context，然后打开 Home：

```bash
node - <<'NODE'
const { createRequire } = require('module');
const require2 = createRequire(process.cwd() + '/');
const { chromium } = require2('/Users/felicity/.nvm/versions/node/v20.19.2/lib/node_modules/agent-browser/node_modules/playwright-core');
(async () => {
  const v = await fetch('http://127.0.0.1:9444/json/version').then(r=>r.json());
  const browser = await chromium.connectOverCDP(v.webSocketDebuggerUrl);
  const ctx = await browser.newContext({ locale: 'zh-CN' });
  const page = await ctx.newPage();
  await page.goto('https://x.com/home', { waitUntil: 'domcontentloaded', timeout: 60000 });
  console.log(JSON.stringify({ url: page.url(), title: await page.title() }, null, 2));
  await ctx.close();
  await browser.close();
})().catch(e=>{ console.error(e); process.exit(1); });
NODE
```

成功标准：
- 输出的 `url` 仍为 `https://x.com/home`
- 没有跳转到登录流程

---

## Step 5：抓取 For You 最近 20 条（输出 `for_you_20_9444.json`）

运行抓取脚本：

```bash
node tools/x_for_you_20.mjs --port 9444 --state x-auth-state.json --out for_you_20_9444.json
```

脚本要点：
- 通过 CDP 连接到 Chrome（9444）
- 新建 context，并注入 `storageState`（双保险：即使 profile 写入失败也尽量能跑通）
- 打开 `https://x.com/home`，尝试点击 For you
- 从 `article` 结构中提取推文信息，滚动直到收集满 20 条
- 过滤推广（Promoted/推广/赞助）

成功输出示例：
```json
{ "ok": true, "count": 20, "out": "for_you_20_9444.json" }
```

---

## Step 6：打印 20 条的逐条摘要（从 JSON）

```bash
python3 - <<'PY'
import json
def short(s, n=140):
  s=(s or "").replace("\n"," ").strip()
  return s if len(s)<=n else s[:n-1]+"…"
items=json.load(open("for_you_20_9444.json","r",encoding="utf-8"))["items"]
print("count", len(items))
for i,it in enumerate(items,1):
  print(f"{i:02d} {it.get('author')} | {it.get('time')} | media={it.get('mediaCount')} | {short(it.get('text'))}")
  print(f"    {it.get('url')}")
PY
```

---

## 复用方式（后续日常使用）

### 1) 复用同一个 profile 重新启动 Chrome

```bash
open -na "Google Chrome" --args --user-data-dir=/tmp/chrome-cdp9444
```

### 2) 若要继续给脚本/工具接管，则仍用同一个端口+目录启动

```bash
open -na "Google Chrome" --args --remote-debugging-port=9444 --user-data-dir=/tmp/chrome-cdp9444
```

---

## 排错

### A) 导入后仍跳登录页
- `x-auth-state.json` 可能已过期/缺少关键 cookies
- 重新导出新的 storageState 再导入

### B) 端口连不上
- 端口被占用：换 9445/9555
- Chrome 没用 `--remote-debugging-port` 启动：重启并带上参数

### C) `curl` 访问 127.0.0.1 失败但 Node 可以
- 通常是 shell 代理环境变量导致 curl 走了代理；用 `curl --noproxy '*' ...`

---

## 安全提示

- `x-auth-state.json` 含 cookies/登录态，等同账号凭证；不要上传、不要提交到 Git。

