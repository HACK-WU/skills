---
name: module-expert-team
description: 派出多专家子 agent 并行深挖单个业务模块，按功能分类产出"业务专家"包（如告警处理专家、日志查询专家），每个专家包含架构/数据流/模型/测试/实现/接口/运维等参考文档，并调用 create-skill 生成该领域专用技能（标准格式可直接加载）。落盘到项目级 .module-experts/{中文业务专家名}/。触发短语："掌握这个模块"、"深度分析 xxx 模块"、"梳理这个模块"、"建模块专家团"、"module expert team"，或需要对某业务模块建立深度、持久、可复用的领域专家资产时。
---

# 模块专家团

## 概述

**目的**：把单个业务模块深度消化成一个"业务专家"资产包（知识文档 + 专用技能），供后续设计 / 排查 / 重构直接取用，避免每次重摸代码。

**功能**：模块范围扫描（AI 自行判断）→ 知识库优先查 → 派出多专家子 agent 并行产出技术切面文档 → 合成模块入口 → 调用 create-skill 生成领域专用技能 → 校验 → 落盘到 `.module-experts/{中文业务专家名}/`。

**使用场景**：
- 即将对某业务模块做重大设计 / 重构 / 迁移，需要先彻底掌握它
- 反复排查某业务模块问题，希望沉淀一份持久专家资产
- 新人 / 新 agent 接手某业务模块，需要快速建立全景认知
- 用户说"掌握这个模块""深度分析 xxx 模块""梳理这个模块的来龙去脉"时

## 组织模型：业务专家

> `.module-experts/` 的**子目录 = 业务专家**（按功能分类，中文业务名，如"告警处理专家""日志查询专家"）。每个专家内含技术切面文档 + 专用技能目录。

```
.module-experts/
├── INDEX.md
├── 告警处理专家/                  # 专家 = 业务功能分类（中文名）
│   ├── agent.md                   # 专家职责摘要：这个专家是干嘛的（必出）
│   ├── skills/                    # 该专家专用技能（标准 create-skill 格式，可直接加载）
│   │   └── add-alert-rule/
│   │       └── SKILL.md
│   ├── architecture.md            # 技术切面 = 专家内文档；兼作模块入口
│   ├── implementation.md
│   ├── data-flow.md
│   ├── models.md
│   ├── api.md
│   ├── tests.md
│   └── ops.md
├── 日志查询专家/
│   └── ...
└── ...
```

- **专家目录**：中文业务名，由模块的业务功能派生（Step 0 与用户确认）
- **技术切面文档**：architecture / implementation / data-flow / models / api / tests / ops，按需产出，存放于专家目录下
- **agent.md（必出）**：专家职责摘要，用一句话说明"这个专家是干嘛的"、负责哪些模块、何时找他；作为专家名片供后续查找
- **skills/ 目录**：该专家的专用技能，由 `module-expert-team` 调用 `create-skill` 生成，遵循标准 skill 格式可直接加载；技能子目录名用 kebab-case（create-skill 要求）
- **模块入口**：`architecture.md` 兼作总览与切面索引

## 与相邻 skill 的边界

| skill | 关系 |
|---|---|
| code-survey | 轻量、按需、跨多维度、一次性；本 skill 是单业务模块深挖、持久落盘 |
| codekb-skill | 本 skill 可选地把知识原子写入 ki KB；专家文档存深度参考，KB 存可查询原子，互补 |
| solution-capture | 沉淀"问题解法"；本 skill 沉淀"业务模块全景知识 + 专用技能"，复用其包 + INDEX 范式 |
| **create-skill** | **本 skill 调用它生成专家的专用技能**；技能格式以 create-skill 规范为准，不在此重复定义 |

## 核心原则

1. **业务专家为轴**：`.module-experts/` 子目录是业务专家（中文名），不是技术切面
2. **单模块深挖**：一次只针对一个业务模块，不泛化到全项目
3. **按需切面**：根据模块性质选择产出哪些切面文档，不硬凑空文档（无 DB 不写 models.md）
4. **知识库优先**：先查 ki（项目记忆 → KB），已知不重复读
5. **并行专家**：切面 ≥ 2 时用 task-dispatch 并行
6. **专用技能务实**：只对识别出的具体可复用操作任务调 create-skill 造技能，不造 stub
7. **不编造**：无内容则标注「该模块无此项」，不凑话

## 执行流程

### Step 0：确认模块边界与专家名

- 必须有明确的模块根路径（目录或包名）；路径不明确时仅问一次
- 由模块的业务功能派生**中文专家名**（如 `pkg/alert` → "告警处理专家"），与用户确认后定名
- 专家名即目录名：`.module-experts/{中文专家名}/`

### Step 1：模块范围扫描（AI 自行判断）

主 agent 用 `list_dir` / `search_file` 快速摸清模块根目录结构，自行判断：

- 文件清单与语言 / 框架 / 测试目录 / 入口点
- **该产出哪些切面文档**（发现 DB / ORM / migration → models；router / controller → api；测试目录 → tests；配置 / 部署 → ops）
- 模块规模：源文件过多（如 > 200）时改为采样，不逐文件全读

> 不依赖任何脚本，由 AI 基于目录结构与文件命名自行决策。

### Step 2：知识库优先查（如 ki 可用）

按 codekb-skill 规则，对目标模块先查 ki（项目记忆索引 → KB），命中则复用、跳过对应切面的部分代码阅读。无 ki 则跳过本步。

### Step 3：派出专家团（并行）

依据 Step 1 判断结果选择切面。切面 ≥ 2 时调用 task-dispatch 并行，每个切面一个子 agent。

- **task-name**：`module-expert-{专家名拼音或英文简称}`
- **子任务产出**：每个切面产出 `.module-experts/{中文专家名}/{切面}.md`（中间产物可先写在 `.codebuddy/task-dispatch/.../subtasks/{NN}-{切面}/{切面}.md`，完成后落盘到最终位置）
- **子 agent prompt 要点**：给定模块根 + 中文专家名 + 该切面调研清单（见 [reference.md](reference.md)）+ 同批产出的其他切面清单（供 architecture 预置索引）；用 search_content / search_file / read_file 调研；按切面模板产出，标注关键文件路径与来源

**切面定义**（适用时产出）：

| 切面 | 文件 | 核心内容 |
|---|---|---|
| architecture | `architecture.md` | 职责、边界、子模块、依赖图、分层；兼作模块入口与切面索引 |
| implementation | `implementation.md` | 核心算法、设计模式、热点路径、关键类 |
| data-flow | `data-flow.md` | 入口 → 出口生命周期、状态流转、异步流 |
| models | `models.md` | 数据模型、DB schema、ORM 映射、迁移、校验 |
| api | `api.md` | 公开入口、契约、错误码、版本策略 |
| tests | `tests.md` | 单测位置、覆盖、模式、如何跑、缺口 |
| ops | `ops.md` | 配置、部署、feature flag、日志 / 监控 |

> architecture 与 implementation 为核心切面，默认必出；其余按适用性。

### Step 4：合成专家入口

主 agent 汇总各切面产出，写入两份文件：

**A. `agent.md`（专家名片，必出）**——总结这个专家是干嘛的：
- 一句话职责：该专家负责的**业务领域**
- 负责的模块：`.module-experts/{中文专家名}/` 对应的模块根路径与一句话职责
- 何时找这个专家：列出典型使用场景（如"排查告警不触发""新增告警规则"）
- 包含的资产：切面文档清单 + 专用技能清单（或「暂无」）
- 出处行：生成日期 + git commit

**B. `architecture.md`** 补充：
- 切面索引：链接到同专家目录下其他切面文档（`./implementation.md`、`./data-flow.md` 等）
- 关键发现 / 主要风险 / 常见坑（Top）
- 术语表
- 出处行：生成日期 + git commit（仅被动 provenance，不含同步校验逻辑）

### Step 5：造专用技能（调 create-skill）

基于已产出的切面文档，识别该业务领域中**具体、可复用的操作型任务**（如告警处理专家的"新增告警规则""排查告警不触发"）：

- 每识别出一个有价值的操作任务 → **调用 `create-skill` 技能**，在其指导下生成标准格式 `SKILL.md`，落盘到 `.module-experts/{中文专家名}/skills/{kebab-skill-name}/`
- 技能格式以 create-skill 规范为准，本 skill 不重复定义
- **质量底线**：技能必须含真实触发短语与可执行步骤，禁止 stub；识别不出任何操作任务时，留空 `skills/` 并在 `architecture.md` 注明「暂无专用技能」

### Step 6：校验

主 agent 自检产出：

- `agent.md` 与 `architecture.md`、`implementation.md` 必有且非空
- 各切面文档非空、无纯占位符（`TODO` / `待补充`）
- 无内容的切面标注「该模块无此项」而非留空
- `architecture.md` 含切面索引
- `skills/` 下每个技能有合规 `SKILL.md`（frontmatter + 正文），无 stub

不合格 → 补全后重检。

### Step 7：更新索引

在 `.module-experts/INDEX.md`（不存在则建）按专家追加 / 更新：

```
# 模块专家包索引
> 由 module-expert-team 自动维护

## {中文专家名}  （职责摘要见 agent.md）
- 模块根：{path}
- 生成日期：{date}  git commit：{hash}
- 切面文档：architecture, implementation, data-flow, ...
- 专用技能：skills/{skill1}, skills/{skill2}（或「暂无」）
```

### Step 8：可选写 ki KB

将模块知识原子（按 codekb-skill 8 类白名单）写入 ki KB，便于后续 query 命中。专家文档内不重复堆 KB 原文，仅引用。

## 验证（测试方式）

1. 抽查：`architecture.md` 能否脱离代码独立读懂该业务模块
2. 各切面文档是否标注关键文件路径与信息来源
3. 无内容的切面是否标注「该模块无此项」而非编造
4. 核心切面（architecture + implementation）是否必出且非空
5. `skills/` 下技能是否为标准格式、含真实触发短语与步骤、非 stub

## 行为边界

- 一次一个业务模块，不批量
- 专家目录用中文业务名；skills 子目录用 kebab-case
- 不内置过期同步 / 重跑机制（按决策）；文档为生成时快照
- 不替代 code-survey 的设计前轻量调研
- 不写 memory；写 KB 走 codekb-skill 规则
- 专用技能格式交由 create-skill 规范，不在本 skill 内重复定义

## 更多资源

- 各切面调研清单与产出模板，参见 [reference.md](reference.md)
