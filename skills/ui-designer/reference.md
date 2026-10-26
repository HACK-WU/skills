# UI 设计师参考规范库

本文件是 ui-designer 的详细参考：布局模式、ASCII 布局图规范、栅格、配色、字体、token、响应式断点、视觉参考库、方案文档模板与 HTML demo 规范。仅当需要具体规格时读取。

---

## 布局模式库

按页面类型选型，一页可组合多种：

| 模式 | 特征 | 适用 | ASCII 示意 |
|------|------|------|-----------|
| **单列居中** | 内容居中单列，最大宽度约束 | 登录、注册、落地页、表单 | `┌───卡片───┐` 上下留白 |
| **双栏** | 左右两栏（主 + 侧），侧栏可收 | 内容页、个人中心 | 主 8 列 + 侧 4 列 |
| **侧边栏导航** | 固定/可折叠侧栏 + 主内容 | 管理后台、SaaS 控制台 | 侧栏 200-240px + 主内容 |
| **卡片网格** | 等宽卡片网格，响应式列数 | 列表、商品、文件、任务 | `[卡][卡][卡]` → 移动端 1 列 |
| **master-detail** | 左列表 + 右详情，联动手动 | 邮件、消息、编辑场景 | 左 1/3 列表 + 右 2/3 详情 |
| **仪表盘** | 顶栏 + 图表卡片网格 + 指标 | 数据看板、监控 | 指标行 + 图表区 + 明细表 |
| **向导分步** | 步骤条 + 单步表单 | 注册流程、配置向导 | Step1→Step2→Step3 |
| **弹层/抽屉** | 覆盖层承载次要任务 | 编辑、筛选、确认 | 遮罩 + 居中弹窗 / 右侧抽屉 |

**选择建议**：
- 信息密集（后台、看板）→ 侧边栏导航 + 卡片网格
- 单一任务（登录、下单）→ 单列居中，减少干扰
- 需要对比/联动（列表详情）→ master-detail
- 不确定时默认：内容型单列 + 栅格；后台侧边栏

---

## ASCII 布局图规范

ASCII 布局图是**布局定稿物**，也是进入 HTML demo 的**前置闸门**：demo 将实现的每个页面（含关键状态视图，如弹窗 / 抽屉）各一张，经用户确认后才可编写 demo。绘制规范以 `ui-to-ascii` 为准：

- **字符集**：外框与分区用 `┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼ ─ │`；组件内文字直接写组件名 / 占位文案
- **宽度**：整体 ≤80 字符（复杂大图可放宽到 ~100）
- **中文全角对齐**：1 汉字 ≈ 2 西文字符宽；右框线对不齐时优先在文字右侧补空格
- **组件占位符**：输入框 `[__________]`、按钮 `[ 登录 ]`、复选 `[x]` / `[ ]`、图标 `[img]` / `(●)`、图片 `[图]`
- **编号锚点**：需要说明的元素旁挂 `①②③`，图下方用编号列表说明（间距 / 交互 / 状态等）
- **复杂度降级**：单屏组件过多（密集 dashboard 等）→ 画"整体区域骨架图 + 各区域局部放大图"，同一套锚点串联
- **只画能确认的结构**：拿不准的位置写 `[待确认]`，不臆造

**绘制方式**：

| 情形 | 做法 |
|------|------|
| 常规页面（单区域 / 浅嵌套） | 按上述规范内联绘制 |
| 结构复杂（多区域嵌套 / 多屏跳转 / 单图放不下） | `use_skill("ui-to-ascii")` 描述生成模式（直接输出到对话，不单独存档；定稿版仍收入方案文档 §2） |
| 需独立存档 ASCII 图（非方案文档内嵌）；或用户直接提供设计稿 / 截图要求转换 | `use_skill("ui-to-ascii")` 图转存模式，落 `.ui-ascii/{slug}.md` |

**定稿流程**：绘制 → 附在阶段 2 输出中请用户确认 → 定稿版收入方案文档 §2 → 才可进入 demo（SKILL.md 阶段 6 前置闸门）。

---

## 栅格系统

- **基准**：12 列栅格，`gutter`（列间距）取间距 token 中的 16px 或 24px
- **用法**：区块跨列数说明占比（如 主内容 span=8 / 侧栏 span=4，中间留 1 列 gutter）
- **移动端**：断点 < 768px 时全部降为单列（span=12），或按 4 列细分

---

## 配色体系

### 色板结构（每色给出具体 hex）

| 类别 | token 命名 | 说明 |
|------|-----------|------|
| 主色 | `--color-primary` | 主操作按钮、链接、选中态、焦点 |
| 辅助色 | `--color-secondary` | 次要操作、辅助信息 |
| 成功 | `--color-success` | 成功反馈、正向状态 |
| 警告 | `--color-warning` | 警告、需要注意 |
| 错误 | `--color-error` | 错误反馈、危险操作 |
| 中性文本 | `--color-text / --color-text-secondary / --color-text-disabled` | 正文 / 次要 / 禁用 |
| 中性背景 | `--color-bg / --color-bg-elevated / --color-bg-hover` | 页面 / 浮层 / 悬停 |
| 边框 | `--color-border / --color-border-light` | 分割 / 弱分割 |

### 常用起点色板（可直接取用）

```css
:root {
  --color-primary: #1677ff;          /* 悬停 #0958d9，点击 #003eb3 */
  --color-success: #52c41a;
  --color-warning: #faad14;
  --color-error:   #ff4d4f;
  --color-text:             #1f1f1f;
  --color-text-secondary:   #595959;
  --color-text-disabled:    #bfbfbf;
  --color-bg:               #ffffff;
  --color-bg-page:          #f5f5f5;
  --color-bg-hover:         #f0f0f0;
  --color-border:           #d9d9d9;
}
```

### 设计约束

- **对比度**：正文与背景对比度 ≥ 4.5:1（WCAG AA）；大号文字 ≥ 3:1
- **功能色语义**：成功/警告/错误只用于对应语义，不混用
- **主色克制**：主色只用于主操作与选中态，不铺满页面（可配 10%-20% 的浅色主色背景层）
- **暗色模式**（按需）：背景降级为深色系（如 `#141414` / `#1f1f1f`），文字提亮为 `#e6e6e6`，主色可提亮一档；用 CSS 变量覆盖实现

---

## 字体系统

- **字体栈**：`-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif`
- **等宽**（代码/数字）：`ui-monospace, SFMono-Regular, "Cascadia Mono", Consolas, monospace`

### 字号阶梯

| token | 值 | 用途 |
|-------|-----|------|
| `--font-xs` | 12px | 辅助说明、表尾 |
| `--font-sm` | 14px | 正文次要、表单标签 |
| `--font-md` | 16px | 正文（默认） |
| `--font-lg` | 20px | 卡片标题 |
| `--font-xl` | 24px | 页面标题 |
| `--font-xxl` | 32px | 数字指标、大标题 |

- **行高**：正文 1.5-1.7，标题 1.3-1.4
- **字重**：常规 400、中 500（标题）、粗 600（强调）；避免 700+ 大范围使用

---

## 间距 / 圆角 / 阴影 token

```css
:root {
  /* 间距（4px 基准） */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;

  /* 圆角 */
  --radius-sm: 4px;   /* 输入框、小控件 */
  --radius-md: 6px;   /* 按钮、卡片 */
  --radius-lg: 8px;   /* 弹窗 */
  --radius-xl: 12px;  /* 大卡片、抽屉 */

  /* 阴影 */
  --shadow-sm: 0 1px 2px rgba(0,0,0,.06);
  --shadow-md: 0 4px 12px rgba(0,0,0,.1);
  --shadow-lg: 0 12px 32px rgba(0,0,0,.16);
}
```

---

## 响应式断点

| 断点 | 视口宽度 | 布局策略 |
|------|----------|----------|
| `sm` | < 576px | 手机：单列、导航收抽屉、表格转卡片 |
| `md` | 576-768px | 平板：双栏收紧、卡片 2 列 |
| `lg` | 768-1200px | 桌面：标准布局（本方案默认基准） |
| `xl` | > 1200px | 宽屏：主内容加最大宽度约束（如 1200px 居中） |

**移动优先写法**：先写 sm 样式，用 `min-width` 媒体查询逐级增强。

---

## 方案文档模板

```markdown
# UI 设计方案：{功能名称}

> 输入来源：交互设计文档 / 需求描述 · 状态：草案 · 日期：{日期}

## 1. 概述
（页面清单、目标设备、技术栈约束）

## 2. 页面结构（ASCII 布局图 · 定稿件）
### 2.1 {页面名}
（ASCII 布局图 + 布局模式 + 栅格占比 + 响应式策略；状态视图如弹窗 / 抽屉各附图）

## 3. 组件状态
| 组件 | 默认 | 悬停 | 聚焦 | 禁用 | 加载 | 错误 |
|------|------|------|------|------|------|------|

## 4. 视觉 token
（配色/字体/间距/圆角/阴影 全部 token 表）

## 5. 响应式规则
（各断点行为）

## 6. 待确认事项
| 编号 | 事项 | 影响 | 状态 |
|------|------|------|------|
```

---

## HTML demo 规范

### 硬性约束

1. **布局已定稿**：对应页面的 ASCII 布局图已获确认（SKILL.md 阶段 6 前置闸门），demo 结构与定稿图一致
2. **单文件**：一个 `index.html` 内联 CSS 与 JS；页面多时按 `index.html` + 子页面，仍零构建
3. **零依赖**：不引入框架、CDN 库、构建工具、包管理；字体用系统字体栈。**豁免**：用户明确指定框架（如 React/Vue）时，遵循用户约束——允许单文件 CDN 引入或用户提供的构建环境（与 SKILL.md 阶段 6 一致）
4. **CSS 变量承载 token**：`:root` 中定义，变量名与方案文档 token 完全一致
5. **语义化标签**：`header / nav / main / aside / footer / section / form / button`
6. **移动优先**：sm 基准 + `min-width` 媒体查询增强
7. **交互最小化**：仅演示关键交互（表单校验、Tab、弹窗），用原生 JS；不接真实后端，数据用 mock

### 骨架模板

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{页面名}</title>
<style>
  :root {
    /* 与方案文档 token 一一对应 */
    --color-primary: #1677ff;
    --color-error: #ff4d4f;
    --color-text: #1f1f1f;
    --color-bg: #ffffff;
    --color-border: #d9d9d9;
    --font-md: 16px;
    --space-2: 8px;
    --space-4: 16px;
    --radius-md: 6px;
    --shadow-md: 0 4px 12px rgba(0,0,0,.1);
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         color: var(--color-text); background: var(--color-bg); font-size: var(--font-md); }
  /* 移动优先布局 + 媒体查询增强 */
</style>
</head>
<body>
  <header>…</header>
  <main>…</main>
  <script>
    // 仅演示用原生 JS，最小交互
  </script>
</body>
</html>
```

### 状态演示要求

- **必达**：默认态
- **关键页面**：错误态（如表单校验失败）、空态（空列表）至少演示一种
- **可交互控件**：悬停态在 CSS 里定义（`:hover`）；禁用/加载态在 demo 中可切换演示

### 可访问性基础（demo 必带）

- 表单控件配 `<label>`（或用 `aria-label`），不要裸 `placeholder` 当标签
- 图片/图标配 `alt` 或 `aria-hidden="true"`
- 可点击元素用 `<button>` / `<a>`（语义化），支持键盘 Tab 聚焦与 Enter 触发
- 对比度满足 reference.md「配色体系」的 WCAG AA 要求

---

## 风格工具库

ui-designer 可加载外部风格工具库提升设计品味，避免模板化输出。支持多来源（可同时安装）：

| 来源 | 仓库 | 内容 |
|------|------|------|
| **主来源** | [taste-skill](https://github.com/Leonxlnx/taste-skill) | 13 个设计风格指令 skill（反套路默认技能 + 极简/高端/粗野等风格 + 图像生成） |
| **补充来源** | [anthropics/skills](https://github.com/anthropics/skills)（Anthropic 官方） | 前端设计方法论 `frontend-design` + 主题工具 `theme-factory` |

**工具库默认必需**：目录固定为**当前工作区根目录** `ui-tools/`（即 `{cwd}/ui-tools/skills/`）；缺失时默认必须先安装（见 SKILL.md 阶段 0.4），不得降级跳过。**已有 `ui-tools/design-reference/` 且本次不探索新风格时可跳过安装/加载**，参考库已提供项目基线。

### 安装（当前工作区根目录）

在**当前工作区根目录**（`{cwd}`）创建 `ui-tools/` 并安装（依赖 Node.js + npx）：

```bash
mkdir -p ui-tools && cd ui-tools
# 主来源：taste-skill 全部 13 个
npx skills add https://github.com/Leonxlnx/taste-skill --agent openclaw -y
# 补充来源：anthropics/skills 按需选装（frontend-design / theme-factory）
npx skills add https://github.com/anthropics/skills --skill frontend-design theme-factory --agent openclaw -y
```

### 场景路由表

> 路由表是**推荐起点**，实际设计时以 `ui-tools/skills/` 中真实存在的 skill 为准（工具库升级/新增 skill 时 AI 应自适应扩展映射，勿局限于下表）。

| 场景 | 加载风格 skill（ui-tools/skills/{name}/SKILL.md） | 说明 |
|------|--------------------------------------------------|------|
| 新 landing / 作品集 / 通用页面 | `design-taste-frontend` | 默认反套路技能（v2）：简报推理 + 设计系统映射 |
| 需要"有辨识度的设计方法论"（任何新 UI / 重设计） | `frontend-design` | Anthropic 官方：主体驱动、排版承载个性、结构即信息（taste-skill 的互补方法论） |
| 需要即用主题（颜色 + 字体对） | `theme-factory` | 10 个预设主题可直接套用，也可动态生成新主题（展示 PDF 依赖视觉环境，受限时用主题色板数据） |
| 用户指定"极简 / 编辑风" | `minimalist-ui` | Notion/Linear 风：暖单色、bento 网格、无重阴影 |
| 用户指定"高端 / 昂贵感" | `high-end-visual-design` | 高级代理风：留白、精致字体、弹簧动效 |
| 用户指定"粗野 / 工业风" | `industrial-brutalist-ui` | 瑞士字体、强对比、数据密集、模拟损耗 |
| 改造现有项目 UI | `redesign-existing-projects` | 先审计再修复布局/间距/层级，不破坏功能 |
| 需要设计稿图像参考 | `imagegen-frontend-web` / `imagegen-frontend-mobile` | 每 section 一图 / 移动端流程（只出图，不写码） |
| 品牌规范 / 色板 / Logo | `brandkit` | 品牌套件板（只出图） |
| 图像 → 代码工作流 | `image-to-code` | 先生成参考图再实现代码 |
| 输出频繁截断 | `full-output-enforcement` | 防半成品兜底（非设计风格） |
| Codex / GPT 环境 | `gpt-taste` | Codex 专用严格变体（高布局方差 + GSAP） |
| Google Stitch 生态 | `stitch-design-taste` | Stitch 规范，产出 DESIGN.md |

### 加载与兜底机制

1. **检测**：阶段 0.4 检查当前工作区 `ui-tools/skills/` 是否存在；**默认缺失必须安装**（已有参考库且不探索新风格时可跳过）
2. **选择**：阶段 4.0 按场景路由表匹配（用户明确偏好优先于路由默认）
3. **加载**：读取对应 `SKILL.md` 作为设计指令，融合进 token / 排版 / 动效 / 间距决策
4. **兜底**：仅场景无匹配时使用本文件内置的配色体系 / token / 布局库（默认工具库存在是前提；已有参考库且不探索新风格时可跳过）
5. **边界**：风格指令只影响视觉呈现，不改变页面结构（阶段 1-2）与交互流程（来自交互文档）

---

## 视觉参考库

参考库是**项目视觉基线**，不是生产组件库：只提供视觉参考、组件状态与规格；页面实现必须按项目技术栈重实现，禁止整段复制参考 HTML/CSS。

**路径与边界**：

- 固定 `{project}/ui-tools/design-reference/`；
- 不得放入 `.claude/skills`、`.codex/skills`、`.qoder/skills`、`.agents/skills`、`.cursor/skills`、仓库根 `skills/`；
- 参考库内不得出现 `SKILL.md`。

### 目录结构

```text
ui-tools/design-reference/
├── INDEX.md                 # 组件清单唯一真源
├── meta.json                # 全局元数据（版本/来源/日期）
├── tokens.css               # token 唯一真源
├── components/
│   ├── button.html          # 组件参考（所有变体/状态）
│   ├── button.spec.md       # 组件规格
│   └── ...
├── preview/
│   └── index.html           # 组件画廊（375/768/1440）
└── screenshots/             # 可选基准截图
```

### 建库模式（A/B/C）

| 模式 | 特征 | 种子来源 | 关键动作 |
|---|---|---|---|
| **A. Greenfield** | 无前端页面、无设计系统 | 用户品牌 / taste-skill 风格方向 → ui-ux-pro-max | 先定 1 个风格方向，再生成 token |
| **B. Brownfield-formal** | 已有 tokens / Tailwind config / 组件库 / 品牌规范 | 项目现有 token | 镜像现有 token，参考库只做视觉镜像 |
| **C. Brownfield-informal** | 已有页面，但无正式 token/设计系统 | 现有页面提取基线 | 选 2–3 个代表页面，提取色板/字阶/间距/状态；不发明新风格 |

**C 模式提取要点**：

- 选一个列表、一个表单/详情、一个高流量页面；
- 提取色板、字号、间距、圆角、阴影、组件状态；
- 记录 `meta.json.baselineSources`；
- 发现不一致时提议归一化，用户确认后再做；
- 生成 v0.x（视觉镜像），确认后升 1.0.0。

**A 模式风格方向**：

- 优先级：用户品牌规范 > taste-skill 风格方向 > ui-ux-pro-max 行业默认；
- 先定 `styleDirection`（如 calm editorial / bold brutalist），再生成 token；
- 不让行业默认直接决定风格。

### meta.json 模板

```json
{
  "schemaVersion": 1,
  "project": "my-app",
  "version": "1.0.0",
  "source": "brownfield-extraction | project-design-system | ui-ux-pro-max@x.y.z",
  "baselineSources": ["src/pages/orders/list.tsx"],
  "styleDirection": "inherit-existing | calm editorial | bold brutalist",
  "createdAt": "2026-10-26T10:00:00Z",
  "updatedAt": "2026-10-26T10:00:00Z",
  "tokens": "tokens.css",
  "preview": "preview/index.html",
  "notes": "3–5 个核心组件；主色按现有页面提取"
}
```

### INDEX.md 模板

```markdown
# 视觉参考库索引

> 基线版本：1.0.0 ｜ 来源：brownfield-extraction（src/pages/orders/list.tsx） ｜ 更新：2026-10-26

| 组件 | 用途 | 变体 | 状态 | 依赖 token | 参考文件 | 规格 | 使用页面 | 版本 |
|---|---|---|---|---|---|---|---|---|
| button | 主操作/次操作 | primary, secondary | default, hover, focus, disabled, loading | --color-primary, --radius-md | components/button.html | components/button.spec.md | docs/ui-design/orders.md | 1.0.0 |
```

规则：新增/删除组件、视觉变更、使用页面变化都必须更新 INDEX；INDEX 引用的文件必须存在。

### tokens.css 规则

- 颜色、字号、字重、行高、间距、圆角、阴影、动效时长全部用 CSS 变量；
- 组件 HTML 只使用 `var(--token)`，不得写死 hex / 字号 / 间距；
- 项目已有 Tailwind / design tokens 时，参考库映射项目 token，不另起一套；
- 支持 light/dark（按项目需要）。

### 组件 HTML 规则

1. 静态、零构建、零外部依赖（不引 CDN / 框架 / 网络）；
2. 只引用 `../tokens.css`；
3. 展示所有变体与适用状态（default / hover / focus / disabled / loading / error）；
4. 语义化 HTML + a11y 属性；
5. 不使用 JS（或仅极简状态切换）；
6. 根节点标记 `data-ref-component` / `data-ref-version`；
7. 同组件所有变体放在同一文件；
8. 不含真实业务数据 / 隐私信息。

### 组件 spec 模板

```markdown
# Button

## 用途

## Anatomy
- root / label / loading indicator

## Variants
- primary / secondary

## States
- default / hover / focus-visible / disabled / loading

## Tokens
- --color-primary, --color-on-primary, --radius-md, --space-sm

## Sizing
- md：padding var(--space-sm) var(--space-md)；最小点击区域 44×44

## Responsive
- 移动端可全宽；桌面内联

## Accessibility
- 原生 button；focus-visible 可见 ring；loading 用 aria-busy

## Do / Don't
- Do: 用语义 button
- Don't: 用 div 模拟按钮

## 实现提示（栈无关）
- 项目已有 Button 时按其主题 token 调整，不复制参考 HTML

## 变更记录
- 1.0.0 初始
```

### preview 与截图

- `preview/index.html` 汇总所有组件，至少展示 375 / 768 / 1440；
- 截图可选，存 `screenshots/`；无法截图时设计文档标 `[未截图]`，不得宣称已验证；
- 参考库 v1.0 必须过自检 gate：对比度 4.5:1（非文本 3:1）、focus-visible、状态齐全、无破版、无硬编码 token、每个组件有 spec、meta 记录来源。

### 外部设计知识源（ui-ux-pro-max）

只作为建库种子，不作为页面实现依赖。

安装（已实现 `--no-record`，目标不写 `targets.list`）：

```bash
bash scripts/skill-install.sh install -n ui-ux-pro-max \
  --repo nextlevelbuilder/ui-ux-pro-max-skill \
  --no-record -t <project>/ui-tools/vendor
```

实际落点：`<project>/ui-tools/vendor/skills/ui-ux-pro-max/`。

使用方项目没有本仓库安装器时：

```bash
mkdir -p <project>/ui-tools/vendor && cd <project>/ui-tools/vendor
npx skills add https://github.com/nextlevelbuilder/ui-ux-pro-max-skill \
  --skill ui-ux-pro-max --agent openclaw -y
```

调用桥（统一入口，不散落调用 search.py）：

```bash
python3 <ui-designer skill 目录>/scripts/ui_ux_pro_max.py probe --project-root .
python3 <ui-designer skill 目录>/scripts/ui_ux_pro_max.py generate "订单列表 后台" --project "Orders" --project-root .
python3 <ui-designer skill 目录>/scripts/ui_ux_pro_max.py domain --domain ux --query "error summary validation" --project-root .
python3 <ui-designer skill 目录>/scripts/ui_ux_pro_max.py stack --stack react --query "form validation" --project-root .
```

> Windows 下用 `python` 替代 `python3`。

- 仅建库时调用 `generate` 一次；页面实现阶段不再调用；
- 未安装 / Python 不可用：用项目设计系统或内置 token 建库，标 `⚠️ 外部设计知识源不可用`；
- 不修改其本体；只读 data/scripts；核心 skill 不需要 API Key。

### 同步闸门

**改前判断**，命中以下任一即走闸门：

- 修改 `tokens.css`；
- 修改组件公共 class / 结构 / 状态 / `spec.md`；
- 修改会影响多个页面的公共组件；
- 用户要求把新样式沉淀为组件。

| 选项 | 行为 | 版本 |
|---|---|---|
| A. 只改本页 | 页面局部覆盖 token；不 fork 结构；记录偏离 | 不变 |
| B. 更新参考库 | 更新 HTML + spec + INDEX；列出受影响页面；不改旧页面 | patch/minor |
| C. 更新参考库并同步使用页 | 同 B，并逐页检查/更新使用页 | minor/major |

更新前确认 git/备份可回退；更新后重新截图检查受影响页面。单页一次性微调、页面级布局差异、用户明确“只改这一页”不走闸门。

### 旧页面轻量记录

参考库合规只覆盖新建/本次修改/已登记页面；未触碰旧页面不判偏离。旧页面首次修改时补一条记录（设计文档「UI 参考库」节或页面旁 `reference-usage`）：

```markdown
## UI 参考库
- 参考库：ui-tools/design-reference/ ｜ 版本：1.0.0
- 使用组件：button 1.0.0 / input 1.0.0
- 本页偏离：无 / {具体偏离与原因}
- 未入库组件：无
```

### 常见坑

- 把参考库放进 IDE skill 扫描目录，或在参考库里放 `SKILL.md`；
- 把参考 HTML 整段复制进页面（不是复用，是复制粘贴）；
- 项目已有组件库却重写同名组件；
- 页面里写死 hex / 字号 / 间距，绕过 tokens.css；
- 每页都调用 ui-ux-pro-max 重新生成（应只在建库时用一次）；
- 未经确认改参考库，导致其他页面基线漂移；
- 用一张 1440 截图代替 375/768/1440 三档检查。

---

## 体验计划与体验报告

设计/demo 交付后用于体验验证与追溯的两种文档（对应 SKILL.md 阶段 6.5）。**双文档均须记录对应代码 commit 信息**，保证可回溯"哪个版本的设计/demo 对应哪次体验"。

### commit 记录规范

| 项 | 获取方式 | 说明 |
|----|----------|------|
| commit hash | `git rev-parse --short HEAD` | 短 hash 即可定位版本 |
| commit message | `git log -1 --format=%s` | 描述性提交信息 |
| 未提交状态 | — | 标注 `[工作区未提交]` + 变更文件清单，**不编造 commit** |

记录位置：文档顶部「关联 commit」字段，格式 `{hash} {message}`。

### 体验计划模板

```markdown
# 体验计划：{功能名称}

> 关联 commit：{hash} {message} · 日期：{日期}

## 1. 体验目标
[本次体验要验证什么，一句话]

## 2. 体验项清单
| # | 体验项 | 来源（交互文档场景） | 体验方法 | 验收标准 |
|---|--------|---------------------|----------|----------|
| E-01 | 登录流程 | S-01 | 浏览器走查 | 输入正确账号密码可登录 |
| E-02 | 移动端适配 | S-01 | 375px 视口 | 卡片满宽、无横向滚动 |

## 3. 体验环境
[浏览器 / 设备 / 视口 / 工具库版本等]
```

### 体验报告模板

```markdown
# 体验报告：{功能名称}

> 关联 commit：{hash} {message} · 体验日期：{日期}

## 1. 体验结果
| # | 体验项 | 结果 | 证据 / 描述 |
|---|--------|------|-------------|
| E-01 | 登录流程 | ✅ 通过 | 输入正确账号密码成功登录 |
| E-02 | 移动端适配 | ⚠️ 存疑 | 375px 下按钮略溢出，待确认 |

## 2. 发现问题
| # | 问题 | 严重度 | 建议 | 关联体验项 |
|---|------|--------|------|-----------|
| 1 | 按钮在 375px 溢出 | 中 | 按钮改用 min-width + 弹性宽度 | E-02 |

## 3. 结论
[通过 / 有条件通过 / 不通过；不通过时列修复方向与对应阶段，修复后更新报告并标注新 commit]
```
