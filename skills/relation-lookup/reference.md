# 强关联查询参考

详细 ki 检索 API 与使用细则。主指令见 SKILL.md。

## ki 检索 API

| API | 用途 | 关键参数 |
|-----|------|----------|
| `ki_search` | 语义检索强关联记录 | `scope`（项目标识）、`query`（自然语言 + 关键代码符号）、`tags`（固定 `relation`）、`limit`、`threshold` |
| `ki_query_group` | 按模块整组检索某分组的全部记录 | `scope`、`groups`（group 路径，如 `关联关系/支付系统`） |
| `ki_manage_index_list` | 列出 scope 及顶层 group（辅助定位分组） | - |
| `ki_tag_list` | 列出 scope 下已用 tag（辅助确认 relation tag） | `scope` |

## 分组与 tags 约定（查询侧）

- **scope**：项目标识，与 `strong-relation` 写入时一致
- **group**：`关联关系/{功能模块名}`（写入侧统一父分组「关联关系」+ 动态子分组）
- **tags**：写入侧统一为 `relation`，故查询侧固定用 `tags="relation"` 过滤

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
