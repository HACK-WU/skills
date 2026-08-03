# Topic Teach 参考模板

供 [SKILL.md](SKILL.md) 各阶段引用的模板与格式规范。产物成品示例见 [examples.md](examples.md)。

## 目录

- [单课模板](#单课模板)
- [学习档案模板](#学习档案模板)
- [知识地图模板](#知识地图模板)
- [接力提示词模板](#接力提示词模板)
- [HTML 内联片段模板（按需使用）](#html-内联片段模板按需使用)
- [免责声明与风险提示模板](#免责声明与风险提示模板)
- [Quiz 文件格式](#quiz-文件格式)

---

## 单课模板

`lessons/lesson-NN-{slug}.md` 骨架（速览模式 `overview.md` 为其浓缩版，可省略课后小测，但须含"速览大纲"与"延伸学习提示词"，见 SKILL.md 速览模式）：

````markdown
# 第 N 课：{课名}

> 所属课程：{主题} ｜ 水平：{零基础/入门/进阶} ｜ 上一课：[第 N-1 课](lesson-NN.md)

## 🎯 本课目标

- 目标 1（学完能干什么，动词开头）
- 目标 2
- 目标 3（≤ 3 条）

## 从一个类比说起

{生活化类比，2-4 句。先讲类比故事，再点破"这就是 {核心概念}"}

## 原理讲解

### {小节 1}

{讲解正文。涉及流程/结构/交互/状态时配 Mermaid 图，图后一句话解读}

```mermaid
flowchart TD
    A[...] --> B[...]
```

> 💡 **类比的边界**：{上面的类比在哪一点上不再成立，真实机制是什么}

### {小节 2}

...

## 动手环节

{技术域：可运行命令/代码 + 预期输出；非技术域：案例推演 + 计算表格}

### 命令速查卡（仅技术域）

| 命令 | 作用 | 常用参数 |
|------|------|----------|
| ... | ... | ... |

## 🐞 常见误区

1. **{误区 1}**：{为什么容易这么想错，正确理解是什么}
2. **{误区 2}**：...

## 一图总结

```mermaid
{本课知识浓缩图}
```

## 课后小测

**Q1**：{题干}
- A. ...
- B. ...
- C. ...
- D. ...

<details><summary>答案与解析</summary>

**答案：X**。{一句话解析，点明易混点}

</details>

**Q2**：...

## 🚀 下一课接力提示词

> 学完本课后，**复制下面这段文字发给 AI**，即可无缝进入下一课（无需重新描述上下文）：

```
继续学 {主题}。我的学习档案在 .teach-topics/{topic-slug}/00-学习档案.md，
刚学完第 {N} 课《{课名}》，请按大纲继续讲解第 {N+1} 课《{课名}》。
```

> 若这是最后一课，改为"🎉 课程已完成"提示 + 建议进入 Phase 3 汇总手册。
````

---

## 学习档案模板

`00-学习档案.md`：

```markdown
# {主题} 学习档案

## 学习者画像

| 项目 | 值 | 来源 |
|------|-----|------|
| 主题 | k8s 基础 | 用户指定 |
| 当前水平 | 零基础 | 用户指定 |
| 学习目标 | 动手实操 | 默认值（用户未指定） |
| 输出格式 | Markdown（主载体，HTML 按需） | 默认值 |
| 模式 | 课程制 | 自动判定，用户已确认 |

## 课时进度表

| 课时 | 课名 | 状态 | 完成日期 | 小测成绩 |
|------|------|------|----------|----------|
| 01 | 容器与 Pod | ✅ 已完成 | 2026-07-31 | 2/2 |
| 02 | Deployment 与副本 | 🔄 进行中 | - | - |
| 03 | Service 与网络 | ⬜ 未开始 | - | - |

## 大纲调整记录

> 大纲是活文档，每次调整在此追加一行（与 `01-知识地图.md` 同步更新）。

| 日期 | 调整内容 | 原因 |
|------|----------|------|
| 2026-07-31 | 第 2 课拆为 2a/2b 两课 | 用户反馈 Deployment 概念偏难，需放慢节奏 |
| 2026-08-02 | 新增第 6 课"网络策略" | 用户目标从"理解概念"改为"动手实操" |
```

**断点续学规则**：读此表找第一个非"已完成"课时继续；状态流转为 `⬜ 未开始 → 🔄 进行中 → ✅ 已完成`。续学前先看"大纲调整记录"，确认课程表是否已变。

---

## 知识地图模板

`01-知识地图.md`（**活文档**：随学习进度 / 目标变更 / 重点变更动态调整，调整记录写回 `00-学习档案.md` 的"大纲调整记录"表）：

````markdown
# {主题} 知识地图

> 本文件是活文档，随学习进度动态调整。每次调整：更新下方图表与课程表 → 在 `00-学习档案.md` 追加调整记录。

## 前置依赖图

```mermaid
graph TD
    A[Linux 进程与隔离] --> B[容器基础]
    B --> C[Pod]
    C --> D[Deployment]
    C --> E[Service 网络]
    style A fill:#ddd,color:#999
```

> 灰色节点为按你的画像判断已掌握的前置，课程中不再展开。

## 课程表

| 课号 | 课名 | 一句话目标 | 预计篇幅 | 状态 |
|------|------|-----------|----------|------|
| 01 | ... | ... | 短/中/长 | ✅ 已完成 |
| 02 | ... | ... | 短/中/长 | ⬜ 未开始 |

## 当前阶段边界

本次学习计划讲到这里：第 {N} 课《{课名}》。完成该课后可阶段性收束，或按需扩展。
````

---

## 接力提示词模板

**目的**：让用户复制一句话即可无缝续学，无需重新描述上下文。所有模式（课程制 / 速览 / 续学 / 汇总后）均需提供。

### 1. 课程制 · 下一课接力提示词

写在每课产物 `lessons/lesson-NN-{slug}.md` 末尾，同时原样贴在对话中：

````markdown
## 🚀 下一课接力提示词

> 学完本课后，**复制下面这段文字发给 AI**，即可无缝进入下一课（无需重新描述上下文）：

```
继续学 {主题}。我的学习档案在 .teach-topics/{topic-slug}/00-学习档案.md，
刚学完第 {N} 课《{课名}》，请按大纲继续讲解第 {N+1} 课《{课名}》。
```

> 若这是最后一课，改为"🎉 课程已完成"提示 + 建议进入 Phase 3 汇总手册。
````

### 2. 速览 · 延伸学习提示词

写在 `overview.md` 末尾，让速览可自然升级为系统学习：

````markdown
## 🚀 想深入？复制发给 AI

```
我刚看了 .teach-topics/{topic-slug}/overview.md 关于 {主题} 的速览，
想进一步学习，请按我的情况（{水平} / 目标 {目标}）把 {延伸方向} 展开成一个课程。
```
````

### 3. 汇总手册 · 结课提示词

写在 `final-课程手册.md` 末尾（课程制 Phase 3）：

```markdown
## 🚀 接下来可以做什么

- **复盘**：复制"考我一下 {主题}，针对 {薄弱点}"进行知识点对齐。
- **进阶**：告诉我下一步想深入的方向，我会基于当前档案调整大纲继续。
```

---

## 免责声明与风险提示模板

非技术域（投资/理财/医疗/法律）每篇产物**顶部**放：

```markdown
> ⚠️ **免责声明**：本材料仅用于知识学习，不构成投资/医疗/法律建议。文中数据标注了时点，
> 可能已过时；任何决策请咨询持牌专业人士并自行核实最新信息。
```

数字标注格式：`年化利率约 X%（数据时点：YYYY-MM，核查于 YYYY-MM）`。

**红线自查清单**（每篇非技术域产物发布前过一遍）：
- [ ] 未推荐任何具体标的 / 产品 / 药品 / 操作
- [ ] 所有数字有时点标注
- [ ] 顶部含免责声明
- [ ] 案例人物为虚构且已注明

---

## HTML 内联片段模板（按需使用）

**定位**：HTML 不是主载体。仅当 md 中确有"关系图 / 数据流 / 复杂结构"等 Mermaid 难以清晰表达的内容时，优先在 md 内**内联 HTML 片段**（`<details>` + 内嵌 `<style>`）；仅当用户明确要求独立 HTML 文件时才生成完整 `final-课程手册.html`。**禁止对 md 内容做无增量价值的整篇转写**——HTML 必须比 md 多提供"可视化 / 交互 / 跳转"层面的价值。

> **⚠️ 兼容性注意**：内联 `<style>` 在 GitHub / GitLab 等平台会被剥离（仅 `<details>` / `<div>` 等结构保留），本地预览（VS Code / Typora）则正常渲染。因此：结构型内容（折叠、框线布局）适合内联；若可视化强依赖 CSS 样式且用户主要在网页平台查看，应改用独立 HTML 文件而非内联。

### 内联片段示例（写入 md）

```markdown
<details>
<summary>💡 展开：容器网络数据流可视化</summary>
<style>
  .flow-box { border: 1px solid #ccc; border-radius: 6px; padding: .75rem; margin: .5rem 0; }
  .flow-arrow { color: #2e7d32; font-weight: 700; }
</style>
<div class="flow-box">
  Pod A（10.0.0.2）<span class="flow-arrow">→</span> eth0 <span class="flow-arrow">→</span> veth <span class="flow-arrow">→</span> cni0 网桥 <span class="flow-arrow">→</span> 路由表 <span class="flow-arrow">→</span> 物理网卡
</div>
</details>
```

> 若仅需折叠交互（不依赖样式），可省略 `<style>`，`<details>` + 纯文本/表格即可在 GitHub 正常折叠。

### 独立 HTML 骨架（仅用户明确要求时）

`final-课程手册.html` 单文件结构（静态富媒体，无 JS 交互逻辑，Mermaid 渲染除外）：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{主题} 课程手册</title>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  mermaid.initialize({ startOnLoad: true });
</script>
<style>
  /* Tufte 风格要点：大留白、衬线正文、窄栏 */
  body { max-width: 860px; margin: 0 auto; padding: 2rem 1.5rem;
         font-family: "Source Han Serif SC", "Noto Serif CJK SC", Georgia, serif;
         line-height: 1.75; color: #111; }
  h1, h2, h3 { font-family: "Source Han Sans SC", "Noto Sans CJK SC", sans-serif; }
  h2 { border-bottom: 1px solid #ddd; padding-bottom: .3rem; margin-top: 3rem; }
  code, pre { font-family: "JetBrains Mono", Consolas, monospace; background: #f6f6f6; }
  pre { padding: 1rem; overflow-x: auto; border-radius: 6px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ddd; padding: .5rem .75rem; text-align: left; }
  th { background: #f6f6f6; }
  /* callout 提示框 */
  .callout { border-left: 4px solid; padding: .75rem 1rem; margin: 1rem 0; border-radius: 0 6px 6px 0; }
  .callout.tip     { border-color: #2e7d32; background: #f0f7f0; }
  .callout.trap    { border-color: #c62828; background: #fdf0f0; }
  .callout.warn    { border-color: #ef6c00; background: #fdf6ec; }
  details { margin: 1rem 0; }
  details > summary { cursor: pointer; font-weight: 600; }
  nav.toc { background: #fafafa; padding: 1rem 1.5rem; border-radius: 8px; }
</style>
</head>
<body>

<h1>{主题} 课程手册</h1>
<p class="meta">水平：{画像} ｜ 生成日期：{日期} ｜ 共 {N} 课</p>

<!-- 非技术域必须：免责声明 -->
<div class="callout warn">⚠️ <strong>免责声明</strong>：...</div>

<nav class="toc">
  <strong>目录</strong>
  <ol>
    <li><a href="#map">知识地图</a></li>
    <li><a href="#lesson-1">第 1 课：{课名}</a></li>
    <!-- 每课一项 -->
  </ol>
</nav>

<h2 id="map">知识地图</h2>
<pre class="mermaid">graph TD
  A[...] --> B[...]</pre>

<h2 id="lesson-1">第 1 课：{课名}</h2>
<!-- 按单课结构转写：目标 → 类比 → 原理(含 mermaid) → 实操 → 误区 → 一图总结 -->
<div class="callout tip">💡 <strong>重点</strong>：...</div>
<div class="callout trap">🐞 <strong>常见误区</strong>：...</div>
<details><summary>展开：命令速查卡</summary>
  <table>...</table>
</details>

<!-- 学习目标附加章节（应试→考点速记 / 决策→决策清单）放最后 -->

</body>
</html>
```

要点：
- **仅按需使用**：默认不生成独立 HTML；优先用上面的内联片段。生成独立文件前先自问"这个 HTML 比 md 多提供了什么增量价值？"——答不出就不生成
- Mermaid 图写在 `<pre class="mermaid">` 中，由 CDN 脚本渲染
- callout 三类固定语义：`tip`（💡 重点）/ `trap`（🐞 误区）/ `warn`（⚠️ 风险）
- 长内容（速查卡、扩展阅读）一律用 `<details>` 折叠，保持主线清爽
- 无网络环境下 Mermaid 不渲染但原文可读，可接受

---

## Quiz 文件格式

与 module-teach 的 quiz-history 格式一致（命名统一：最新一轮 `07-知识点对齐.md` + 历史 `quiz-history/round-NN.md`），便于用户跨技能形成统一习惯。完整机制见 module-teach Phase 8，此处仅列出文件格式。

`quiz-history/round-NN.md`：

```markdown
# 第 NN 轮知识点对齐 · {主题}

- 日期：YYYY-MM-DD
- 正确率：X/Y（ZZ%）

## 题目明细

### Q1（知识点：{标签}）

题干：...
- A. ...（迷惑来源：{与正确项差在哪}）
- B. ...
- C. ...
- D. ...

正确答案：B ｜ 用户作答：A ｜ ❌
解析：...
```

`quiz-history/INDEX.md`：

```markdown
# 知识点对齐轮次索引 · {主题}

| 轮次 | 日期 | 正确率 | 错题知识点 |
|------|------|--------|-----------|
| 01 | 2026-07-31 | 3/5 (60%) | Service 类型区分、Pod 生命周期 |
```
