---
name: create-rules
description: 引导用户创建符合规范的 AI 规则文件（rules/*.md）。当用户要求创建规则、编写规则、新建规则文件时使用。触发短语包括："创建规则"、"写一个规则"、"新建规则"、"create rule"、"add rule"。
---

# 创建规则文件

## 规则文件格式

规则文件必须放在 `rules/` 目录下，使用 `.md` 扩展名。每个规则文件的 **frontmatter 必须包含以下字段**：

```yaml
---
description: [必填] 规则的简要描述，说明规则的作用和触发场景
alwaysApply: [必填] true 或 false，表示是否总是应用此规则
enabled: [必填] true 或 false，表示规则是否启用
updatedAt: [必填] ISO 8601 格式的更新时间，如 2026-06-13T16:35:00.000Z
provider: [可选] 规则提供者，可为空
---
```

### Frontmatter 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `description` | string | 是 | 规则描述，用于 AI 判断何时应用此规则 |
| `alwaysApply` | boolean | 是 | `true` 表示每次对话都应用，`false` 表示仅在匹配时应用 |
| `enabled` | boolean | 是 | `true` 启用，`false` 禁用 |
| `updatedAt` | string | 是 | ISO 8601 格式时间戳，每次修改规则时更新 |
| `provider` | string | 否 | 规则提供者名称，可留空 |

## 创建流程

### 第一步：收集信息

向用户确认以下内容：

1. **规则名称**：简洁明了，使用 kebab-case（如 `writing-pipeline`）
2. **规则描述**：一句话说明规则的作用和触发场景
3. **alwaysApply**：是否每次对话都应用？
   - `true`：全局规则，始终生效（如编码规范、审查流程）
   - `false`：条件规则，仅在特定场景生效
4. **enabled**：是否立即启用？
5. **规则内容**：具体的规则指令

### 第二步：生成规则文件

在 `rules/` 目录下创建 `{rule-name}.md` 文件，格式如下：

```markdown
---
description: {规则描述}
alwaysApply: {true/false}
enabled: {true/false}
updatedAt: {当前时间 ISO 8601}
provider:
---

# {规则标题}

## 规则

{规则的具体内容和指令}

## 执行

{规则的执行方式和流程}

## 例外

{不需要应用此规则的情况}
```

### 第三步：更新安装脚本

创建规则文件后，**必须同步更新安装脚本**，将新规则文件添加到 `--rules` 模式的文件列表中：

1. 更新 `scripts/skill-install.sh` 中 `--rules` 分支的 `FILES=()` 数组
2. 更新 `scripts/skill-install.ps1` 中 `$Rules` 分支的 `Install-Files "rules" @()` 数组

使用 `skill-updater` skill 完成同步，或手动添加：

```bash
# skill-install.sh 的 --rules 部分
FILES=(
    "writing-pipeline.md"
    "new-rule.md"  # 新增
)
```

```powershell
# skill-install.ps1 的 $Rules 部分
Install-Files "rules" @(
    "writing-pipeline.md",
    "new-rule.md"  # 新增
) $RulesDest
```

## 规则编写最佳实践

### 1. 描述要精准

- ✅ 好的描述：`文档或代码编写完成后，自动调用 auto-review skill 进行质量审查和修复闭环`
- ❌ 差的描述：`一些规则`

### 2. 内容要结构化

使用清晰的章节划分：

```markdown
# 规则标题

## 规则
规则的核心定义和要求

## 执行
规则的执行步骤和流程

## 例外
不需要应用此规则的特殊情况
```

### 3. 保持简洁

- 规则文件应控制在 100 行以内
- 避免冗长的解释，直接给出指令
- 使用表格、列表等结构化格式