---
name: ki-memory-write
description: 统一往 ki-search 写入记忆的 SSOT（单一事实源）。封装写 ki 的公共动作（ki 可用性检测、scope 确定、格式硬约束、降级策略），按记忆类型分发到不同 reference 策略：专题记忆（模块内部知识路标）、接口信息（对外 API）、数据流（数据实体流向）、强关联（跨模块耦合）、决策记忆（为什么这么定）、错误库（报错→解法）。触发短语："写专题记忆"、"写 ki 记忆"、"记录强关联到 ki"、"记录决策"、"记录这个报错"、"ki memory write"。
---

# ki 记忆写入（SSOT）

## 概述

**目的**：把"往 ki-search 写记忆"这个**公共动作**收敛为一处，消除 expert-team（专题记忆/接口信息/数据流/决策记忆）与 strong-relation（强关联）、debug / solution-capture（错误库）各自重复声明的格式硬约束、ki 可用性检测、scope 确定、降级策略，避免双源漂移。

**功能**：统一的 ki 写入公共动作层，按记忆类型分发到不同策略（各策略独立一个 reference），策略方只调用本 skill，不再内嵌 ki 写入细节。

**使用场景**：
- expert-team 专家/专题落盘后写"专题记忆"（模块内部知识路标）
- expert-team 识别专家模块暴露接口后写"接口信息"（按子功能聚合的可检索原子）
- expert-team 识别专家模块数据实体后写"数据流"（数据实体流向）
- expert-team 识别模块关键决策后写"决策记忆"（当初为什么这么定、砍了什么备选）
- strong-relation 识别强关联后写"强关联"（跨模块耦合）
- debug 定位成功 / solution-capture 沉淀后写"错误库"（报错原文 → 根因/解法，语义去重）
- 任何需要往 ki 写入"路标型 / 接口型 / 数据流型 / 决策型 / 错误型 / 关联型"记忆的场景

## 定位

```
expert-team 落盘 → 提炼专题记忆（路标）→ ki-memory-write（专题记忆策略）→ ki_bulk_sync_relation
expert-team 落盘 → 识别暴露接口 → ki-memory-write（接口信息策略）→ ki_bulk_sync_relation
expert-team 落盘 → 识别数据实体 → ki-memory-write（数据流策略）→ ki_bulk_sync_relation
expert-team 落盘 → 识别关键决策 → ki-memory-write（决策记忆策略）→ ki_bulk_sync_relation
strong-relation 识别关联 → 判定方向强度 → ki-memory-write（强关联策略）→ ki_bulk_sync_relation
debug 定位成功 / solution-capture 沉淀 → ki-memory-write（错误库策略）→ ki_bulk_sync_relation
```

**六类记忆统一走 `ki_bulk_sync_relation`，group 均为「父目录/{功能模块名}」结构**（父目录区分记忆类型，子目录按功能模块动态创建）：

| 记忆类型 | group | relation | tags |
|----------|-------|----------|------|
| 专题记忆 | `专题记忆/{功能模块名}` | 根据内容进行总结 | 无 |
| 接口信息 | `接口信息/{功能模块名}` | 子功能名（同一子功能的接口集合共用一条 relation） | `api` |
| 数据流 | `数据流/{功能模块名}` | 数据实体名（表/消息主题/缓存 key/数据结构） | `data` |
| 决策记忆 | `决策记录/{功能模块名}` | 决策主题（不含特殊字符） | `decision` |
| 错误库 | `错误库/{功能模块名}` | 错误特征（短短语，非报错原文） | `error` |
| 强关联 | `关联关系/{功能模块名}` | `{模块A}-{模块B}` | `relation` |

> **group 子目录六类统一按功能模块名**，技术栈/工具名写进正文与 keywords，不占 group 位；错误库中无明确归属模块的（Docker / Nginx / 工具链 / 语言级问题）归 `错误库/通用`。
>
> **禁用 `ki_store` / `ki_bulk_store`**：二者只写向量层、不写本地 KB，会产出孤儿向量。写知识一律走 `ki_sync_relation` / `ki_bulk_sync_relation`（双写 KB + 向量）。

- **输入**：记忆类型（专题记忆 / 接口信息 / 数据流 / 决策记忆 / 错误库 / 强关联）+ 已提炼/识别好的记忆内容
- **输出**：写入 ki-search 的记忆原子
- **边界**：本 skill **只负责"写 ki"这个动作**（检测 → scope → 格式约束 → 降级），**不负责**内容的提炼/识别——专题记忆的"提炼路标"、接口信息的"识别暴露接口"、数据流的"识别数据实体"、决策记忆的"识别关键决策"是 expert-team 的事，强关联的"识别关联 + 判定方向"是 strong-relation 的事，错误库的"定位根因 + 给解法"是 debug / solution-capture 的事。策略内容（字段模板、分组/tags 约定）在各自 reference 中定义。

## 核心原则

1. **只写动作，不做认知**：本 skill 收敛"写 ki"的公共动作，不承担记忆内容的提炼/识别/判定——那是调用方（expert-team / strong-relation / debug / solution-capture）的职责
2. **格式硬约束 SSOT**：ki 记忆的格式硬约束（禁用 yaml、标题、表格）**只在本 skill 定义一次**，调用方不再各自声明
3. **策略分 reference**：专题记忆、接口信息、数据流、决策记忆、错误库、强关联的字段模板 / 分组 / tags / API 差异，分别在 `reference-topic-memory.md`、`reference-api.md`、`reference-data-flow.md`、`reference-decision.md`、`reference-error.md`、`reference-strong-relation.md` 中定义，SKILL.md 只放公共动作
4. **降级不阻塞**：ki 不可用时跳过写入并告知调用方（对话内输出记忆内容清单），不阻塞调用方主流程
5. **scope 一致**：写入所用 scope = 项目标识，与各策略既有一致

## 执行流程

### Step 0：环境检测

1. 确认 ki 可用（`ki_bulk_sync_relation` / `ki_manage_index_list` 可调用）
2. **ki 不可用** → 告知调用方，将记忆内容以对话内清单输出，**不阻塞**调用方主流程，本流程终止

### Step 1：确定记忆类型与策略

根据调用方传入的记忆类型，选择对应 reference 策略：

| 记忆类型 | 调用方 | 策略 reference | 写入 API |
|----------|--------|---------------|----------|
| 专题记忆 | expert-team（Step 8） | [reference-topic-memory.md](reference-topic-memory.md) | `ki_bulk_sync_relation` |
| 接口信息 | expert-team（Step 8.3） | [reference-api.md](reference-api.md) | `ki_bulk_sync_relation` |
| 数据流 | expert-team（Step 8.4） | [reference-data-flow.md](reference-data-flow.md) | `ki_bulk_sync_relation` |
| 决策记忆 | expert-team（Step 8.6） | [reference-decision.md](reference-decision.md) | `ki_bulk_sync_relation` |
| 错误库 | debug（Step 5.5）/ solution-capture（Step 7.5） | [reference-error.md](reference-error.md) | `ki_bulk_sync_relation` |
| 强关联 | strong-relation（Step 4） | [reference-strong-relation.md](reference-strong-relation.md) | `ki_bulk_sync_relation` |

### Step 2：按策略写入

加载对应策略 reference，按其字段模板 + 分组/tags/API 约定执行写入。

### Step 3：格式硬约束校验（写入前必做）

写入前校验记忆内容**不含**以下项（违反即先修正再写入）：

- yaml 元数据（`---` frontmatter）
- `##` / `###` 等 markdown 标题
- `|` 表格分隔符等 markdown 结构语法

统一为**纯文本描述 + `-` 列表**，保证 ki-search 向量化时语义纯净、检索准确。

> **为什么**：yaml 元数据和 md 标题会污染向量化，降低 ki-search 检索效率。

### Step 3.5：写入 API 硬约束（写入前必做）

- **禁用 `ki_store` / `ki_bulk_store`**——二者只写向量层、不写本地 KB，会产出孤儿向量；写知识一律走 `ki_sync_relation` / `ki_bulk_sync_relation`（双写 KB + 向量）
- **建议带 `keywords`**（3-5 个）：必须是**自然语言词汇**（禁代码符号），且必须真实出现在 `module_info` 原文中。语义召回型记忆（决策记忆 / 错误库 / 专题记忆）收益最明显

### Step 4：刷新缓存与校验落盘

写入后执行两步：

1. **刷新缓存**（必须）：`ki_query_group`（`mode="full"`）——ki 写入后需刷新索引缓存，否则低频写入的记忆（决策记忆、错误库）可能检索不到
2. **校验归档**：用 `ki_query_group`（group = 对应根分组，如 `专题记忆` / `接口信息` / `数据流` / `决策记录` / `错误库` / `关联关系/{功能模块名}`）确认记忆原子已归入正确分组，抽查 1-2 条确认已可检索，失败则修正后重写

## 更多资源

- 专题记忆策略（8 字段路标模板 + 维护规则），参见 [reference-topic-memory.md](reference-topic-memory.md)
- 接口信息策略（子功能聚合模板 + tag=`api`），参见 [reference-api.md](reference-api.md)
- 数据流策略（数据实体流向模板 + tag=`data`），参见 [reference-data-flow.md](reference-data-flow.md)
- 决策记忆策略（决策/被否决方案/触发条件/证据门 + tag=`decision`），参见 [reference-decision.md](reference-decision.md)
- 错误库策略（报错原文→根因/解法 + 查重前置 + 非平凡门槛 + tag=`error`），参见 [reference-error.md](reference-error.md)
- 强关联策略（三元组/双向影响线模板 + 分组/tags 约定），参见 [reference-strong-relation.md](reference-strong-relation.md)
- 记忆的**查询**（SSOT），调用 `use_skill("ki-memory-lookup")`
