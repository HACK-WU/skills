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
