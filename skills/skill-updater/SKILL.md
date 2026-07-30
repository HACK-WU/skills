---
name: skill-updater
description: 自动更新安装脚本的技能文件列表并同步 README。当用户添加新技能、删除技能或修改技能文件结构后，使用此技能同步更新 skill-install.sh 和 skill-install.ps1 中的静态文件列表，以及 README.md 中的"技能一览"表格和"项目结构"树。触发短语包括："更新安装脚本"、"同步技能列表"、"新增技能后更新脚本"、"技能列表不同步"。
---

# 技能安装脚本更新器

## 何时使用

仅在以下情况使用本 skill：

- 用户添加了新的技能目录或文件
- 用户删除了技能目录或文件
- 用户修改了技能文件结构（如添加子目录、移动文件）或技能的 frontmatter `description` 发生实质变化
- 安装脚本中的静态文件列表与实际 `skills/` 目录不一致
- `README.md` 的"技能一览"表格或"项目结构"树与实际 `skills/` 目录不一致
- 用户明确要求"更新安装脚本"或"同步技能列表"

## 核心功能

本技能指导 AI 完成以下任务：

1. 扫描 `skills/` 目录结构，生成完整的文件列表
2. 更新 `scripts/skill-install.sh` 中 `install_skills()` 函数的静态 `FILES` 数组
3. 更新 `scripts/skill-install.ps1` 中 `Install-Skills` 函数的静态 `$files` 数组
4. 同步更新 `README.md` 中的"技能一览"表格和"项目结构"目录树
5. 排除 `skill-updater` 技能自身（维护工具不应被用户安装，但需在 README 中展示）

## 执行步骤

### 第一步：扫描技能目录

使用 `search_file` 工具递归扫描 `skills/` 目录，获取所有 `.md` 文件：

```
search_file(target_directory="<workspace>/skills", pattern="*.md", recursive=true)
```

### 第二步：过滤文件

从搜索结果中移除以下文件：

1. **排除 `skill-updater` 技能**：移除所有以 `skill-updater/` 开头的路径
2. **排除隐藏文件**：移除以 `.` 开头的文件和目录

过滤后得到完整的技能文件列表，按路径字母序排列。

### 第三步：读取当前安装脚本

在修改之前，先用 `read_file` 读取两个安装脚本的当前内容：
- `scripts/skill-install.sh`
- `scripts/skill-install.ps1`

定位到静态文件列表块，确认替换范围。

### 第四步：更新安装脚本

#### 更新 `skill-install.sh`

定位 `install_skills()` 函数内的静态 `FILES=()` 数组（在 `⚠️ gh 不可用，使用静态 skill 列表` 提示之后）。

使用 `replace_in_file` 整体替换该 `FILES=()` 数组块。生成格式为：

```bash
        FILES=(
            "auto-review/SKILL.md"
            "bug-impact-analysis/SKILL.md"
            "challenger/SKILL.md"
            ...
            "work-breakdown/SKILL.md"
        )
```

- 文件按路径字母序排列
- 每个路径双引号包围，12 空格缩进（函数内 case 分支 + if 块）
- 最后一个元素不加多余逗号

#### 更新 `skill-install.ps1`

定位 `Install-Skills` 函数内的静态 `$files = @()` 数组（在 `⚠️ GitHub API 不可用，使用静态 skill 列表` 提示之后）。

使用 `replace_in_file` 整体替换该 `$files = @()` 数组块。生成格式为：

```powershell
        $files = @(
            "auto-review/SKILL.md",
            "bug-impact-analysis/SKILL.md",
            "challenger/SKILL.md",
            ...
            "work-breakdown/SKILL.md"
        )
```

- 文件按路径字母序排列
- 每个路径双引号包围，行末逗号分隔，12 空格缩进
- 最后一个元素不加逗号

### 第五步：同步更新 README.md

安装脚本更新完成后，检查根目录 `README.md` 是否与 `skills/` 目录一致，不一致时同步修改以下两处：

#### 1. "技能一览"表格

- **新增技能**：读取该技能 `SKILL.md` 的 frontmatter `description`，提炼一句话作用描述和触发词，按技能定位追加到对应分类表格：

| 分类 | 归属判断 |
|------|----------|
| `需求与设计` | 服务于编码前的需求分析、设计、调研、骨架生成环节 |
| `代码质量` | 服务于编码后的审查、测试、排错、质疑环节 |
| `工具` | 不属于以上两类的通用辅助能力（沉淀、检索、项目维护等） |

无法明确归类时询问用户。表格行格式：

```markdown
| **[技能名](./skills/技能名/SKILL.md)** | 一句话作用描述 | "触发词1"、"触发词2" |
```

- **删除技能**：从表格中移除对应行
- **修改技能**：若 description 发生实质变化，同步更新作用描述和触发词

#### 2. "项目结构"目录树

在 `## 项目结构` 代码块的 `skills/` 树中新增/删除对应目录行，注释为 4-8 字的中文简述：

```
├── 技能名/                  # 中文简述
```

注意保持树形符号（`├──` / `└──`）正确：新增到末尾时需将原末尾行的 `└──` 改为 `├──`；删除末尾行时需将新末尾行的 `├──` 改为 `└──`。

#### 3. 删除技能时的额外检查

删除技能时，附带检查 README 顶部"设计流程"ASCII 图中是否引用了该技能名：若有引用，提醒用户流程图需人工调整（流程图布局不适合自动修改）。

### 第六步：验证更新

1. 对比生成的文件数与第一步扫描结果（排除 skill-updater 后）是否一致
2. 确认 `skill-updater` 未被包含在安装脚本列表中
3. 用 `read_lints` 检查两个脚本无语法错误
4. 确认 README.md 与 `skills/` 目录双向一致：
   - 正向：每个技能同时出现在"技能一览"表格和"项目结构"树中
   - 反向：表格和树中没有实际已不存在的技能（孤儿条目），表格链接路径 `./skills/<技能名>/SKILL.md` 真实存在

## 示例：完整更新流程

假设 `skills/` 目录当前包含以下结构：

```
skills/
├── challenger/
│   ├── SKILL.md
│   ├── strategies/
│   │   ├── bug-fix.md
│   │   ├── feature.md
│   │   └── optimization.md
│   └── templates/
│       └── report.md
├── code-review/
│   └── SKILL.md
├── skill-updater/          # 此技能需要排除
│   └── SKILL.md
└── work-breakdown/
    └── SKILL.md
```

### 1. 调用 search_file

```
search_file(target_directory="skills", pattern="*.md", recursive=true)
```

结果：8 个文件（含 skill-updater/SKILL.md），过滤后剩 7 个。

### 2. 读取并替换 skill-install.sh

读取脚本，定位 `install_skills()` 函数中的 `FILES=()` 数组，整体替换为：

```bash
        FILES=(
            "challenger/SKILL.md"
            "challenger/strategies/bug-fix.md"
            "challenger/strategies/feature.md"
            "challenger/strategies/optimization.md"
            "challenger/templates/report.md"
            "code-review/SKILL.md"
            "work-breakdown/SKILL.md"
        )
```

### 3. 读取并替换 skill-install.ps1

读取脚本，定位 `Install-Skills` 函数中的 `$files = @()` 数组，整体替换为：

```powershell
        $files = @(
            "challenger/SKILL.md",
            "challenger/strategies/bug-fix.md",
            "challenger/strategies/feature.md",
            "challenger/strategies/optimization.md",
            "challenger/templates/report.md",
            "code-review/SKILL.md",
            "work-breakdown/SKILL.md"
        )
```

### 4. 同步 README.md

假设本次是新增了 `work-breakdown` 技能：

- 在"技能一览"的对应分类表格中追加一行：

```markdown
| **[work-breakdown](./skills/work-breakdown/SKILL.md)** | 将需求拆分为完全独立的垂直切片工作项 | "拆成独立任务"、"怎么并行开发" |
```

- 在"项目结构"树中追加目录行：

```
├── work-breakdown/          # 需求拆分
```

### 5. 验证

- 过滤后文件数 = 7，替换后列表 7 元素 → ✓
- `skill-updater` 不在安装脚本列表中 → ✓
- `read_lints` 无错误 → ✓
- README 表格与项目结构树均包含 `work-breakdown` → ✓

## 注意事项

1. **必须先读后改**：每次更新前用 `read_file` 读取脚本最新内容，再执行 `replace_in_file`
2. **整体替换数组块**：替换整个 `FILES=()` 或 `$files = @()` 数组，包括开闭括号行
3. **不要手动编辑**：文件列表必须从 `search_file` 扫描结果自动生成，不可凭记忆手写
4. **保持缩进一致**：两个脚本中静态列表均为 12 空格缩进
5. **排除维护技能**：`skill-updater` 是内部维护工具，安装脚本列表中永远排除；但 README 中照常展示（README 是项目说明，不是安装清单）
6. **只更新静态列表**：两个脚本中 API 发现逻辑会自动排除 `skill-updater`（通过条件跳过），无需修改
7. **README 双处同步**："技能一览"表格和"项目结构"树必须同时更新，只改一处会导致 README 内部不一致
8. **描述从 SKILL.md 提炼**：README 中的作用描述和触发词必须来自技能自身的 frontmatter description，不可凭空编写

## 触发短语

以下短语会触发本技能：

- "更新安装脚本"
- "同步技能列表"
- "新增技能后更新脚本"
- "技能列表不同步"
- "skill-install 脚本需要更新"
- "安装脚本文件列表过时"

## 相关文件

- `scripts/skill-install.sh` - Bash 安装脚本
- `scripts/skill-install.ps1` - PowerShell 安装脚本
- `README.md` - 项目说明（"技能一览"表格 + "项目结构"树）
- `skills/` - 技能目录根目录
