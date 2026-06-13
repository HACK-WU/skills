---
description: GitNexus MCP 强制规则，指导 AI 何时用 GitNexus、何时用 grep、如何组合使用
alwaysApply: false
enabled: true
updatedAt: 2026-06-13T17:30:00.000Z
provider:
---

## GitNexus MCP 强制规则

### 工具选择

| 需求 | 工具 |
|------|------|
| 结构关系（依赖、调用、影响） | **GitNexus**（优先） |
| 精确定位（字符串/字段/枚举/常量/配置键） | **grep**（优先） |
| 已知符号名查上下游 | `context` |
| 修改关键类/函数/接口前 | `impact`（必须） |
| 追踪方法级调用链 | `cypher` |
| 只知道概念不知符号名 | `query`（仅此场景） |
| 提交前检查影响面 | `detect_changes` |
| 跨文件重命名 | `rename`（必须先 dry_run=true） |
| 修改 API handler/对外接口 | `api_impact` 或 `impact`+grep |
| `route_map`/`shape_check`/`tool_map` | 低优先级，不作主工具 |

混合需求（结构+定位）**必须混合使用** GitNexus 与 grep，禁止只依赖单一手段。

### MCP 不可用时

**直接告知用户**，切换到 grep/源码阅读继续处理，**禁止伪造结果**，禁止主动输出运维修复方案。

### 核心约束

- **所有结论最终以源码为准**，禁止将图谱结果当最终事实。
- 修改前四步：定位目标 → 结构理解 → 影响评估 → 源码确认，影响不清禁止改代码。
- 方法级查询稳定性弱于类级；属性访问、枚举、字符串引用覆盖不完整。
- 结果异常时先怀疑能力边界，不下否定结论。
