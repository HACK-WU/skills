# 接口信息查询策略参考

ki-memory-lookup 的「接口信息」查询策略细则。主流程见 SKILL.md。写入方为 `ki-memory-write`（接口信息策略，由 expert-team 调用）。

## 定位

接口信息 = 子功能粒度的可检索原子（子功能 → 接口列表：API 路径 → 后端接口名 → 文件位置 → 职责）。查询它用于"查某接口在哪定义 / 怎么调 / 谁提供"，命中即得接口定位，不必重新翻代码。

## 检索 API

| API | 用途 | 关键参数 |
|-----|------|----------|
| `ki_search` | 语义检索接口信息 | `scope`（项目标识）、`query`（接口路径 / 后端接口名 / 职责关键词）、`tags`（固定 `api`） |

- **scope**：项目标识，与写入时一致

## 检索方式

- **按接口路径检索**：`ki_search(query="{API 路径} {方法} 后端接口")`，如 `ki_search(query="POST /api/order/create 后端接口")`
- **按后端接口名检索**：`ki_search(query="{后端函数名}")`，如 `ki_search(query="OrderService.createOrder")`
- **按子功能检索**：`ki_search(query="{子功能名} 接口")`，命中即得该子功能的接口列表
- **按模块整组检索**：`ki_query_group(groups="接口信息/{功能模块名}")`，查某模块的所有接口信息
- **tags 过滤**（固定）：`ki_search` 一律用 **`tags="api"`** 过滤（接口信息写入时统一带 `api` tag），收窄范围提高准确度；**若过滤后命中过少/为空**（如历史存量数据未带该 tag），回退为去掉 tags 过滤的语义检索，避免漏召回

## 检索示例

```text
ki_search
  scope:  my-project
  query:  POST /api/order/create 后端接口
  tags:   api
  limit:  10
```

## 利用结果

- **命中** → 得接口定位：API 路径 / 后端接口名 / 文件位置 / 职责，直接据此定位代码或了解接口用途
- **未命中 / ki 不可用** → 静默跳过，不阻塞主流程，回退正常读代码

## 与其它记忆的关系

- 接口信息看模块**内**的单个接口；专题记忆看模块**整体**路标；强关联看模块**间**耦合——三者粒度互补，各自独立 tag 检索
