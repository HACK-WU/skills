# Module Teach · 示例

> 仅展示格式与风格，内容为示意，不代表真实模块。假设目标模块为 `skills/module-teach`（即本技能自身）。

## 示例 1：Phase 2 代码 Wiki 片段

```markdown
# 代码 Wiki：module-teach

**本文引用的文件**
- [技能主文件](file://skills/module-teach/SKILL.md)
- [模板](file://skills/module-teach/reference.md)

## 目录
1. [项目结构](#项目结构)
2. [关键文件](#关键文件)
3. [依赖关系](#依赖关系)

## 项目结构
- `SKILL.md`：技能主指令（流程 + 落盘约定）
- `reference.md`：格式规范与 HTML/Mermaid 模板
- `examples.md`：阶段样例
章节来源：[目录](file://skills/module-teach)

## 关键文件
| 文件 | 职责 | 范围 |
| SKILL.md | 定义 8 阶段渐进流程 | [专用] |
| reference.md | code-to-wiki 格式 + 模板 | [通用] |
章节来源：[SKILL.md](file://skills/module-teach/SKILL.md#L1-L40)

## 依赖关系
- 依赖 create-skill 规范（产出格式）
- 无外部库依赖
章节来源：[SKILL.md](file://skills/module-teach/SKILL.md#L1-L5)
```

## 示例 2：Phase 3 正确性核对片段

```markdown
# 正确性核对：module-teach

## 核对清单

| 序号 | 前序结论 | 判定 | 代码来源 | 备注 |
|------|----------|------|----------|------|
| 1 | 产物落盘到 `.teach/{slug}/` | 已确认 | [SKILL.md](file://skills/module-teach/SKILL.md#L34-L44) | |
| 2 | 全 7 个 md 阶段 | 有误→已修正 | [SKILL.md](file://skills/module-teach/SKILL.md#L34-L44) | 实际含 6 个 md + 1 个 html，非 7 个 md |
| 3 | 通用知识需引权威源 | 存疑 | — | 待用户确认是否强制外链 |

## 修正记录
- 结论"7 个 md 阶段" → 修正为"6 个 md + 1 个 html"，来源见上。
```

## 示例 3：最终 HTML 文档片段（能力大纲 + 数据流）

```html
<h2 id="outline">1. 能力大纲</h2>
<p>本模块把"读懂陌生代码"结构化成一个渐进教学流程。<span class="tag specific">专用</span></p>
<ul>
  <li>确认范围（通用 / 专用 / 两者）<span class="tag general">通用</span> 概念讲解引用权威文档</li>
  <li>8 阶段产出，末阶段汇总为富媒体 HTML</li>
</ul>

<h2 id="dataflow">6. 数据流</h2>
<pre class="mermaid">
flowchart TD
  U[用户需求] --> C[确认范围]
  C --> O[能力大纲] --> W[代码Wiki]
  W --> V{正确性核对}
  V -->|通过| F[功能推演] --> S[应用场景] --> D[数据流] --> H[最终HTML]
  V -->|有误| W
</pre>
<!-- 图表来源：SKILL.md 工作流程章节 -->
```
