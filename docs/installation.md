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

> 直接使用 `npx skills` 不会生成 `~/.hackwu-skills/` 管理源和 `targets.list`，因此无法使用本安装器的 `update` / `remove` / `list` 持续跟踪管理。如需后续管理，请使用本仓库的 `skill-install.sh`。

## 命令与参数说明

安装器使用子命令形式：`install`（默认）、`update`、`remove`、`list`。

| 命令 | 作用 |
|------|------|
| `install`（默认） | 安装 skill 到目标目录（重新安装即更新） |
| `update` | 更新管理源中已安装的 skill 并同步到目标目录 |
| `remove <names>` | 从管理源删除指定 skill 并同步删除所有目标 |
| `list` | 列出管理源中已安装的 skill（含来源仓库） |

| 参数 | 作用 |
|------|------|
| `-n <names>` | 指定 skill，多个用逗号分隔（如 `-n code-review,design-craft`） |
| `-t <path>` | 指定目标目录，可多次使用（与 `--file` 互斥；`update` 时限定同步范围） |
| `--repo <owner/repo>` | 指定安装源仓库，可多次使用；`install`/`update` 指定安装源，`list` 按来源过滤；默认 `HACK-WU/skills` |
| `--file <path>` | 从配置文件读取目标目录（与 `-t` 互斥） |

> 不带任何参数运行即显示完整帮助。默认操作为 `install`。

### 安装其他项目的 skill

默认安装本仓库（`HACK-WU/skills`）。如需安装其他技能项目（如 `anthropics/skills`、`mattpocock/skills` 或任意 `owner/repo`），用 `--repo` 指定：

```bash
# 只安装指定仓库（替代默认仓库）
bash skill-install.sh install --repo anthropics/skills -t ~/projects/app

# 多个仓库混合安装到同一管理源
bash skill-install.sh install --repo HACK-WU/skills --repo anthropics/skills -t ~/projects/app
```

> **混合模式**：多个仓库的 skill 会混在同一管理源 `~/.hackwu-skills/skills/` 中，同步时全部写入目标 `skills/`。`remove` 删除同名 skill 时会在所有目标中同步删除（不区分来源仓库）。`-n` 名称过滤会应用到每个安装源。

### 更新与查看

```bash
# 更新管理源中已安装的全部 skill 并同步到所有已记录目标
bash skill-install.sh update

# 只更新指定 skill / 指定仓库 / 指定目标
bash skill-install.sh update -n code-review --repo HACK-WU/skills -t ~/projects/app

# 查看已安装 skill（含来源仓库），可按仓库过滤
bash skill-install.sh list
bash skill-install.sh list --repo anthropics/skills
```

> **update 语义**：只更新管理源中**已安装**的 skill 的最新版本（不追加未安装的 skill），并同步到目标（未指定 `-t` 时同步所有已记录目标）。`-n` 指定 skill 时按所属仓库分组更新。

### 删除

```bash
bash skill-install.sh remove code-review,design-craft
# → 从管理源删除指定 skill，并同步删除所有目标目录中对应的 skill
```

> 管理源 `~/.hackwu-skills/` 是技能更新的来源：`-t` 目标始终从管理源增量同步（覆盖更新同名文件，不删除目标中多余文件），`remove` 会自动同步到所有曾安装过的目标目录（记录于 `~/.hackwu-skills/targets.list`）。

**注意事项**：

- **update 与 install 的区别**：`install` 会追加安装（可装新 skill）；`update` 只更新已安装的 skill 版本，不追加新 skill。
- **`-n` 语义**：`-n` 控制的是"往管理源追加哪些 skill"，而非"目标只保留哪些"。首次安装（管理源为空）时 `-n code-review` 目标只有 code-review；但管理源已有其他 skill 后，`-n` 仅追加，目标会同步管理源全部 skill。若需目标只含子集，请先 `remove` 清理管理源再用 `-n` 安装。
- **增量同步不删除多余文件**：同步采用增量覆盖（如 rsync 不带 `--delete`），目标 `skills/` 中管理源没有的文件（如手动添加的自定义 skill 或本地修改）**不会被删除**，同名文件会被管理源版本覆盖更新。目标中的手动修改会被覆盖，如需保留请勿放在同名路径下。
- **运行时依赖**：安装器需要 **Node.js >= 22** + npx。`npx skills` 依赖 Node 22（`node:util` 的 `styleText` 自 21.7 起可用，skills 包 engines 声明 ≥22.20.0）。`update` / `list` 解析管理源 `skills-lock.json` 也用 node 内置 `JSON.parse`（复用既有 node 依赖，**无需 python3**）。未检测到 npx 或 Node 版本过低时脚本会报错并给出升级指引（Linux/macOS：nvm 或官网 LTS；Windows：winget/Chocolatey 或官网 LTS）。

## 目标目录

目标目录三选一（优先级从高到低）：

| 方式 | 示例 |
|------|------|
| `-t` 直接指定（支持多个） | `-t ~/projects/app -t ~/projects/api` |
| `--file` 配置文件 | `--file ~/my-targets.txt`（每行一个目录，`#` 注释） |
| 不指定，读默认配置 | 优先当前目录 `./.skill-targets`，未找到再用家目录 `~/.skill-targets` |

> 直接执行脚本（未指定 `-t` / `--file`）时，默认配置文件查找顺序为 **当前目录 `./.skill-targets` → 家目录 `~/.skill-targets`**。适合在项目仓库根放置 `.skill-targets` 指定该项目专用目标；未放则回退到用户级配置。两个文件均为每行一个目录、`#` 注释的文本文件。当前目录文件存在时（即使为空）即优先使用、不再回退家目录；install 时会打印实际使用的配置文件路径。

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
