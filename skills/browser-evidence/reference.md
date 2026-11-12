# browser-evidence 细则

> 何时读：探测结果异常（找不到 / 装了不能跑 / 截图失败），或需要跨平台命令、登录态复用、WSL 特例时。日常只读 SKILL.md 三步工作流即可。

## 1. 平台判定全表

| 环境 | 命令 | 判据 |
|---|---|---|
| macOS | `uname -s` | `Darwin` |
| Linux | `uname -s` | `Linux`，且 `/proc/version` **不含** `microsoft` |
| **WSL1 / WSL2** | `uname -s` + `grep -qi microsoft /proc/version` | `Linux` 且命中 `microsoft` |
| Windows PowerShell | `$env:OS` / `$IsWindows` | `Windows_NT` / `$true` |
| Windows Git Bash | `uname -s` | `MINGW64_NT-*` / `MSYS_NT-*` |

```bash
# POSIX 一行判定
os=$(uname -s); [ "$os" = Linux ] && grep -qi microsoft /proc/version && os=wsl; echo "$os"
```

```powershell
# PowerShell 一行判定
if ($IsWindows) { 'windows' } else { 'posix' }
```

> **WSL 判错的代价**：把 WSL 当 Windows，会去探测一个 PATH 里根本不存在的 `ego-browser`，白跑一轮后仍要降级。

## 2. 探测命令（全部允许失败）

| 后端 | POSIX | PowerShell |
|---|---|---|
| ego-browser | `command -v ego-browser` | `Get-Command ego-browser -ErrorAction SilentlyContinue` |
| ego-browser 版本 / 指南 | `ego-browser skill 2>&1 \| tail -3` | `ego-browser skill 2>&1 \| Select-Object -Last 3` |
| agent-browser | `command -v agent-browser && agent-browser --version` | `Get-Command agent-browser; agent-browser --version` |
| Playwright 模块 | `node -e "console.log(require.resolve('playwright'))"` | `node -e "console.log(require.resolve('playwright'))"` |
| Playwright CLI | `<项目>/node_modules/.bin/playwright --version` | `<项目>\node_modules\.bin\playwright.cmd --version` |
| Chrome 二进制（备用） | `ls ~/.cache/ms-playwright 2>/dev/null` | `dir $env:LOCALAPPDATA\ms-playwright` |
| 本机 Chrome | `command -v google-chrome \|\| command -v chromium` | `Get-Command chrome -ErrorAction SilentlyContinue` |

**ego-browser 的成功判据**：`ego-browser skill` 输出末尾必须出现 `[ego-browser:skill] end of guide`。该行缺失说明输出被截断（或版本过老），按上游建议落盘后分段读，**不要凭残缺输出操作**。

**Playwright 的探测不要用 `npx`**：未安装时 `npx playwright` 会触发下载（实测报 `canceled due to missing packages and no YES option`）。`require.resolve` 只解析、不下载。

## 3. ego-browser 最小命令集

ego-browser 的页面操作命令**由本地安装版本决定**，必须以其自身输出为准：

```bash
ego-browser skill          # 打印与本地版本匹配的使用指南（含哨兵行）
ego-browser upgrade        # 升级；需用户批准，且升级后要重跑 skill
```

- 本文件**不复述**其页面命令——复述必然随版本漂移，这正是它把指南做成动态输出的原因
- 平台限制：仅 macOS / Windows；Linux 无安装程序
- 登录态：**原生**（它就是用户日常用的浏览器），Agent 在独立 Space 里操作，不抢用户窗口
- **高风险**：profile 级的 cookie / 缓存清除不可逆且波及整个 profile（用户所有站点一并登出），执行前必须征得同意并说明影响面
- 首次使用需在 GUI 完成 onboarding，Agent 无法代办

## 4. agent-browser 最小命令集

> 直接调用 `agent-browser`，**永远不要 `npx agent-browser`**（上游文档明写 npx 走 Node 会明显更慢）。
> **子命令随版本变动**：下表以 0.25.x 为准（`open` / `wait` / `set viewport` / `screenshot --annotate` / `record` 已实测）；`state`、`network har`、`trace`、`diff` 等未逐一实测，**用前先跑一次 `agent-browser --help` 确认参数形态**，报"unknown command"时按提示改，而不是硬试。

```bash
# 会话与导航
agent-browser --session {name} open {url}
agent-browser --session {name} wait --load networkidle
agent-browser --session {name} close

# 理解页面
agent-browser --session {name} snapshot -i            # 可交互元素（带 @eN 引用）
agent-browser --session {name} snapshot               # 读正文 / 标题 / 列表
agent-browser --session {name} click @e3
agent-browser --session {name} fill @e1 "text"
agent-browser --session {name} type @e1 "text"        # 逐字符（录视频时用）

# 画面
agent-browser --session {name} set viewport 1440 900
agent-browser --session {name} screenshot --annotate {out}/step-1.png
agent-browser --session {name} screenshot --full {out}/full.png
agent-browser --session {name} record start {out}/repro.webm
agent-browser --session {name} record stop

# 观测
agent-browser --session {name} console
agent-browser --session {name} errors
agent-browser --session {name} network requests
agent-browser --session {name} network har start {out}/net.har
agent-browser --session {name} trace start {out}/trace.json

# 登录态（三条路径，见第 6 节）
agent-browser --profile Default open {url}            # 借 Chrome profile
agent-browser --auto-connect snapshot                 # 接管正在跑的 Chrome
agent-browser --session {name} state save {out}/auth.json

# 批量
agent-browser batch --bail "open {url}" "set viewport 375 812" "screenshot {out}/375.png"
```

- 浏览器来源：默认用 Chrome；**会自动探测并复用已有的 Chrome / Brave / Playwright / Puppeteer**，所以常常无需 `agent-browser install`
- 真找不到浏览器时，**请用户自己执行** `agent-browser install`（Linux 可能还需要 `--with-deps`）
- 多视口批量用 `batch`；跨视口比对可配合 `diff screenshot --baseline`

## 5. Playwright 最小命令集

```bash
<项目>/node_modules/.bin/playwright --version     # 探测
<项目>/node_modules/.bin/playwright install chromium   # ❌ 本 skill 不代跑，提示用户
```

多视口截图脚本骨架（存成 `shot.mjs`，用**能解析到 playwright 的那个 node_modules** 跑）：

```js
// shot.cjs —— 刻意用 CommonJS：ESM 解析**不认** NODE_PATH，用 import 时下面的命令会失败
const { chromium } = require('playwright');

(async () => {
  const [url, outDir] = process.argv.slice(2);
  const sizes = ['375x812', '768x1024', '1440x900'];

  const browser = await chromium.launch();
  for (const size of sizes) {
    const [width, height] = size.split('x').map(Number);
    const page = await browser.newPage({ viewport: { width, height } });
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.screenshot({ path: `${outDir}/${size}.png`, fullPage: true });
    await page.close();
  }
  await browser.close();
})();
```

```bash
mkdir -p .walkthrough/order-list/screenshots
NODE_PATH=/path/to/node_modules node shot.cjs http://localhost:3000 .walkthrough/order-list/screenshots
```

- 模块散落在多处时（项目内 / 全局 / npx 缓存），用 `NODE_PATH` 指向能解析的那一处，**不要为此重装**
- 需要登录态时用 `storageState`：先人工登录导出，再在 `newContext({ storageState })` 里复用——**不要**把真实账号密码写进脚本

## 6. 登录态三条路径

| 路径 | 适用 | 代价 / 风险 |
|---|---|---|
| **ego-browser 原生** | macOS / Windows，且页面就在用户自己的浏览器里 | 无迁移成本；但仅限这两个平台 |
| **agent-browser `--profile`** | 复用本机 Chrome 的登录态 | 读用户 profile 目录，需用户同意；profile 在升级 / 迁移时可能失效 |
| **agent-browser `--auto-connect`** | 接管**已在运行**的 Chrome | 会导航走用户当前标签页，只在其知情时用 |
| **Playwright `storageState`** | 需要可复现、可进 CI | 需先人工登录导出一次；导出文件含凭据，**不得入库** |

> 三条路径都触及真实账号。**默认不用**：先问"目标页是否必须登录"，能匿名走查就别碰登录态。

## 7. WSL 与远程开发特例

| 场景 | 现象 | 处理 |
|---|---|---|
| 服务在 WSL，浏览器也在 WSL | `http://localhost:3000` 可直接访问 | 正常 A 档 |
| 服务在 WSL，`ego-browser` 装在 Windows 宿主 | WSL 里 `command -v ego-browser` 为空 | 归 Linux 侧 → agent-browser / Playwright；**不要**假设能调 `.exe` |
| 页面是 `file://` | 部分后端 / 容器内路径映射不到 | 改用本地 HTTP 服务（`python -m http.server`）再访问 |
| 服务在远程机 / 容器 | 本机 localhost 不通 | 先建端口转发（SSH `-L` 或 TUNNEL），确认能打开再取得证 |
| 无图形界面 | 必须 headless | agent-browser / Playwright 默认 headless；ego-browser 需要 GUI，此类环境直接出局 |

**WSL 通过 interop 调 `ego-browser.exe` 属未验证路径**：可能受 PATH 映射、GUI 会话、输出编码影响。本 skill 不把它列为主链路；用户明确要求时可试一次，**失败即静默回退**，不得把它当既定能力写进报告。

## 8. 故障排查

| 报错 / 现象 | 根因 | 处理 |
|---|---|---|
| `npx playwright` 报 `canceled due to missing packages` | 未安装且 npx 想下载 | 改 `require.resolve` 探测；装不装由用户决定 |
| `Cannot find module 'playwright'` | 模块不在当前解析路径 | 用 `NODE_PATH` 指向能解析的 node_modules，或换 agent-browser |
| agent-browser 报找不到浏览器 | 本机无 Chrome 且无 Playwright / Puppeteer | 请用户跑 `agent-browser install`（不代跑） |
| 截图全白 / 只有骨架 | 页面未加载完、SPA 异步渲染 | `wait --load networkidle` 后再截；必要时 `wait <selector>` |
| 截图尺寸不对 | 未设视口或设了但复用旧会话 | `set viewport W H` 后重新导航再截 |
| 中文乱码（Windows） | 控制台编码 | `chcp 65001`（cmd）/ `$OutputEncoding`（PowerShell） |
| 元素点不到 | 选择器失效 / 元素在 iframe | 先 `snapshot -i` 拿 `@eN` 引用，再 `click @eN`；iframe 需先切换上下文 |
| 会话串台（两道任务互影响） | 共用了同一个 session | 每轮任务用独立 `--session {slug}`，结束 `close` |

## 9. 隐私与合规

- 截图可能含**真实用户数据**（列表页、详情页、头像、手机号）——落盘前提示，对外交付前脱敏
- 远程 provider（`browserbase` / `kernel` / `browseruse` / `browserless` / `agentcore`）会把页面内容与 DOM 送出本机，**默认禁用**
- `state save` / `storageState` 导出文件等价于凭据，**不得提交进仓库**，建议加入 `.gitignore`
- 不把生产环境的会话 cookie 带到测试环境，反之亦然
