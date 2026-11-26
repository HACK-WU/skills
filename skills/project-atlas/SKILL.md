---
name: project-atlas
description: 把项目的架构、核心链路、跨服务闭环装配成一个可切换视图的离线 HTML 图集：一页可挂多图，节点可点开源码或外部契约，衔接关系（data_id 这类标识符）单列成表。触发："项目知识地图"、"架构图集"、"模块数据流"、"跨服务闭环"、"衔接键"、"atlas"。
---

# 项目知识地图（Project Atlas）

> 装配者 + 策划者。**不画图**（图源交 archify），负责选视图、装成单文件、把节点接到代码。

## 概述

**目的**：补上"看懂一个系统"这个入口页的空白——现有产出全是散件（`module-teach` 是长文、`expert-team` 是双层文档、`archify` 是一图一 HTML），没有人给出"先建立整体认知，再去查细节"的**单一入口**。本 skill 把项目的架构、核心链路、后台进程、配置、指定模块的数据流，装配成**一个 HTML 图集**，并在节点上挂源码位置。

**功能**：
- **视图策划**：按项目实际结构决定出哪几张图、分几个分类、每张图回答什么问题（先出计划，用户确认后才生成）
- **配置驱动渲染**：一份 `atlas.config.json` 管标题 / 大纲 / 层级 / 页面清单 / 每页图源与代码映射；框架在运行时读取并渲染，**换 JSON 刷新即生效，不改一行代码**
- **内置示例兜底**：没有配置时框架渲染自带示例（打开即有效果页），配置就位后自动切换成真实图集
- **导出 Markdown**：页面顶部「导出 ↓」或 `export_markdown.py`，把图集导成 **Markdown 目录包**（zip，按大纲建目录，每页一个 `.md` + `images/*.svg`）。ZIP 由前端自写（`CompressionStream` + 手写文件头），不引第三方库；纯前端、无需后端与重跑构建
- **节点级代码关联**：点击节点打开右侧抽屉，显示 `路径:起-止行` + commit + 一句 why + 行号对齐的高亮代码
- **一页多图**：一页可挂多张图（`pages[].figures[]`），每图独立 fig-bar、解读与失败态；同一节点在多图间共用一份代码映射，抽屉里提示「也出现在哪几张图」。不写 `figures` 即退回单图，老配置零改动
- **分批并行**：大项目（视图 ≥6 且模块 ≥3）先并行摸底、样板定风格后并行出图；三份契约（大纲 / 共享组件词典 / 分片计划）经确认才动手，避免单 agent 从头蒙头做到底
- **外部服务第三态**：`external: true` 的节点没有源码，抽屉显示**归属 / 契约 / 回程落点**；站点级 `externals` 字典让同一份契约只写一处；可点率分母排除它们
- **衔接关系**：`links[]` 声明节点之间传什么、靠什么标识符对上（`data_id` 这类）。标识符单列成表（形态 / 持久化落点 / 基数），事件次之，状态型返回折叠成一行不展示——**闭环的判据不只是"流回去了"，还要能说清"两头靠什么对上"**
- **片段采集与校验**：脚本从源码抽取片段，双向校验"节点 ↔ 片段"（零孤儿、零悬空）
- **字体去重**：archify 每张 SVG 内嵌 3 份 base64 字体（占文件 27%），装配时提到壳层去重，实测单图 330 KB → 235 KB
- **范围参数化**：全项目 / 指定模块（指定模块时视图集合自动收窄）
- **资产复用**：优先读 `.fe-index`（模块边界/依赖/表）、`.module-experts`（C0 架构）、gitnexus（调用链），不重复全仓扫描

**使用场景**：
- 用户说"给我出个项目知识地图""做一个架构图集""把整个项目的架构画成一个网页"
- 用户说"把这个模块的数据流画出来""看某个模块的架构"
- 新人接手 / 交付前要一份"不看文档也能懂"的入口页
- 已有 `archify` 产物散落多份，需要一个索引页把它们收成一个
- 与相邻 skill 的分流：要**读某个模块的实现**用 `module-teach`；要**出单张图**直接找 `archify`；要**导出 SVG 文件**用 `archify-svg-export`；本 skill 只做"多视图 + 单文件 + 接代码"

## 定位

```
archify（出图） ──┐
archify-svg-export（导 SVG） ──┼──▶ project-atlas（本 skill：策划 + 装配 + 接代码）──▶ atlas.config.json + views/
.fe-index / .module-experts（模块与架构事实） ──┘
```

- **输入**：项目路径（或指定模块路径）+ 可选资产（索引 / 专家包 / 已有 archify 产物）
- **输出**：一个图集目录 —— `site.json` + `nav/<分类>/<页面>.json`（目录树；也可用单文件 `atlas.config.json`）+ `views/*.svg` + `snippets.json`；框架 `framework/index.html` 放同目录即可运行。`pack_atlas.py` 导出**单文件分发版**
- **边界**：不画图、不解析 Mermaid、不做在线分享、不做 WYSIWYG 编辑
- **产物不入 git**：配置目录默认加 `.gitignore`（图集是派生物，可再生）

## 核心原则

1. **图源不自研**：视图由 `archify` 生成（JSON IR → deliver → SVG）；`archify` 不可用时降级复用已有 SVG/HTML，仍不可用才手写 SVG，并声明降级
2. **框架是资产，配置是唯一变量**：`framework/index.html` 固定（样式 + 渲染逻辑 + 内置示例），AI 只写 `atlas.config.json`。**禁止每次现场重写框架**，也**不要为加一页去改脚本**——框架一旦漂移，交互约束全部失效
3. **一份配置管一个图集**：站点结构与每页内容都收在 `atlas.config.json`；**禁止一图一 HTML**（那是 archify 的产物形态）
4. **视图预算是硬约束，按图不按页**：去重后每视图约 235 KB（实测），故默认 6–8 张图、单文件目标 ≤3 MB（≈12 张）、硬上限 10 MB。**一页多图不占页数预算但占图数预算**；多图的唯一理由是"必须同屏对照"，否则拆页。超限先减图，不许"先做出来再说"
5. **所有节点都可点，且尽量都有代码**：模板给每个 `data-node-id` 绑点击，有 `code[]` 的看代码块，没有的显示"该节点无直接源码 + 相关文件"。**可点率目标 ≥80%**（次要/外部节点可为 concept，但点开必须有反馈，不能死节点）——覆盖率低于 50% 时 `check_atlas.py` 会告警
6. **抽屉由四种操作关闭**：`×` / `ESC` / 切换视图 / **点面板以外的任意处**（含图空白、侧栏、正文）。点节点本身不关闭，直接在节点间切换
7. **窄屏走底部抽屉**：视口 <1000px 时抽屉改为底部半屏，不遮挡图体
8. **节点必须可溯源**：每个节点要么能指到 `file:line`，要么在 `atlas.config.json` 的 `pages` 里显式标 `concept: true`（概念节点，无代码）。**编造出源码里不存在的组件 = 本次产物作废**
9. **片段是生成时快照**：面板必须显示 commit 与"生成时快照，不代表 HEAD"，且 `why` 不说空话
10. **视图必配解读**：每个视图至少 3 条"怎么读这张图"，只画不解释的图等于没画
11. **先收敛契约再动手**：大纲（出哪几张图 / 每图问题 / 片段范围）+ 共享组件词典 + 分片计划，三件齐了才交用户确认（唯一确认点）；确认后按计划串行或并行执行
12. **失败不留半成品**：导出先写临时文件，校验通过再原子替换；**有阻断项就不写产物**（"导出失败但留下旧版/空壳"比直接失败更危险，调用方会以为成功）。运行时每张图独立失败态：一张图加载失败只在该图位置报图源路径与原因，不拖垮同页其他图
13. **外部只到契约粒度**：跨出项目边界的部分只画"谁、什么契约、回程落在本页哪个节点"，不画外部服务的内部多跳——外部信息没有唯一真源，画得越细腐坏得越快。外部节点缺 `owner` / `contract` 即视为编造，这比编造内部组件更危险（内部有 `data-node-id` 可对，外部静态校验抓不到）
14. **并行前先收敛契约**：只有阶段 0（摸底）与阶段 2（出图）能并行，且并行前必须有**共享组件词典**；子 agent 只写自己那页、节点 id 只从词典取、不许动共享文件。小项目（视图 <6 或模块 <3）**不并行**——协调成本大于收益，单 agent 更快

## 工作流总览

```
阶段 0  前置探测（+ 大项目并行摸底）
        能力与资产：archify / 导出能力 / 索引资产 / 已有产物 / 体积基线
        并行摸底：视图 ≥6 且模块 ≥3 时，N 个子 agent 各摸一个模块 → 「模块事实卡」
        ────────────────────────────────────────────────────────
阶段 1  契约收敛（唯一确认点）
        ① 大纲：出哪几页 / 改哪几页 / 不做哪些 + 理由
        ② 共享组件词典：节点 id ↔ 组件（跨图关联只认这一份）
        ③ 分片计划：哪些并行、几个 agent、谁是样板页
        ↓ 用户确认后才动手
        ────────────────────────────────────────────────────────
阶段 2  出图：样板先行（1 页出完 → 定风格基准）→ 并行剩余（每页一个子 agent，共用词典）
阶段 3  片段采集：scripts/collect_snippets.py → snippets.json + 覆盖率报告（脚本，串行）
阶段 4  运行：把框架放到配置同目录 → 起本地服务即实时渲染（改配置刷新即可）；需要发给别人时再导出单文件
阶段 5  校验：scripts/check_atlas.py（三方对齐 / 图源 / 片段 / 体积 / 导出文件）
阶段 6  验收走查：浏览器实测（内置示例态 + 真实配置态 + 三档视口 + 五类交互）
阶段 7  更新：改配置即可；图源或片段变更后重跑阶段 3–5；刷新 commit 基线
阶段 8  分发与导出（可选）：HTML 单文件发人（deploy.md）/ Markdown 目录包进文档库（export-md.md）
```

> **为什么只有阶段 0 和阶段 2 能并行**：这两段是"读多写少"的独立产出——摸底只读代码，出图每页一个文件。阶段 3–6 全部依赖前置产物（采集要配置齐、校验要图源在、走查要能打开），拆开只会制造等待。**并行前必须有契约**（阶段 1 的词典），否则各 agent 自己起 id，合并即失配。

## 阶段 0：前置探测

逐项探测，**结果写进阶段 1 的计划**，不静默跳过：

| 项 | 探测方式 | 缺失时 |
|---|---|---|
| archify | **当前可用 skill 列表里有 `archify`**（`use_skill("archify")` 能加载）。**不探测安装路径**——skill 可装在任意位置，路径只在真要调 CLI 时才需要，由 archify 自己的文档给出 | 降级：复用已有 SVG / 手写 SVG，并声明（不自动安装） |
| SVG 导出能力 | **可用 skill 列表里有 `archify-svg-export`** + 有 Chrome/Chromium | 用 archify 的多主题导出；再不行用 HTML 内嵌 iframe（体积翻倍，需重新核算预算） |
| 模块与依赖事实 | `.fe-index/`（`use_skill("index-lookup")`）、`.module-experts/`、gitnexus MCP | 直接读目录与入口文件自行摸底 |
| 已有产物 | 图集目录（`atlas.config.json` + `views/`）、项目内散落的 `*.architecture.html` / `*.svg` / archify `*.json` | 无则全量生成 |
| 体积基线 | 已有 SVG 单文件大小（含字体） | 原始 SVG 约 316 KB/图，装配去重后约 235 KB/图 |

> **前端项目注意**：图集描述的是"系统怎么跑"，不是"页面长什么样"。前端项目优先出组件树 / 请求链路 / 状态流，不出视觉走查（那是 `ui-designer` / `frontend-walkthrough`）。

### 并行摸底（大项目）

触发条件与 1.3 的并行判据相同（**视图 ≥6 且模块 ≥3**，否则串行）。每个子 agent 摸一个模块，回一张**事实卡**：

```jsonc
{
  "module": "导入管线",
  "entry": "src/lib/import.ts:48",
  "symbols": [{ "name": "importRun", "file": "src/lib/import.ts", "lines": [48, 62] }],
  "deps": ["chunker", "zvec", "fts"],
  "flows": [
    { "name": "一次导入", "steps": ["chunk", "embed", "zvec.upsert", "fts.index"],
      "flow_owner": "导入管线" }
  ],
  "risks": ["失败回滚边界不清"]
}
```

- 事实卡是**阶段 1 词典与大纲的原料**，也是后续出图 agent 的输入
- **跨模块链路按 `flow_owner` 归属**：agent 要显式写出"我认为这条链路由谁发起"。多份事实卡都认领同一条链路时，主 agent **按依赖方向裁决**（入口文件在上游的那个赢），而不是看谁先报
- 摸不到的（要跑起来才知道）标 `[需运行验证]`，**不猜**

## 阶段 1：契约收敛（唯一确认点）

三份产物：**大纲 + 共享组件词典 + 分片计划**。三件齐了才交用户确认。

> **"确认前不动手"的边界**：不动的是**产物**（`views/` / `nav/` / `atlas.config.json` / `snippets.json`）；计划物本身（大纲、词典、分片表）必须写出来给用户看，否则没法确认。

### 1.1 视图类型

每张图选一个 archify 图种，**默认四类分组**（可按项目裁剪）：

| 分类 | 典型视图 | archify 图种 | 回答什么问题 |
|---|---|---|---|
| 架构总览 | 运行时架构 | `architecture` | 这个系统由什么组成，谁和谁相连 |
| 核心链路 | 一次请求 / 搜索 / 导入 / 删除 | `sequence` / `workflow` | 一次操作到底经过哪些环节 |
| 后台进程 | 调度器、索引、备份 | `architecture` | 哪些东西在我没操作时也在跑 |
| 配置与环境 | 配置项地图 | `tree` | 想改行为该动哪一段 |
| 数据流转（按需） | 某模块的数据进出 | `dataflow` | 数据从哪来、到哪去、谁消费 |

**视图挑选判据**（不是越多越好）：
- 优先"**读者会反复问的问题**"，而不是"代码里有几个目录"
- 一个视图只回答一个问题；问题说不清就不出这张图
- **闭环判据**：这张图能不能读到"谁发起 → 谁处理 → 落到哪 → 谁读回来/怎么观测"？读不到就是单边视图——单边视图会给出错误的可用性直觉（"写进去了" ≠ "能查到"）
- 同一分类超过 3 张时，考虑合并或降到"指定模块"模式

### 1.2 共享组件词典

**并行 agent 之间的接口**。没有它，三个 agent 会把同一个组件叫成 `zvec` / `vec` / `vector-store`，合并后跨图关联全断。

```jsonc
{
  "daemon": { "label": "daemon 路由",   "kind": "code",     "file": "src/lib/mcp-http-api.ts" },
  "kb":     { "label": "kb/ 原始数据",  "kind": "resource", "pages": ["overview", "daemons"] },  // pages 由主 agent 合并后回填
  "zvec":   { "label": "zvec 向量索引", "kind": "concept" },
  "etl":    { "label": "数据平台 ETL",  "kind": "external", "owner": "数据平台团队" }
}
```

- **来源**：`.fe-index` 的模块名 + 并行摸底事实卡里出现 ≥2 次的组件名 + 用户已知术语
- **规则**：词典确认后，所有出图 agent **只能用其中的 id**；需要新组件先在事实卡里申请入典，由主 agent 统一加
- **粒度**：只收"会跨页出现"或"要挂代码/契约"的组件；某页内部的小步骤不进词典（否则词典本身膨胀成第二份配置）
- 落图集目录下的 `.atlas/dict.json`（与产物同处，随 `.atlas/.gitignore` 不入仓库），**不写进 `atlas.config.json`**（它是实现细节，不是图集配置）
- **词典只由主 agent 写**：出图 agent 只读、不自行添加或改名——多 agent 同写一份词典＝换了个文件继续冲突
- **建完自检同义重复**：同一个 `file` 出现两个不同 id（`zvec` 和 `vec` 都指向 `src/lib/zvec.ts`）＝同义项，必须合并。不合并的话两个 agent 各用一个，**校验全绿但跨图关联已经断了**

### 1.3 分片计划

```markdown
| # | 页 | 图数 | 执行者 | 依赖 | 模式 |
|---|---|:---:|---|---|---|
| 1 | overview | 1 | 主 agent | — | **样板（串行）** |
| 2 | import | 1 | 子 agent A | 样板定稿 | 并行 |
| 3 | cross | 2 | 子 agent B | 样板定稿 | 并行 |
```

**是否启用并行**（全部满足才并行，否则单 agent 串行）：

| 判据 | 阈值 | 理由 |
|---|---|---|
| 视图数 | ≥ 6 | 少于 6 张时协调成本大于收益 |
| 模块边界 | ≥ 3 个可独立摸清的模块 | 分不出块就没法分派 |
| 子 agent 数 | `min(模块数, 4)` | 经验值，未实测校准；超过 4 个时合并成本明显上升 |

> **并行前必须先确认 archify 能并发**：出图不只是写 JSON，还包含 `deliver`（常要跑浏览器渲染）。如果 archify 的导出是同步阻塞、独占浏览器的，4 个 agent 并行会互相抢资源——**这时只并行"图源 JSON 编写"，SVG 导出串行做**。没确认并发能力之前，不宣称并行能提速。

**分片单位是「页」不是「图」**：同一页的多张图本来要互相呼应（共享节点、解读连贯），拆给不同 agent 反而要协调。不同页天然各写一个 `nav/<分类>/<页面>.json`，**目录树模式下无写冲突**——这是并行优先用目录树模式的原因。

### 1.4 计划预览（输出后等确认）

```markdown
## 图集计划：{项目名}

**范围**：全项目 / 指定模块 `{path}`
**图源**：archify（可用）/ 复用已有 SVG（{N} 个）/ 手写 SVG（降级）
**产物**：目录树 `site.json` + `nav/` + `views/` + `snippets.json`（并行时**必须**用目录树）；分发时另出 `atlas.html`
**体积预估**：{N} 视图 · 去重后约 {X} MB（上限 10 MB）
**执行方式**：单 agent 串行 ／ 并行 {K} 个子 agent（判据：视图 {N} ≥6 且模块 {M} ≥3）

| # | 分类 | 视图 | 图种 | 回答什么问题 | 节点数 | 可挂代码节点 |
|---|------|------|------|-------------|--------|-------------|
| 1 | 架构总览 | 运行时架构 | architecture | 由什么组成 | ~10 | 3 |
| 2 | 核心链路 | 一次搜索 | sequence | 经过哪些环节 | ~7 | 3 |

**共享组件词典**：{N} 个 id（跨图关联只认这一份）——`daemon` `kb` `zvec` `etl` …

**分片计划**：

| # | 页 | 执行者 | 依赖 |
|---|---|---|---|
| 1 | overview | 主 agent（**样板**） | — |
| 2 | import | 子 agent A | 样板定稿 |
| 3 | cross | 子 agent B | 样板定稿 |

**片段范围**：{哪些节点挂代码}；其余标为概念节点
**不做的**：{明确排除的视图 + 理由}
```

规则：
- **只输出一次**，用户确认即执行；用户改动按改动后执行，不重发全量计划
- 用户长时间不回应不自行开工
- 计划里必须出现"不做的视图 + 理由"——防后续被问"为什么没有 XX"
- 确认后**词典冻结**：出图时冒出新组件，先申请入典由主 agent 统一加，**不许各 agent 自己造 id**（造了合并即失配）
- 增量场景（在已有图集上加页/改页）**不单独再确认一次**，直接体现在同一份大纲里：哪些新增、哪些改动、哪些不动

## 阶段 2：出图与取 SVG

### 2.0 样板先行（并行时必做）

先由主 agent 出一页样板，定下四件事作为后续 agent 的基准：

| 基准项 | 定什么 |
|---|---|
| 节点命名 | 词典里的 id 怎么落到图上（`daemon` 还是 `daemon-router`） |
| 解读 | 每图几条、每条多长、语气 |
| `code[]` 与 `why` | 一个节点挂多少行、why 写多细 |
| `links` | 哪条边算 `identifier`、`carries` 写事件名还是载荷摘要 |

样板不做，M 个 agent 会产出 M 种风格，读起来像几个人拼的。

### 2.1 并行分派（每页一个子 agent）

**三条硬约束**：

1. **只写自己的页**：子 agent 只产出 `nav/<分类>/<页面>.json` + `views/*.svg`，**不许碰** `atlas.config.json` / `snippets.json` / 别人的页面文件——那是单文件，多 agent 同写必冲突
2. **节点 id 只从词典取**：引用词典外的 id = 打回重做，不进入合并
3. **先读样板 + 自己的事实卡**：不读样板就没有风格基准，不读事实卡就会瞎猜

主 agent 合并时做四件事：收齐页面文件 → **词典校验**（越界 id 打回）→ 回填词典的 `pages`（每个 id 出现在哪几页，独占写）→ 跑阶段 3–5。

**打回上限 2 次**：仍不合格就由主 agent 自己重做该页——不无限重试，也不放任降级（质量差的页混进去，读者第一眼就看出是拼的）。

### 2.2 单页动作

1. **生成图源**：按 `use_skill("archify")` 的规范写 `{type}.json`（图种 + 节点 + 边 + 分组），`deliver` 出 HTML
   - 节点 id 用稳定的语义 slug（`daemon` / `domain` / `kb`），**不要用序号**——后续片段映射靠它
   - 视图里出现的组件必须能在源码找到，或其 `concept: true`
2. **导 SVG**：调 `use_skill("archify-svg-export")`（仅显式调用型 skill；该 skill 不在可用列表时，用 archify 自带 `Export → SVG` 的等价 CLI 路径，仍不可用则用 HTML 内嵌方案并重算预算）
3. **给边补语义 id**：画边时顺手写 `data-link="from->to"`（对应 `links[]` 的 `from`/`to`），框架才能在线的中点自动标出 `carries`。**不加就不标**——表格照常完整，所以老图源不用回改；archify 产出的 SVG 目前不带这个属性，需要边标签就得手写或后处理
4. **落位**：`views/{view-id}.svg`，命名与小写 slug 一致；同时保留 `views/{view-id}.json` 作为图源（便于下次改动）。一页多图时第 1 张 `views/{pid}.svg`、其后 `views/{pid}-{n}.svg`
5. **优先复用**：已有 `*.svg` 且图源 JSON 未变 → 直接复用，不重新生成（阶段 7 增量靠这条）

## 阶段 3：片段采集

**不手写片段**（demo 的 `snippets.json` 是手写的，19 条全靠手工对齐，节点改名即静默失配）。

1. 在页面配置的 `code[]` 里声明：`{id, file, lines: [起, 止], why}`（目录模式是 `nav/<分类>/<页面>.json`，单文件模式是 `pages[id]`）；抽象名词写 `{id, concept: true}`，外部服务写 `{id, external: true}`（归属与契约从 `site.externals` 补齐）
2. 跑脚本：

```bash
python3 <project-atlas skill 目录>/scripts/collect_snippets.py <图集目录> snippets.json --repo-root .
# 单文件模式也可：collect_snippets.py atlas.config.json snippets.json --repo-root .
```

3. 脚本产出 `snippets.json` + **覆盖率报告**：

```
片段采集：19/45 内部节点已挂代码（概念节点 7 个、外部节点 2 个不计入）
概念节点（无代码，前端显示说明）：web, agent, cli, llm
外部节点（只依赖契约，不采集源码）：etl, audit
校验失败：overview/daemon  行号越界（文件仅 2100 行，声明 2127-2142）
```

4. **行号越界 / 文件不存在 / 缺 why → 立即修正配置里的 `pages`**，不许让脚本"尽力而为"地截断

## 阶段 4：运行（可选导出单文件）

**日常不需要任何构建**：把框架复制到配置同目录，起本地静态服务即可，改配置刷新就生效。

```bash
cp <project-atlas skill 目录>/framework/index.html {目标目录}/
cd {目标目录} && python3 -m http.server 8000   # 打开 http://localhost:8000/index.html
```

框架的加载顺序：

```
读到 atlas.config.json  → 按配置渲染（pages 内联在配置里；图源按 views/{id}.svg 拉取并内联进 DOM）
读不到（双击 file://）  → 渲染内置示例配置（打开即有效果页，页首信息条标「示例」）
```

**要发给别人 / 要双击就能看**时，才导出单文件（把配置、图源、片段烘焙进 HTML）：

```bash
python3 <project-atlas skill 目录>/scripts/build_atlas.py <图集目录> dist/atlas.html
# 分发场景直接用 pack_atlas.py 更省事（见阶段 8）
```

导出脚本做三件事（**确定性工作不交给 AI**）：
1. 用真实配置替换框架的内置示例配置（含 `pages` 与 `snippets`），导出后不依赖任何外部文件
2. 按 `nav` 把各页图源内联进内置图源位（替换示例图、删除未用到的示例图）
3. **字体去重**：把各 SVG 内重复的 `@font-face{src:url(data:font/woff2;base64,...)}` 抽到壳层（`@font-face` 是文档级注册，Shadow DOM 内可直接用）。实测口径：archify 单图字体 90 KB（占 52%）；单图总量不变（字体只是搬家），N 张图才省 (N−1)×字体大小——6 图约省 450 KB

> 运行时渲染不做字体去重（只加载当前页，代价可接受）；去重是导出单文件时才做的优化。

**为什么不需要构建**：可点态由前端按 `pages[].code[]` 在运行时打标，图源在渲染时才拉取。所以加一页 = 改配置 + 放 SVG，不碰代码。

### 两种输入形态

三个脚本都既接受**目录树**，也接受**单文件**，行为等价：

```
目录树（推荐，多人/多会话并行时用它）        单文件（≤4 页时够用）
atlas/                                      atlas.config.json
├── site.json         全局                  { title, branch,
├── nav/                                       nav[], pages{} }
│   ├── 01-架构总览/        ← 目录名只定序
│   │   ├── _group.json     { id, name, q }
│   │   └── overview.json   ← 文件名即页面 id
│   └── 03-服务与测试/
│       ├── _group.json     { id, name, q, page: "stack" }  ← 有 page = 两级
│       └── stack.json
└── views/
```

| 操作 | 目录树模式要做的事 |
|---|---|
| 加一页 | 放一个 `<id>.json` 进分类目录（+ 图源），**其他文件不动** |
| 删一页 | 删掉那个文件 |
| 改某页 | 只改那一个文件 |
| 调顺序 | `_group.json` 写 `"order": ["import","search"]`；不写则按文件名排序 |
| 加分类 | 新建 `04-xxx/` 目录 + `_group.json` |
| 调整体 | 只改 `site.json` |

> 浏览器无法列目录，所以目录树需要一次合成：`build_atlas.py <目录> <out.html>` 会顺带写出 `atlas.config.json`（运行时用）。改完目录跑一次 build 即可，不必手改任何 JSON。

**四条运行期约定**：

| 约定 | 说明 |
|---|---|
| 同目录 | 框架与 `atlas.config.json` 必须同目录，图源路径相对该目录解析 |
| 片段优先级 | 配置内联 `snippets` > 同目录 `snippets.json` > 空（全部不可点） |
| 导出单文件 | 带 `baked: true`，运行时不读外部配置——不会被分发目录里的旧 config 覆盖 |
| 配置出错 | 顶部显示红色提示条并回退示例（**不静默**），注明是语法错、缺 nav 还是读取失败 |

## 阶段 5：校验

```bash
python3 <project-atlas skill 目录>/scripts/check_atlas.py .
python3 <project-atlas skill 目录>/scripts/check_atlas.py . --html dist/atlas.html   # 额外校验导出文件
```

| 检查项 | 通过标准 |
|---|---|
| 配置引用 | `nav[].page` 必须都有对应 `pages[id]` → **0 个缺失** |
| 图源完整性 | 每页每张 `figures[]` 的 svg 都存在；`figures[].id` 本页内唯一 → **0 个缺失 / 0 个重复** |
| 节点对齐 | `code[].id` 必须能在本页**任一**图源的 `data-node-id` 里找到 → **0 个** |
| 片段对齐 | 有 `file` 的 `code[]` 必须有片段；`concept` / `external` 与片段互斥 → **0 个孤儿 / 0 个缺失** |
| 漏配节点 | 报 warn：图上有节点但 `code[]` 里没有（多半是新加节点忘了配） |
| 外部契约 | 每个 `external` 都有 `owner` + `contract`；有 `returnsTo` 且落回本页内部节点，或显式 `oneWay: true` → **0 个缺失 / 0 个悬空** |
| 衔接关系 | `links[].from/to` 都在本页 `code[]` 里；`identifier` 必须有 `carries`，缺 `storedAt` 报 warn（标识符没说明存哪）→ **0 个悬空 / 0 个无名** |
| 页面完整性 | 每页有 title + summary + ≥1 个 docs；**每张图** ≥3 条解读，`q` 写在 nav 的分类上 |
| 可点覆盖率 | 每页「内部可点节点 / 内部节点」≥50%，建议 ≥80%；**外部节点不计入分母**，脚本逐页报比例 |
| 体积（导出时） | 单文件 ≤3 MB 目标、≤10 MB 硬上限——按**总图数**估，不按页数（一页 3 图 = 3 份体积） |
| 离线（导出时） | 无外链资源；无未替换占位符 |
| 交互约束 | 所有节点可点（`data-coded` / `data-bare` / `data-external` 三态）；抽屉由 `×`/`ESC`/切页/**点面板外**关闭。**静态脚本不覆盖，此项靠阶段 6 实测** |

不合格 → 修 `atlas.config.json` 的 `pages` 或图源，重跑阶段 3–5；最多 2 轮，第 3 轮仍不过则把未通过项写进交付说明，不静默放行。

## 阶段 6：验收走查

必须**实测**，不能只看代码（交互与观感属体验类判定）：

| 检查 | 做法 |
|---|---|
| 内置示例态 | 双击 `framework/index.html`（同目录无配置）→ 渲染示例、页首信息条带「示例」、节点可点看示例代码 |
| 真实配置态 | 框架 + `atlas.config.json` + 本地服务 → 页首信息条无「示例」、图源来自 `views/`、点击是真实源码 |
| 导出文件态 | `build_atlas.py` 产出的单文件双击 → 与真实配置态一致、无外链、无「示例」标记 |
| 加载失败提示 | 故意写错 `svg` 路径 → 图区显示具体路径与错误，不静默空白 |
| 三档视口 | 1440 / 900 / 375 → 侧栏折叠、抽屉不遮挡图体（<1000px 走底部抽屉） |
| 五类交互 | 点有代码节点 / 点概念节点（应无 pointer、点击无面板）/ `ESC` / `×` / 点图空白（**不应关闭**） |
| 切页竞态 | 快速连续切两次页 → 最终显示的是后一页的图，不出现前一页的图串台 |
| 回归 | 早期三处缺陷不得复现：全节点可点、背景点击误关、窄屏遮挡 |

无浏览器能力时（`use_skill("browser-evidence")` 判定为不可用）：标注"未实测"，只交付静态校验结论，**不得声称走查通过**。

## 阶段 7：更新

- **改配置即更新**（无需重建）：配置改了什么，刷新页面就是什么。图源或代码位置变更后重跑阶段 3–5。重跑前比对 `atlas.config.json` 里的 `baseline`：
  - 图源 JSON 未变 + 代码未变 → 直接复用，跳过阶段 2
  - 代码变了 → 重跑阶段 3–5，`snippets.json` 全量刷新
- 刷新 `atlas.config.json` 的 `baseline` 与 `generated_at`
- `.atlas/.gitignore` 内容固定为 `*`（含 `.gitignore` 自身需 `!.gitignore` 才能生效于空目录，脚本已处理）
- **不做**：视图级差量、片段级增量、监听文件自动重建（这些留到确有需求时再验证）

## 阶段 8：分发与导出（可选）

两个出口，目标不同：**HTML 给"看"，Markdown 给"改"**。

### 8.1 分发 HTML（给看的人）

```bash
python3 <skill>/scripts/pack_atlas.py <图集目录> dist/          # build → check → 收拢依赖 → 清单
python3 <skill>/scripts/pack_atlas.py <图集目录> dist/ --zip    # 额外打 zip
```

一条命令完成构建、校验、`interactive` 依赖收拢与清单（`dist/MANIFEST.txt` 含大小与 sha256），任一步失败即终止。
产物是**自包含单文件**，分发 = 拷这一个文件（图源、字体、片段、配置全内联）。
落地形态、打包范围、四种目标系统的注意事项、`interactive` 外链陷阱、分发前自检与回滚，见 [deploy.md](deploy.md)。

### 8.2 导出 Markdown（给改的人 / 进文档库）

```bash
# 页面：顶部「导出 ↓」一点即可（纯前端，无需脚本）
# 命令行：
python3 <skill>/scripts/export_markdown.py <图集目录> dist-md/       # 或 xxx.zip
```

产物按大纲建目录：`README.md` + `<分类>/<页面标题>.md` + `images/*.svg`（图源原样，含内联字体）。
**md 文件名用页面标题**（非法字符换连字符、超 60 字截断、同目录重名加 `-2/-3`），图片仍用 `pid`；
每个有代码的节点导出「路径 + why + 代码块快照」，`--no-code` 可只留路径。
两个入口输出 md **逐字节一致**（共用同一份模板）。md 模板、五个实现要点（ZIP UTF-8 标志位 / 图源取值优先级 / 补 xmlns / 补字体 / 别给手绘图补字体）、已知限制（企业 Wiki 不支持内联 SVG、需解压后查看）与验证方法，见 [export-md.md](export-md.md)。

## 数据契约（一份配置）

**`atlas.config.json`** —— 站点结构、每页内容、代码映射都在这里；换它就是换整个图集：

```jsonc
{
  "title": "kisearch 知识地图",
  "subtitle": "不看文档列表，也能先看清这个系统",
  "intro": "把架构、核心链路、后台进程分别画成图……",
  "notice": "图为内联 SVG：只有带代码的节点可点击，其余为概念节点。",  // 首页提示条，可省
  "branch": "main",                      // 生成基线分支
  "baseline": "de5c495",                 // 生成基线 commit
  "generated_at": "2026-11-24 11:45",    // 生成时间（带时分更直观）
  "views_dir": "views",                  // 可省，默认 views

  // 站点级外部服务字典：契约写一处，多页引用；页面里只写 { "id": "etl", "external": true }
  "externals": {
    "etl":   { "owner": "数据平台团队", "contract": "MQ · topic kb.changed · at-least-once",
               "returnsTo": "callback", "returnForm": "回写 zvec + POST /internal/index-ready" },
    "audit": { "owner": "安全审计平台", "contract": "Syslog over TLS · 单向上报", "oneWay": true }
  },

  "nav": [
    { "id": "arch", "name": "架构总览", "q": "由什么组成，谁和谁相连？",
      "children": [ { "id": "overview", "page": "overview" } ] },   // 有 children = 分组，可继续嵌套
    { "id": "ops", "name": "后台进程", "q": "哪些东西在后台跑？", "page": "daemons" }  // 无 = 两级
  ],

  "pages": {                              // 每页：加载哪张图 + 怎么读 + 点节点看哪段代码
    "overview": {                         // 单图页（老形态，仍然有效）
      "title": "运行时架构总览",
      "type": "architecture",
      "svg": "views/overview.svg",        // 可省，默认 views/{id}.svg
      "interactive": "views/overview.html",   // 可选，交互版外链
      "summary": "三种入口都汇到同一个 daemon……",
      "points": [["daemon 只做路由", "鉴权、并发、锁在这里，业务逻辑不在。"]],
      "docs": ["src/lib/mcp-http-api.ts"],
      "code": [
        { "id": "daemon", "file": "src/lib/mcp-http-api.ts", "lines": [1016, 1030],
          "why": "入口分发：/api/* 请求统一由 handleApiRequest 处理" },
        { "id": "llm", "concept": true }   // 概念节点：无代码，点击给出说明与相关文件
      ]
    },

    "daemons": {                          // 一页多图（不写 figures 即退回单图）
      "title": "后台进程：从写入到被读到的闭环",
      "summary": "上半张是「谁在写」，下半张是「被谁读」。只画生产侧，读者会以为写进去就等于能查到。",
      "figures": [
        { "id": "write", "name": "谁在写这些资源", "type": "architecture",
          "svg": "views/daemons-1.svg",   // 可省，默认 views/{pid}-{序号}.svg
          "q": "哪些进程在我没操作时改动索引？",   // 这张图回答什么问题
          "points": [["调度器按源计时", "…"]] },   // 每图至少 3 条
        { "id": "read", "name": "写完之后被谁读走", "type": "sequence",
          "svg": "views/daemons-2.svg",
          "points": [["写入不等于可检索", "…"]] }
      ],
      "docs": ["src/lib/datasource-scheduler.ts"],
      "code": [                           // 页级一维：同一 id 在多图之间共用一段代码
        { "id": "sched", "file": "src/lib/datasource-scheduler.ts", "lines": [55, 70], "why": "…" },
        { "id": "zvec", "concept": true },
        { "id": "etl", "external": true }  // 外部节点：owner/contract/returnsTo 从 site.externals 补齐
      ],
      "links": [                          // 衔接关系：节点之间传什么、靠什么标识符对上
        { "from": "sched", "to": "zvec", "carries": "batch_id", "kind": "identifier",
          "shape": "string(32)", "storedAt": "scope_meta.last_batch", "cardinality": "1:1",
          "note": "下一轮增量同步靠它判断从哪继续；没存住就会全量重扫" },
        { "from": "sched", "to": "kb", "carries": "扫描结果", "kind": "status",
          "note": "只回成功/失败，不构成衔接键——图上不画、表格里折叠" }
      ]
    }
  },

  "snippets": {                           // 可选：不写则由 collect_snippets.py 产出独立 snippets.json
    "overview": { "daemon": { "file": "…", "line": 1016, "endLine": 1030, "commit": "…", "why": "…", "snippet": "…" } }
  }
}
```

**硬约定**：

| 约定 | 说明 |
|---|---|
| `nav[].page` | 指向 `pages` 里的键名。nav 是**任意深度**的树：节点有 `children` 即分组（可继续嵌套），否则必须有 `page`。侧栏**第 3 层起默认折叠**，当前页路径自动展开，点分组标题可手动切换 |
| `pages[].figures[]` | 一页多图。不写则把页级 `svg`/`type`/`points` 当单图（老配置零改动）。`figures[].id` **本页内必须唯一**——跨图关联与图源 key 都靠它区分；每图至少 3 条解读 |
| `pages[].code[].id` | 必须与本页**任一** `figures[].svg` 里的 `data-node-id` 一致（至少一张图里有）；`check_atlas.py` 三方对齐校验 |
| `pages[].code[].lines` | `[起行, 止行]`，1-based 闭区间；与 `concept` / `external` 互斥 |
| `pages[].code[].symbol` | 可选。关键符号（类名/函数名）；不填则由 `collect_snippets.py` 从片段首行自动提取 |
| `pages[].code[].why` | 必填一句话，说明"为什么看这段"；空则采集脚本拦下 |
| `pages[].code[].concept` | 概念节点（抽象名词，无源码）。**仍然可点**，点开给"无对应源码 + 相关文件"，不是死节点 |
| `pages[].code[].external` | 外部服务。**owner + contract 必填**（编造外部服务静态校验抓不到，契约字段是唯一准入门槛）；`returnsTo` 必须落回本页内部节点，只发不收的链路标 `oneWay: true` |
| `site.externals` | 外部服务字典（按 id）。页面里只写引用，避免同一份契约在多页各填一份而漂移 |
| `pages[].links[]` | 衔接关系。`from` / `to` 必须是本页 `code[]` 里的 id。`kind`：`identifier`（标识符，后续操作靠它定位）/ `event`（事件载荷）/ `status`（只回成功失败）/ `none`。**只有 `identifier` 是衔接键**，`status` / `none` 不构成下一次操作的入口，不上图、表格里折叠 |
| `links[].carries` | 传的是什么。`identifier` 必填（标识符得有名字），`event` 建议填 |
| `links[].storedAt` | 标识符存在哪。同一条键只要**任意一段**写清即可；整条都没写会告警——只在内存里的话，进程重启后就对不上，图上看还是闭环、实际已断 |
| 图源 `data-link` | 画图时给边加 `data-link="from->to"`，框架按 `links[]` 在**边的中点**自动叠加标签（identifier 实底绿标 / event 淡色 / status·none 不标）。没有这个属性的边不标——老图源零改动，标签数据驱动，改配置即改标签 |
| 可点率口径 | 分母**只算内部节点**（排除 external）——外部天然没有源码，否则跨服务图的覆盖率永远不达标 |
| 可点态 | **不在 SVG 里标**，前端按 `code[]` 运行时打标（`data-coded` / `data-bare` / `data-external`）——加图不必改 SVG、不必改脚本 |
| `branch` | 生成基线分支名（与 `baseline`、`generated_at` 一起渲染在页首信息条上） |

> 新增一张图的完整动作：写图源 → 导 SVG 到 `views/{id}.svg` → 在 `pages` 里加一条 → 在 `nav` 里挂一行。**四步全是配置与素材，框架代码零改动。**

## 与相邻 skill 的边界

| skill | 关系 |
|---|---|
| `archify` | **图源提供方**。本 skill 只消费其产物，不重复其校验与渲染能力 |
| `archify-svg-export` | 只导出 SVG（仅显式调用型）。本 skill 在阶段 2 显式调用它；未装则降级 |
| `module-teach` | 讲**一个模块怎么实现**（长文），本 skill 给**系统全景**（图集）；模块可以只是图集里的一张视图 |
| `module-teach` / `topic-teach` 的 SVG | 教学用插图，手写 SVG；本 skill 用 archify 产物，二者不互换 |
| `expert-team` / `expert-lookup` | 专家包里的架构描述与 Mermaid 图是**视图策划的素材**；本 skill 不回写专家资产 |
| `backend-index` / `frontend-index` | 模块边界、依赖、表、接口的**事实来源**，避免全仓重摸；本 skill 只读 |
| `ui-designer` | 它设计**产品界面**；本 skill 的产物是**内部知识页**，不追求产品级视觉规范（但受本 skill 的交互硬约束） |
| `design-craft` | 要出**技术设计文档**找它；本 skill 是文档之外的可视化入口 |
| `code-survey` | 设计前的轻量调研；本 skill 是交付物，落盘且可重复打开 |
| `task-dispatch` | **并行分派的执行机制**。本 skill 只定分片规则与交接契约（共享组件词典 / 一页一文件 / 样板基准），具体怎么拆任务派子 agent 复用它 |
| `delivery-slicing` | 大图集要拆给多个会话并行时，按它"目录互斥、契约只读"的切法切；本 skill 的共享组件词典就是那份契约 |

## 反模式

- ❌ **一图一 HTML**：产出 6 个文件让用户自己找 → 违反核心原则 3，必须收成一个
- ❌ **每次现场重写壳**：AI 手写 400 行 HTML → 交互约束必然漂移，改图源 + 重跑装配即可
- ❌ **给所有节点挂 pointer**：看起来都能点，点进去空面板（demo 实测 30/49 空）→ 只按 `data-coded` 渲染
- ❌ **点图空白关面板**：`document` 级点击关闭，打断对照阅读 → 只留 `×`/`ESC`/切视图
- ❌ **手写 snippets.json**：手工对齐节点与行号，改名即静默失配 → 一律脚本采集 + 校验
- ❌ **把 HTML 内联进图集**：800 KB/图 × N，且每个都带一份字体 → 用导出的 SVG + 字体去重
- ❌ **视图越多越好**：20 张图 16 MB，打开即卡 → 6–8 个视图，其余用"指定模块"模式另出一份
- ❌ **只画不解释**：没有"回答什么问题"和解读，读者只能自己猜 → 每视图必配 `q` + ≥3 条解读
- ❌ **编造组件**：图上画了源码里不存在的服务 → 节点必须可溯源，或显式标 `concept: true`
- ❌ **对行号做"尽力而为"**：声明 2127-2142 但文件只有 2100 行就静默截断 → 校验失败即停，改配置里的 `pages`
- ❌ **产物入 git**：`.atlas/` 是派生物，写进仓库拖慢 clone → 自动 `.gitignore`
- ❌ **未实测就宣称走查通过**：只看代码就说"交互没问题" → 无浏览器时必须标注未实测
- ❌ **没有词典就并行出图**：几个 agent 各自给同一组件起 id（`zvec` / `vec` / `vector-store`），合并后跨图关联全断 → 先收敛词典再分派
- ❌ **子 agent 写 `atlas.config.json`**：多 agent 同写单文件必互相覆盖 → 目录树模式下一页一个文件，各写各的
- ❌ **样板没定就批量开工**：M 个 agent 产出 M 种解读风格，凑起来像几个人拼的 → 先出一页定基准确认
- ❌ **小项目强行并行**：3 张图拆给 3 个 agent，协调开销比画图还大 → 视图 <6 或模块 <3 就单 agent 串行

## 更多资源

- 视图策划模板与挑选示例、**分批并行判据与子 agent 契约**、`atlas.config.json` 字段细则、目录树模式、交互规范（可点态 / 抽屉 / 响应式三档）、体积与字体去重原理、校验项逐条判定、验收走查清单：见 [reference.md](reference.md)
- **分发与集成**：打包范围、四种落地形态（本地 / 静态站 / iframe / Wiki）、`interactive` 外链陷阱、分发前自检与回滚：见 [deploy.md](deploy.md)
- **导出 Markdown**：两个入口、产物结构、md 模板、五个实现要点、已知限制与验证：见 [export-md.md](export-md.md)
- 框架：`framework/index.html`（样式 + 运行时渲染 + 内置示例；**这是唯一真源**，demo 只作设计归档）
- 片段采集：`scripts/collect_snippets.py`（输入图集目录或显式 `atlas.config.json`，输出 `snippets.json` + 覆盖率报告，自动提取类名/函数名作为符号）
- 输入加载：`scripts/atlas_io.py`（目录树与单文件的统一加载层，三个脚本共用；改目录约定只改这一处）
- 导出：`scripts/build_atlas.py`（真实配置烘焙 + 图源内联 + 字体去重 + 原子替换，仅分发时用）
- 校验：`scripts/check_atlas.py`（三方对齐 / 图源 / 片段 / 导出文件）
- 打包：`scripts/pack_atlas.py`（build + check + 收拢 interactive 依赖 + `MANIFEST.txt` + 可选 zip）
- 导出 Markdown：`scripts/export_markdown.py`（与页面「导出 ↓」同一份模板：README + 每页 md + images/*.svg，可输出目录或 zip）
