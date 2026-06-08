# Skills

一套面向软件工程全流程的 AI Agent 技能集。从需求挖掘到技术设计，从代码评审到交互设计，覆盖"想清楚 → 设计好 → 写对代码"的完整链路。

## 技能一览

### 需求与设计

| 技能 | 作用 | 触发词 |
|------|------|--------|
| **[requirement-mining](./requirement-mining/SKILL.md)** | 深度挖掘真实需求，打穿表象找根因，转译为技术需求清单 | "我想做一个xxx"、"帮我分析需求" |
| **[interaction-design](./interaction-design/SKILL.md)** | 设计人机交互层——谁在用、怎么操作、看到什么、出错怎么办 | "设计一下怎么用"、"交互怎么设计" |
| **[work-breakdown](./work-breakdown/SKILL.md)** | 将需求拆分为完全独立的垂直切片工作项，每个切片贯穿所有层 | "拆成独立任务"、"怎么并行开发" |
| **[data-flow-model](./data-flow-model/SKILL.md)** | 构建 ER 图和数据流图，支持并发/分布式/实时流/批处理等场景分析 | "画 ER 图"、"数据怎么流"、"设计数据模型" |
| **[design-craft](./design-craft/SKILL.md)** | 将需求描述转化为面向技术评审的设计文档，默认多文档结构 | "写设计文档"、"帮我设计"、"dd" |
| **[design-review](./design-review/SKILL.md)** | 对设计文档进行结构化评审，产出分级问题清单 | "评审设计"、"review 设计文档" |

### 代码质量

| 技能 | 作用 | 触发词 |
|------|------|--------|
| **[code-review](./code-review/SKILL.md)** | 多语言多维度 Code Review，覆盖安全、性能、架构等七大维度 | "review 这个提交"、"code review" |
| **[challenger](./challenger/SKILL.md)** | 代码质疑者，对 code-review 结果进行二次审查 | "质疑这个修复"、"二次审查" |

### 工具

| 技能 | 作用 | 触发词 |
|------|------|--------|
| **[expert-panel](./expert-panel/SKILL.md)** | 启动多角色专家团进行方案评审 | "专家团评审"、"expert panel" |
| **[create-skill](./create-skill/SKILL.md)** | 引导创建新的 Agent Skill | "创建 skill"、"写一个技能" |
| **[migrate-to-codehub](./migrate-to-codehub/SKILL.md)** | 从其他项目提取优秀设计，迁移到 CodeHub | "迁移到 CodeHub" |

## 设计流程

这些技能可以串联使用，形成完整的设计-开发流程：

```
requirement-mining → interaction-design → work-breakdown → data-flow-model → design-craft
      理解需求            设计交互层           拆成独立切片       数据建模+流图      技术设计
                                                                                              ↓
                                                                                      design-review
                                                                                      code-review
                                                                                      challenger
                                                                                            代码质量
```

## 其他 Skill 项目

社区中有很多优秀的 Agent Skill 项目，值得参考和借鉴：

| 项目 | 作者 | 简介 |
|------|------|------|
| [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock | 121k star，面向真实工程的技能集，涵盖 TDD、调试、架构改进、需求对齐 |
| [anthropics/skills](https://github.com/anthropics/skills) | Anthropic | Anthropic 官方 Agent Skills 示例集，含文档处理、创意设计、开发技术等技能，附带 Agent Skills 规范 |
| [obra/superpowers](https://github.com/obra/superpowers) | Jesse Vincent | Claude Code 增强技能集 |

> 如果你有好的 Skill 项目，欢迎提 PR 添加到这里。

## 项目结构

```
skills/
├── requirement-mining/    # 需求挖掘
│   ├── SKILL.md
│   └── references/
├── interaction-design/    # 交互设计
│   └── SKILL.md
├── work-breakdown/        # 工作项拆分
│   └── SKILL.md
├── data-flow-model/       # 数据建模与流图
│   └── SKILL.md
├── design-craft/          # 设计文档生成
│   ├── SKILL.md
│   ├── reference.md
│   └── SUB_TEMPLATE.md
├── design-review/         # 设计文档评审
│   ├── SKILL.md
│   └── reference.md
├── code-review/           # 代码评审
│   └── SKILL.md
├── challenger/            # 代码质疑
│   ├── SKILL.md
│   ├── strategies/
│   └── templates/
├── expert-panel/          # 专家团评审
│   ├── SKILL.md
│   └── references/
├── create-skill/          # 创建技能
│   └── SKILL.md
└── migrate-to-codehub/    # 迁移到 CodeHub
    └── SKILL.md
```

## 贡献

1. Fork 本项目
2. 创建你的 skill 目录（参考 [create-skill](./create-skill/SKILL.md)）
3. 提交 PR

## 许可证

[MIT](./LICENSE)
