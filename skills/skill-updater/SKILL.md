---
name: skill-updater
description: 自动更新安装脚本的技能文件列表。当用户添加新技能、删除技能或修改技能文件结构后，使用此技能同步更新 skill-install.sh 和 skill-install.ps1 中的文件列表。触发短语包括："更新安装脚本"、"同步技能列表"、"新增技能后更新脚本"、"技能列表不同步"。
---

# 技能安装脚本更新器

## 何时使用

仅在以下情况使用本 skill：

- 用户添加了新的技能目录或文件
- 用户删除了技能目录或文件
- 用户修改了技能文件结构（如添加子目录、移动文件）
- 安装脚本中的文件列表与实际 `skills/` 目录不一致
- 用户明确要求"更新安装脚本"或"同步技能列表"

## 核心功能

本技能指导 AI 完成以下任务：

1. 扫描 `skills/` 目录结构，生成完整的文件列表
2. 更新 `scripts/skill-install.sh` 中的 `FILES` 数组
3. 更新 `scripts/skill-install.ps1` 中的文件列表
4. 排除 `skill-updater` 技能自身（维护工具不应被用户安装）

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

过滤后得到完整的技能文件列表，按名称排序。

### 第三步：读取当前安装脚本

在修改之前，先用 `read_file` 读取两个安装脚本的当前内容：
- `scripts/skill-install.sh`
- `scripts/skill-install.ps1`

定位到 `--skills` 分支中的文件列表块，确认替换范围。

### 第四步：更新安装脚本

#### 更新 `skill-install.sh`

使用 `replace_in_file` 替换 `# 注意: skill-updater ...` 注释及其下方整个 `FILES=()` 数组块。每个文件路径占一行，用双引号包围，4 空格缩进。生成格式为：

```bash
# 注意: skill-updater 是内部维护工具，不包含在用户安装列表中
FILES=(
    "challenger/SKILL.md"
    "challenger/strategies/bug-fix.md"
    ...
    "work-breakdown/SKILL.md"
)
```

- 文件按路径字母序排列
- 最后一个元素不加多余逗号

#### 更新 `skill-install.ps1`

使用 `replace_in_file` 替换 `# 注意: skill-updater ...` 注释及其下方整个 `Install-Files "skills" @(...)` 块。格式为：

```powershell
# 注意: skill-updater 是内部维护工具，不包含在用户安装列表中
Write-Host "Skills -> $(Join-Path $TargetPath 'skills')"
Install-Files "skills" @(
    "challenger/SKILL.md", "challenger/strategies/bug-fix.md",
    "challenger/strategies/feature.md", "challenger/strategies/optimization.md",
    ...
    "work-breakdown/SKILL.md"
) (Join-Path $TargetPath "skills")
```

- 同名目录的文件放在同一行，逗号分隔，行末不加逗号
- 最后一行（`work-breakdown/SKILL.md`）不加逗号

### 第五步：验证更新

1. 对比生成的文件数与第一步扫描结果（排除 skill-updater 后）是否一致
2. 确认 `skill-updater` 未被包含
3. 用 `read_lints` 检查两个脚本无语法错误

### 第六步：更新 `--scripts` 模式（如需要）

检查 `scripts/requirement-mgr/` 目录下的 `.py` 文件是否有变更。如有新增或删除，同步更新两个安装脚本中 `--scripts` 分支的文件列表。步骤同上。

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

读取脚本，定位到第 106 行的 `# 注意: skill-updater ...` 注释及第 107-138 行的 `FILES=()` 数组，整体替换为：

```bash
    # 注意: skill-updater 是内部维护工具，不包含在用户安装列表中
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

读取脚本，定位到 `# 注意: skill-updater ...` 及下方 `Install-Files "skills" @(...)` 块，整体替换为：

```powershell
    # 注意: skill-updater 是内部维护工具，不包含在用户安装列表中
    Write-Host "Skills -> $(Join-Path $TargetPath 'skills')"
    Install-Files "skills" @(
        "challenger/SKILL.md", "challenger/strategies/bug-fix.md",
        "challenger/strategies/feature.md", "challenger/strategies/optimization.md",
        "challenger/templates/report.md", "code-review/SKILL.md",
        "work-breakdown/SKILL.md"
    ) (Join-Path $TargetPath "skills")
```

### 4. 验证

- 过滤后文件数 = 7，替换后 bash 数组 7 元素 → ✓
- `skill-updater` 不在列表中 → ✓
- `read_lints` 无错误 → ✓

## 注意事项

1. **必须先读后改**：每次更新前用 `read_file` 读取脚本最新内容，再执行 `replace_in_file`
2. **整体替换注释+数组块**：不要只替换文件列表，要连同 `# 注意: skill-updater ...` 注释一起替换，保证可定位
3. **不要手动编辑**：文件列表必须从 `search_file` 扫描结果自动生成，不可凭记忆手写
4. **保持缩进一致**：bash 脚本用 4 空格缩进，PowerShell 用 8 空格缩进
5. **排除维护技能**：`skill-updater` 是内部维护工具，永远排除
6. **提交变更**：更新后提交到版本控制，确保团队同步

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
- `skills/` - 技能目录根目录
