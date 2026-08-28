---
name: ki-memory-lookup
description: 统一查询 ki-search 记忆的 SSOT（单一事实源）。封装查 ki 的公共动作（ki 可用性检测、scope 确定、符号提准、降级不阻塞），按记忆类型分发到不同 reference 策略：专题记忆（模块内部知识路标）、接口信息（对外 API）、数据流（数据实体流向）、强关联（跨模块耦合）。触发短语："查记忆"、"查强关联"、"改A要连带改B吗"、"这个模块牵动哪些"、"ki memory lookup"。
---

# ki 记忆查询（SSOT）

## 概述

**目的**：把"查 ki-search 记忆"这个**公共动作**收敛为一处，统一承载专题记忆（模块内部路标）、接口信息（对外 API）、数据流（数据实体流向）与强关联（跨模块耦合）四类记忆的查询，消除查询逻辑散落、SSOT 不清晰的问题。

**功能**：统一的 ki 查询公共动作层，按记忆类型分发到不同策略（各策略独立一个 reference），引用方只调用本 skill，不再内嵌 ki 查询细节。

**使用场景**：
- 强关联查询（供 code review / debug / 设计 / 测试 / 修改前刹车检查等 skill 引用）：检索"改了某模块要连带改哪里"
- 专题记忆查询（供 expert-lookup 等检索）：知晓"有此专家 + 关键入口"
- 接口信息查询：检索"某接口在哪定义 / 怎么调 / 谁提供"
- 数据流查询：检索"某表/字段/消息谁写的 / 谁读的 / 干什么用"
- 项目记忆查询（"遇事不决 ki-search"，调用 use_skill("ki-search-first")）

## 定位

```
查询请求 → ki-memory-lookup（本 skill，只查询）→ ki_search / ki_query_group 检索
                                                    ↓
          返回命中的记忆（专题记忆路标 / 接口信息 / 数据流 / 强关联牵动清单）
```

- **输入**：目标模块/代码的关键符号（类名、方法名、接口名等）或自然语言问题
- **输出**：命中的记忆（专题记忆路标 / 接口信息 / 数据流 / 强关联牵动清单）
- **边界**：本 skill **只查询** ki 记忆，**不写入**（写入是 `ki-memory-write` 的事）

## 核心原则

1. **只查不写**：本 skill 查询既有记忆，不负责识别/判定/写入（那是 `ki-memory-write` 及其调用方的事）
2. **SSOT**：ki 查询参数细节只在本 skill 定义，引用方 skill 只写明调用时机，不重复写 ki 查询细节
3. **符号提准**：query 中带上关键代码符号（类名/方法名/接口名等），显著提高检索准确度
4. **降级不阻塞**：ki 不可用 / 无可用记录 / 未命中 → 静默跳过，不阻塞调用方主流程
5. **记录以代码为准**：记忆是辅助参考，与代码实际不符时以代码为准

## 执行流程

### Step 0：确定记忆类型与策略

根据查询目标选择对应 reference 策略：

| 记忆类型 | 典型场景 | 策略 reference | 检索 API |
|----------|----------|---------------|----------|
| 强关联 | 改代码前感知牵动、code review、排错、设计 | [reference-strong-relation.md](reference-strong-relation.md) | `ki_search`（tags=relation）/ `ki_query_group` |
| 专题记忆 | 知晓有此专家 + 关键入口 | [reference-topic-memory.md](reference-topic-memory.md) | `ki_search`（无 tags） |
| 接口信息 | 查接口在哪定义/怎么调/谁提供 | [reference-api.md](reference-api.md) | `ki_search`（tags=api）/ `ki_query_group` |
| 数据流 | 查某表/字段/消息谁写谁读 | [reference-data-flow.md](reference-data-flow.md) | `ki_search`（tags=data）/ `ki_query_group` |

### Step 1：提取模块关键词 + 关键代码符号

从目标代码 / 问题中提取功能模块名 + **关键代码符号**（2-3 个）。代码符号按实际情况选取最能标识目标的一端——类名、方法名、接口名、函数名、枚举/常量名等；核心是选"写入记忆时会出现的、能唯一定位的符号"，带上它们能显著提高检索准确度。

### Step 2：按策略检索

加载对应策略 reference，按其检索方式（`ki_search` 语义检索 / `ki_query_group` 整组检索 / tags 过滤）执行。

### Step 3：利用结果

- **强关联命中** → 记录**牵动清单**（`{被改模块} 与 {其他模块} 强关联：方向/强度/原因`；双向记录按两条影响线分别列出），作为跨模块一致性检查的重点
- **专题记忆命中** → 知晓"有此专家 + 关键入口"，跳转前校验专家路径存在
- **接口信息命中** → 得接口定位（子功能 + 接口列表：API 路径 / 后端接口名 / 文件位置 / 职责），直接据此定位代码
- **数据流命中** → 得数据流向（实体类型 / 结构 / 生产方 / 消费方 / 业务用途），直接据此定位代码
- **未命中 / ki 不可用** → 静默跳过，不阻塞主流程

## 更多资源

- 强关联查询策略（检索 API + tags 过滤 + 检索技巧），参见 [reference-strong-relation.md](reference-strong-relation.md)
- 专题记忆查询策略，参见 [reference-topic-memory.md](reference-topic-memory.md)
- 接口信息查询策略（tags=api 过滤），参见 [reference-api.md](reference-api.md)
- 数据流查询策略（tags=data 过滤），参见 [reference-data-flow.md](reference-data-flow.md)
- 记忆的**写入**（SSOT），调用 `use_skill("ki-memory-write")`
