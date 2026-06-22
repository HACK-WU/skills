# Skills

一套面向软件工程全流程的 AI Agent 技能集。从需求挖掘到技术设计，从代码评审到交互设计，覆盖"想清楚 → 设计好 → 写对代码"的完整链路。

## 设计流程

这些技能可以串联使用，形成完整的设计-开发流程：

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                          设 计 阶 段                                    │
 │                                                                         │
 │  requirement   interaction   work        data-flow    design           │
 │  -mining   →   -design   →   -breakdown  -model   →   -craft           │
 │                                                                         │
 │    理解需求      设计交互层     拆成独立切片   数据建模+流图   技术设计         │
 └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                      验 证 阶 段（复杂需求自动触发）                         │
 │                                                                         │
 │                          demo-verify                                    │
 │                                                                         │
 │                        验证风险点 → 继续 / 回退设计                         │
 └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
│                               质 量 阶 段                                 │
│                                                                          │
│  design-review  →  coding  →  code-review  →  challenger  →  test-planner│
│                                                                          │
│   设计评审          代码实现         代码评审       二次质疑        测试验证   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                        实 现 总 结                                       │
 │                                                                         │
 │              implementation-report                                      │
 │                                                                         │
 │             生成实现报告，记录最终效果和偏差                                  │
 └─────────────────────────────────────────────────────────────────────────┘
```

## 快速安装

```bash
# 一键安装
curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.sh | \
  bash -s -- --skills -t /path/to/your-project
```

> 也可以先下载脚本后执行：
> ```bash
> git clone https://github.com/HACK-WU/skills.git && cd skills
> # 或 curl -fsSL .../skill-install.sh -o skill-install.sh
> bash scripts/skill-install.sh --skills -t /path/to/your-project
> ```

### 参数说明

| 参数 | 作用 |
|------|------|
| `--skills` | 安装 AI Skill 定义文件（与 `--rules` 互斥） |
| `--rules` | 安装 AI 规则文件（与 `--skills` 互斥） |

**目标目录**（三选一，优先级从高到低）：

| 方式 | 示例 |
|------|------|
| `-t` 直接指定（支持多个） | `-t ~/projects/app -t ~/projects/api` |
| `--file` 配置文件 | `--file ~/my-targets.txt`（每行一个目录，`#` 注释） |
| 不指定，读默认配置 | `--skills` → `~/.skill-targets`，`--rules` → `~/.rule-targets` |

### Windows（PowerShell）

参数映射：`--skills` → `-Skills`，`--rules` → `-Rules`，`-t` → `-Target`，`--file` → `-ConfigFile`。

```powershell
.\skill-install.ps1 -Skills -Target C:\projects\my-app
.\skill-install.ps1 -Rules -Target C:\projects\my-app
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
| **[negative-requirement](./skills/negative-requirement/SKILL.md)** | 从正向需求出发分析负向场景，设计程序的检测、恢复和引导策略 | "错误处理"、"异常场景"、"边界情况" |
| **[api-design](./skills/api-design/SKILL.md)** | 基于设计文档生成详细的 API 设计文档，含完整接口契约和错误码定义 | "设计 API"、"接口设计"、"api design" |
| **[demo-verify](./skills/demo-verify/SKILL.md)** | 针对设计中的风险点构建验证原型，确认可行后再投入开发（复杂需求自动触发） | "先做个 demo 验证"、"试试看" |
| **[design-review](./skills/design-review/SKILL.md)** | 对设计文档进行结构化评审，产出分级问题清单 | "评审设计"、"review 设计文档" |
| **[scenario-rehearsal](./skills/scenario-rehearsal/SKILL.md)** | 设计完成后模拟真实使用场景推演，验证数据走向和关键设计点可行性 | "推演一下这个设计"、"验证设计方案" |
| **[implementation-report](./skills/implementation-report/SKILL.md)** | 需求完成后生成实现总结报告，记录最终实现效果和偏差 | "生成实现报告"、"记录完成情况" |

### 代码质量

| 技能 | 作用 | 触发词 |
|------|------|--------|
| **[code-review](./skills/code-review/SKILL.md)** | 多语言多维度 Code Review，覆盖安全、性能、架构等七大维度 | "review 这个提交"、"code review" |
| **[challenger](./skills/challenger/SKILL.md)** | 代码质疑者，对 code-review 结果进行二次审查，支持三种质疑策略 | "质疑这个修复"、"二次审查" |
| **[auto-review](./skills/auto-review/SKILL.md)** | 文件写入后自动触发审查修复闭环，判断复杂场景并调用 challenger | "review 这个提交"、"code review" |
| **[test-planner](./skills/test-planner/SKILL.md)** | 根据需求文档自动生成结构化测试计划，覆盖功能/性能/安全等维度 | "生成测试计划"、"写测试用例" |

### 工具

| 技能 | 作用 | 触发词 |
|------|------|--------|
| **[expert-panel](./skills/expert-panel/SKILL.md)** | 启动多角色专家团进行方案评审 | "专家团评审"、"expert panel" |
| **[document-writer](./skills/document-writer/SKILL.md)** | 为项目生成高质量 README 及子文档，根据项目类型自动选择策略 | "生成 README"、"写项目文档" |
| **[create-rules](./skills/create-rules/SKILL.md)** | 引导创建符合规范的 AI 规则文件 | "创建规则"、"写一个规则" |
| **[create-skill](./skills/create-skill/SKILL.md)** | 引导创建新的 Agent Skill | "创建 skill"、"写一个技能" |
| **[content-simplifier](./skills/content-simplifier/SKILL.md)** | 精简 skill 和 rules 文件内容，识别冗余，优化决策流程清晰度 | "精简skill"、"优化rules"、"清理冗余" |
| **[memory-creator](./skills/memory-creator/SKILL.md)** | 指导 AI 生成简洁的记忆内容描述 | "记住这个"、"创建记忆" |
| **[migrate-to-codehub](./skills/migrate-to-codehub/SKILL.md)** | 从其他项目提取优秀设计，迁移到 CodeHub | "迁移到 CodeHub" |
| **[requirement-doc-store](./skills/requirement-doc-store/SKILL.md)** | 需求相关文档通用存储规范，按文档类型自动决定存储路径 | 需求文档落盘时自动触发 |

### 规则

| 规则 | 作用 | 适用场景 |
|------|------|----------|
| **[gitnexus-mcp-rules](./rules/gitnexus-mcp-rules.md)** | GitNexus MCP 强制规则，指导工具选择和使用方式 | 使用 GitNexus MCP 时 |
| **[writing-pipeline](./rules/writing-pipeline.md)** | 自动审查修复闭环，复杂场景调用 challenger 二次质疑 | 文档或代码编写完成后 |

### 需求管理脚本

项目内置一套 Python CRUD 脚本，通过 `req` CLI 命令统一入口，支持以编程方式管理需求元数据。

```bash
# 安装 req 命令（自动获取最新版本）
curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/install-latest.sh | bash
```

| 命令 | 功能 |
|------|------|
| `req list` | 查询需求列表，支持按状态/标签/依赖筛选，表格或 JSON 输出 |
| `req create` | 新建需求，自动生成 REQ-NNN 全局 ID，原子写入 meta.json |
| `req update` | 修改需求元数据（状态/标签/依赖/提交/变更记录），版本号自增 |
| `req delete` | 安全删除需求，反向依赖检查，级联清理引用，支持 dry-run |

> 📖 完整文档：[docs/README.md](./docs/README.md)

### 需求管理文档

| 文档 | 说明 |
|------|------|
| [快速开始](./docs/README.md) | 安装、配置、核心命令速览 |
| [命令参考](./docs/command-reference.md) | `req` 命令行工具的所有命令及其参数和输出示例 |
| [配置指南](./docs/configuration.md) | 配置文件格式、配置项详解和约束规则 |
| [架构文档](./docs/requirement-mgr-guide.md) | 系统架构、技术实现细节、数据模型 |
| [故障排查](./docs/troubleshooting.md) | 常见问题及解决方案 |


## 项目结构

```
skills/
├── requirement-mining/       # 需求挖掘
├── interaction-design/       # 交互设计
├── work-breakdown/          # 需求拆分
├── data-flow-model/          # 数据流模型
├── design-craft/             # 技术设计
├── negative-requirement/     # 负向场景分析
├── api-design/               # API 设计
├── design-review/            # 设计评审
├── demo-verify/              # 验证原型
├── scenario-rehearsal/       # 场景推演
├── implementation-report/    # 实现报告
├── code-review/              # 代码评审
├── challenger/               # 代码质疑
├── auto-review/              # 自动审查修复闭环
├── test-planner/             # 测试计划生成
├── expert-panel/             # 专家团
├── document-writer/          # 项目文档生成
├── create-rules/             # 创建规则
├── create-skill/             # 创建技能
├── content-simplifier/       # 内容精简
├── memory-creator/           # 记忆生成
├── migrate-to-codehub/       # 迁移工具
└── requirement-doc-store/    # 需求文档存储规范

rules/
├── gitnexus-mcp-rules.md      # GitNexus MCP 强制规则
└── writing-pipeline.md        # 自动审查修复闭环

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
