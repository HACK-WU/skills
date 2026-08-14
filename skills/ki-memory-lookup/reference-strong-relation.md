# 强关联查询策略参考

ki-memory-lookup 的「强关联」查询策略细则。主流程见 SKILL.md。写入方为 `ki-memory-write`（强关联策略，由 strong-relation 调用）。

## ki 检索 API

| API | 用途 | 关键参数 |
|-----|------|----------|
| `ki_search` | 语义检索强关联记录 | `scope`（项目标识）、`query`（自然语言 + 关键代码符号）、`tags`（固定 `relation`）、`limit`、`threshold` |
| `ki_query_group` | 按模块整组检索某分组的全部记录 | `scope`、`groups`（group 路径，如 `关联关系/支付系统`） |
| `ki_manage_index_list` | 列出 scope 及顶层 group（辅助定位分组） | - |
| `ki_tag_list` | 列出 scope 下已用 tag（辅助确认 relation tag） | `scope` |

## 分组与 tags 约定（查询侧）

- **scope**：项目标识，与写入时一致
- **group**：`关联关系/{功能模块名}`（写入侧统一父分组「关联关系」+ 动态子分组）
- **tags**：写入侧统一为 `relation`，故查询侧固定用 `tags="relation"` 过滤

## 检索方式

- **按语义检索**（`ki_search`，**query 中带上关键代码符号**）：
  - 查"改某模块要连带改什么"：`ki_search(query="改 {模块A} 要连带改什么 {关键类名}")`
  - 查某类关联：`ki_search(query="{模块A} 数据源 消费端 {关键接口名}")`
- **按模块整组检索**（`ki_query_group`）：查某模块的所有强关联用 `ki_query_group(groups="关联关系/{功能模块名}")`
- **tags 过滤**（固定）：`ki_search` 一律用 **`tags="relation"`** 过滤（强关联记录写入时统一带 `relation` tag），收窄范围提高准确度；**若过滤后命中过少/为空**（如历史存量数据未带该 tag），回退为**去掉 tags 过滤**的语义检索，避免漏召回

## 检索示例

```text
# 语义检索（带关键代码符号）
ki_search
  scope:  my-project
  query:  改 订单服务 要连带改什么 OrderService
  tags:   relation
  limit:  10

# 整组检索
ki_query_group
  scope:  my-project
  groups: 关联关系/支付系统
```

## 检索技巧

1. **query 带符号**：关键代码符号（类名/方法名/接口名）是写入 `module_info` 时的定位依据，带上能显著提高命中准确度
2. **tags 回退**：固定 `tags="relation"` 过滤后若命中过少/为空（如历史存量数据未带 tag），去掉 tags 过滤扩大召回
3. **结果以代码为准**：命中的强关联记录属辅助参考，与代码实际不符时以代码为准

## 利用结果（牵动识别）

- **牵动识别**：命中某模块的强关联记录后，按记录标注的**方向/影响线**逐条核对——改到某条影响线的**左端（改动源）**时，务必检查其**右端（被影响方）**是否同步修改或需覆盖；**双向关联**（记录含两条影响线、两端互为源目标）时，改任一端都要核对另一端的影响线，不得漏检反方向
- **方向以记录为准**：方向/强度以写入的 `module_info` 标注为准，不凭"消费端/生产端"自行推断不对称；记录标注双向就按双向处理，标注单向才按单向核对
