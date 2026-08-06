# e2e-testing 示例旅程

> 配套 `e2e-testing` 技能。演示"解析意图 → 拆 step → setup → 执行(含 api/db/mq/wait) → 断言 → teardown → 报告"的完整闭环。以下 YAML 为旅程定义，具体工具（API 客户端库、DB 驱动等）运行时按项目选择。

## 示例 1：用户注册并下单（API + DB + MQ + Wait）

**意图**：验证"注册 → 下单"全链路，且下单后真实落库、库存异步扣减、订单事件真实发布。

```yaml
scenario: 用户注册并下单
requirement_ref: REQ-register-order      # 绑定的需求/设计文档条目（见需求绑定）
env:
  env_name: staging
  base_url: "${ENV.API_BASE_URL}"        # 真实值来自 .env.e2e（回退 .env），禁止硬编码
credentials:
  token: "${ENV.API_TOKEN}"              # 同上，运行时会话内解析为完整 token
steps:
  - id: setup
    type: setup
    name: 清理历史测试数据
    config: { action: "DELETE FROM users WHERE email='e2e_test@x.com'" }
    # 危险操作，执行前会向用户确认

  - id: register
    type: api                      # 遵循 api-testing 约定
    name: 注册用户
    config:
      method: POST
      endpoint: "/users"
      body: { name: "e2e", email: "e2e_test@x.com" }
    produces: [user_id, token]
    assert: { result: true, code: 201, data_has: [id] }

  - id: create_order
    type: api
    name: 创建订单
    depends_on: [register]
    config:
      method: POST
      endpoint: "/orders"
      headers: { Authorization: "${ctx.credentials.token}" }
      body: { user_id: "${ctx.data.user_id}", item: "book" }
    produces: [order_id]
    assert: { result: true, code: 201, data_has: [id] }

  - id: db_check
    type: db
    name: 校验订单真实落库
    depends_on: [create_order]
    config:
      query: "SELECT status FROM orders WHERE id=${ctx.data.order_id}"
    assert: { row_exists: true, value_eq: { status: "created" } }

  - id: wait_inventory
    type: wait
    name: 等待库存异步扣减
    depends_on: [create_order]
    config:
      until: "inventory.service.decremented(order_id=${ctx.data.order_id})"
      timeout: 30
      poll: 2

  - id: mq_check
    type: mq
    name: 校验订单创建事件已发布
    depends_on: [create_order]
    config:
      op: consume
      topic: "order.created"
      match: { order_id: "${ctx.data.order_id}" }
      timeout: 10
    assert: { message_received: true }

  - id: teardown
    type: teardown
    name: 清理测试数据
    config: { action: "DELETE FROM orders, users WHERE user_id=${ctx.data.user_id}" }
```

**Context 流转说明**：
- `register` 产出 `user_id`/`token` → `create_order` 通过 `${ctx.data.user_id}` 与 `${ctx.credentials.token}` 引用。
- `create_order` 产出 `order_id` → 被 `db_check`/`wait_inventory`/`mq_check` 三个无相互依赖的 step 并行消费。
- `wait_inventory` 处理异步最终一致，避免 `db_check`/`mq_check` 偶发失败。

## 示例 2：UI + API 混合（真实页面下单后查 API 状态）

**意图**：用户在真实浏览器下单，再用 API 校验后端状态一致（UI 提取的值喂给 API 断言）。

```yaml
scenario: 浏览器下单并校验后端
steps:
  - id: ui_login
    type: ui
    name: 浏览器登录
    config: { action: goto, url: "${ctx.env.base_url}/login" }
    assert: { visible: true }

  - id: ui_create
    type: ui
    name: 页面提交订单并提取订单号
    depends_on: [ui_login]
    config: { action: extract, selector: ".order-id", extract_key: page_order_id }
    produces: [page_order_id]

  - id: api_verify
    type: api
    name: API 校验该订单存在
    depends_on: [ui_create]
    config:
      method: GET
      endpoint: "/orders/${ctx.data.page_order_id}"
    assert: { result: true, code: 200, data_eq: { id: "${ctx.data.page_order_id}" } }
    # 跨组件终态：页面看到的订单号 == API 返回订单号
```

## 示例 3：dry-run 预览（中等安全门禁）

执行前可先 dry-run，只打印将执行的步骤与解析后的 config，不落地：

```
🔍 DRY-RUN 预览（stage: staging，不执行真实操作）
  [1] setup    : DELETE FROM users WHERE email='e2e_test@x.com'   ⚠️ 写操作
  [2] api      : POST /users  → produces user_id, token
  [3] api      : POST /orders (user_id=${user_id}) → produces order_id
  [4] db       : SELECT status FROM orders WHERE id=${order_id}   ⚠️ 依赖 [3]
  [5] wait     : until inventory decremented (order_id=${order_id})
  [6] mq       : consume order.created (order_id=${order_id})
  [7] teardown : DELETE orders,users WHERE user_id=${user_id}      ⚠️ 写操作
确认无误后可去掉 dry-run 正式执行；写操作仍会在执行时逐个确认。
```

## 示例 4：敏感信息外部化（.env.e2e）

测试定义文件不含任何真实密钥/URL，全部走 `.env.e2e`：

```yaml
# tests/e2e/register_order.yaml（定义文件，无密）
scenario: 用户注册并下单
requirement_ref: REQ-register-order
env:
  env_name: staging
  base_url: "${ENV.API_BASE_URL}"   # 来自 .env.e2e（回退 .env）
credentials:
  token: "${ENV.API_TOKEN}"         # 来自 .env.e2e（回退 .env）
steps: [ ... ]                       # 同示例 1，但 URL/token 均为变量
```

```bash
# .env.e2e 优先（不入库，gitignore）—— 真实值在此
API_BASE_URL=https://staging.api.x.com
API_TOKEN=Bearer eyJxxxxxxxxxxxxxxxx

# 若不存在 .env.e2e，可回退使用项目根 .env（同样不入库，gitignore）
# .env.e2e.example（入库模板，供他人复制为 .env.e2e 或 .env）
API_BASE_URL=
API_TOKEN=
```

> AI 在阶段 2 搭建 Context 时优先读取 `.env.e2e`（不存在则回退 `.env`），填入 `ctx.env.base_url` / `ctx.credentials.token`；定义文件始终保持无密。

## 报告示例（对应示例 1）

```markdown
# E2E 测试报告：用户注册并下单

## 概览
- 通过步骤：6 / 总 7（teardown 不计入判定）
- 环境：staging.api.x.com（env_name: staging）
- 旅程状态：✅ PASS

## 明细
| 步骤 | 类型 | 状态 | 关键 evidence | 失败根因 |
|------|------|------|---------------|----------|
| setup | setup | ✅ | 清理 0 行 | — |
| register | api | ✅ | code=201, data.id=123 | — |
| create_order | api | ✅ | code=201, order_id=789 | — |
| db_check | db | ✅ | row exists, status=created | — |
| wait_inventory | wait | ✅ | 库存扣减 detected@4s | — |
| mq_check | mq | ✅ | 收到 order.created | — |
| teardown | teardown | ✅ | 删除 user=123,order=789 | — |

## 副作用清单
- 已创建：user_id=123, order_id=789
- 已清理：✅ teardown 已删除

## 建议
- 全链路通过，跨组件终态一致（落库 + 事件 + 库存扣减均符合预期）。
```

## 示例 5：动态体验验证（登录模块，分批）

**意图**：e2e 通过后，对"用户登录"功能做动态体验——白盒读代码规划分支覆盖，黑盒像真人操作评估体验质量与负面反馈。

### 前置门禁

```
✅ 对应 e2e 场景 login_scenario：PASS
   - register+login 旅程通过，登录返回 token 正确
→ 允许进入动态体验
```

### 批次 1 体验计划（白盒）

读 `src/auth/login.py`，识别分支：

```yaml
experience_plan:
  scope: "用户登录-核心分支"
  requirement_ref: REQ-login
  code_refs:
    - "src/auth/login.py:login() 主流程"
    - "src/auth/login.py:密码错误分支"
    - "src/auth/login.py:账号不存在分支"
    - "src/auth/login.py:账号锁定分支"
  experience_points:
    - id: login_normal
      branch: "密码正确"
      path_type: positive
      action: "用正确账号密码登录"
      expect:
        correctness: "返回 token + 用户基本信息"
        feedback_focus: "返回字段是否充分、是否含过期时间"

    - id: login_wrong_password
      branch: "密码错误"
      path_type: negative
      action: "故意输错密码"
      expect:
        correctness: "拒绝登录"
        feedback_focus: "错误提示是否清晰、是否暴露用户存在性、是否有剩余次数"

    - id: login_nonexistent_user
      branch: "账号不存在"
      path_type: negative
      action: "用不存在的账号登录"
      expect:
        correctness: "拒绝登录"
        feedback_focus: "提示是否与'密码错误'一致（防账号枚举）"

    - id: login_locked_account
      branch: "账号锁定"
      path_type: boundary
      action: "连续输错密码至锁定阈值后登录"
      expect:
        correctness: "账号被锁定，拒绝登录"
        feedback_focus: "锁定提示是否含解锁时间/方式"
```

### 批次 1 体验执行（黑盒）

agent 像真人操作（不读代码），观察记录：

```yaml
experience_record:
  - id: login_normal
    actual:
      correctness: "返回 token + {id, name}，无过期时间"
    assessment:
      correctness: pass
      feedback_completeness: "中——缺 token 过期时间，前端无法预判刷新"
      optimization: "建议返回 expires_in"

  - id: login_wrong_password
    actual:
      correctness: "拒绝登录 ✅"
      feedback: "返回'密码错误'，未提示剩余次数"
    assessment:
      correctness: pass
      error_friendliness: "良——清晰但无引导"
      optimization: "建议补'剩余 N 次尝试'，达阈值提示将锁定"

  - id: login_nonexistent_user
    actual:
      correctness: "拒绝登录 ✅"
      feedback: "返回'账号不存在'"
    assessment:
      correctness: pass
      error_friendliness: "差——暴露账号存在性，可被枚举"
      optimization: "🔴 应与'密码错误'返回一致提示，防账号枚举"

  - id: login_locked_account
    actual:
      correctness: "账号锁定 ✅"
      feedback: "返回'账号已锁定'"
    assessment:
      correctness: pass
      error_friendliness: "中——未告知解锁时间"
      optimization: "建议补'N 分钟后自动解锁'"
```

### 批次 1 体验小结（用户确认）

```
覆盖分支：4/4（核心分支全覆盖）
正确性：全通过
关键发现：
  🔴 账号不存在与密码错误提示不一致 → 可被枚举攻击
  🟡 登录成功缺 token 过期时间
  🟡 锁定提示缺解锁时间
→ 用户确认后，进入批次 2（如登录+记住设备、第三方登录等扩展分支）
```

### 体验报告（全部批次完成）

```markdown
# 动态体验报告：用户登录模块

## 前置门禁
- 对应 e2e 场景：login_scenario，PASS ✅

## 体验范围（分批）
- 批次1：登录核心分支（4 体验点）
- 批次2：登录扩展分支（3 体验点）

## 体验明细
| 体验点 | 路径类型 | 正确性 | 反馈全面性 | 错误反馈友好度 | 可优化点 |
|--------|----------|--------|-----------|---------------|----------|
| 正常登录 | 正面 | ✅ | 中（缺过期时间） | — | 补 expires_in |
| 错误密码 | 负面 | ✅ | — | 良（缺剩余次数） | 补剩余次数 |
| 账号不存在 | 负面 | ✅ | — | 差（暴露存在性） | 🔴 与密码错误一致化 |
| 账号锁定 | 边界 | ✅ | — | 中（缺解锁时间） | 补解锁时间 |

## 优化建议（按优先级）
1. 🔴 账号不存在/密码错误提示一致化，防账号枚举（安全+体验）
2. 🟡 登录成功返回补 expires_in，前端可预判 token 刷新
3. 🟡 锁定提示补"N 分钟后自动解锁"
4. 🟢 错误密码补"剩余 N 次尝试"

## 体验结论
- 覆盖分支：7 / 总 7
- 正确性：全通过（e2e 已保证）
- 体验质量：需优化（1 个安全问题 + 3 个体验改进）
- 负面路径反馈：不一致，存在账号枚举风险
```

> **注意**：本示例中 agent 在 D1 读 `login.py` 识别 4 个分支（白盒规划），在 D2 像真人登录操作、不读代码（黑盒体验），在 D3 依据"合理用户预期"评估反馈质量（判据不锚代码）。负面路径均为只读（输错密码/不存在账号），未做任何破坏性写操作。
