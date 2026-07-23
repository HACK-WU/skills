# Skills

一套面向软件工程全流程的 AI Agent 技能集。从需求挖掘到技术设计，从代码评审到交互设计，覆盖"想清楚 → 设计好 → 写对代码"的完整链路。

## 设计流程

这些技能可以串联使用，形成完整的设计-开发流程：

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                          设 计 前 置                                      │
 │                                                                          │
 │  requirement-mining   dependency-docs    code-survey    demo-verify      │
 │                                                                          │
 │    理解需求   →   整理第三方依赖   →   代码现状调研   →   验证风险点原型     │
 └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                              设 计 阶 段                                  │
 │                                                                          │
 │      interaction   work        data-flow    design                       │
 │       -design   →   -breakdown  -model   →   -craft                      │
 │                                                                          │
 │       设计交互层     拆成独立切片   数据建模+流图   技术设计                 │
 └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           场 景 推 演                                     │
│                                                                          │
│                        scenario-rehearsal                                │
│                                                                          │
│                    模拟真实场景验证可行性 → 返回修改 / 继续                 │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                          设 计 评 审                                      │
 │                                                                          │
 │                          design-review                                   │
 │                                                                          │
 │                    评审设计文档 → 返回修改 / 继续                          │
 └──────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                            骨 架 生 成                                    │
 │                                                                          │
 │               design-to-code（同批顺序无关时调用 task-dispatch 并行 ）     │
 │                                                                          │
 │                    设计 → 代码骨架 + 契约级注释                            │
 └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                          系 统 化 编 码                                   │
 │                                                                          │
 │       code-implement（批量编码，task-dispatch 并行，契约验证）             │
 │                                                                          │
 │          骨架契约注释 → 参考 code-survey + dependency-docs → 填充实现      │
 └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                               质 量 阶 段                                │
 │                                                                         │
 │          code-review  →  challenger  →  test-planner                    │
 │                                                                         │
 │           代码评审       二次质疑        测试验证                         │
 └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                        实 现 总 结                                       │
 │                                                                         │
 │                 implementation-report                                   │
 │                                                                         │
 │                 生成实现报告，记录最终效果和偏差                           │
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

一键下载并执行（用 curl 拉取脚本后直接运行；PowerShell 中 `curl` 是 `Invoke-WebRequest` 的别名，需使用 `curl.exe` 调用真正的 curl）：

```powershell
curl.exe -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.ps1 -o skill-install.ps1; .\skill-install.ps1 -Skills -Target C:\projects\my-app
curl.exe -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.ps1 -o skill-install.ps1; .\skill-install.ps1 -Rules -Target C:\projects\my-app
```

若已下载脚本到本地，可直接执行：

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
| **[frontend-api-guide](./skills/frontend-api-guide/SKILL.md)** | 将 API 设计转化为前端可直接编码的调用流程文档，含 UI 映射和错误处理速查 | "生成前端 API 文档"、"API 调用流程" |
| **[demo-verify](./skills/demo-verify/SKILL.md)** | 针对设计中的风险点构建验证原型，确认可行后再投入开发（复杂需求自动触发） | "先做个 demo 验证"、"试试看" |
| **[design-review](./skills/design-review/SKILL.md)** | 对设计文档进行结构化评审，产出分级问题清单 | "评审设计"、"review 设计文档" |
| **[scenario-rehearsal](./skills/scenario-rehearsal/SKILL.md)** | 模拟真实使用场景推演，支持设计文档（验证设计点可行性）与需求文档（验证需求完整性/一致性/验收可达）两种模式 | "推演一下这个设计"、"推演一下这个需求"、"验证设计方案" |
| **[request-guard](./skills/request-guard/SKILL.md)** | 在用户突然提出修改请求时快速检查合理性，防止被突发奇想带着跑 | "改一下"、"改成"、"优化一下" |
| **[implementation-report](./skills/implementation-report/SKILL.md)** | 需求完成后生成实现总结报告，记录最终实现效果和偏差 | "生成实现报告"、"记录完成情况" |
| **[dependency-docs](./skills/dependency-docs/SKILL.md)** | 设计前识别并整理第三方依赖文档，每个依赖独立成文，≥2 个时 task-dispatch 并行收集 | "整理第三方依赖"、"收集 API 文档" |
| **[code-survey](./skills/code-survey/SKILL.md)** | 设计前对代码库按需调研 13 个维度，ki 优先，≥2 个维度时 task-dispatch 并行搜索 | "代码调研"、"了解现有代码" |
| **[design-to-code](./skills/design-to-code/SKILL.md)** | 从设计文档生成代码骨架+契约级注释，同批顺序无关时 task-dispatch 并行加速 | "生成代码骨架"、"搭骨架" |
| **[code-implement](./skills/code-implement/SKILL.md)** | 系统化地从骨架填充实现，参考 code-survey + dependency-docs，分批编码 + 契约验证 | "编码实施"、"填充骨架"、"实现代码" |
| **[module-teach](./skills/module-teach/SKILL.md)** | 按渐进流程分析讲解代码模块，区分通用与专用知识，产出含 Mermaid 图与 HTML 的学习材料 | "讲讲这个模块"、"学习代码"、"帮我搞懂这块代码" |

### 代码质量

| 技能 | 作用 | 触发词 |
|------|------|--------|
| **[code-review](./skills/code-review/SKILL.md)** | 多语言多维度 Code Review，覆盖安全、性能、架构等七大维度 | "review 这个提交"、"code review" |
| **[challenger](./skills/challenger/SKILL.md)** | 质疑者，对代码变更/设计文档进行二次质疑，代码支持三种策略、设计文档支持设计质疑策略 | "质疑这个修复"、"质疑这个设计"、"二次审查" |
| **[auto-review](./skills/auto-review/SKILL.md)** | 文件写入后自动触发审查修复闭环，判断复杂场景并调用 challenger | "review 这个提交"、"code review" |
| **[test-planner](./skills/test-planner/SKILL.md)** | 自动生成结构化测试计划，支持需求文档/设计文档/API 设计三种来源模式 | "生成测试计划"、"从设计生成测试"、"API 契约测试" |
| **[bug-impact-analysis](./skills/bug-impact-analysis/SKILL.md)** | Bug 修复影响分析，分析根因是否被真正解决、修复是否引入副作用 | "分析 bug 影响"、"评估修复风险" |
| **[api-testing](./skills/api-testing/SKILL.md)** | 基于 httpflex-py 的 HTTP API 自主测试，自动解析接口描述、生成客户端、设计用例矩阵并断言 | "测试 API"、"自动化接口测试"、"验证接口" |
| **[e2e-testing](./skills/e2e-testing/SKILL.md)** | 对真实运行系统执行端到端验证，按业务旅程编排多类型步骤，验证跨组件终态 | "端到端验证"、"真实链路测试"、"跑一遍完整流程" |

### 工具

| 技能 | 作用 | 触发词 |
|------|------|--------|
| **[review-panel](./skills/review-panel/SKILL.md)** | 启动多角色评审团进行方案评审 | "评审团评审"、"review panel" |
| **[document-writer](./skills/document-writer/SKILL.md)** | 为项目生成高质量 README 及子文档，根据项目类型自动选择策略 | "生成 README"、"写项目文档" |
| **[create-rules](./skills/create-rules/SKILL.md)** | 引导创建符合规范的 AI 规则文件 | "创建规则"、"写一个规则" |
| **[create-skill](./skills/create-skill/SKILL.md)** | 引导创建新的 Agent Skill | "创建 skill"、"写一个技能" |
| **[content-simplifier](./skills/content-simplifier/SKILL.md)** | 精简 skill 和 rules 文件内容，识别冗余，优化决策流程清晰度 | "精简skill"、"优化rules"、"清理冗余" |
| **[memory-creator](./skills/memory-creator/SKILL.md)** | 指导 AI 生成简洁的记忆内容描述 | "记住这个"、"创建记忆" |
| **[migrate-to-codehub](./skills/migrate-to-codehub/SKILL.md)** | 从其他项目提取优秀设计，迁移到 CodeHub | "迁移到 CodeHub" |
| **[requirement-doc-store](./skills/requirement-doc-store/SKILL.md)** | 需求相关文档通用存储规范，按文档类型自动决定存储路径 | 需求文档落盘时自动触发 |
| **[task-dispatch](./skills/task-dispatch/SKILL.md)** | 将编码任务拆分为子任务并行分配给子 agent，主 agent 合并集成 | "并行开发"、"拆分子任务并行执行" |
| **[skill-updater](./skills/skill-updater/SKILL.md)** | 新增/删除技能后同步更新安装脚本中的静态文件列表 | "更新安装脚本"、"同步技能列表" |
| **[expert-lookup](./skills/expert-lookup/SKILL.md)** | 查找并复用已沉淀的业务专家资产包，通过语义匹配定位可复用的分析框架 | "查找专家"、"复用分析框架"、"有类似分析吗" |
| **[expert-team](./skills/expert-team/SKILL.md)** | 派出多专家子 agent 并行深挖业务模块，各自独立分析后合并成完整画像 | "深挖模块"、"专家团队分析"、"并行分析" |
| **[solution-capture](./skills/solution-capture/SKILL.md)** | 将解决非平凡问题的过程沉淀为可复用的解决方案 skill，存入 .solutions/ | "记录这个方案"、"沉淀一下"、"保存解决方案" |
| **[solution-lookup](./skills/solution-lookup/SKILL.md)** | 查找并复用已沉淀的解决方案 skill，通过关键词匹配定位 .solutions/ 中的方案 | "有没有类似方案"、"之前怎么解决的"、"查找方案" |

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
| `req archive` | 归档需求或单个文档到 archive/，整体归档更新状态，文档级归档（--doc）不改状态，支持 dry-run 和 --force |

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
├── dependency-docs/          # 第三方依赖整理
├── code-survey/              # 代码现状调研
├── design-craft/             # 技术设计
├── design-to-code/           # 设计到代码骨架
├── code-implement/           # 骨架编码实施
├── negative-requirement/     # 负向场景分析
├── api-design/               # API 设计
├── frontend-api-guide/       # 前端集成指南
├── design-review/            # 设计评审
├── demo-verify/              # 验证原型
├── scenario-rehearsal/       # 场景推演
├── request-guard/            # 请求守卫
├── implementation-report/    # 实现报告
├── code-review/              # 代码评审
├── challenger/               # 质疑（代码/设计）
├── auto-review/              # 自动审查修复闭环
├── bug-impact-analysis/      # Bug 影响分析
├── test-planner/             # 测试计划生成
├── review-panel/             # 评审团
├── task-dispatch/            # 任务并行调度
├── document-writer/          # 项目文档生成
├── create-rules/             # 创建规则
├── create-skill/             # 创建技能
├── skill-updater/            # 安装脚本更新
├── content-simplifier/       # 内容精简
├── memory-creator/           # 记忆生成
├── migrate-to-codehub/       # 迁移工具
├── requirement-doc-store/    # 需求文档存储规范
├── expert-lookup/            # 业务专家查找
├── expert-team/              # 专家团队并行深挖
├── solution-capture/         # 解决方案沉淀
└── solution-lookup/          # 解决方案查找

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
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | Addy Osmani | 开源 Agent Skills 合集，含多类工程实践技能 |

> 如果你有好的 Skill 项目，欢迎提 PR 添加到这里。

## 贡献

1. Fork 本项目
2. 创建你的 skill 目录（参考 [create-skill](./skills/create-skill/SKILL.md)）
3. 提交 PR

## 许可证

[MIT](./LICENSE)
