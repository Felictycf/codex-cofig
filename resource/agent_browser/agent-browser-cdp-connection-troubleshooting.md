---
title: agent-browser 连接已启动 Chrome（CDP）失败排查与解决方案
---

# agent-browser 连接已启动 Chrome（CDP）失败排查与解决方案

## 背景与目标
你希望用 `agent-browser` “接管”已经启动的 Chrome，并在该浏览器实例中自动化操作（例如访问 `https://x.com/i/bookmarks`）。接管的底层机制是 **Chrome DevTools Protocol（CDP）**。

当你执行类似命令时出现错误：

```bash
AGENT_BROWSER_SOCKET_DIR=/tmp/agent-browser-sock agent-browser --debug --session x connect http://127.0.0.1:9333
# ✗ Failed to connect via CDP to http://127.0.0.1:9333 ...
```

本文解释原因，并给出一套稳定可复用的解决方案（也是我之前处理同类问题的方式）。

## 典型症状（Symptoms）
- `agent-browser connect <port>` 或 `agent-browser connect http://127.0.0.1:<port>` 报：
  - `Failed to connect via CDP...`
  - 或提示需要 `--remote-debugging-port=<port>`

即使你确认 Chrome 已经带端口启动并监听，仍然无法连接。

## 核心原因（Root Causes）

### 1) 你给 `connect` 的地址类型不对：HTTP 端点 vs WebSocket 端点
CDP 的“真正控制通道”是 **WebSocket**，形如：

- `ws://127.0.0.1:9333/devtools/browser/<id>`

而很多情况下（取决于工具实现与版本），`agent-browser connect` **并不能可靠地仅凭 `http://127.0.0.1:9333` 推导并完成握手**，会直接失败。

### 2) Chrome 可能没按预期启用远程调试端口
如果 Chrome 不是用以下参数启动的，就不会开放 CDP 端口：

- `--remote-debugging-port=9333`

### 3) `AGENT_BROWSER_SOCKET_DIR` 不是 CDP 连接参数
`AGENT_BROWSER_SOCKET_DIR=/tmp/agent-browser-sock` 只影响 agent-browser 自己的 daemon 进程通信 socket 存放位置：
- 它不决定 Chrome 的 CDP 可用性
- 它不能修复“连不上 Chrome”的问题

## 正确的连接方式（Recommended）
稳定做法是：**先从 CDP 的 HTTP 信息接口拿到 `webSocketDebuggerUrl`，再用它进行 connect。**

### 步骤 1：确认端口在监听
```bash
lsof -nP -iTCP:9333 -sTCP:LISTEN
```

你应该能看到类似：
- `Google Chrome ... TCP 127.0.0.1:9333 (LISTEN)`

### 步骤 2：获取 WebSocket 调试地址
```bash
curl -s http://127.0.0.1:9333/json/version
```

在输出 JSON 中找到：
- `webSocketDebuggerUrl`

示例（关键字段）：
```json
{
  "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/browser/d8230d44-caaf-426b-b9aa-d721e39db049"
}
```

### 步骤 3：用 WebSocket 地址连接
```bash
agent-browser --session x connect "ws://127.0.0.1:9333/devtools/browser/d8230d44-caaf-426b-b9aa-d721e39db049"
```

### 步骤 4：验证连接有效
```bash
agent-browser --session x get url
agent-browser --session x tab
```

## 为什么我之前的解决方案和你现在的是同一个？
是同一个思路。

我之前遇到的情况是：
- 端口确实在监听（例如 9222）
- 但 `agent-browser connect 9222` / `connect http://localhost:9222` 仍然失败
- 最终通过 `curl http://127.0.0.1:9222/json/version` 获取 `webSocketDebuggerUrl`，再用 `agent-browser connect <ws://...>` 成功接管

你现在对 9333 的问题，本质相同：**用 WS 端点连接更可靠**。

## Chrome 启动命令（确保可接管）

### 启动一个“独立实例”（推荐：不影响你主 Chrome）
```bash
open -na "Google Chrome" --args --remote-debugging-port=9333 --user-data-dir=/tmp/chrome-cdp-9333
```

要点：
- `--remote-debugging-port=9333`：开放 CDP
- `--user-data-dir=...`：使用独立 profile，避免和主 Chrome 冲突/锁冲突

### 常见陷阱：同一个 profile 不能并行给多个 Chrome 实例用
不要同时启动两个实例都指向同一个 `--user-data-dir`（容易被锁住或行为冲突）。

## 快速排错清单（Checklist）
1) 端口监听是否存在？
```bash
lsof -nP -iTCP:9333 -sTCP:LISTEN
```

2) CDP HTTP 信息接口是否可访问？
```bash
curl -s http://127.0.0.1:9333/json/version
```

3) 是否用 `webSocketDebuggerUrl` 进行 connect？
```bash
agent-browser connect "ws://127.0.0.1:9333/devtools/browser/<id>"
```

4) 是否连到了你期望的那个 Chrome（可能同时开了 9222、9333）？
- 分别 curl 两个端口的 `/json/version`，对比返回的 `<id>` 与实例

## FAQ

### Q1：我能用 `agent-browser connect http://127.0.0.1:9333` 吗？
有时可以，有时不行。最稳妥的是用 `webSocketDebuggerUrl`（`ws://...`）。

### Q2：`AGENT_BROWSER_SOCKET_DIR` 能修复 connect 失败吗？
不能。它不影响 Chrome CDP 端口，只影响 agent-browser daemon 自身的 socket 目录。

### Q3：多个 agent-browser 能同时接管同一个 Chrome 吗？
技术上可以（都连同一个 WS/CDP），但会共享标签页/焦点/滚动，**并发操作很容易互相干扰**。要并行建议：
- 不同 Chrome 实例（不同端口 + 不同 profile），或
- 串行使用同一个实例

## 最推荐的“一行式”连接流程（9333）
```bash
WS=$(curl -s http://127.0.0.1:9333/json/version | python3 -c 'import sys,json; print(json.load(sys.stdin)["webSocketDebuggerUrl"])')
agent-browser --session x connect "$WS"
```

