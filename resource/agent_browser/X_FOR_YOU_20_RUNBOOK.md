# X「For You」最近 20 条抓取与总结（Runbook）

本文档记录一次完整可复现的流程：在 macOS 上复用你本机 Chrome（有头）+ 远程调试端口（CDP），加载已有 `storageState`（`x-auth-state.json`），进入 `https://x.com/home` 的 **For you** 时间线，滚动抓取最近 **20 条（过滤推广）**，并产出结构化 JSON，便于后续再做中文总结/归类。

仓库相关文件：
- 抓取脚本：`tools/x_for_you_20.mjs`
- 导入脚本（把 storageState 写入正在运行的 Chrome profile）：`tools/x_import_state_to_user_data_dir.mjs`
- 登录态（Playwright storage state）：`x-auth-state.json`
- 输出结果（示例）：`for_you_20.json`

---

## 目标与约束

**目标**
- 直接进入 `https://x.com/home`，定位到 For you 时间线。
- 抓取时间线中最近 20 条推文（去掉 Promoted/推广/赞助）。
- 产出 JSON：包含每条的 URL、时间、作者、@handle、正文、媒体数量、是否引用等字段。

**约束/现实情况**
- X 的内容加载/滚动是动态的（无限滚动），无法一次性拿到固定列表。
- `agent-browser` 自带的 `state load` 在当前版本不支持“运行中加载到现有 context”，它提示“必须在浏览器启动时加载”（CLI 没有暴露 `--state` 选项）。因此这里使用一个轻量脚本 `tools/x_for_you_20.mjs`，通过 Playwright 在 CDP 连接上新建 context 时注入 `storageState`。

---

## 前置条件

1) 你本机已安装 Chrome（macOS）  
   示例路径：`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`

2) 你已经有可用的 Playwright `storageState` 文件  
   文件：`x-auth-state.json`  
   结构应包含：
   - `cookies`: 数组
   - `origins`: 数组

3) 本项目里已有 `tools/x_for_you_20.mjs`（本次已添加）

---

## Step 1：用 CDP 启动一个“可被接管”的 Chrome（有头）

建议用一个独立的 user-data-dir，避免和你日常 Chrome 的 profile lock 冲突：

```bash
open -na "Google Chrome" --args \
  --remote-debugging-port=9333 \
  --user-data-dir=/tmp/chrome-cdp9333
```

说明：
- `--remote-debugging-port=9333`：开启 CDP 服务。
- `--user-data-dir=/tmp/chrome-cdp9333`：指定这次 Chrome 的用户数据目录（独立、可控）。
- 这会打开一个你能看得见的 Chrome 窗口（有头）。

---

## Step 2：验证 CDP 端口是否可用

```bash
curl -sS http://127.0.0.1:9333/json/version
```

预期返回 JSON，其中必须包含类似字段：
- `webSocketDebuggerUrl`: `ws://127.0.0.1:9333/devtools/browser/...`

如果你的终端配置了 HTTP 代理（例如 `http_proxy` 指向 `127.0.0.1:7890`），curl 可能会走代理导致失败；可用：

```bash
curl --noproxy '*' -sS http://127.0.0.1:9333/json/version
```

如果没有 `webSocketDebuggerUrl` 或请求失败：
- 检查 Chrome 是否真的用上述命令启动（而不是普通方式启动）。
- 换一个端口（如 9222、9334），避免占用。

---

## Step 3：为什么 “connect 9333 / http://127.0.0.1:9333” 可能失败

在这次流程中，`agent-browser connect 9333` / `connect http://127.0.0.1:9333` 曾报错：
> Failed to connect via CDP to http://localhost:9333 ...

原因是 Playwright 的 `connectOverCDP()` 对不同入口的兼容性差异：  
**用 `webSocketDebuggerUrl`（ws://...）最稳**，因此后续脚本直接读取 `/json/version` 并使用 `ws://...` 来连接。

---

## Step 4：用 `x-auth-state.json` 直接进入 X Home（核心步骤）

运行抓取脚本（会自动读取 CDP ws url，并用 `storageState` 创建新 context）：

```bash
node tools/x_for_you_20.mjs \
  --port 9333 \
  --state x-auth-state.json \
  --out for_you_20.json
```

如果你的环境禁止脚本主动访问 `http://127.0.0.1:<port>`（例如某些沙箱限制），可先用 curl 拿到 ws 地址再传入：

```bash
curl -sS http://127.0.0.1:9333/json/version
# 复制其中的 webSocketDebuggerUrl，然后：
node tools/x_for_you_20.mjs --ws "ws://127.0.0.1:9333/devtools/browser/..." --state x-auth-state.json --out for_you_20.json
```

脚本行为概述：
1. `GET http://127.0.0.1:9333/json/version` 获取 `webSocketDebuggerUrl`
2. `chromium.connectOverCDP(wsUrl)` 连接到你已打开的 Chrome
3. `browser.newContext({ storageState })` 注入登录态
4. 打开 `https://x.com/home`，若不在 `/home` 则判定登录态失效
5. 尝试点击 For you（匹配 `For you/为你/推荐`）
6. 读取页面中的 `article`，抽取推文信息，滚动直到收集满 20 条
7. 写入 `for_you_20.json` 并退出

---

## Step 5：输出文件格式（`for_you_20.json`）

输出结构：

```json
{
  "items": [
    {
      "url": "https://x.com/<user>/status/<id>",
      "time": "2026-01-24T07:20:53.000Z",
      "author": "显示名 ...",
      "handle": "@user",
      "text": "正文 ...",
      "mediaCount": 1,
      "quoteUrl": "https://x.com/<...>/status/<...>",
      "promoted": false
    }
  ]
}
```

字段说明：
- `url`: 推文链接（主键，用来去重）
- `time`: 优先取 `time[datetime]`，否则退化为显示文本
- `author`: 用户名块（显示名/handle/时间可能混在一起，脚本做了清理但仍以页面实际为准）
- `handle`: 尝试从作者区域提取 `@...`，提取不到则为 `null`
- `text`: 推文正文，提取不到则为 `null`（如纯图片/视频可能为空）
- `mediaCount`: 图片或视频数量（粗略统计）
- `quoteUrl`: 引用推文链接（若存在）
- `promoted`: 是否被识别为推广（脚本会过滤 `true` 的条目）

---

## Step 6：从 JSON 生成中文“逐条摘要”

你可以用 Python 把 `for_you_20.json` 打印成“20 条逐条摘要”：

```bash
python3 - <<'PY'
import json

def short(s, n=140):
  s=(s or "").replace("\\n"," ").strip()
  return s if len(s)<=n else s[:n-1]+"…"

items=json.load(open("for_you_20.json","r",encoding="utf-8"))["items"]
for i,it in enumerate(items,1):
  print(f"{i:02d} {it.get('author')} | {it.get('time')} | media={it.get('mediaCount')} | {short(it.get('text'))}")
  print(f"    {it.get('url')}")
PY
```

---

## 常见问题与排错

### 1) `Daemon failed to start`

在某些受限环境里（例如被沙箱限制创建 Unix socket），`agent-browser` 的 daemon 会因为无法 `listen` 到 sock 而失败，常见报错类似：
`listen EPERM: operation not permitted ... default.sock`

解决思路：
- 在你自己的正常终端环境里通常不会遇到。
- 如果环境确实限制 socket：需要放宽限制或改用不受限的执行环境。

### 2) 进入 `x.com/home` 仍然跳登录页

如果脚本判断 `page.url()` 不是 `/home`，一般是：
- `x-auth-state.json` 已过期（cookies 失效）
- 登录态导出时缺少关键 cookies

修复方式：
- 用浏览器正常登录一次 X，然后重新导出新的 `storageState`（确保包含 x.com 域 cookies）。

---

## 可选：把 `x-auth-state.json` 写入 `/tmp/chrome-cdp9333`（一次性导入，后续可复用无需手动登录）

如果你的目标是“以后直接用同一个 `--user-data-dir=/tmp/chrome-cdp9333` 运行/被 agent-browser 启动也能保持登录态”，可以执行一次导入，把 `storageState` 的 cookies/localStorage 写进当前正在运行的 Chrome profile。

前提：你已经用如下命令启动了 Chrome（可见窗口）：

```bash
open -na "Google Chrome" --args --remote-debugging-port=9333 --user-data-dir=/tmp/chrome-cdp9333
```

执行导入（会连接到这个 Chrome 并写入状态）：

```bash
node tools/x_import_state_to_user_data_dir.mjs --port 9333 --state x-auth-state.json
```

导入完成后验证方式（建议）：
1) 关闭该 Chrome
2) 重新用同一个 user-data-dir 打开并访问 `https://x.com/home`，确认不再要求登录

如果你想用 agent-browser 直接复用该目录（注意不要与正在运行的 Chrome 同时占用该目录）：

```bash
agent-browser --headed \
  --executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --profile /tmp/chrome-cdp9333 \
  open https://x.com/home
```

### 3) 抓取变慢或卡住

X 页面在滚动时会加载大量内容，个别 `locator.innerText()` 可能等待过久。脚本已做：
- 降低默认超时
- 只扫描前 40 个 `article`
- 每轮滚动后等待固定时间

如果仍卡：
- 降低 `rounds` 上限或滚动次数
- 先人工滚动几屏再运行脚本（让页面有内容）

---

## 安全与隐私

- `x-auth-state.json` 含 cookies/登录态信息，等同“登录凭证”，请勿提交到 Git、勿外传。
- 如果需要共享复现流程，请只共享 `tools/x_for_you_20.mjs` 和本文档，不要共享 state 文件。
