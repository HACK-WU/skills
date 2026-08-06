# e2e-testing 参考：Step 类型契约 / Context / 安全门禁

> 配套 `e2e-testing` 技能。AI 在编排旅程时应**照搬以下契约**，不要凭空发明 step 字段或取值语法。所有约定基于抽象步骤模型，具体工具运行时再选。

## 1. Step 统一契约

每个 step 为 YAML/字典对象，字段如下（带 `*` 为必填）：

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 步骤唯一标识，供 `depends_on` 与 `${ctx}` 引用 |
| `type` | ✅ | 步骤类型（见目录：`api/db/ui/mq/cli/wait/assert/transform/setup/teardown`） |
| `name` | ✅ | 人类可读名称 |
| `depends_on` | — | 上游 step id 列表，决定顺序；为空则可并行 |
| `config` | ✅ | 类型相关配置（见各类型小节） |
| `produces` | — | 执行后写入 `ctx.data` 的键列表 |
| `on_fail` | — | `abort`(默认) / `continue` / `retry` |
| `assert` | — | 内联断言（类型相关，见各类型） |
| `retry` | — | `on_fail: retry` 时：`{ max: 3, backoff: 1 }`（秒） |

**执行结果**（每个 step 产出，汇入报告与 Context）：
```yaml
{ status: pass|fail|skip, outputs: {...}, evidence: {...}, error: null }
```
- `outputs` 中 `produces` 列出的键写入 `ctx.data`。
- `evidence` 为可观测证据（如 HTTP code、查询行数、消息内容摘要），用于报告。

## 2. Context 解析（A+B 结合）

`ctx` 结构：
```yaml
ctx:
  env:         { base_url, env_name, ... }
  credentials: { token: "Bearer eyJ…", cookie: "session=abc…" }  # 运行时会话内可持完整值以发起请求；仅写入文件/展示用户时脱敏为前缀
  data:        { user_id: 123, order_id: 789, ... }
```
> 🔐 **敏感信息入口**：`ctx.env` / `ctx.credentials` 的值在阶段 2 由 env 文件注入（首选 `.env.e2e`，若不存在回退 `.env`，见 SKILL.md「敏感信息外部化」）。**定义文件（scenario/脚本）中不得出现真实 URL/密钥字面值**，只写 `${ENV.XXX}` 引用。
> 📌 **需求绑定**：Scenario 顶层携带 `requirement_ref` 指向需求/设计文档条目（见 SKILL.md「需求绑定」），断言判据来自规格而非代码内部实现。

**取值语法**：
- 完全限定：`${ctx.data.user_id}`、`${ctx.env.base_url}`、`${ctx.credentials.token}`。
- 简写：在 `config` 中写 `${user_id}`，解析时优先匹配 `ctx.data`，再回退 `ctx.env` / `ctx.credentials`。
- **`${ENV.XXX}` 先于 `${ctx.x}` 解析**：`${ENV.XXX}` 是来自 env 文件的环境变量占位符（首选 `.env.e2e`，回退 `.env`），在旅程启动（阶段 2 之前）即被解析为真实值并映射到 `ctx.env` / `ctx.credentials`（如 `ENV.API_BASE_URL` → `ctx.env.base_url`）；之后才进入下方 `${ctx.x}` 的统一解析。定义文件中只用 `${ENV.XXX}`，不直接写真实值。
- 解析时机：step **执行前**统一替换 `config` 中出现的所有 `${ctx.x}` 占位符。
- 未命中：标记为解析失败 → 该 step `abort`（除非 `on_fail: continue`）。

**顺序约束（B 部分）**：`depends_on` 决定拓扑序；未被依赖且无依赖他人者可并行执行。

## 3. Step 类型契约

> ⚠️ **条件是 AI 的语义意图，不是被引擎执行的谓词**：各类型中的 `until` / `match` / `expr` / `expect` 等是**给 AI 的语义指令**，由 AI 在运行时决定如何落地（如 `wait.until` 可转为轮询某 API 或查询 DB；`mq.match` 可转为消费指定 topic 并比对字段；`assert.expr` 由 AI 基于 `ctx` 求值）。它们不是由某解析器自动执行的表达式。

### 3.1 `api` —— 遵循 api-testing 约定
- `config`: `{ method, endpoint, headers?, query?, body?, auth? }`
- 响应归一化：`{ result, code, message, data }`（与 api-testing 一致）。
- `assert`（引用 api-testing 业务断言）：
  ```yaml
  assert:
    result: true
    code: 201
    data_has: [id, name]          # data 含这些字段
    data_eq: { status: "created" } # 取值等于
  ```
- `produces`: 从 `data` 中提取的键，如 `[user_id, token]`（提取 `data.id` → `ctx.data.user_id`）。
- 注意：单请求失败**不抛异常**，先判 `result` 再读 `data`。

### 3.2 `db` —— 真实落库校验/操作
- `config`: `{ driver?, query, params?, expect: row|none }`
- `assert`: `{ row_exists: true|false, value_eq: {...}, min_rows: 1 }`
- `produces`: 查询结果首行 / 受影响行数等。
- 注意：写操作（INSERT/UPDATE/DELETE）属**危险操作**，需走安全门禁确认。

### 3.3 `ui` —— 浏览器真实交互
- `config`: `{ action: click|fill|goto|extract, selector?, value?, url? }`
- `assert`: `{ visible?: bool, text_eq?: str, extracted?: <key> }`
- `produces`: `extract` 动作提取的 DOM 值。
- 注意：用真实浏览器（如 playwright）驱动，不 mock；提取的值写入 ctx 供后续 API 比对。

### 3.4 `mq` —— 消息发布/消费
- `config`: `{ op: publish|consume, topic, payload?, match?, timeout? }`
- `assert`: `{ message_received: true, match_eq: { order_id: "${ctx.data.order_id}" } }`
- `produces`: 收到的消息体。
- 注意：常用于校验"真实事件是否发出"（如 order.created）。

### 3.5 `cli` —— 命令行/脚本
- `config`: `{ command, args?, cwd?, timeout? }`
- `assert`: `{ exit_code: 0, stdout_contains?: str }`
- `produces`: `stdout` / `exit_code`。
- 注意：危险命令（rm/删除）需安全门禁确认。

### 3.6 `wait` —— 异步/最终一致轮询
- `config`: `{ until: <条件描述或 step 引用>, timeout: 30, poll: 2 }`
  - `until` 可为：对某 step 的断言重检、对外部条件的轮询谓词。
- 不写 `produces`（或产出轮询最终状态）。
- 注意：跨组件最终一致（库存扣减、异步任务）必须用 `wait`，不要直接断言。

### 3.7 `assert` —— 纯跨步校验（无副作用）
- `config`: `{ expr: "<基于 ctx 的判定>", expect: true }`
- 例：`expr: "ctx.data.db_status == ctx.data.api_status"`。
- 不产生副作用，不写 `produces`。

### 3.8 `transform` —— 纯计算/派生（无副作用）
- `config`: `{ set: { full_name: "${ctx.data.first} ${ctx.data.last}" } }`
- `produces`: `set` 中列出的键。
- 用于构造下游需要的派生值。

### 3.9 `setup` / 3.10 `teardown` —— 生命周期
- `setup.config`: 准备动作（清旧数据、建测试租户）。
- `teardown.config`: 清理动作（删测试数据）。
- 二者应**对称**；teardown 缺失且旅程有副作用 → 报告中强制提示。
- **幂等要求（必读）**：`setup` 与 `teardown` **必须幂等**，以支持旅程重复执行。
  - `setup` 应先处理"数据已存在"的情况（清旧/复用/带唯一后缀重命名），而非无条件插入导致二次运行报错。
  - `teardown` 应容错"数据已不存在"（删除失败不影响报告 PASS，仅记录），避免重复运行时因找不到数据而失败。

## 4. 失败语义

- **`abort`（默认）**：step 失败 → 停止旅程，剩余 step 标记 `skip`；报告标注 abort 点。
- **`continue`**：记录失败但继续（仅用于独立探针，如"顺带看下缓存"）。
- **`retry`**：按 `retry:{max,backoff}` 重试，全部失败才判定该 step 失败。用于已知抖动的异步场景。

### 4.1 异常分支约定（防半成品 / 重复副作用）

- **`setup` 失败即早退**：若存在 `setup` 步骤失败，**必须在产生任何真实副作用前 abort** 整个旅程（后继 step 一律 `skip`），不得在残缺环境下继续。报告须标注"setup 未完成，未产生真实副作用"。
- **`wait` 超时等同失败**：`wait` 达到 `timeout` 仍未满足条件 → 该 step `fail` → 默认 `abort`。不要把超时误判为"通过"。
- **`retry` 写操作需幂等**：`on_fail: retry` 用于**写/删**类 step（db 写、非幂等 api 写/删）时，会**重复产生真实副作用**（如重复建单）。必须确保操作幂等（带去重键 / 用 upsert / 先查后写），否则禁止使用 `retry`；无法保证幂等时改用 `abort` 并提示用户手动清理。

## 5. 安全门禁（中等强度）

> 🛑 **硬门禁（不可绕过）**：以下"危险操作确认"是**强制执行项，AI 不得以"用户可能同意""只是小操作""dry-run 已看"等理由跳过**。未获显式确认前，危险 step 一律不执行；这是底线，优先级高于任何效率考量。

- **危险操作确认（硬门禁）**：`db` 写操作、`cli` 删除类、`api` 非幂等写/删，执行前必须向用户展示将执行的操作并获显式确认（y/yes 等明确肯定）。确认前**绝不**发起该请求/命令。
- **环境告警**：`env.env_name == production` 时，强告警（红色提示）但不阻断；建议默认非生产。
- **dry-run 预览**：提供 dry-run 模式，只打印将执行的步骤序列与各 step 的 config（含解析后的 `${ctx}`），不落地任何真实操作。用户可在确认前审阅。
- **凭证脱敏**：`ctx.credentials` 在 AI 运行会话内存中可持有**完整** token/cookie（否则无法发起真实请求）；**仅在写入文件或展示给用户时**脱敏（只显前缀，如 `Bearer eyJ…`），不回显完整凭证。切勿将完整凭证写入 `ctx.data` 或任何落盘文件。
- **teardown 推荐**：有真实创建必须对称清理；缺失则报告显式提示手动处理。
- **确认交互格式示例**：
  ```
  ⚠️ 即将执行真实写操作（环境: staging）：
    [db] DELETE FROM orders WHERE user_id=123
  是否继续？[y/N]
  ```

## 6. 并行与拓扑

- 同一 `depends_on` 层、且彼此无数据依赖的 step 可并行执行。
- 解析 `${ctx.x}` 时确保上游 `produces` 已写入；跨并行 step 的依赖必须用 `depends_on` 显式声明，禁止隐式时序假设。

## 7. 动态体验验证契约

> 配套「动态体验验证」增强维度（见 SKILL.md）。本节定义体验计划与体验点的结构化契约，供 AI 在白盒规划阶段照搬。

### 7.1 体验计划（ExperiencePlan）

每个批次一份体验计划，YAML/字典表达"意图与结构"（同 Step 模型，非被引擎解析的 DSL）：

```yaml
experience_plan:
  scope: "用户登录模块"          # 本批体验范围（模块/功能域）
  requirement_ref: REQ-login     # 绑定的需求条目（同 Scenario）
  code_refs:                      # 白盒规划依据的代码位置
    - "src/auth/login.py:login()"
    - "src/auth/login.py:分支-密码错误"
  experience_points:              # 体验点清单
    - id: login_normal
      branch: "密码正确分支"
      path_type: positive         # positive 正面 / boundary 边界 / negative 负面
      action: "用正确账号密码登录"
      expect:                     # 预期体验（正确性锚需求，不锚代码）
        correctness: "返回 token + 用户信息"
        feedback_focus: "返回字段是否充分、是否含下一步引导"
    - id: login_wrong_password
      branch: "密码错误分支"
      path_type: negative
      action: "故意输错密码"
      expect:
        correctness: "拒绝登录，返回错误"
        feedback_focus: "错误提示是否清晰、是否暴露'用户存在'、是否有剩余次数"
```

### 7.2 体验点字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 体验点唯一标识 |
| `branch` | ✅ | 对应的代码分支/功能点（白盒识别结果） |
| `path_type` | ✅ | `positive`（正面）/ `boundary`（边界）/ `negative`（负面） |
| `action` | ✅ | 体验动作描述（像真人的操作） |
| `expect.correctness` | ✅ | 预期正确性（锚需求规格，不锚代码） |
| `expect.feedback_focus` | — | 体验关注点（反馈全面性/友好度等） |

### 7.3 体验记录（执行后产出）

```yaml
experience_record:
  id: login_wrong_password
  status: observed                # observed 已观察 / skipped
  actual:                         # 实际观察到的输出
    correctness: "拒绝登录 ✅"
    feedback: "返回 '密码错误'，未提示剩余次数，未暴露用户存在性"
  assessment:                     # 四维评估
    correctness: pass
    feedback_completeness: "中等——缺剩余次数"
    error_friendliness: "良——清晰但不具引导性"
    optimization: "建议补充'剩余 N 次尝试'提示"
```

### 7.4 评估四维度细则

| 维度 | 判断依据 | 举例 |
|------|----------|------|
| 正确性 | 需求规格（给定 X 应得到 Y） | 登录成功返回 token ✅ |
| 反馈全面性 | 合理用户预期：信息是否够用、有无下一步引导 | 登录成功只返回 token 无用户信息 → 不够全面 |
| 错误反馈友好度 | 负面路径下：提示是否清晰、可操作、不泄露敏感信息 | "密码错误"清晰但无剩余次数 → 可优化 |
| 可优化点 | 即使正确，体验改善空间 | 列表返回字段过多、步骤冗余、缺引导 |

> **判据来源铁律**：正确性锚需求规格；其余三维基于"合理用户预期"，**均不锚代码实现**。读代码只在 D1 规划阶段为识别分支，D2/D3 执行评估时不读代码。

> **"合理用户预期"基准**：判据参考①需求文档的交互约定 ②行业惯例（如"登录失败不应暴露用户存在性"是安全共识、"错误提示应含可操作的下一步"是体验惯例）。无明确约定时标注 `[主观判断]` 供人工复核。
