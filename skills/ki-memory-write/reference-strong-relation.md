# 强关联策略参考（写入侧）

ki-memory-write 的「强关联」策略细则。主流程见 SKILL.md。调用方为 strong-relation（Step 4，先完成识别关联 + 判定方向强度）。查询强关联走 `use_skill("ki-memory-lookup")`。

## 定位

强关联 = **改了 A 必须连带改 B（或强烈建议连带改）** 的跨模块耦合，用 ki 的 **group 分组**机制归档（非零散 `ki_store`），保证按功能模块归档、可被整组检索。

## 核心 API（写入侧）

| API | 用途 | 关键参数 |
|-----|------|----------|
| `ki_sync_relation` | 写入单条强关联原子（推荐） | `scope`（项目标识）、`group`（模块分组路径，支持 `/` 嵌套）、`relation`（关联名，用 `-` 连接两端，如 `A-B`）、`module_info`（描述内容）、`tags`（统一为 `relation`） |
| `ki_store` | 简单文本向量存储（无分组） | `scope`、`text`、`tags` |
| `ki_manage_index_create` | 手动建 group 节点 | `scope`、`name`、`parent` |
| `ki_manage_index_list` | 列出所有 scope 及顶层 group | - |

## 分组约定

- **scope**：项目标识，与 expert-team 专题记忆所用 scope 一致
- **group 父目录**：**统一固定名「关联关系」**（不复用专题记忆名称，作为所有强关联记录的根分组）
- **group 子目录**：**按功能模块动态创建**，`关联关系/{功能模块名}`（如 `关联关系/支付系统`）；先 `ki_manage_index_list` 查已有子分组，有则复用，无则新建
- **relation**：关联名，用连字符 `-` 连接两端模块名（如 `订单服务-支付通知服务`），不含 `→` 等特殊字符
- **module_info**：关联描述（见下方模板，纯文本 + 列表）
- **tags**：**统一为 `relation`**（固定，写入时每条强关联都带，供查询侧用 `tags="relation"` 过滤收窄范围）

## 写入模板（module_info）

### 单向关联

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

### 双向关联（两条依赖线方向相反）

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

## 写入要点

- **每条关联一条原子**：关联多时，每条（或每小组）单独写一条原子，全部归入同一子分组，保持分组一致
- **一个功能模块涉及多个文件**：两端用列表列出所有相关类与文件位置，不限于单个；单向时 `{模块A}端` 即改动源、`{模块B}端` 即被影响方；双向时两端互为源目标，标签保持中性
- **校验**：写入后用 `ki_query_group`（group = `关联关系/{功能模块名}`）确认已归入正确子分组，抽查 1-2 条

## 降级

ki 不可用时告知调用方并给出关联清单（对话内），不阻塞流程。
