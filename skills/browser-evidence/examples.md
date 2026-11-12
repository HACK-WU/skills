# browser-evidence 示例

> 三个示例覆盖三种典型环境：macOS 有 ego-browser、WSL 只有 agent-browser、三后端全无。每个都给出**探测输出 → 声明行 → 取证动作 → 降级边界**。

## 示例 1：macOS + ego-browser（需要用户登录态）

**场景**：用户说"看看我们后台的订单详情页有什么体验问题"，该页必须登录，本机是 macOS 且装了 ego lite。

### 探测

```bash
uname -s                                  # Darwin
command -v ego-browser                    # /Applications/ego lite.app/.../ego-browser
ego-browser skill 2>&1 | tail -1          # [ego-browser:skill] end of guide  ← 哨兵行在
```

### 声明与选型

选择理由：**必须登录 + 登录态就是用户自己的** → ego-browser 的 Space 隔离能直接复用，不用导出 cookie。

```text
取证后端：ego-browser｜平台：macOS 14｜档位：A
```

### 取证

1. `ego-browser skill` 读指南（本文件不复述其页面命令，版本一变就过时）
2. 在独立 Space 打开订单详情页，按 `frontend-walkthrough` 的八态逐个造
3. 每态按「证据包最小规格」取证：交互类录屏 + 分步截图，静态类单张标注图

### 边界

- ❌ 不跑 `ego-browser upgrade`（改本机软件，需用户批准）
- ❌ 不清 profile 级 cookie / 缓存（不可逆，会登出用户全部站点）
- ✅ 只动本任务 Space，不碰用户其他标签页

---

## 示例 2：WSL2 + agent-browser（多视口截图）

**场景**：Linux/WSL 开发机，项目 `npm run dev` 起在 `localhost:3000`，要 375 / 768 / 1440 三档截图。

### 探测

```bash
uname -s                                          # Linux
grep -qi microsoft /proc/version && echo WSL      # WSL
command -v ego-browser                            # 空 → 平台硬门，直接出局
command -v agent-browser && agent-browser --version   # agent-browser 0.25.4
```

**不要**去试 `npx playwright --version`——未安装时会触发下载，探测变安装。

### 声明与选型

选择理由：**只要画面、要批量多视口** → agent-browser 的 `set viewport` + `batch` 最省事；且它自动复用了本机已有的 Chromium，无需 `install`。

```text
取证后端：agent-browser 0.25.4｜平台：WSL2｜档位：A
```

### 取证

```bash
S=order-list
mkdir -p .walkthrough/$S/screenshots .walkthrough/$S/videos
agent-browser --session $S open http://localhost:3000/orders
agent-browser --session $S wait --load networkidle

# 三视口（每档先设视口，再截；截完可顺手记 meta）
for vp in "375 812" "768 1024" "1440 900"; do
  read -r w h <<< "$vp"
  agent-browser --session $S set viewport $w $h
  agent-browser --session $S screenshot --full .walkthrough/$S/screenshots/default-${w}x${h}.png
done

# 一条交互缺陷的证据包
agent-browser --session $S record start .walkthrough/$S/videos/issue-001-repro.webm
agent-browser --session $S screenshot --annotate .walkthrough/$S/screenshots/issue-001-step-1.png
agent-browser --session $S click @e7
sleep 1
agent-browser --session $S screenshot --annotate .walkthrough/$S/screenshots/issue-001-result.png
sleep 2
agent-browser --session $S record stop
agent-browser --session $S errors        # 顺手收 console
agent-browser --session $S close
```

产物按契约落 `meta.json`（`backend: agent-browser` / `viewport: 375x812` / `tier: A`）。

### 边界

- ❌ 不跑 `agent-browser install`（要装请用户执行）
- ❌ 不用 `--auto-connect` 接管用户正在用的 Chrome（除非用户明确同意）
- ✅ WSL 里不假设能调 Windows 宿主的 `ego-browser.exe`——未验证路径，不写进结论

---

## 示例 3：三后端全无（B2 档 + 请用户供图）

**场景**：干净容器，`agent-browser` / `playwright` 都没装，`ego-browser` 平台不符，项目也起不来。

### 探测

```bash
command -v ego-browser        # 空
command -v agent-browser      # 空
node -e "require.resolve('playwright')"   # 抛错 → 模块不存在
```

三条全不通 → **不重试、不装东西**，直接进降级链。

### 声明

```text
取证后端：无｜平台：Linux｜档位：B2（按 product-manager 口径为 L3）
```

### 交给用户的两件事（一次说清，别分两轮）

**① 想让我自己截，任选一条装（命令给你，我不代跑）**

```bash
npm i -g agent-browser && agent-browser install    # 全平台，最省事
# 或：在项目里装 playwright（需项目本身是 Node 项目）
npm i -D playwright && ./node_modules/.bin/playwright install chromium
```

**② 不想装，就按这份拍摄清单给图**

```text
1. 列表页默认态（有数据）
2. 列表页空态（筛选无结果 / 新账号）
3. 详情页默认态
4. 表单校验错误态（故意留空提交）
5. 接口失败态（断网后操作）
6. 窄屏 375 宽（至少一屏）
分辨率：桌面 ≥1440 宽；无法提供第 N 项请说明，我按可得画面降级。
```

### 边界

- 用户供图可作 `🟢`（真实画面），但**必须写清来源**："证据：用户提供截图（2026-11-12）"
- 用户也不提供 → 落到 `C` 档（PM L0），**体验类结论强制 🔴**，报告头声明"未看到实际渲染"
- ❌ 禁止用代码里有 `loading` 分支这类静态信号冒充画面证据（属 `🟡`）

---

## 三个示例的共同点

| 环节 | 共同做法 |
|---|---|
| 探测 | 一次性三条命令，允许全失败，**不装东西** |
| 声明 | 报告头一行写清 后端 / 平台 / 档位 |
| 降级 | 每级都说"能做什么 + 证据上限"，不跳级 |
| 产物 | 统一文件名 + `meta.json`，下游不感知后端 |
