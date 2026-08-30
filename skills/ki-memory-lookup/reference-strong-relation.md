# 强关联查询策略参考

ki-memory-lookup 的「强关联」查询策略细则。主流程见 SKILL.md。写入方为 `ki-memory-write`（强关联策略，由 strong-relation 调用）。

## ki 检索 API

| API | 用途 | 关键参数 |
|-----|------|----------|
| `ki_search` | 语义检索强关联记录 | `scope`（项目标识）、`query`（自然语言 + 关键代码符号）、`tags`（固定 `relation`）、`limit`、`threshold` |
| `ki_query_group` | ① `subtree` 列子 Group 树 / ② `groups`+`mode="full"` 列某 Group 的全部 Relations | `scope`、**`subtree`**（子 Group 树，与 `groups` 互斥、不支持多值）、**`groups`**（Group 路径，支持逗号分隔多值）、**`mode`**（列 Relations 时必须 `"full"`）、`depth`（子树层级） |
| `ki_get_module_info` | 取某条 relation 的本地 KB 原文 | `scope`、`group`（模糊匹配）、`relation`（**精确匹配**，从清单复制） |
| `ki_manage_index_list` | 列出 scope 及**顶层** Group | - |
| `ki_tag_list` | 列出 scope 下已用 tag（辅助确认 relation tag） | `scope` |

> `ki_manage_index_list` **只输出顶层 Group**，看不到第二层（如 `关联关系/订单服务`）——定位模块子分组请用 `subtree`。

## 分组与 tags 约定（查询侧）

- **scope**：项目标识，与写入时一致
- **group**：`关联关系/{功能模块名}`（写入侧统一父分组「关联关系」+ 动态子分组）
- **tags**：写入侧统一为 `relation`，故查询侧固定用 `tags="relation"` 过滤

## 检索方式

### 首选：精确列举（目录优先）

强关联**漏一条 = 漏改一个模块**——语义检索的召回遗漏会直接转化为漏改风险。故用 `ki_query_group` 确定性穷举（调用示例见「检索示例」节）。

> ⚠️ **必须显式 `mode="full"`**：`ki_query_group` 默认 `mode="hot"` + `hot_count=5`，**只返回最热的 5 条 relation**——比语义检索漏得更多，且**不报错**（`auto_fallback` 会静默语义兜底，掩盖"少给了"这件事）。

**先定位 group 路径——用 `subtree` 两级导航**（不要猜模块名）：`groups` 支持模糊匹配，写错**不报错**（`auto_fallback` 静默走语义兜底，返回不相关内容却看似正常）；且**代码模块名与 ki 功能模块名常不一致**（如代码目录 `order-service` vs group `关联关系/订单服务`）。故：

| 级 | 调用 | 作用 |
|----|------|------|
| 1 | `ki_query_group(subtree="关联关系")` | 列出「关联关系」下**所有模块子分组**（不受 5 条限制、不需 `mode="full"`） |
| 2 | `ki_query_group(groups="关联关系/{模块名}", mode="full")` | 列出该模块的**全部强关联条目** |

> **为何不用 `ki_manage_index_list`**：它只输出**顶层 Group**（如 `关联关系`），**看不到第二层**（`关联关系/订单服务`），无法用于确认模块子分组名。
>
> **`subtree` 两个陷阱**（实测）：
> 1. **不支持逗号分隔多值**——传多值会被当整体模糊匹配，可能静默匹配到完全不相关的 group（score 极低仍不报错）。**一次只传一个路径**
> 2. **近似匹配会跑偏**——匹配不到时返回低分近似结果，**核对返回头部的 💡 提示行**确认实际解析出的路径
>
> **子分组很多时别靠肉眼认**：先 `subtree="关联关系"` 看全貌；若列表长，改用 `subtree="{模糊模块名}"` 让 ki **模糊匹配自动补全**（实测有效：`subtree="缓存"` → 💡 补全为 `基础设施/缓存`），再核对提示行确认补全结果。
>
> **已知确切 group 路径时可跳过第 1 级**（如同一次会话内刚列过该模块），直接走第 2 级。默认仍建议走两级——AI 容易"以为自己知道"模块名，而代码模块名与 ki 模块名常不一致。
>
> 两级都取不到 → 回退语义检索。

**拿到清单后，避免过度调用**：

1. 先列清单——relation 名 = `{模块A}-{模块B}`，一眼看出牵动谁
2. 清单信息已够判断 → 不必再取；不够 → `ki_get_module_info`（`group` 模糊匹配、**`relation` 精确匹配，从清单复制名称**）逐条取原文

**⚠️ 必须全取，不许挑着看**：relation 名只含两端模块名，**不含强度与方向**——无法据此判断"必改"还是"可选"。若照搬"看名字挑相关的看"，恰恰会漏掉最该看的那条。数量有限（一个模块几条到十几条），全量取成本可接受。

### 辅助：语义检索（`ki_search`）

仅在**不确定该查哪个 group**（只知道代码符号、不知模块名）或精确列举为空时兜底：

- 查"改某模块要连带改什么"：`ki_search(query="改 {模块A} 要连带改什么 {关键类名}")`
- 查某类关联：`ki_search(query="{模块A} 数据源 消费端 {关键接口名}")`
- **tags 固定 `relation`**；过滤后命中过少/为空 → 去掉 tags 扩大召回

## 检索示例

```text
# 首选：两级导航
# 第 1 级——列出「关联关系」下有哪些模块子分组（不需 mode=full，不受 5 条限制）
ki_query_group
  scope:   my-project
  subtree: 关联关系

# 第 2 级——列出该模块的全部强关联条目（注意 mode=full，否则默认只返回 5 条）
ki_query_group
  scope:  my-project
  groups: 关联关系/支付系统
  mode:   full

# 取某条原文（relation 名从上面清单复制，精确匹配）
ki_get_module_info
  scope:    my-project
  group:    关联关系/支付系统
  relation: 订单服务-支付通知服务

# 辅助：语义检索（带关键代码符号）
ki_search
  scope:  my-project
  query:  改 订单服务 要连带改什么 OrderService
  tags:   relation
  limit:  10
```

## 检索技巧

1. **先列后取**：强关联优先走 `mode="full"` 精确列举，不依赖语义；`ki_search` 只用于定位 group 或兜底
2. **全取不挑**：relation 名不含强度/方向，无法据此筛选，必须全量取后按 `module_info` 标注的方向/强度逐条核对
3. **query 带符号**：走 `ki_search` 时，关键代码符号（类名/方法名/接口名）是写入 `module_info` 时的定位依据，带上能显著提高命中准确度
4. **tags 回退**：固定 `tags="relation"` 过滤后若命中过少/为空（如历史存量数据未带 tag），去掉 tags 过滤扩大召回
5. **结果以代码为准**：命中的强关联记录属辅助参考，与代码实际不符时以代码为准

## 利用结果（牵动识别）

- **牵动识别**：命中某模块的强关联记录后，按记录标注的**方向/影响线**逐条核对——改到某条影响线的**左端（改动源）**时，务必检查其**右端（被影响方）**是否同步修改或需覆盖；**双向关联**（记录含两条影响线、两端互为源目标）时，改任一端都要核对另一端的影响线，不得漏检反方向
- **方向以记录为准**：方向/强度以写入的 `module_info` 标注为准，不凭"消费端/生产端"自行推断不对称；记录标注双向就按双向处理，标注单向才按单向核对
