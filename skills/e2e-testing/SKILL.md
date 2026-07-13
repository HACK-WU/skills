---
name: e2e-testing
description: 对真实运行系统执行端到端验证的技能。按业务旅程编排多类型步骤（api/db/ui/mq/cli/wait/assert/transform/setup/teardown，具体用哪些由被测功能决定），通过跨步骤共享 Context 串联状态，验证跨组件最终一致状态。涉及 HTTP API 步骤时遵循 api-testing 的响应结构与报告约定。当用户要求"跑一遍完整流程看看对不对""真实链路测试""端到端验证""检查跨系统终态"时使用。
---

# 端到端真实操作测试（e2e-testing）

## 概述

**目的**：把"端到端验证"从手点多系统、肉眼比对，变成"AI 读旅程、编排步骤、跑真实操作、验跨组件终态"。针对**真实运行中的系统**执行完整业务旅程（注册→下单→支付→查状态…），验证数据在多个组件间最终一致，而非单接口的连通性。

**与 api-testing 的关系**：`api-testing` 聚焦**单个 HTTP 接口**的"连通性 + 业务断言"，彼此隔离、数据是构造的。本技能**不重复实现接口测试**，而是在 `api` 类步骤上**仅引用** `api-testing` 已文档化的约定（响应结构、业务断言、凭证脱敏、报告风格），把其能力作为 e2e 编排中的一个动作类型。具体约定见下文「与 api-testing 的约定引用」与 `reference.md`。

**使用场景**：
- 用户说"帮我跑一遍完整下单流程""做个端到端验证""真实链路测试一下"
- 需要验证跨系统终态：下单后 DB 是否落库、消息是否发出、库存是否扣减
- 一个操作的输出要喂给后续操作（如建出的 user_id 用于下单）
- 涉及真实副作用且需要 setup/teardown 与确认门禁

## 核心概念

> 💡 **本技能是给 AI 的编排规范，而非被独立引擎解析执行的 DSL**：下方 `Step` / `Context` / `${ctx.x}` 是 AI 的**认知与编排框架**。AI 在运行时按约定**自行选择工具并实现每一步**（如 `api` 步骤选 httpflex 或项目自有客户端、`db` 步骤选对应驱动），而非由某解析器机械读取 YAML。文档中的 YAML 示例仅用于表达"意图与结构"。

### 1. Scenario（业务旅程）
一次完整验证的目标，例如"用户注册并下单"。包含：`env`（环境信息）、`credentials`（脱敏后的凭证）、有序的 `steps` 列表。

### 2. Step（抽象可扩展步骤）
统一的步骤契约，使不同类型的动作能被同一引擎编排。完整字段见 `reference.md`：

```yaml
- id: create_order
  type: api                      # 步骤类型（见下方目录）
  name: 创建订单
  depends_on: [register]        # 顺序/并行依赖（决定执行次序）
  config: { ... }               # 类型相关配置
  produces: [order_id]          # 执行后写回 Context 的键
  on_fail: abort                # abort(默认) / continue / retry
  assert: { ... }               # 可选内联断言
```

### 3. Context（跨步骤状态流转）—— 本技能灵魂
一张**跨步骤共享的状态字典**，让真实操作的输出在旅程中流动：

```
ctx = {
  env:        { base_url, env_name, ... },
  credentials:{ token, cookie, ... },   # 运行时会话内可持完整凭证以发起真实请求
  data:       { user_id, order_id, ... } # 业务实体，由 step.produces 写入
}
```
> ⚠️ **凭证脱敏边界**：`ctx.credentials` 在 AI 运行会话内存中可持有**完整** token/cookie（否则无法发起真实请求）；**仅在写入文件或展示给用户时**做脱敏（只显前缀，如 `Bearer eyJ…`）。切勿将完整凭证写入 `ctx.data` 或任何落盘文件。

取值采用 **A+B 结合**：
- **A. 依赖顺序**：`depends_on: [register]` 决定执行先后，并支持无依赖步骤并行。
- **B. 占位符取值**：step 配置中用 `${ctx.data.user_id}`（或简写 `${user_id}` 优先解析 `ctx.data`）引用上游产出，执行前统一解析。
- 详见 `reference.md §Context`。

### 4. Setup / Teardown（生命周期）
- `setup`：旅程前准备（建测试租户、清旧数据、起依赖服务）。
- `teardown`：旅程后清理（删测试数据、释放资源）。**真实操作有副作用时强烈建议对称清理**；缺失时必须在报告中提示。
- **必须幂等**：二者都应支持旅程重复执行——`setup` 先处理"数据已存在"、`teardown` 容错"数据已不存在"，避免二次运行报错或污染。详见 `reference.md §3.9/3.10`。

### 5. Safety Gate（安全门禁，中等强度）
- 写/删等**危险操作需用户显式确认**后才执行。
- 不强制 dry-run，但提供 **dry-run 预览**（只打印将执行的操作，不落地）。
- **环境可指定**；若指向生产 → **强告警**但不硬阻断。
- **凭证脱敏**：token/cookie 只在 Context 与报告中存前缀（如 `Bearer eyJ…`），不回显完整凭证。
- 详见 `reference.md §安全门禁`。

## 工作流程（7 阶段）

```
[0]解析意图 → [1]拆 step+依赖 → [2]setup+建 Context → [3]按序/并行执行
   → [4]跨步断言+终态校验 → [5]teardown → [6]出 journey 报告
```

### 阶段 0：解析测试意图
从用户描述/设计文档提取：目标业务旅程、涉及的环境与凭证（缺失须确认，不臆测）、期望终态（如"订单落库且库存-1"）。

### 阶段 1：拆解为 Scenario + Steps
将旅程拆成步骤，**标注每个 step 的 `type` 与 `depends_on`**，并标出哪些 step 产出哪些 key（`produces`）供下游 `${ctx.x}` 引用。具体用哪些类型由**被测功能**决定（不预设固定集）。

### 阶段 2：搭建 Context（执行 setup）
先跑 `setup` 类步骤，初始化 `ctx.env` / `ctx.credentials` / `ctx.data`。

### 阶段 3：按序 / 并行执行 Steps
- 按 `depends_on` 拓扑排序；无依赖链的步骤可并行。
- 执行前解析 `${ctx.x}` 占位符。
- `api` 类步骤遵循 api-testing 约定发请求并做业务断言。
- 异步/最终一致处用 `wait` 步骤轮询，直到条件满足或超时。
- 失败处理：默认 `abort` 整个旅程（后续步骤依赖前置状态）；独立探针标 `continue`；抖动标 `retry`。

### 阶段 4：跨步断言 + 终态校验
- 每个 step 的内联 `assert` 在自身执行后校验。
- 独立的 `assert` 步骤可做跨 step 的终态比对（如"DB 状态 == API 返回状态"）。
- `db` / `mq` 类步骤直接验证真实落地（落库行、发布事件）。

### 阶段 5：Teardown 清理
执行 `teardown` 类步骤，回滚/清理真实副作用；缺失则报告中显式提示。

### 阶段 6：出 Journey 级报告
按下方模板输出（风格对齐 api-testing）。

## Step 类型目录（概览，契约见 reference.md）

| 类型 | 用途 | 典型 produces |
|------|------|---------------|
| `api` | HTTP 调用（遵循 api-testing 约定） | 响应 `data` 中的业务键 |
| `db` | 数据库查询/执行，校验真实落库 | 查询结果/受影响行 |
| `ui` | 浏览器交互（真实页面） | 提取的 DOM 值/状态 |
| `mq` | 消息发布/消费，校验事件真实发出 | 收到的消息 |
| `cli` | 命令行/脚本执行 | stdout/exit code |
| `wait` | 轮询条件直到满足/超时（异步最终一致） | 轮询结果 |
| `assert` | 纯跨步校验，无副作用 | 无 |
| `transform` | 纯计算/派生值写入 ctx，无副作用 | 派生键 |
| `setup` | 旅程前准备 | 测试数据/环境句柄 |
| `teardown` | 旅程后清理 | 无 |

> 目录为**示例且可扩展**：被测功能需要其他真实操作类型时，按统一 Step 契约新增即可。

## 与 api-testing 的约定引用

当 `step.type == api` 时，**引用**（不运行时调用）`api-testing` 技能（`skills/api-testing`）已文档化的规范：

1. **响应结构**：归一化为 `{ result: bool, code: int, message: str, data: any }`；失败也返回结构不抛异常。
2. **业务断言**：不仅看 `code`，还要校验 `data` 的**字段存在性 / 类型 / 取值**（可取嵌套 `data.user.name`）。**仅借鉴该断言思路**（校验 data 而非只看 code），具体 HTTP 客户端由被测项目的工具决定，**不强依赖 httpflex**——可用的库都可（项目自有客户端、requests、httpx 等），只要产出归一化的 `{result,code,message,data}` 结构供本技能做 `assert` 即可。
3. **凭证脱敏**：token/cookie 只显前缀，不回显完整凭证。
4. **报告风格**：明细表 + 失败根因，与本技能 journey 报告对齐。

> 若项目已用 httpflex-py，可直接照搬 `api-testing/reference.md` 的客户端模板生成 `api` 步骤客户端；否则按项目既有方式发请求，只需遵循上述响应结构与业务断言约定。本技能只负责编排与状态流转，不绑定具体 HTTP 实现。

## 报告模板（Journey 级）

```markdown
# E2E 测试报告：{scenario 名}

## 概览
- 通过步骤：X / 总 Y
- 环境：staging.api.x.com（env_name: staging）
- 旅程状态：✅ PASS / ❌ FAIL（abort 于 step: create_order）

## 明细
| 步骤 | 类型 | 状态 | 关键 evidence | 失败根因 |
|------|------|------|---------------|----------|
| register | api | ✅ | code=201, data.id=123 | — |
| create_order | api | ✅ | code=201, order_id=789 | — |
| db_check | db | ✅ | row exists, status=created | — |
| mq_check | mq | ❌ | 未收到 order.created | 事件未发布/主题不匹配 |
...

## 副作用清单（供审计/teardown）
- 已创建：user_id=123, order_id=789
- 已清理：teardown 删除上述数据 ✅ / ⚠️ 未清理，请手动处理

## 建议
- mq_check 失败：检查订单服务是否确实发布 order.created 事件。
```

## 常见陷阱

- **忘记 `produces`/`depends_on`**：下游 `${ctx.x}` 解析失败 → 每个产出 step 必须声明 `produces`，消费方必须 `depends_on` 上游。
- **把 e2e 当单元测试写**：e2e 验证真实副作用与跨组件终态，不要 mock 内部依赖。
- **异步未用 `wait`**：下单后库存扣减是异步的，直接 `db` 校验会偶发失败 → 用 `wait` 轮询。
- **生产环境误操作**：指向生产时务必强告警 + 危险操作确认；优先在非生产环境跑。
- **凭证泄露**：报告/日志只存脱敏前缀，不要把完整 token 写进 `ctx.data` 或文件。
- **teardown 缺失**：有真实创建就必须有对称清理，否则污染测试数据。

## 更多资源

- 各 Step 类型完整契约、Context 解析、安全门禁细节：[reference.md](reference.md)
- 完整示例旅程（注册下单 + UI 混合）：[examples.md](examples.md)
- HTTP API 步骤约定来源：[api-testing](../api-testing/SKILL.md)
