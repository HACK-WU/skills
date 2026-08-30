---
name: ki-memory-lookup
description: 统一查询 ki-search 记忆的 SSOT（单一事实源）。封装查 ki 的公共动作（ki 可用性检测、scope 确定、符号提准、降级不阻塞），按记忆类型分发到不同 reference 策略：专题记忆（模块内部知识路标）、接口信息（对外 API）、数据流（数据实体流向）、强关联（跨模块耦合）、决策记忆（为什么这么定）、错误库（报错→解法）。触发短语："查记忆"、"查强关联"、"改A要连带改B吗"、"这个模块牵动哪些"、"当初为什么这么定"、"这个报错见过吗"、"ki memory lookup"。
---

# ki 记忆查询（SSOT）

## 概述

**目的**：把"查 ki-search 记忆"这个**公共动作**收敛为一处，统一承载专题记忆（模块内部路标）、接口信息（对外 API）、数据流（数据实体流向）、强关联（跨模块耦合）、决策记忆（为什么这么定）、错误库（报错→解法）六类记忆的查询，消除查询逻辑散落、SSOT 不清晰的问题。

**功能**：统一的 ki 查询公共动作层，按记忆类型分发到不同策略（各策略独立一个 reference），引用方只调用本 skill，不再内嵌 ki 查询细节。

**使用场景**：
- 强关联查询（供 code review / debug / 设计 / 测试 / 修改前刹车检查等 skill 引用）：检索"改了某模块要连带改哪里"
- 专题记忆查询（供 expert-lookup 等检索）：知晓"有此专家 + 关键入口"
- 接口信息查询：检索"某接口在哪定义 / 怎么调 / 谁提供"
- 数据流查询：检索"某表/字段/消息谁写的 / 谁读的 / 干什么用"
- 决策记忆查询：检索"当初为什么这么定 / 砍掉的备选是什么 / 该不该重新评估"
- 错误库查询：贴**整段报错堆栈**检索"这个报错怎么解"（`.solutions/` 关键词匹配命中率低时的语义补位）
- 项目记忆查询（"遇事不决 ki-search"，调用 use_skill("ki-search-first")）

## 定位

```
查询请求 → ki-memory-lookup（本 skill，只查询）→ ki_search / ki_query_group 检索
                                                    ↓
          返回命中的记忆（专题记忆路标 / 接口信息 / 数据流 / 决策记录 / 错误解法 / 强关联牵动清单）
```

- **输入**：目标模块/代码的关键符号（类名、方法名、接口名等）、自然语言问题、或**报错原文/堆栈片段**（错误库场景）
- **输出**：命中的记忆（专题记忆路标 / 接口信息 / 数据流 / 决策记录 / 错误解法 / 强关联牵动清单）
- **边界**：本 skill **只查询** ki 记忆，**不写入**（写入是 `ki-memory-write` 的事）

## 核心原则

1. **只查不写**：本 skill 查询既有记忆，不负责识别/判定/写入（那是 `ki-memory-write` 及其调用方的事）
2. **SSOT**：ki 查询参数细节只在本 skill 定义，引用方 skill 只写明调用时机，不重复写 ki 查询细节
3. **目录优先于语义**（**决策记忆、强关联**）：这两类数量有限（一个模块通常几条到十几条）且 **relation 名本身可读**，先用 `ki_query_group` 确定性列举全部条目、按 relation 名判断、再取内容——比 `ki_search` 更完整、更可控，不存在语义召回遗漏。`ki_search` 退为辅助补位
   - **两级导航**：① `ki_query_group(subtree="{根分组}")` 列出所有模块子分组 → ② `ki_query_group(groups="{根分组}/{模块名}", mode="full")` 列出该模块全部条目。**不要凭代码目录名猜模块名**（代码模块名与 ki 功能模块名常不一致，如 `order-service` vs `订单服务`）
   - ⚠️ **`groups` 必须显式 `mode="full"`**：默认 `mode="hot"` + `hot_count=5`，**只返回最热 5 条**，比语义检索漏得更多，且不报错（`auto_fallback` 静默兜底）。**`subtree` 不受此限制**（返回的是结构而非条目），也无需 `mode="full"`
   - ⚠️ **`subtree` 不支持逗号分隔多值**：传多值会被当整体模糊匹配，可能静默匹配到不相关 group；且近似匹配会跑偏，**须核对返回头部的 💡 提示行**确认实际解析出的路径
   - 拿到清单后：**清单信息已够判断就不必逐条取**，不够再用 `ki_get_module_info`（`relation` 为精确匹配，从清单复制名称）取原文
4. **符号提准**：走 `ki_search` 时，query 中带上关键代码符号（类名/方法名/接口名等），显著提高检索准确度
5. **降级不阻塞**：ki 不可用 / 无可用记录 / 未命中 → 静默跳过，不阻塞调用方主流程
6. **记录以代码为准**：记忆是辅助参考，与代码实际不符时以代码为准

## 执行流程

### Step 0：确定记忆类型与策略

根据查询目标选择对应 reference 策略：

| 记忆类型 | 典型场景 | 策略 reference | 检索 API |
|----------|----------|---------------|----------|
| 强关联 | 改代码前感知牵动、code review、排错、设计 | [reference-strong-relation.md](reference-strong-relation.md) | **首选** `ki_query_group` 两级导航（`subtree` 找模块 → `groups`+`mode=full` 列条目，**全取不挑**）/ 辅助 `ki_search`（tags=relation） |
| 专题记忆 | 知晓有此专家 + 关键入口 | [reference-topic-memory.md](reference-topic-memory.md) | `ki_search`（无 tags） |
| 接口信息 | 查接口在哪定义/怎么调/谁提供 | [reference-api.md](reference-api.md) | `ki_search`（tags=api）/ `ki_query_group` |
| 数据流 | 查某表/字段/消息谁写谁读 | [reference-data-flow.md](reference-data-flow.md) | `ki_search`（tags=data）/ `ki_query_group` |
| 决策记忆 | 当初为什么这么定、砍了什么备选、该不该重新评估 | [reference-decision.md](reference-decision.md) | **首选** `ki_query_group` 两级导航（`subtree` 找模块 → `groups`+`mode=full` 列条目；**评审场景全看**）/ 辅助 `ki_search`（tags=decision） |
| 错误库 | 贴报错堆栈查"这个报错怎么解" | [reference-error.md](reference-error.md) | `ki_search`（tags=error，语义优先）/ `ki_query_group` |

> **为何只有强关联与决策记忆走"目录优先"**：这两类数量有限、relation 名可读，精确列举能穷举。其余四类中，接口信息/数据流数量中等、专题记忆用自然语言检索更自然、**错误库可能成百上千条必须语义优先**——一刀切反而更差。

### Step 1：按路径准备定位信息

两条路径需要的信息不同，**不要一律去猜模块名**：

| 路径 | 需要准备 |
|------|----------|
| **目录优先**（强关联 / 决策记忆） | 只需**根分组名**——由记忆类型决定，固定为 `关联关系` / `决策记录`。**模块名不需预提取**：由第 1 级 `subtree` 列出子分组后从中挑选，避免代码模块名与 ki 功能模块名不一致导致猜错 |
| **语义检索**（其余四类 + 目录路径的兜底） | 提取**功能模块名 + 关键代码符号**（2-3 个）。代码符号按实际情况选取最能标识目标的一端——类名、方法名、接口名、函数名、枚举/常量名等；核心是选"写入记忆时会出现的、能唯一定位的符号"，带上能显著提高检索准确度 |

### Step 2：按策略检索

加载对应策略 reference，按其检索方式执行。**强关联与决策记忆先走「目录优先」两级导航**（① `subtree` 列出模块子分组 → ② `groups`+`mode="full"` 列举该模块全部条目 → 按 relation 名判断 → `ki_get_module_info` 取内容），`ki_search` 仅在两级都取不到时作语义补位。

### Step 3：利用结果

- **强关联命中** → 记录**牵动清单**（`{被改模块} 与 {其他模块} 强关联：方向/强度/原因`；双向记录按两条影响线分别列出），作为跨模块一致性检查的重点
- **专题记忆命中** → 知晓"有此专家 + 关键入口"，跳转前校验专家路径存在
- **接口信息命中** → 得接口定位（子功能 + 接口列表：API 路径 / 后端接口名 / 文件位置 / 职责），直接据此定位代码
- **数据流命中** → 得数据流向（实体类型 / 结构 / 生产方 / 消费方 / 业务用途），直接据此定位代码
- **决策记忆命中** → 得决策成因（决策 / 背景约束 / 被否决方案及理由 / 重新评估触发条件）；避免重复讨论已否决方案，触发条件满足时提示重新评估
- **错误库命中** → 得报错解法（根因 / 解法 / 验证方式 / 关联方案）；执行后必须按「验证方式」确认，失效则更新条目而非新建
- **未命中 / ki 不可用** → 静默跳过，不阻塞主流程

## 更多资源

- 强关联查询策略（**目录优先** `mode="full"` 精确列举 + **必须全取不挑**），参见 [reference-strong-relation.md](reference-strong-relation.md)
- 专题记忆查询策略，参见 [reference-topic-memory.md](reference-topic-memory.md)
- 接口信息查询策略（tags=api 过滤），参见 [reference-api.md](reference-api.md)
- 数据流查询策略（tags=data 过滤），参见 [reference-data-flow.md](reference-data-flow.md)
- 决策记忆查询策略（**目录优先** `mode="full"` 精确列举 + 避免重复讨论已否决方案），参见 [reference-decision.md](reference-decision.md)
- 错误库查询策略（tags=error 过滤 + 贴整段堆栈检索），参见 [reference-error.md](reference-error.md)
- 记忆的**写入**（SSOT），调用 `use_skill("ki-memory-write")`
