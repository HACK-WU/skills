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

### 写入示例

```text
ki_sync_relation
  scope:  my-project
  group:  关联关系/支付系统
  relation: 订单服务-支付通知服务
  tags:  relation
  module_info:
    [强关联] 订单服务 与 支付通知服务
    强度：必改——改订单数据结构，支付通知必须连带改；改支付通知，订单不用管
    原因：支付通知消费订单的金额/状态字段，共享订单 DTO 结构

    源端（订单服务）：
    - OrderService @ orders/service.py
    - OrderDTO @ orders/dto.py
    - OrderRepository @ orders/repository.py

    目标端（支付通知服务）：
    - PaymentNotifier @ payment/notifier.py
    - NotificationTemplate @ payment/template.py
    - MessageDispatcher @ payment/dispatcher.py
```

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
| 业务规则强依赖 | 一方行为强依赖另一方输出格式 | 计算 → 依赖其结果的校验/展示 |

### 低概率/不记录（弱关联）

- 普通读操作（读但不受结构变更影响）
- 可选依赖 / 插件式扩展（改了不强连带）
- 单纯调用但两端契约稳定、无共享结构

### 识别技巧

1. **先 impact 再确认**：`impact` 列出调用方，但**不能仅凭 impact 判定强关联**（GitNexus 的关联太泛化）——必须读共享的数据结构/接口签名确认耦合强度
2. **数据结构是重点**：两个文件共享同一个 DTO/结构体/表结构/消息格式 → 高度疑似强关联
3. **方向看消费关系**：谁是数据/行为的生产者，谁是消费者，改生产端通常牵动消费端（不对称）

## 与相邻 skill 边界

| skill | 关系 |
|-------|------|
| relation-lookup | **查询侧**：本 skill（strong-relation）负责**写入**强关联，`relation-lookup` 负责**查询**（只查不写，SSOT），引用方 skill 都调用 relation-lookup |
| expert-team | 产出的模块专家是其触发前置；本 skill 记录模块间强关联，与其专题记忆互补（专题记忆=模块内部路标；本 skill=模块间耦合） |
| expert-lookup | expert-lookup 的 C4（数据流向与消费）记录模块**内部**的数据流向与消费方（模块级概括）；本 skill 记录**跨模块**的强关联（含多端代码位置、方向、强度）。同一消费关系若跨模块，C4 写模块内视角，本 skill 写跨模块视角，互补不重复 |
| data-flow-model | data-flow-model 画"设计期未来"的数据流/ER 图；本 skill 记录"现存代码"的强耦合，不画图 |
| bug-impact-analysis | bug-impact-analysis 分析"某次修复"的具体影响；本 skill 沉淀"持续性的跨模块耦合契约" |
| gitnexus-index | gitnexus-index 管索引运维；本 skill 消费索引（用 GitNexus 查询）做关联识别 |
