# Code Review 典型场景示例

> 本文件是 [SKILL.md](SKILL.md) 的配套示例库，展示各语义一致性维度的典型问题模式与修复方向。
> 示例仅用于说明审查方法论，**禁止将示例中的代码/结论直接套用到实际审查对象上**。

## 场景 1：注释说"缓存"，代码却没缓存

```python
# semantic_intent: 使用缓存避免重复计算斐波那契数列
_fib_cache: dict[int, int] = {}

def fibonacci(n: int) -> int:
    """计算第n个斐波那契数，结果会被缓存以提升性能。"""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)  # ❌ 递归但未查缓存
```

🔑 语义一致性分析：docstring 声明缓存但实现未使用缓存 → 🏚️ 语义正确，实现不完整（P0）

```python
# ✅ 更优实现
_fib_cache: dict[int, int] = {}

def fibonacci(n: int) -> int:
    """计算第n个斐波那契数，结果会被缓存以提升性能。"""
    if n in _fib_cache:          # ✅ 命中缓存直接返回
        return _fib_cache[n]
    if n <= 1:
        _fib_cache[n] = n
        return n
    result = fibonacci(n - 1) + fibonacci(n - 2)
    _fib_cache[n] = result       # ✅ 结果写入缓存
    return result
```

## 场景 2：commit message 说"修复"，实际只是"绕过"

```python
def get_user_profile(user_id: str) -> dict:
    """根据用户ID获取用户档案信息。"""
    users = db.query("SELECT * FROM users WHERE id = %s", (user_id,))
    try:
        return users[0]
    except IndexError:
        return {}  # ❌ 静默返回空字典，掩盖根因
```

🔑 语义一致性分析：commit 称"修复空列表问题"，实际是静默吞掉异常 → 🏚️ 语义正确，实现方向错误（P0）

```python
# ✅ 更优实现: 显式返回 Optional，让调用方决定如何处理
def get_user_profile(user_id: str) -> Optional[dict]:
    """根据用户ID获取用户档案，未找到时返回 None。"""
    users = db.query("SELECT * FROM users WHERE id = %s", (user_id,))
    if not users:
        logger.info(f"User not found: {user_id}")
        return None
    return users[0]
```

## 场景 3：函数名暗示"验证"，实际做了"转换"

```python
def validate_phone_number(phone: str) -> str:
    """验证手机号是否合法。"""
    phone = phone.strip().replace("-", "").replace(" ", "")
    if not phone.startswith("+"):
        phone = "+86" + phone
    return phone  # ❌ 返回格式化后的号码，不是验证结果
```

🔑 语义一致性分析：函数名 validate_ 暗示布尔判断，实际做了格式化转换 → ⚖️ 命名与实现的职责错位（P1）

```python
# ✅ 更优实现: 拆分为两个函数，各司其职
def normalize_phone_number(phone: str) -> str:
    """将手机号标准化为国际格式（+86xxxxxxxxx）。"""
    phone = phone.strip().replace("-", "").replace(" ", "")
    if not phone.startswith("+"):
        phone = "+86" + phone
    return phone

def is_valid_phone_number(phone: str) -> bool:
    """检查标准化后的手机号是否符合格式要求。"""
    phone = normalize_phone_number(phone)
    return bool(re.match(r"^\+86\d{11}$", phone))
```

## 场景 4：注释过时，代码已变

```python
def process_order(order: dict) -> dict:
    # TODO: 这个函数只处理国内订单，国际订单以后再说  ← 注释说"只处理国内"
    if order.get("country") == "CN":
        return domestic_process(order)
    else:
        return international_process(order)  # ❌ 但代码已支持国际订单
```

🔑 语义一致性分析：TODO 注释说"只处理国内订单"，代码已实现国际订单处理 → 📝 实现正确，语义描述过时（P1）

```python
# ✅ 修复: 更新注释以反映当前实现
def process_order(order: dict) -> dict:
    """处理订单，根据国家自动路由到国内/国际处理流程。"""
    if order.get("country") == "CN":
        return domestic_process(order)
    else:
        return international_process(order)
```

## 场景 5：上层是"事件维度"，却复用了"实体维度"的下游查询

```python
# ❌ 上层语义："最近 N 个时间单位内发生过 X 事件的主体"
#   下游对象：EntityQueryHandler——其时间过滤是"实体在窗口内存活"
#   形参对得上、能跑通，语义维度却完全不同
search = EntityQueryHandler(start_time, end_time).get_search_object()
search.aggs.bucket("subject", "terms", field="subject_field", ...)
```

🔑 语义一致性分析：

- 上层语义维度：**事件时点**（最近 N 个时间单位发生 X）
- 下游对象语义维度：**实体生命周期窗口**（实体在 [start, end] 期间存活）
- 两者参数能对齐但**概念不可传递** → 🧭 调用关系语义不可传递（P0）
- 错误的修补方向：在 `EntityQueryHandler` 上加 "filter by event_time" 参数——治标不治本，原对象的存在前提仍是"实体集合"而非"事件流"

```python
# ✅ 更优方向：换到承载"事件"语义的抽象上（活动日志 / 审计表 / 变更流 / 消息流）
search = EventLogModel.search() \
    .filter("term", event_type=TARGET_EVENT_TYPE) \
    .filter("range", event_time={"gte": start_time, "lte": end_time}) \
    .filter("terms", scope_field=scope_values)  # 自行处理权限/范围
search.aggs.bucket("subject", "terms", field="subject_field", ...)
```

🔑 **方法论提炼**：
当上层语义是"**最近 N 个时间单位发生 X 事件**"这类事件维度时，应在项目中寻找承载"事件流"语义的抽象（活动日志、审计表、变更流、消息队列）。**不要**把"实体集合 + 时间过滤"当作"事件流"使用——前者过滤的是实体的存在状态，后者过滤的是事件的发生时点，看似都能"按时间筛"，语义维度上完全不同。该方法论可推广到所有"调用方-被调方"语义维度错配的场景（时间/集合/一致性/边界/单位/权限/排序，见 reference.md 维度 0.5 的隐式语义维度清单）。

## 场景 6：只修了正常参数路径，异常参数路径语义被破坏

```python
# ❌ 原始代码：根据用户类型返回不同的处理结果
def get_user_discount(user_type: str, order_amount: float) -> float:
    """根据用户类型计算订单折扣金额。所有用户类型均返回折扣金额。"""
    if user_type == "vip":
        return order_amount * 0.8
    elif user_type == "svip":
        return order_amount * 0.7
    else:
        return order_amount  # 普通用户无折扣
```

```python
# ❌ 修改后：为 VIP 增加了阶梯折扣，但返回语义在参数路径间发生了分裂
def get_user_discount(user_type: str, order_amount: float) -> float:
    """根据用户类型计算订单折扣金额。所有用户类型均返回折扣金额。"""
    if user_type == "vip":
        if order_amount >= 1000:
            return order_amount * 0.7   # 大额订单享更高折扣
        return order_amount * 0.8
    elif user_type == "svip":
        return order_amount * 0.7
    else:
        return 0.0  # 🐛 修改：普通用户改为返回 0.0（意图：无折扣）
```

🔑 条件路径语义一致性分析（维度 0.7）：

| 参数路径 | 修改前返回 | 修改后返回 | 语义变化 |
|----------|-----------|-----------|---------|
| `user_type="vip"`, `amount=2000` | `1600.0`（折扣后金额） | `1400.0`（折扣后金额） | ✅ 语义一致：折扣后金额 |
| `user_type="vip"`, `amount=500` | `400.0`（折扣后金额） | `400.0`（折扣后金额） | ✅ 语义一致 |
| `user_type="svip"` | `700.0`（折扣后金额） | `700.0`（折扣后金额） | ✅ 语义一致 |
| `user_type="normal"` | `1000.0`（原价 = 折扣后金额） | `0.0` | ❌ 语义分裂 |

- **路径间语义不一致**：VIP / SVIP 路径返回"折扣后金额"，普通用户路径改为返回"折扣额"——同一函数，不同参数路径下返回值的**含义**发生了变化
- **调用方风险**：调用方 `total = get_user_discount(type, amount)` 在普通用户场景下会得到 `0.0`，导致订单总金额变为 0
- **维度 0.6 关联**：docstring 说"返回折扣金额"，方法整体语义在参数路径间不再自洽

```python
# ✅ 修复：保持所有参数路径的返回语义一致
def get_user_discount(user_type: str, order_amount: float) -> float:
    """根据用户类型计算订单折扣后的应付金额。

    Returns:
        折扣后的应付金额。普通用户返回原价（即无折扣）。
    """
    if user_type == "vip":
        if order_amount >= 1000:
            return order_amount * 0.7
        return order_amount * 0.8
    elif user_type == "svip":
        return order_amount * 0.7
    return order_amount  # 普通用户返回原价，语义仍为"应付金额"
```

🔑 **方法论提炼**：
当函数包含参数驱动的分支逻辑时，**每条参数路径都是一条独立的语义通道**。修改某条路径后必须验证：
1. 该路径自身的返回语义是否仍与方法整体语义一致（不是只看"值对不对"，而是看"含义变没变"）
2. 不同路径之间的返回语义是否仍互相一致（所有路径返回的应该是"同一种东西"）
3. 调用方在不同参数下对返回值的语义期望是否仍被满足

## 场景 7：PR Review 模式

**用户输入**："code review 一下 PR 10862"

**AI 执行流程**：

1. **识别 PR Review 模式**：检测到 "PR" + 数字编号
2. **获取 PR diff**：执行 `gh pr diff 10862`
3. **获取 PR 上下文**：执行 `gh pr view 10862` 获取标题、描述、目标分支
4. **标准 Review 流程**：按阶段 0-6 执行完整审查

**示例输出片段**：

```
📋 Code Review Report

PR: #10862 "feat: 添加用户登录验证码功能"
目标分支: main
变更文件: src/auth/login.py, src/auth/captcha.py, tests/test_login.py
...
```

**用户输入**："review 对 develop 的改动"

**AI 执行流程**：

1. **识别目标分支**：用户指定 develop
2. **获取 diff**：执行 `git diff develop...HEAD`
3. **标准 Review 流程**

## 场景 8：无参数函数的执行场景分析（维度 0.8）

```python
# 修改前
def init_database():
    """初始化数据库连接池和表结构。"""
    global db_pool
    db_pool = create_pool(DB_CONFIG)
    db_pool.execute(CREATE_TABLES_SQL)

# 修改后
def init_database():
    """初始化数据库连接池和表结构。"""
    global db_pool
    db_pool = create_pool(DB_CONFIG)
    # 🐛 修改：移除了表结构创建，假设表已存在
    # db_pool.execute(CREATE_TABLES_SQL)
```

🔑 执行场景语义一致性分析：

**场景识别**：

| 场景 ID | 场景名称 | 场景描述 | 识别依据 |
|---------|----------|----------|----------|
| S1 | 首次部署 | 全新环境，数据库为空 | 调用时机：首次部署 |
| S2 | 正常重启 | 数据库已有表结构 | 调用时机：服务重启 |
| S3 | 数据库迁移后 | 表结构已通过迁移工具创建 | 业务上下文：使用了 migration 工具 |
| S4 | 测试环境 | 可能需要重建表 | 外部状态：测试数据库 |

**修改代码的场景覆盖分析**：

| 场景 ID | 修改代码是否执行 | 执行结果 | 语义一致性 | 分析说明 |
|---------|------------------|----------|------------|----------|
| S1 | ✅ 执行 | 跳过建表 | ❌ | 首次部署时表不存在，连接池创建成功但后续查询会失败 |
| S2 | ✅ 执行 | 跳过建表 | ✅ | 表已存在，跳过建表不影响功能 |
| S3 | ✅ 执行 | 跳过建表 | ✅ | 迁移工具已建表，跳过合理 |
| S4 | ✅ 执行 | 跳过建表 | ⚠️ | 测试环境可能需要重建表，需确认是否有其他机制 |

**问题场景聚焦展示**：

**[ES1]** 首次部署场景语义破坏

- 🏷️ 场景：首次部署 (S1)
- 📍 涉及：`src/db/init.py:8`（注释掉 `db_pool.execute(CREATE_TABLES_SQL)`）
- 🔍 问题分析：
    - 该场景下的执行路径：`init_database()` → `create_pool()` → 跳过建表 → 返回
    - 与预期语义的偏差：docstring 说"初始化数据库连接池和表结构"，但修改后只做了连接池初始化
- 💡 修复建议：
    - 方案 A：保留建表逻辑，但使用 `CREATE TABLE IF NOT EXISTS` 使其幂等
    - 方案 B：拆分为两个函数 `init_connection_pool()` 和 `ensure_tables()`，明确职责
    - 方案 C：在部署文档中明确要求先执行数据库迁移，再启动服务

🔑 **方法论提炼**：
对于无参数函数，分析重点应放在**调用时机**和**外部状态**上：该函数在什么时机被调用（启动/运行/关闭）？调用时外部依赖处于什么状态（首次使用/已有数据/异常状态）？修改是否影响了这些不同场景下的语义？

## 场景 9：微小变更的快速模式输出

**用户输入**："看下我工作区这几行改动"（diff 净增+净删共 3 行）

**AI 执行流程**：

1. 阶段 0 门禁 → 阶段 1 获取 diff + 读取完整文件
2. 判定快速模式（≤5 行）→ 跳过专家查询、**跳过功能意图的用户确认交互**（AI 推测语义并标注置信度后直接继续）
3. 串行执行维度 0 + 1 + 2，不并行、不展开完整报告模板

**示例输出（精简报告）**：

```markdown
## ⚡ Code Review（快速模式）

**变更**: `utils/retry.py` 第 42-44 行（3 行）
**AI 推测意图**: 将重试间隔从固定 1s 改为指数退避（置信度 🟢 高，未经确认，如有偏差请指出）

**发现问题**:
1. 🟡 P1 `utils/retry.py:43` — 指数退避无上限，极端情况下单次等待可达数分钟。
   建议：`min(base * 2 ** attempt, MAX_BACKOFF)` 设置上限。

无 P0 问题。安全性 ✅ / Bug 风险 ⚠️（上述 1 项）/ 语义一致性 ✅
```
