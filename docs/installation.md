# 安装指南

本指南说明如何将本技能集安装到目标项目，以及 `req` CLI 的安装方式。

## 一键安装（Linux / macOS）

```bash
curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.sh | \
  bash -s -- -t /path/to/your-project
```

> 也可以先下载脚本后执行：
> ```bash
> git clone https://github.com/HACK-WU/skills.git && cd skills
> # 或 curl -fsSL .../skill-install.sh -o skill-install.sh
> bash scripts/skill-install.sh -t /path/to/your-project
> ```

**效果**：将全部技能安装到管理源 `~/.hackwu-skills/skills/`，再同步到 `/path/to/your-project/skills/`。

## 安装（Windows / PowerShell）

参数映射：`-t` → `-Target`，`-n` → `-NameFilter`，`--file` → `-ConfigFile`。

一键下载并执行（PowerShell 中 `curl` 是 `Invoke-WebRequest` 的别名，需使用 `curl.exe` 调用真正的 curl）：

```powershell
curl.exe -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.ps1 -o skill-install.ps1; .\skill-install.ps1 -Target C:\projects\my-app
```

若已下载脚本到本地，可直接执行：

```powershell
.\skill-install.ps1 -Target C:\projects\my-app
```

## 直接使用 npx skills 安装

安装器底层基于 [`npx skills`](https://skills.sh/)，你也可以直接使用该命令安装，无需经过本仓库脚本：

```bash
# 安装全部技能到当前目录的 skills/
npx skills add HACK-WU/skills --agent openclaw -y

# 只安装指定技能
npx skills add HACK-WU/skills --skill code-review design-craft --agent openclaw -y

# 列出仓库中可安装的技能（不实际安装）
npx skills add HACK-WU/skills --list -y
```

**`--agent` 与落盘目录**：

本安装器固定使用 `--agent openclaw`，将技能写入当前目录 `skills/`，与 `<target>/skills` 布局一致。其他 agent（如 `universal` → `.agents/skills/`）映射不同目录，但本仓库脚本不支持切换。

> 直接使用 `npx skills` 不会生成 `~/.hackwu-skills/` 管理源和 `targets.list`，因此无法使用本安装器的 `--update` / `--remove` / `--list` 持续跟踪管理。如需后续管理，请使用本仓库的 `skill-install.sh`。

## 参数说明

| 参数 | 作用 |
|------|------|
| `-n <names>` | 只安装指定技能，多个用逗号分隔（如 `-n code-review,design-craft`） |
| `-t <path>` | 指定目标目录，可多次使用（与 `--file` 互斥） |
| `--file <path>` | 从配置文件读取目标目录（与 `-t` 互斥） |

> 不带任何参数运行即显示完整帮助。默认操作为安装。

## 管理命令

安装器基于 `npx skills` 持续跟踪管理已安装的技能，管理源位于 `~/.hackwu-skills/`：

| 命令 | 作用 |
|------|------|
| `bash skill-install.sh --update` | 更新管理源到最新版本，并同步到所有已记录的目标目录 |
| `bash skill-install.sh --remove <names>` | 从管理源删除指定技能（逗号分隔），并同步删除所有目标 |
| `bash skill-install.sh --list` | 列出管理源中已安装的技能 |

> 管理源 `~/.hackwu-skills/` 是唯一真相：`-t` 目标始终从管理源镜像同步，`--update` / `--remove` 会自动同步到所有曾安装过的目标目录（记录于 `~/.hackwu-skills/targets.list`）。

**注意事项**：

- **`-n` 语义**：`-n` 控制的是"往管理源追加哪些 skill"，而非"目标只保留哪些"。首次安装（管理源为空）时 `-n code-review` 目标只有 code-review；但管理源已有其他 skill 后，`-n` 仅追加，目标会镜像管理源全部 skill。若需目标只含子集，请先 `--remove` 清理管理源再用 `-n` 安装。
- **镜像同步会删除目标自定义文件**：`--update` / `--remove` 同步时，目标 `skills/` 中不在管理源的文件（如手动添加的自定义 skill）会被删除。请勿在目标 `skills/` 中手动添加文件，所有管理通过安装器进行。
- **运行时依赖**：安装器需要 Node.js + npx。未检测到 npx 时脚本会报错并给出安装指引（Linux/macOS：官网安装包或 nvm/Homebrew；Windows：官网安装包或 winget/Chocolatey）。

## 目标目录

目标目录三选一（优先级从高到低）：

| 方式 | 示例 |
|------|------|
| `-t` 直接指定（支持多个） | `-t ~/projects/app -t ~/projects/api` |
| `--file` 配置文件 | `--file ~/my-targets.txt`（每行一个目录，`#` 注释） |
| 不指定，读默认配置 | `~/.skill-targets` |

## 安装 `req` CLI

`req` 是需求管理 CLI，自动获取最新版本：

```bash
curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/install-latest.sh | bash
# → 安装 requirement-mgr 最新版本，验证安装：req --version
```

## 快速上手

安装完成后，即可在项目中直接使用：

1. **触发一个技能**：在对话中描述需求即可自动匹配，例如：
   - "帮我分析这个需求" → 触发 `requirement-mining`
   - "review 这个提交" → 触发 `code-review`
2. **用 `req` 管理需求元数据**：

   ```bash
   $ req list
   # → 需求列表（表格或 JSON 输出，无需求时为空列表）
   ```

3. **串联完整流程**：技能可组合成完整流水线，参考根 README 的[设计流程](../README.md#workflow)图。
