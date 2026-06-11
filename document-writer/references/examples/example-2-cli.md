# 示例 2：CLI 工具 — 文件批量重命名工具

假设项目为 `bulkrename`，一个命令行批量重命名工具，8 个命令，12 个配置项。

---

## Before（典型 AI 默认输出）

````markdown
# bulkrename

A CLI tool to rename files in bulk.

## Installation

```bash
npm install -g bulkrename
```

## Usage

```bash
bulkrename --pattern "*.jpg" --replace "photo-{n}"
```

## Commands

- `bulkrename rename` — Rename files
- `bulkrename preview` — Preview changes
- `bulkrename undo` — Undo last rename

## Configuration

Create a `.bulkrenamerc` file to configure default options.

## License

MIT
````

**问题诊断**：
- 概述只有一句话，不知道它比手动 `mv` 好在哪
- 使用示例没有终端输出，读者不知道执行后屏幕会显示什么
- 命令列表只有一句话描述，无参数、无选项、无输出
- 配置没有示例，不知道 `.bulkrenamerc` 的文件格式和内容
- 没有子文档导航

---

## After（本 skill 策略输出）

### README.md

````markdown
# bulkrename

一个安全的命令行批量重命名工具，支持预览、撤销和正则匹配。

## 概述

`bulkrename` 是一个 Node.js 命令行工具。

**解决的问题**：
- 手动 `mv` 批量重命名容易出错，且无法批量撤销
- 现有的 `rename` 命令缺少预览和安全确认机制
- 需要正则替换等高级功能时，shell 脚本编写门槛高

**与其他方案的区别**：
- 与手动 `mv` 相比：提供预览模式，改前先看效果
- 与 `rename` CLI 相比：内置撤销功能，改错了可以回退
- 与 shell 脚本相比：无需记忆 sed/awk 语法，直观的命令行接口

## 安装

### 前置条件
- Node.js >= 16.0.0

### 安装命令
```bash
npm install -g bulkrename
```

### 验证安装
```bash
bulkrename --version
# → bulkrename v1.0.0
```

## 快速开始

```bash
# 预览：将当前目录下所有 .txt 改为 .md（不实际执行）
$ bulkrename preview --pattern "*.txt" --replace "{name}.md"
# →
#   PREVIEW — 以下文件将被重命名（不会实际执行）
#   ────────────────────────────────────────────────
#   readme.txt    → readme.md
#   notes.txt     → notes.md
#   todo.txt      → todo.md
#   ────────────────────────────────────────────────
#   共 3 个文件

# 执行重命名
$ bulkrename rename --pattern "*.txt" --replace "{name}.md"
# →
#   ✓ readme.txt → readme.md
#   ✓ notes.txt  → notes.md
#   ✓ todo.txt   → todo.md
#   重命名完成：3/3 成功
```

## 核心命令速览

### `bulkrename preview`
```bash
$ bulkrename preview --pattern "img-*.png" --replace "photo-{n}.png"
# → PREVIEW：img-01.png → photo-1.png / img-02.png → photo-2.png / ...
```
详见 [命令参考](./command-reference.md)

### `bulkrename rename`
```bash
$ bulkrename rename --pattern "DSC*.jpg" --replace "vacation-{date}.jpg"
# → ✓ DSC0001.jpg → vacation-2025-06-11.jpg ...
```
详见 [命令参考](./command-reference.md)

### `bulkrename undo`
```bash
$ bulkrename undo
# → 撤销最近一次重命名？[y/N] y
#   ✓ photo-1.png → img-01.png ...
```
详见 [命令参考](./command-reference.md)

### 正则替换
```bash
$ bulkrename rename --regex "(.*)-\d+" --replace "$1" --dry-run
# → PREVIEW：report-2024.pdf → report.pdf
```
详见 [命令参考](./command-reference.md)

## 文档导航

| 文档 | 内容 |
|------|------|
| [命令参考](./command-reference.md) | 8 个命令的完整参数、选项和输出示例 |
| [配置指南](./configuration.md) | 配置文件格式、12 个配置项详解 |
| [集成指南](./integration.md) | CI/CD 和脚本中调用 bulkrename |

## License

MIT
````

### command-reference.md（节选）

````markdown
# 命令参考

## 概述

`bulkrename` 的所有命令及其参数和输出示例。所有命令支持 `--dry-run` 全局选项以预览效果。

## 全局选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--dry-run` | boolean | `false` | 仅预览，不实际修改文件 |
| `--yes` / `-y` | boolean | `false` | 跳过所有确认提示 |
| `--config` | string | `.bulkrenamerc` | 指定配置文件路径 |

---

## 命令列表

### `bulkrename preview`

预览将要进行的重命名操作，不做实际修改。

```bash
$ bulkrename preview --pattern "*.log" --replace "archive-{date}.log"
# →
#   PREVIEW — 以下文件将被重命名（不会实际执行）
#   ────────────────────────────────────────────────
#   error.log     → archive-2025-06-11.log
#   access.log    → archive-2025-06-11.log
#   debug.log     → archive-2025-06-11.log
#   ────────────────────────────────────────────────
#   共 3 个文件
```

```bash
# 递归子目录
$ bulkrename preview --pattern "*.tmp" --recursive
# →
#   PREVIEW
#   src/temp.tmp       → src/temp
#   tests/fixture.tmp  → tests/fixture
#   dist/cache.tmp     → dist/cache
#   共 3 个文件（含子目录）
```

**选项**：
| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--pattern` | string | 必填 | glob 匹配模式 |
| `--replace` | string | 必填 | 替换模板，支持 `{name}`/`{ext}`/`{n}`/`{date}` |
| `--recursive` / `-r` | boolean | `false` | 递归处理子目录 |
| `--regex` | string | - | 使用正则匹配（与 `--pattern` 互斥） |
| `--dir` | string | `./` | 目标目录 |

### `bulkrename rename`

执行重命名操作。

```bash
$ bulkrename rename --pattern "*.jpeg" --replace "{name}.jpg"
# →
#   确认重命名以下 2 个文件？[y/N] y
#   ✓ photo.jpeg  → photo.jpg
#   ✓ avatar.jpeg → avatar.jpg
#   重命名完成：2/2 成功
```

```bash
# 带序号
$ bulkrename rename --pattern "*.png" --replace "screenshot-{n:03}.png"
# →
#   ✓ capture1.png → screenshot-001.png
#   ✓ capture2.png → screenshot-002.png
#   重命名完成：2/2 成功
```

**选项**：同 `preview`，额外支持：
| 选项 | 类型 | 说明 |
|------|------|------|
| `--force` / `-f` | boolean | 覆盖已存在的文件 |

### `bulkrename undo`

撤销最近一次 `rename` 操作。

```bash
$ bulkrename undo
# →
#   将撤销最近一次重命名（2025-06-11 10:30）
#   共 5 个文件将被还原。确认？[y/N] y
#   ✓ screenshot-001.png → capture1.png
#   ✓ screenshot-002.png → capture2.png
#   ...
#   撤销完成：5/5 成功
```

```bash
# 查看历史并选择撤销哪次
$ bulkrename undo --list
# →
#   [1] 2025-06-11 10:30 — 5 files: *.png → screenshot-{n}.png
#   [2] 2025-06-10 14:15 — 3 files: *.txt → *.md
#   [3] 2025-06-09 09:00 — 12 files: DSC*.jpg → vacation-*.jpg

$ bulkrename undo --id 2
# → 确认撤销第 2 次操作？[y/N] y
#   撤销完成：3/3 成功
```

**选项**：
| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--list` | boolean | `false` | 列出可撤销的历史记录 |
| `--id` | number | 最近一次 | 指定撤销第几次操作 |
| `--force` | boolean | `false` | 跳过确认 |

### ...（其余 5 个命令，均按完整格式）

## 变量模板参考

替换模板 `--replace` 支持以下变量：

| 变量 | 说明 | 示例输入 | 示例输出 |
|------|------|----------|----------|
| `{name}` | 原文件名（不含扩展名） | `photo.jpg` | `photo` |
| `{ext}` | 原扩展名（含点） | `photo.jpg` | `.jpg` |
| `{n}` | 自增序号 | - | `1`, `2`, `3` ... |
| `{n:03}` | 补零自增序号 | - | `001`, `002` ... |
| `{date}` | 当前日期 | - | `2025-06-11` |
| `{date:YYYY-MM}` | 自定义日期格式 | - | `2025-06` |

## 相关文档
- [README](./README.md) — 项目概述与快速开始
- [配置指南](./configuration.md) — 配置文件详解
- [集成指南](./integration.md) — CI/CD 集成
````

### configuration.md（节选）

````markdown
# 配置指南

## 概述

`bulkrename` 支持通过 `.bulkrenamerc` 配置文件设置默认选项，命令行参数优先级高于配置文件。

## 配置文件

在项目根目录创建 `.bulkrenamerc`（JSON 格式）：

```json
{
  "defaultPattern": "*.log",
  "defaultDir": "./logs",
  "recursive": true,
  "dryRun": true,
  "variables": {
    "project": "myapp",
    "env": "production"
  }
}
```

**查找顺序**：当前目录 → 父目录（逐级向上）→ `~/.bulkrenamerc`（全局配置）

## 配置项详解

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `defaultPattern` | string | `"*"` | 默认的 glob 匹配模式 |
| `defaultDir` | string | `"./"` | 默认的目标目录 |
| `recursive` | boolean | `false` | 默认是否递归子目录 |
| `dryRun` | boolean | `true` | 默认是否安全模式（仅预览） |
| `yes` | boolean | `false` | 默认是否跳过确认 |
| `force` | boolean | `false` | 默认是否覆盖已存在文件 |
| `preserveCase` | boolean | `true` | 是否保留原文件名大小写 |
| `ignoreErrors` | boolean | `false` | 遇到错误是否继续 |
| `maxDepth` | number | `Infinity` | 递归最大深度 |
| `exclude` | string[] | `[]` | 排除的 glob 模式列表 |
| `variables` | object | `{}` | 自定义替换变量 |
| `historyLimit` | number | `10` | undo 历史记录最大条数 |

## 典型配置场景

### 安全优先（推荐默认）

```json
{
  "dryRun": true,
  "force": false,
  "preserveCase": true
}
```

### CI 管道（自动化运行）

```json
{
  "dryRun": false,
  "yes": true,
  "force": true,
  "ignoreErrors": false
}
```

## 相关文档
- [README](./README.md) — 项目概述与快速开始
- [命令参考](./command-reference.md) — 所有命令
- [集成指南](./integration.md) — CI/CD 集成
````
