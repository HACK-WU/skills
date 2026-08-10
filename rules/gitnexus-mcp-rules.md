---
description: GitNexus MCP 强制规则 + 使用指导（融合 gitnexus-guide），指导 AI 何时用 GitNexus、何时用 grep、每个工具/资源怎么用、如何组合使用
alwaysApply: true
enabled: true
updatedAt: 2026-08-10T00:00:00.000Z
---

## GitNexus MCP 强制规则与使用指导

### 适用范围（全场景强制）

本规则对**所有工作场景**生效，不限于编码：

| 场景 | 强制要求 |
|------|----------|
| 编码/重构 | 按"变更动作强制触发表"执行 |
| code review | 审查命中触发表动作的变更时，必须用 `impact`/grep 实证影响面，禁止仅凭 diff 推断"无影响"；数据流向/消费方结论必须有查询证据 |
| challenger 质疑 | 验证质疑点（调用方清单、消费方效果、影响范围）时必须实际执行 GitNexus/grep 查询取证，禁止凭文本推理下结论 |
| 推演/场景演练 | 推演涉及的调用链、依赖关系必须先经 `context`/`cypher` 确认，禁止基于想象的调用链推演 |
| 排错/调试、影响分析 | 按"工具选择条款"选择工具，结论须回到源码确认 |

子 agent / 被其他 skill 调用时同样受本规则约束，不得以流程简化为由跳过。

### 变更动作强制触发表

执行下列任一变更动作前（"提交前"行在提交动作前执行），**必须**先完成对应查询，影响不清禁止改代码：

| 变更动作 | 强制查询 |
|----------|----------|
| 修改方法签名（参数名/类型/默认值/返回值/增删参数） | `impact` 查调用方 + grep 查全部调用点，重点核对命名参数调用与未显式传参处 |
| 删除/移动符号 | `impact` + grep 字符串引用 |
| 跨文件重命名 | 固定顺序：`impact` → `rename(dry_run=true)` → 复核 → 正式执行 |
| 修改枚举值/常量/配置键 | grep 全局引用（图谱对此覆盖不全，禁止只依赖 `impact`） |
| 修改公共类/接口/基类 | `impact`（重点检查 risk、byDepth、affected_modules） |
| 修改 API handler/路由/对外契约 | `api_impact`；不可用则退回 `impact` + grep + 源码确认 |
| 修改方法体实现但改变返回语义/副作用（签名不变） | `impact`/`context` 查调用方，确认所有使用方语义仍成立 |
| 修改共享工具函数/中间件 | `impact` 确认所有使用方语义仍成立 |
| 提交前 | `detect_changes`，发现高风险符号必须补 `impact` |

**豁免场景**（不触发强制查询）：

- 仅修改注释、文档；日志文案需先 grep 确认未被告警/解析规则依赖
- 仅修改函数体内局部变量，且不改变行为契约
- 新增全新文件且尚无任何引用
- 私有方法且调用方全部在同文件内可见

从严判定：一次编辑同时包含豁免与非豁免动作时，按非豁免动作触发；无法确定是否命中豁免时，视为非豁免。

### 工具选择条款

- 结构关系（依赖、调用、影响、归属流程）→ **GitNexus 优先**；精确定位（字符串/字段/枚举/常量/配置键/具体实现）→ **grep 优先**。混合需求必须混合使用，禁止只依赖单一手段下结论。
- `context`：已知具体类名/函数名查上下游时必须优先使用；同名符号必须用 file_path/uid 消歧；禁止用于枚举常量、属性访问、纯文本定位。
- `impact`：修改关键目标前必须先执行；结果明显过少或与源码认知不一致时，必须视为覆盖不全，禁止据此认定"没有影响"。
- `cypher`：仅当 context/impact 无法满足需求时使用，用于方法级调用链追踪；禁止作为默认入口工具。
- `query`：仅在只知概念、不知符号名时使用；一旦确认具体符号，必须立即切换到 `context` 或 grep。
- `route_map`/`shape_check`/`tool_map`：低优先级，不作主工具；返回空结果时禁止据此推导"没有关系/没有影响"。

### 场景 → 工具映射（gitnexus-guide 融合）

以下为 **gitnexus-guide** 场景映射与操作流程，先据此判断任务类型、再选工具。任何任务**先读 `gitnexus://repo/{name}/context`**（代码库总览 + 索引新鲜度检查）；若提示索引过期，先跑 `node .gitnexus/run.cjs analyze` 再继续。

| 任务 | 入口工具/流程 |
|------|--------------|
| 理解架构 / "X 怎么工作的" | `query` 找流程 → `context` 深挖符号 → 读 `gitnexus://repo/{name}/process/{展示名}` 追踪完整调用链 |
| 爆炸半径 / "改 X 会破坏什么" | `impact`(upstream) → 读 affected_processes → `detect_changes` 复核 |
| 追踪 Bug / "为什么 X 挂了" | `query` 症状 → `context` 可疑点 → 读 process → `trace`(A→B 调用链) |
| 重命名/抽取/拆分/重构 | `impact` 摸依赖 → `rename(dry_run=true)` 预览 → 复核 → 正式执行 |
| 工具/资源/schema 参考 | 读 `gitnexus://repo/{name}/schema`（写 cypher 前必读） |

### 工具/资源能力参考（gitnexus-guide 融合）

**核心工具**：

- `query`：按概念找相关执行流（process 按相关度排序）。**结果偏泛，仅作探索起点**；确认具体符号后切 `context`/grep。
- `context`：单符号 360° 视图——入/出引用（CALLS/IMPORTS/EXTENDS/IMPLEMENTS 等）、参与流程、文件位置。同名符号返回排名候选，用 uid（零歧义）或 file_path/kind 消歧。
- `impact`：符号爆炸半径，按深度分组：**d=1 WILL BREAK（直接调用者）→ 优先审**；d=2 LIKELY AFFECTED；d=3 MAY NEED TESTING。含风险等级（LOW/MEDIUM/HIGH/CRITICAL）、受影响流程、受影响模块、每条边置信度。hub 符号（大量直接调用者）先 `summaryOnly:true` 看总数与风险，再按 depth 分页下钻（`limit`/`offset` 每个深度独立生效）。
- `trace`：两个符号间最短调用链，一次返回（含每跳文件:行、边类型、置信度）。`no_path` 时返回 `furthest`（链条断点：动态分派/反射/外部边界）+ `truncated:true`（若被遍历上限截断）——**用 furthest 定位断点，不要据此断言"无关系"**。
- `rename`：跨文件协调改名，返回置信度标注的编辑（graph 编辑高置信可放行，text_search 编辑需人工复核）。**必须先 `dry_run:true` 预览**。
- `detect_changes`：git diff → 受影响流程 + 风险。提交前必跑；发现高风险符号补 `impact`。
- `api_impact`：API 路由改前报告（消费方/中间件/响应形状漂移/风险）。`route_map`/`shape_check`/`tool_map` 为辅助，空结果不能推导"无关系"。
- `explain`/`pdg_query`（需 `analyze --pdg`）：污点分析（source→sink）与控制/数据依赖（CDG/REACHING_DEF）。
- `group_list`/`group_sync`/`list_repos`：多仓库分组与契约注册表；`list_repos` 分页（limit 默认 50 max 200，用 nextOffset 遍历全量）。

**资源**（轻量导航读，~100-500 tokens）：

- `gitnexus://repo/{name}/context`：统计、过期检查
- `gitnexus://repo/{name}/clusters`：功能模块（内聚度）｜`cluster/{name}`：模块成员
- `gitnexus://repo/{name}/processes`：全部执行流｜`process/{展示名}`：逐步调用链
- `gitnexus://repo/{name}/schema`：Cypher 图 schema（**写 cypher 前必读**）

**坑（实测）**：

- `process` 资源必须用**展示名**（如 `"ExecuteDeleteRelation → ExpandPath"`），**不能用内部 ID**（`proc_8_...`）——内部 ID 访问返回 not found。
- `query` 对"概念"检索偏泛（BM25+向量混合），主链路符号常散落在 `definitions` 而非 processes，别据此认定"没相关代码"，要落到源码确认。
- `detect_changes`/`impact` 对**测试文件符号、字符串引用、枚举/常量**覆盖不全，必须 grep 兜底。

### MCP 不可用时

**直接告知用户**，切换到 grep/源码阅读继续处理，**禁止伪造结果**，禁止主动输出运维修复方案。

此时"变更动作强制触发表"降级执行：对应查询改为 grep + 源码阅读必查，强制性不变。

### 核心约束

- **所有结论最终以源码为准**，禁止将图谱结果当最终事实。
- 修改前四步：定位目标 → 结构理解 → 影响评估 → 源码确认，影响不清禁止改代码。
- 执行任何命中触发表的变更前，若未完成对应查询，视为流程违规，必须停止编辑、先补做影响评估。
- 方法级查询稳定性弱于类级；属性访问、枚举、字符串引用覆盖不完整。
- 结果异常时先怀疑能力边界，不下否定结论。
