# 模块专家团 · 切面调研清单与 code-to-wiki 格式模板

> 子 agent 加载本文件，按所属切面执行调研并按模板产出 `.module-experts/{中文专家名}/{NN-切面中文}.md`（code-to-wiki 风格 Wiki 页）。`agent.md` 由主 agent 在 Step 4 合成，子 agent 不产出，也不套 Wiki 格式。

## 通用格式要求（遵循 code-to-wiki，不跑工具）

每篇切面文档**必须**遵守以下格式（R1–R7 由 AI 在 Step 6 手动自检）：

- 顶部 `**本文引用的文件**` cite 块，列出本篇真正用到的源文件，`[名称](file://相对仓库根目录的路径)`，**无需行号**
- `## 目录` 条目与 `##` 章节一一对应，锚点用中文（如 `[核心组件](#核心组件)`）
- 每个 `##`/`###` 小节末尾有 `章节来源`：`[名称](file://相对路径#Lx-Ly)`，**必须带 `file://` 与行号区间**（纯概念节可豁免 R3）
- 任何 Mermaid 图后紧跟 `图表来源`（同章节来源格式）
- 所有引用路径均 `file://` 前缀
- 来源行号区间须覆盖被论述代码实际跨度，`Lx-Lx` 单点不合规（R6）
- 详细分析须 ≥2 设计维度（设计要点 / 关键流程 / 错误处理 / 风险控制）；架构 / 流程 / 状态机 / 依赖等按需配 ≥1 Mermaid 图（R7）
- 不逐行转储代码，提炼模式与要点
- 无内容的章节标注「该模块无此项」，不留空、不编造

> 命名对照：architecture=`01-架构.md`、implementation=`02-实现.md`、data-flow=`03-数据流转.md`、models=`04-模型.md`、api=`05-接口.md`、tests=`06-测试.md`、ops=`07-运维.md`。

---

## 01-架构（架构）— 必出

### 调研清单
- 模块对外的职责边界：做什么、不做什么
- 子模块 / 包划分：每个子模块的路径 + 一句话职责
- 分层结构（如 controller / service / repo / model）
- 依赖关系：依赖哪些内部模块 / 外部库；被谁依赖
- 关键设计约束 / 不变量（如"所有写操作必经 X"）

### 产出模板（code-to-wiki 格式）
```markdown
# 架构：{专家名} / {模块名}

**本文引用的文件**
- [入口](file://{root}/main.go)
- [模块根](file://{root})

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构总览](#架构总览)
5. [组件详细分析](#组件详细分析)
6. [依赖关系分析](#依赖关系分析)
7. [结论](#结论)

## 简介
{一句话职责 + 模块定位}
章节来源：[README](file://{root}/README.md#L1-L20)

## 项目结构
{目录树 + 各子模块一句话职责，标注路径}
章节来源：[目录](file://{root})

## 核心组件
{主组件清单 + 各自职责}
章节来源：[comp.go](file://{root}/comp.go#L1-L30)

## 架构总览
\`\`\`mermaid
graph TD
  A[入口] --> B[Service]
  B --> C[Repo]
  C --> D[(DB)]
\`\`\`
图表来源：[main.go](file://{root}/main.go#L10-L50)

## 组件详细分析
### {组件 A}
- 设计要点：{...}
- 关键流程：{...}
- 错误处理：{...}
章节来源：[a.go](file://{root}/a.go#L10-L80)

## 依赖关系分析
{内部 / 外部依赖 + 被依赖方，标注文件}
章节来源：[go.mod](file://{root}/go.mod#L1-L20)

## 结论
{架构层面的关键结论 / 风险 / 扩展点}
```

---

## 02-实现（实现）— 必出

### 调研清单
- 核心算法 / 关键流程的实现位置
- 所用设计模式（工厂 / 策略 / 观察者 等）及位置
- 热点路径：高频调用 / 性能敏感代码
- 关键类 / 函数清单（名称 + 路径 + 职责）
- 已知技术债 / hack 注释

### 产出模板（code-to-wiki 格式）
```markdown
# 实现：{专家名} / {模块名}

**本文引用的文件**
- [核心流程](file://{root}/handler.go)
- [算法](file://{root}/algo.go)

## 目录
1. [简介](#简介)
2. [核心流程](#核心流程)
3. [设计模式](#设计模式)
4. [关键类与函数](#关键类与函数)
5. [热点路径](#热点路径)
6. [技术债](#技术债)
7. [结论](#结论)

## 简介
{实现层面一句话概述}
章节来源：[handler.go](file://{root}/handler.go#L1-L30)

## 核心流程
\`\`\`mermaid
flowchart LR
  R[请求] --> V[校验] --> B[业务] --> S[落库]
\`\`\`
图表来源：[handler.go](file://{root}/handler.go#L30-L90)

## 设计模式
| 模式 | 位置 | 用途 |
| 策略 | [s.go](file://{root}/s.go#L1-L40) | {...} |
章节来源：[s.go](file://{root}/s.go#L1-L40)

## 关键类与函数
| 名称 | 路径 | 职责 |
章节来源：[x.go](file://{root}/x.go#L5-L60)

## 热点路径
{高频 / 性能敏感路径 + 文件}
章节来源：[hot.go](file://{root}/hot.go#L1-L50)

## 技术债
{已知 hack / TODO / 待重构点}
章节来源：[legacy.go](file://{root}/legacy.go#L1-L20)

## 结论
{实现层面结论 / 风险}
```

---

## 03-数据流转（数据流转）— 有 api 或 db 时启用

### 调研清单
- 主入口 → 出口的完整数据生命周期
- 请求 / 事件 / 消息的流转路径
- 状态机 / 状态流转
- 异步流（队列 / 定时任务 / 回调）
- 数据变换关键节点

### 产出模板（code-to-wiki 格式）
```markdown
# 数据流转：{专家名} / {模块名}

**本文引用的文件**
- [入口](file://{root}/controller.go)
- [消费](file://{root}/consumer.go)

## 目录
1. [简介](#简介)
2. [数据生命周期](#数据生命周期)
3. [状态流转](#状态流转)
4. [异步流](#异步流)
5. [结论](#结论)

## 简介
{数据流转一句话概述}
章节来源：[controller.go](file://{root}/controller.go#L1-L20)

## 数据生命周期
\`\`\`mermaid
flowchart TD
  In[入口] --> T1[变换] --> Store[(存储)] --> Out[出口]
\`\`\`
图表来源：[controller.go](file://{root}/controller.go#L20-L70)

## 状态流转
\`\`\`mermaid
stateDiagram-v2
  [*] --> 待处理
  待处理 --> 处理中 --> 完成
\`\`\`
图表来源：[state.go](file://{root}/state.go#L1-L40)

## 异步流
{队列 / 定时 / 回调 + 文件}
章节来源：[consumer.go](file://{root}/consumer.go#L1-L50)

## 结论
{数据一致性 / 丢失风险等结论}
```

---

## 04-模型（模型）— 有 db 时启用

### 调研清单
- 数据模型 / 实体定义位置
- DB schema / 表结构
- ORM 映射方式
- 迁移文件位置与惯例
- 校验规则（必填 / 格式 / 业务约束）

### 产出模板（code-to-wiki 格式）
```markdown
# 模型：{专家名} / {模块名}

**本文引用的文件**
- [实体](file://{root}/model/alert.go)
- [迁移](file://{root}/migrations/001.sql)

## 目录
1. [简介](#简介)
2. [实体清单](#实体清单)
3. [DB Schema](#db-schema)
4. [迁移](#迁移)
5. [校验规则](#校验规则)
6. [结论](#结论)

## 简介
{数据模型一句话概述}
章节来源：[alert.go](file://{root}/model/alert.go#L1-L20)

## 实体清单
| 实体 | 路径 | 关键字段 |
| Alert | [alert.go](file://{root}/model/alert.go#L5-L40) | id, rule, status |
章节来源：[alert.go](file://{root}/model/alert.go#L5-L40)

## DB Schema
{表 / 集合概述，标注文件}
章节来源：[schema.sql](file://{root}/migrations/001.sql#L1-L30)

## 迁移
- 位置：[migrations](file://{root}/migrations)  惯例：{...}
章节来源：[001.sql](file://{root}/migrations/001.sql#L1-L30)

## 校验规则
{必填 / 格式 / 业务约束 + 文件}
章节来源：[validate.go](file://{root}/validate.go#L1-L25)

## 结论
{模型层面结论 / 风险}
```

---

## 05-接口（接口）— 有 api 时启用

### 调研清单
- 对外公开入口（HTTP / RPC / CLI / 事件）
- 请求 / 响应契约
- 错误码与错误响应格式
- 版本策略
- 鉴权 / 限流约定

### 产出模板（code-to-wiki 格式）
```markdown
# 接口：{专家名} / {模块名}

**本文引用的文件**
- [路由](file://{root}/router.go)
- [Handler](file://{root}/handler.go)

## 目录
1. [简介](#简介)
2. [入口清单](#入口清单)
3. [契约示例](#契约示例)
4. [错误码](#错误码)
5. [版本与鉴权](#版本与鉴权)
6. [结论](#结论)

## 简介
{接口一句话概述}
章节来源：[router.go](file://{root}/router.go#L1-L20)

## 入口清单
| 入口 | 路径 | 方法 | 说明 |
| 创建 | [r.go](file://{root}/router.go#L10-L15) | POST | {...} |
章节来源：[router.go](file://{root}/router.go#L10-L15)

## 契约示例
{请求 / 响应，标注文件}
章节来源：[handler.go](file://{root}/handler.go#L20-L60)

## 错误码
| 码 | 含义 | 来源 |
| 4001 | {...} | [err.go](file://{root}/err.go#L1-L20) |
章节来源：[err.go](file://{root}/err.go#L1-L20)

## 版本与鉴权
{版本策略 / 鉴权 / 限流 + 文件}
章节来源：[middleware.go](file://{root}/middleware.go#L1-L30)

## 结论
{接口层面结论 / 风险}
```

---

## 06-测试（测试）— 有测试时启用

### 调研清单
- 单元测试位置（目录 / 文件命名惯例）
- 测试框架与组织方式
- 断言风格 / mock 方式
- 如何运行（命令）
- 覆盖情况与缺口

### 产出模板（code-to-wiki 格式）
```markdown
# 测试：{专家名} / {模块名}

**本文引用的文件**
- [测试目录](file://{root}/test)
- [样例用例](file://{root}/test/alert_test.go)

## 目录
1. [简介](#简介)
2. [测试位置](#测试位置)
3. [框架与组织](#框架与组织)
4. [运行命令](#运行命令)
5. [覆盖与缺口](#覆盖与缺口)
6. [结论](#结论)

## 简介
{测试一句话概述}
章节来源：[test](file://{root}/test)

## 测试位置
- 目录：[test](file://{root}/test)  命名惯例：{...}
章节来源：[alert_test.go](file://{root}/test/alert_test.go#L1-L10)

## 框架与组织
{框架 / mock 方式 + 文件}
章节来源：[alert_test.go](file://{root}/test/alert_test.go#L1-L40)

## 运行命令
\`\`\`bash
{命令}
\`\`\`
章节来源：[Makefile](file://{root}/Makefile#L1-L10)

## 覆盖与缺口
{已覆盖 / 薄弱点 + 文件}
章节来源：[alert_test.go](file://{root}/test/alert_test.go#L1-L40)

## 结论
{测试层面结论}
```

---

## 07-运维（运维）— 有配置时启用

### 调研清单
- 配置文件组织 / 环境变量
- 部署相关（Dockerfile / k8s / CI）
- feature flag
- 日志框架 / 级别 / 关键日志点
- 监控 / 指标接入

### 产出模板（code-to-wiki 格式）
```markdown
# 运维：{专家名} / {模块名}

**本文引用的文件**
- [配置](file://{root}/config.yaml)
- [部署](file://{root}/Dockerfile)

## 目录
1. [简介](#简介)
2. [配置](#配置)
3. [部署](#部署)
4. [日志与监控](#日志与监控)
5. [结论](#结论)

## 简介
{运维一句话概述}
章节来源：[config.yaml](file://{root}/config.yaml#L1-L20)

## 配置
- 文件：[config.yaml](file://{root}/config.yaml#L1-L20)  环境变量：{...}
章节来源：[config.yaml](file://{root}/config.yaml#L1-L20)

## 部署
{ Dockerfile / k8s / CI + 文件 }
章节来源：[Dockerfile](file://{root}/Dockerfile#L1-L30)

## 日志与监控
{日志框架 / 关键日志点 / 指标 + 文件}
章节来源：[main.go](file://{root}/main.go#L1-L30)

## 结论
{运维层面结论 / 风险}
```

---

## Step 5：识别专用技能的指引

主 agent 在 Step 4 完成后，基于全部切面文档识别**该业务领域具体、可复用的操作型任务**：

- 判定标准：是一个会被反复执行、有明确步骤、值得固化成技能的操作（如"新增告警规则""排查告警不触发""查询历史日志"）
- 每识别出一个 → 调用 `create-skill` 技能生成标准 `SKILL.md`，落盘到 `.module-experts/{中文专家名}/skills/{kebab-skill-name}/`
- 技能内容须含真实触发短语与可执行步骤；无价值操作任务时留空 `skills/` 并在 `agent.md` 注明
- 技能格式一律以 create-skill 规范为准

---

## 子 agent prompt 模板

```
你是子 agent，负责切面 {NN}-{切面}：{切面名}（产出文件：{NN-切面中文}.md）

## 模块
- 专家名（中文）：{中文专家名}
- 模块根路径：{module_root}
- 模块名：{module-name}

## 调研清单与格式模板
见 reference.md 中「{NN-切面}」章节（须严格遵循 code-to-wiki 格式：cite 块 / 目录 / 章节来源 / 图表来源 / file:// + 行号区间 / Mermaid / 深度）

## 同批产出的其他切面（供 01-架构.md 预置切面索引）
{列出同批切面清单，如 02-实现, 05-接口, 06-测试}

## 方法
1. search_content / search_file 精确定位（优先）
2. read_file 读关键文件，**记录文件路径与行号区间**供章节来源
3. 信息来源标注：ki / 代码搜索 / 语义检索

## 产出
先写到 .codebuddy/task-dispatch/module-expert-{专家简称}/subtasks/{NN}-{切面}/{NN-切面中文}.md
完成后落盘到 .module-experts/{中文专家名}/{NN-切面中文}.md
并写 report.md 说明搜索范围与关键发现
```
