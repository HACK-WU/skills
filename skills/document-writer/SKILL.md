---
name: document-writer
description: 为项目生成高质量 README 及子文档。根据项目类型（库/SDK、CLI 工具、Web 应用、插件）自动选择编写策略，README 作为索引枢纽，详细内容拆分到子文档。强制要求每个对外接口附输入输出示例，杜绝空洞占位符。子文档 ≥ 2 个时自动调用 task-dispatch 并行生成以加速。适用于"生成 README"、"写项目文档"、"补文档"、"document this project"、"write docs"、"write readme"、"给我写文档" 等场景。
---

# 项目文档生成器

## 何时使用

满足以下任一条件时触发本 skill：

- 用户明确要求为项目生成 README 或完整文档
- 新建项目需要对外发布的文档
- 已有项目缺少文档需要补齐
- 用户说"写个 README"、"生成文档"、"document this"、"补文档" 等

### 何时不使用

以下情况**不触发**：

- 用户只是问"README 怎么写" → 直接回答
- 用户只要求写单一章节 → 直接写
- 项目没有代码（纯文档仓库、配置仓库）→ 无法自动识别类型
- 用户明确表示只需要一个简单草稿 → 不走质量检查

### 快速通道

项目同时满足以下**全部条件**时，跳过阶段 2，合并阶段 1 + 2，直接进入内容生成：

- 公开 API 或命令数 ≤ 5 个
- 配置项 ≤ 5 个
- 用户未要求子文档拆分
- 项目类型判定明确（非混合型）

快速通道只生成单个 README（不拆子文档），但仍遵守全部质量底线。

## 核心原则

1. **类型驱动策略**：先识别项目类型，再套用对应策略
2. **示例即血肉**：每个对外接口（API/命令/配置项）必须有输入→输出完整示例
3. **README 是索引**：README 不超过一屏，做导航枢纽；详细信息按主题拆分到子文档
4. **按需拆分**：有拆分阈值，简单项目不冗余拆分，复杂项目不遗漏文档
5. **并行生成**：子文档 ≥ 2 时自动调用 task-dispatch 并行生成
6. **零空洞容忍**：禁止出现 "TODO"、"Coming soon"、"See source code" 等占位符

---

## 工作流总览

```
阶段 1：项目扫描 + 类型识别   → 分析项目结构，自动判定类型
阶段 2：策略确认 + 拆分决策   → 确定文档集，阈值判断是否需要子文档
阶段 3：并行内容生成          → 子文档 ≥ 2 时 task-dispatch 并行生成
阶段 4：补充交叉引用 + 质量检查 → 主 agent 统一补充 README 中的子文档链接
阶段 5：输出落盘              → 写入文件，给出文档导航概览
```

## 阶段 1：项目扫描 + 类型识别

### 1.1 扫描项目结构

分析以下内容（扫描结果不足以判断时再询问用户）：

- 根目录文件：`package.json`、`setup.py`、`pyproject.toml`、`go.mod`、`Cargo.toml`、`Makefile` 等
- 目录结构：`src/`、`lib/`、`commands/`、`routes/`、`controllers/` 等
- 入口文件：`index.js`、`main.go`、`app.py`、`cli.js` 等
- 依赖框架：从依赖列表中识别 Express、Flask、React、Commander 等
- 现有文档：是否已有 README、CONTRIBUTING、CHANGELOG 等

### 1.2 类型判定规则

| 项目类型 | 核心判定特征 |
|----------|-------------|
| **库 / SDK** | `package.json` 含 `main`/`exports`/`module`；`setup.py`；Go module；主要导出函数/类 |
| **CLI 工具** | `package.json` 含 `bin`；使用 commander/yargs/cobra/click/argparse 等；入口以解析命令行参数为主 |
| **Web 应用/服务** | 依赖 express/koa/next/flask/django/gin 等；含路由/控制器定义；包含 HTTP 服务启动逻辑 |
| **插件/扩展** | 依赖宿主框架（VS Code/Webpack/Babel/ESLint 等）；`package.json` 含 `engines`/`contributes` |

**混合类型**：若同时满足多种特征，合并对应策略，输出判定结果让用户确认。

### 1.3 逆向生成模式

若项目**完全没有 README**，进入逆向模式：从代码入口反推用途、从导出接口反推 API 列表、从 CLI 入口反推命令列表，标注「从代码推断，请验证」。

### 1.4 已有 README 更新模式

若项目**已有 README 但质量不达标**：保留项目描述/徽章/用户确认的信息；补充缺失的示例/空白章节；新增该类型策略应触发的子文档；重写信息密度低的章节。标注「保留/新增/重写」让用户确认。

### 1.5 输出判定结果

```markdown
## 项目类型判定

- **项目名称**：[从 package.json/setup.py 等提取]
- **判定类型**：[库 / CLI / Web 应用 / 插件 / 混合型]
- **判定依据**：[列出匹配到的关键特征]
- **推荐文档集**：[列出将生成的文档列表]

请确认或手动指定类型。
```

## 阶段 2：策略确认 + 拆分决策

### 2.1 获取策略模板

根据确认的类型，从 `references/strategies.md` 加载对应策略模板。

### 2.2 拆分阈值判断

**库/SDK**：公开 API > 5 → `api-reference.md`；配置项 > 10 → `configuration.md`；有高级用法 → `advanced-usage.md`

**CLI**：命令数 > 5 → `command-reference.md`；配置项 > 10 → `configuration.md`；支持 CI/CD 集成 → `integration.md`

**Web 应用**：部署步骤 > 3 或多环境 → `deployment.md`；模块/服务 > 3 → `architecture.md`；有本地开发特殊配置 → `development.md`

**插件**：配置项 > 10 → `configuration.md`；API/Hooks > 5 → `api-reference.md`；有多场景示例 → `examples.md`

### 2.3 确认文档集

```markdown
## 文档生成计划

### 主文档
- `README.md` — 索引枢纽，包含概述、快速开始、子文档导航

### 子文档（共 N 个）
- `api-reference.md` — [触发原因：API 数量 12 > 阈值 5]
- `configuration.md` — [触发原因：配置项 15 > 阈值 10]

[若子文档 ≥ 2]
  → 将使用 task-dispatch 并行生成，预计加速 {N} 倍。

确认后开始生成内容。
```

---

## 阶段 3：并行内容生成

### 执行策略

| 子文档数 | 策略 |
|----------|------|
| 0-1 个 | 主 agent 直接生成 README + 子文档 |
| ≥ 2 个 | 调用 `task-dispatch` skill 并行生成 |

### task-dispatch 调度要点

**task-name**：`docs-{项目名称}`（如 `docs-my-lib`）

**子任务拆分**：README + 每个子文档各为一个子任务：

```text
| 编号 | 子任务 | 产出文件 | 类型 |
|------|--------|----------|------|
| D-01 | README 生成 | README.md | 索引枢纽 |
| D-02 | API 参考生成 | api-reference.md | 子文档 |
| D-03 | 配置文档生成 | configuration.md | 子文档 |
```

独立性校验：各文档内容独立（无接口依赖），但 README 作为索引需要引用其他文档，标记为弱依赖（先定子文档文件名，README 按文件名写链接）。

**子 agent prompt 要点**：

```
你是子 agent，负责生成文档 D-{NN}：{文档名称}

## 任务目标
生成 {文档名称}，内容要求：
{从 strategies.md 提取该文档的章节要求、示例规则}

## 输出目录
产出：.codebuddy/task-dispatch/docs-{项目名}/subtasks/D-{NN}/code/
  - 产出文件：{文件名}.md
报告：.codebuddy/task-dispatch/docs-{项目名}/subtasks/D-{NN}/report.md

## 内容质量底线
- 每个对外接口必须有输入→输出完整示例
- 每个命令必须附带预期终端输出
- 禁止任何形式的占位符（TODO、Coming soon、See source code 等）
- 章节要么写满实质内容，要么从导航中移除

## 示例获取优先级
1. 从测试文件提取（最可靠） → 2. 从示例目录提取 → 3. 从代码逻辑推断 → 4. 标注不可得

[若为 README 子任务，追加]
## README 结构
- 标题 + 一行描述
- 概述：做什么 + 解决什么问题
- 快速开始：最简安装 + 最简示例（输入+输出），30 秒内理解项目价值
- 子文档导航：各子文档链接 + 一句话说明
  （子文档文件名列表：{从阶段2获取}）
- 类型专属章节（根据策略模板追加）

完成后写 report.md，列出生成的章节和关键示例。
```

### 合并

主 agent 收集所有子 agent 产出，补充 README 中的子文档交叉引用链接（若子 agent 按指定的文件名生成则链接已正确），进入阶段 4 质量检查。

---

## 阶段 4：补充交叉引用 + 质量检查

### 4.1 补充交叉引用

主 agent 读取 README.md，执行以下交叉引用修复：
1. 确认子文档导航中的链接均指向已生成的子文档文件
2. **验证每个子文档链接的"一句话说明"与子文档实际内容一致**（并行生成时 README 子 agent 无法预知子文档内容，描述可能不准确）
3. 若描述不准确，用子文档实际内容修正

### 4.2 自动检查清单

- [ ] 全文无 Q-01 到 Q-06 禁止模式（见 `references/quality-rules.md`）
- [ ] 每个对外接口有完整示例（输入+输出）
- [ ] 所有子文档链接可对应到实际生成的文件
- [ ] README 行数 ≤ 120
- [ ] 子文档间无重复内容（抽查相邻文档）
- [ ] 概述章不只是标题扩充版

### 4.3 修正缺陷

发现缺陷立即修正后重新检查，直到全部通过。

---

## 阶段 5：输出落盘

### 5.1 写入文件

将生成的文档写入项目根目录。若用户指定了输出目录，写入指定路径。

### 5.2 输出导航概览

```markdown
## 文档生成完成

### 已生成文档

| 文件 | 内容摘要 | 行数 |
|------|----------|------|
| README.md | 项目概述 + 快速开始 + 导航 | 85 |
| api-reference.md | 12 个 API 的完整参考 | 340 |
| configuration.md | 15 个配置项详解 | 120 |

### 快速验证

- 打开 `README.md` → 快速开始 → 复制示例命令 → 应可直接跑通
- 打开 `api-reference.md` → 任意 API → 有明确的输入输出示例
- 子文档间链接 → 全部可达，无死链
```

## 参考

- 类型策略定义：`references/strategies.md`
- 质量检查规则：`references/quality-rules.md`
- 对比例子：`references/examples/`
