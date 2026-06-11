# Skills

一套面向软件工程全流程的 AI Agent 技能集。从需求挖掘到技术设计，从代码评审到交互设计，覆盖"想清楚 → 设计好 → 写对代码"的完整链路。

## 快速安装

```bash
# 安装 AI Skill 定义
curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.sh | bash -s -- /path/to/your-project --skills

# 安装 CRUD 脚本（需求管理工具）
curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.sh | bash -s -- /path/to/your-project --scripts
```

Windows 用户使用 PowerShell 版本：

```powershell
.\skill-install.ps1 C:\projects\my-app -Skills
.\skill-install.ps1 C:\projects\my-app -Scripts
```

## 技能一览

### 需求与设计

| 技能 | 作用 | 触发词 |
|------|------|--------|
| **[requirement-mining](./skills/requirement-mining/SKILL.md)** | 深度挖掘真实需求，打穿表象找根因，转译为技术需求清单，集成 CRUD 脚本持久化 | "我想做一个xxx"、"帮我分析需求" |
| **[interaction-design](./skills/interaction-design/SKILL.md)** | 设计人机交互层——谁在用、怎么操作、看到什么、出错怎么办 | "设计一下怎么用"、"交互怎么设计" |
| **[work-breakdown](./skills/work-breakdown/SKILL.md)** | 将需求拆分为完全独立的垂直切片工作项，每个切片贯穿所有层 | "拆成独立任务"、"怎么并行开发" |
| **[data-flow-model](./skills/data-flow-model/SKILL.md)** | 构建 ER 图和数据流图，支持并发/分布式/实时流/批处理等场景分析 | "画 ER 图"、"数据怎么流"、"设计数据模型" |
| **[design-craft](./skills/design-craft/SKILL.md)** | 将需求描述转化为面向技术评审的设计文档，默认多文档结构 | "写设计文档"、"帮我设计"、"dd" |
| **[demo-verify](./skills/demo-verify/SKILL.md)** | 针对设计中的风险点构建验证原型，确认可行后再投入开发（复杂需求自动触发） | "先做个 demo 验证"、"试试看" |
| **[design-review](./skills/design-review/SKILL.md)** | 对设计文档进行结构化评审，产出分级问题清单 | "评审设计"、"review 设计文档" |
| **[implementation-report](./skills/implementation-report/SKILL.md)** | 需求完成后生成实现总结报告，记录最终实现效果和偏差 | "生成实现报告"、"记录完成情况" |

### 代码质量

| 技能 | 作用 | 触发词 |
|------|------|--------|
| **[code-review](./skills/code-review/SKILL.md)** | 多语言多维度 Code Review，覆盖安全、性能、架构等七大维度 | "review 这个提交"、"code review" |
| **[challenger](./skills/challenger/SKILL.md)** | 代码质疑者，对 code-review 结果进行二次审查 | "质疑这个修复"、"二次审查" |

### 工具

| 技能 | 作用 | 触发词 |
|------|------|--------|
| **[expert-panel](./skills/expert-panel/SKILL.md)** | 启动多角色专家团进行方案评审 | "专家团评审"、"expert panel" |
| **[create-skill](./skills/create-skill/SKILL.md)** | 引导创建新的 Agent Skill | "创建 skill"、"写一个技能" |
| **[migrate-to-codehub](./skills/migrate-to-codehub/SKILL.md)** | 从其他项目提取优秀设计，迁移到 CodeHub | "迁移到 CodeHub" |

### 需求管理脚本

项目内置一套 Python CRUD 脚本，用于以编程方式管理需求元数据。AI Skill 和 CLI 共享同一套入口。

| 脚本 | 功能 |
|------|------|
| `list-requirements.py` | 查询需求列表，支持按状态/标签/依赖筛选，表格或 JSON 输出 |
| `create-requirements.py` | 新建需求，自动生成 REQ-NNN 全局 ID，原子写入 meta.json |
| `update-requirements.py` | 修改需求元数据（状态/标签/依赖/提交/变更记录），版本号自增 |
| `delete-requirements.py` | 安全删除需求，反向依赖检查，级联清理引用，支持 dry-run |

## 设计流程

这些技能可以串联使用，形成完整的设计-开发流程：

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                          设 计 阶 段                                    │
 │                                                                         │
 │  requirement   interaction   work        data-flow    design           │
 │  -mining   →   -design   →   -breakdown  -model   →   -craft           │
 │                                                                         │
 │    理解需求      设计交互层     拆成独立切片   数据建模+流图   技术设计       │
 └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                      验 证 阶 段（复杂需求自动触发）                      │
 │                                                                         │
 │                          demo-verify                                    │
 │                                                                         │
 │                        验证风险点 → 继续 / 回退设计                       │
 └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                          质 量 阶 段                                    │
 │                                                                         │
 │    design-review  →  code-review  →  challenger                        │
 │                                                                         │
 │      设计评审          代码评审         二次质疑                           │
 └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                        实 现 总 结                                       │
 │                                                                         │
 │              implementation-report                                      │
 │                                                                         │
 │             生成实现报告，记录最终效果和偏差                                │
 └─────────────────────────────────────────────────────────────────────────┘
```

## 项目结构

```
skills/
├── requirement-mining/       # 需求挖掘
├── interaction-design/       # 交互设计
├── work-breakdown/          # 需求拆分
├── data-flow-model/          # 数据流模型
├── design-craft/             # 技术设计
├── design-review/            # 设计评审
├── demo-verify/              # 验证原型
├── implementation-report/    # 实现报告
├── code-review/              # 代码评审
├── challenger/               # 代码质疑
├── expert-panel/             # 专家团
├── create-skill/             # 创建技能
└── migrate-to-codehub/       # 迁移工具

scripts/
├── skill-install.sh           # 一键安装器（Linux/Mac）
├── skill-install.ps1          # 一键安装器（Windows）
└── requirement-mgr/           # 需求管理 CRUD 脚本
```

## 其他 Skill 项目

社区中有很多优秀的 Agent Skill 项目，值得参考和借鉴：

| 项目 | 作者 | 简介 |
|------|------|------|
| [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock | 121k star，面向真实工程的技能集，涵盖 TDD、调试、架构改进、需求对齐 |
| [anthropics/skills](https://github.com/anthropics/skills) | Anthropic | Anthropic 官方 Agent Skills 示例集，含文档处理、创意设计、开发技术等技能，附带 Agent Skills 规范 |
| [obra/superpowers](https://github.com/obra/superpowers) | Jesse Vincent | Claude Code 增强技能集 |

> 如果你有好的 Skill 项目，欢迎提 PR 添加到这里。

## 贡献

1. Fork 本项目
2. 创建你的 skill 目录（参考 [create-skill](./skills/create-skill/SKILL.md)）
3. 提交 PR

## 许可证

[MIT](./LICENSE)
