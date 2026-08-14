# 强关联记录参考

详细 ki 写入 API 与强关联识别细则。主指令见 SKILL.md。查询强关联记录请调用 `use_skill("relation-lookup")`。

## ki 写入与分组

本 skill 用 ki 的 **group 分组**机制（非零散 `ki_store`），保证强关联按功能模块归档、可被 `ki_query_group` 整组检索。

### 核心 API（写入侧）

| API | 用途 | 关键参数 |
|-----|------|----------|
| `ki_sync_relation` | 写入单条强关联原子（推荐） | `scope`（项目标识）、`group`（模块分组路径，支持 `/` 嵌套）、`relation`（关联名，用 `-` 连接两端，如 `A-B`）、`module_info`（Markdown 内容）、`tags`（统一为 `relation`） |
| `ki_store` | 简单文本向量存储（无分组） | `scope`、`text`、`tags` |
| `ki_manage_index_create` | 手动建 group 节点 | `scope`、`name`、`parent` |
| `ki_manage_index_list` | 列出所有 scope 及顶层 group | - |

### 分组约定

- **scope**：项目标识，与 `expert-team` 专题记忆所用 scope 一致
- **group 父目录**：**统一固定名「关联关系」**（不复用专题记忆名称，作为所有强关联记录的根分组）
- **group 子目录**：**按功能模块动态创建**，`关联关系/{功能模块名}`（如 `关联关系/支付系统`）；先 `ki_manage_index_list` 查已有子分组，有则复用，无则新建
- **relation**：关联名，用连字符 `-` 连接两端模块名（如 `订单服务-支付通知服务`），不含 `→` 等特殊字符
- **module_info**：Markdown 格式的关联描述（见写入示例）
- **tags**：**统一为 `relation`**（固定，写入时每条强关联都带，供查询侧用 `tags="relation"` 过滤收窄范围）

### 写入示例（单向）

```text
ki_sync_relation
  scope:  my-project
  group:  关联关系/支付系统
  relation: 订单服务-支付通知服务
  tags:  relation
  module_info:
    [强关联] 订单服务 与 支付通知服务
    强度：必改——改订单的对外数据结构，支付通知必须连带改；改支付通知的内部实现，订单不用管
    原因：支付通知消费订单的金额/状态字段，共享订单 DTO 结构

    订单服务端：
    - OrderService @ orders/service.py
    - OrderDTO @ orders/dto.py
    - OrderRepository @ orders/repository.py

    支付通知服务端：
    - PaymentNotifier @ payment/notifier.py
    - NotificationTemplate @ payment/template.py
    - MessageDispatcher @ payment/dispatcher.py
```

### 写入示例（双向：两条依赖线方向相反）

当 A 既是 B 的结构之源（B 消费 A 生成的数据），又是 B 的语义依赖方（A 去适配 B 定义的行为）时，两条线都是强关联，分两条影响线写（影响方向：改左端 → 右端必改），不得漏记反方向：

```text
ki_sync_relation
  scope:  my-project
  group:  关联关系/查询系统
  relation: 查询门面-查询构建器
  tags:  relation
  module_info:
    [强关联] 查询门面 与 查询构建器

    影响线1：改门面的 instant/end_time/step 参数语义 → 构建器必改；原因：构建器对齐补偿逻辑适配门面的 instant 行为语义
    影响线2：改构建器输出的查询参数结构/契约 → 门面必改；原因：门面消费构建器链式 API 组装的参数结构

    原因：语义线与契约线方向相反，均为强关联

    门面端：
    - UnifyQuery.query_data @ query.py
    - UnifyQuery._query_unify_query @ query.py

    构建器端：
    - UnifyQuerySet @ builder.py
    - UnifyQuerySet.instant @ builder.py
```

> 单向示例里的"改 B 不用管"已限定为"改内部实现不用管"；若改的是 B 的对外契约/数据结构/参数，则 B 的消费方（A）仍需跟着改——这正是双向示例要覆盖的情况。

> `relation` 名称用连字符 `-` 连接两端模块名（如 `订单服务-支付通知服务`），不含 `→` 等特殊字符。
> `module_info` **禁用 yaml 元数据和 `##`/`###` 等 md 标题、`|` 表格**——统一纯文本 + `-` 列表，保证 ki-search 向量检索效率。

## 强关联识别细则

### 高概率强关联（重点识别）

| 模式 | 判断依据 | 典型 |
|------|----------|------|
| 数据源 → 消费端 | 消费方读取数据结构/字段，改结构消费必改 | 数据模型 → 序列化/展示/导出 |
| 接口定义 → 实现/调用方 | 改接口签名，所有实现与调用方要改 | 接口/抽象类 → 实现类/调用点 |
| 共享 DTO/结构体 | 多模块共用同一数据结构 | 公共 DTO → 所有使用方 |
| 消息发送 → 消费 | 消息格式变更，生产者与消费者要同步 | 消息生产者 → 消费者 |
| 共享表结构 | 多写方操作同一表，表结构变则全要改 | 多模块写同表 |
| 业务规则强依赖 | 一方行为强依赖另一方输出格式或行为语义 | 计算 → 依赖其结果的校验/展示；上层对齐补偿 → 依赖底层引擎行为语义 |

> **注意方向相反**：上表的「数据源→消费端」「接口定义→调用方」等契约线，与「业务规则强依赖」这条语义线，方向**可能相反**——同一对模块里，A 可以是 B 的结构之源（B 消费 A 的数据），同时又是 B 的语义依赖方（A 去适配 B 的行为）。两条线都要记录，不得只记一条把另一条归结为"不用管"。

### 低概率/不记录（弱关联）

- 普通读操作（读但不受结构变更影响）
- 可选依赖 / 插件式扩展（改了不强连带）
- 单纯调用但两端契约稳定、无共享结构

### 识别技巧

1. **先 impact 再确认**：`impact` 列出调用方，但**不能仅凭 impact 判定强关联**（GitNexus 的关联太泛化）——必须读共享的数据结构/接口签名确认耦合强度
2. **数据结构是重点**：两个文件共享同一个 DTO/结构体/表结构/消息格式 → 高度疑似强关联
3. **方向沿两条依赖线分别判定**：契约/结构线看"谁消费谁的数据结构/参数/消息/接口签名"（改结构之源 → 消费端必改）；语义/行为线看"谁的行为语义被对方适配"（改语义之源 → 适配方必改）。两条线方向可能相反，相反时都要记录，不要只记一条就把另一条归结为"不用管"
4. **方向结论绑定改动性质**：写"改 X 不用管"前，先区分改的是 X 的**内部实现**（对外契约不变，确实不用管）还是**对外契约/数据结构/参数**（变了，X 的消费方必须跟着改），禁止笼统断言"不用管"

## 与相邻 skill 边界

| skill | 关系 |
|-------|------|
| relation-lookup | **查询侧**：本 skill（strong-relation）负责**写入**强关联，`relation-lookup` 负责**查询**（只查不写，SSOT），引用方 skill 都调用 relation-lookup |
| expert-team | 产出的模块专家是其触发前置；本 skill 记录模块间强关联，与其专题记忆互补（专题记忆=模块内部路标；本 skill=模块间耦合） |
| expert-lookup | expert-lookup 的 C4（数据流向与消费）记录模块**内部**的数据流向与消费方（模块级概括）；本 skill 记录**跨模块**的强关联（含多端代码位置、方向、强度）。同一消费关系若跨模块，C4 写模块内视角，本 skill 写跨模块视角，互补不重复 |
| data-flow-model | data-flow-model 画"设计期未来"的数据流/ER 图；本 skill 记录"现存代码"的强耦合，不画图 |
| bug-impact-analysis | bug-impact-analysis 分析"某次修复"的具体影响；本 skill 沉淀"持续性的跨模块耦合契约" |
| gitnexus-index | gitnexus-index 管索引运维；本 skill 消费索引（用 GitNexus 查询）做关联识别 |
