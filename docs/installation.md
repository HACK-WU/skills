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

参数映射：`-t` → `-Target`，`-n` → `-NameFilter`，`--file` → `-ConfigFile`，`--optional` → `-Optional`。

一键下载并执行（PowerShell 中 `curl` 是 `Invoke-WebRequest` 的别名，需使用 `curl.exe` 调用真正的 curl）：

```powershell
curl.exe -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.ps1 -o skill-install.ps1; .\skill-install.ps1 -Target C:\projects\my-app
```

若已下载脚本到本地，可直接执行：

```powershell
.\skill-install.ps1 -Target C:\projects\my-app

# 多个目标 / 多个 skill 用逗号分隔的数组语法（PowerShell 不允许同一参数重复指定）
.\skill-install.ps1 -n module-teach,topic-teach -Target C:\projects\app,C:\projects\api
```

> 注意：PowerShell 版多值参数**不能**像 bash 版那样重复传参（`-n a -n b` 会报 `ParameterAlreadyBound`），详见下文「命令与参数说明」的 PowerShell 注意。

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
| `prune` | 清理目标中"安装器装过但不属于该目标来源"的 skill（默认预演，`-y` 执行） |
| `self-update` | 更新**脚本自身**到最新版本（默认每次运行已自动自检，见下文） |
| `list` | 列出管理源中已安装的 skill（含来源仓库） |

| 参数 | 作用 |
|------|------|
| `-n <names>` | 指定 skill，多个用逗号分隔（如 `-n code-review,design-craft`） |
| `-t <path>` | 指定目标目录，可多次使用（与 `--file` 互斥；`update`/`prune` 时限定处理的目标目录） |
| `--repo <owner/repo>` | 指定安装源仓库，可多次使用；`install`/`update` 指定安装源**并决定同步到目标的范围**，`list` 按来源过滤；默认 `HACK-WU/skills`。也接受仓库子路径 URL（如 `https://github.com/HACK-WU/skills/tree/master/skills-optional`），只装该子目录下的 skill |
| `--optional` | `--repo https://github.com/HACK-WU/skills/tree/master/skills-optional` 的别名，用于安装依赖第三方 skill/模块的**可选技能**；可与 `--repo` 同时使用 |
| `--file <path>` | 从配置文件读取目标目录（与 `-t` 互斥） |
| `-y` / `--yes` | `prune` 时真正执行删除（不加则只预演列出） |
| `--no-self-update` | 本次不做脚本自检 |
| `--force` | `self-update` 时允许降级 / 覆盖 git 工作树内的副本 |
| `--version` | 显示脚本版本 |

> **PowerShell 注意**：PowerShell 不允许同一参数重复指定（bash 式的 `-n a -n b` 会报 `ParameterAlreadyBound`）。`-Target` / `-NameFilter` / `-Repo` 的多个值一律用**逗号分隔的数组语法**单次传入，如 `-n code-review,design-craft`、`-Target C:\a,C:\b`。「可多次使用」仅适用于 bash 版 `skill-install.sh`。

> 不带任何参数运行即显示完整帮助。默认操作为 `install`。

### 安装其他项目的 skill

默认安装本仓库（`HACK-WU/skills`）。如需安装其他技能项目（如 `anthropics/skills`、`mattpocock/skills` 或任意 `owner/repo`），用 `--repo` 指定：

```bash
# 只安装指定仓库（替代默认仓库）
bash skill-install.sh install --repo anthropics/skills -t ~/projects/app

# 多个仓库混合安装到同一管理源
bash skill-install.sh install --repo HACK-WU/skills --repo anthropics/skills -t ~/projects/app
```

> **混合模式与同步范围**：多个仓库的 skill 混在同一管理源 `~/.hackwu-skills/skills/` 中，但**同步到目标时按"本次操作的仓库"圈定范围**——上面第二条命令只把 `HACK-WU/skills` 与 `anthropics/skills` 的 skill 写入目标，不会把管理源里其他仓库的 skill 带过去。范围依据管理源 `skills-lock.json` 的 `source` 判定，同一仓库的不同写法可互相匹配（`owner/repo` / `https://github.com/owner/repo` / `git@host:owner/repo.git`）。`remove` 删除同名 skill 时会在所有已记录目标中同步删除（不区分来源仓库）。`-n` 名称过滤会应用到每个安装源，并同时收窄同步范围。

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

> **update 语义**：只更新管理源中**已安装**的 skill 的最新版本（不追加未安装的 skill），并同步到目标（未指定 `-t` 时同步所有已记录目标）。`-n` 指定 skill 时按所属仓库分组更新。同步范围：指定 `--repo` / `-n` 时 = 该范围（对本次涉及的目标统一生效）；**都未指定时 = 各目标自己的来源记录**（见下文「目标来源记录」）——不会再无条件把管理源全量复制进目标。

### 删除

```bash
bash skill-install.sh remove code-review,design-craft
# → 从管理源删除指定 skill，并同步删除所有目标目录中对应的 skill
```

> 管理源 `~/.hackwu-skills/` 是技能更新的来源：`-t` 目标从管理源增量同步（覆盖更新同名文件，不删除目标中多余文件），且只同步该目标来源记录中的仓库的 skill；`remove` 会把删除同步到所有曾安装过的目标目录（记录于 `~/.hackwu-skills/targets.list`），但不再顺带全量重同步管理源。

### 目标来源记录（targets.list）

`~/.hackwu-skills/targets.list` 每行格式为 `目标目录<TAB>仓库1 仓库2 ...`：

- **仓库列 = 该目标的来源意图**，由 `install` 写入/合并（如 `install --repo tt-a1i/archify -t ~/app` → `~/app` 的来源 = `tt-a1i/archify`）；`update`（未指定 `--repo`/`-n`）与 `prune` 据此圈定范围。
- **老记录（只有路径、没有仓库列）**：首次参与 `update`/`prune` 时，按该目标**现有 skill 在 `skills-lock.json` 中的来源反查**并写回记录（会打印一行提示），行为等价于"保持它现在装的那些仓库"。判定不出来源（目标不存在/为空）则跳过并提示，**不会退化成全量复制**。
- 一个目标要装多个仓库，就把它们都写进 `--repo`（如 `--repo HACK-WU/skills --optional`），记录会自动合并。

### 清理目标中不属于其来源的 skill（prune）

早期版本同步时会全量复制管理源，目标里可能混进了其他仓库的 skill。`prune` 用于按来源记录清理这些外来项：

```bash
bash skill-install.sh prune                          # 预演：列出所有已记录目标里的外来 skill（含其来源仓库）
bash skill-install.sh prune -t ~/app                 # 只检查指定目标
bash skill-install.sh prune -t ~/app -y              # 确认后执行删除
bash skill-install.sh prune -t ~/app --repo HACK-WU/skills -y
                                                     # 显式指定期望来源清理，并纠正该目标的来源记录
```

> 只删除"**在 `skills-lock.json` 中登记过**（＝安装器管理过的）**且不属于该目标来源范围**"的目录。手工新增的目录、目标来源范围内的 skill 一律保留；判定不出来源时拒绝执行（不会误删）。

> **何时需要 `--repo`**：若目标只有老记录（无仓库列），来源靠"按现有内容反查"得出——历史污染会被一并算成"目标自己的来源"，此时 `prune` 会报"无外来 skill"。用 `--repo <期望仓库>` 显式声明该目标**应该**有哪些来源，即可清掉其余项，并把记录纠正为期望值（之后 `prune`/`update` 都以它为准）。

### 脚本自身的更新

安装器每次运行会**自检脚本版本**（默认 24h 一次），发现新版本时**只提示、不自动覆盖**：

```text
[WARN] 脚本有新版本：2026-09-18.1 → 2026-09-18.2（本次仍按旧版本执行）
[INFO]   更新: bash skill-install.sh self-update    （或重新执行一键安装命令）
[INFO]   关闭本次自检: --no-self-update
```

| 做法 | 命令 | 行为 |
|------|------|------|
| **看提示（默认）** | — | 有新版只打印上面几行，本次操作继续用旧版本 |
| **更新** | `self-update` 子命令 | 检查并覆盖自身（留 `<脚本>.bak`），忽略 24h 节流 |
| **跳过自检** | `--no-self-update` | 本次不做自检（也不提示） |

> **为什么只提示不覆盖**：脚本可能被内网 fork、本地改过，或装在只想保持稳定的项目里——静默改写"用户正在用的脚本"超出预期。

**保险（两条路一致）**：

| 保险 | 行为 |
|------|------|
| 管道执行（`curl \| bash`） | 不检查也不提示——一键安装拿到的本来就是最新版 |
| 脚本在 git 工作树内 | 不覆盖，提示在该仓库 `git pull` |
| 下载物校验 | 必须通过「版本哨兵 + 语法校验」才允许落盘（防 HTML 错误页 / 半截文件） |
| 版本方向 | 远端不高于本地不覆盖（`--force` 才允许降级） |
| 回滚 | 覆盖前留 `<脚本>.bak` |

自更新**不做环境变量开关**（避免配置面）：节流间隔与来源都是脚本顶部常量——要指向内网镜像就改那里的自更新来源常量（`SELF_URL_DEFAULT` / `$SelfUrlDefault`；非 https 源会提示"无传输加密"）。

> **离线 / 求稳环境**：加 `--no-self-update` 跳过自检，或把脚本顶部的节流常量（`SELF_CHECK_TTL` / `$SelfCheckTtl`）调大；离线时自检本身也会在 3s 内快速失败，不会长时间阻塞。

> 自检用**短超时快速失败**（连接 3s / 单源 8s）：断网或被墙时不会让本次操作白等；只有显式 `self-update` 才容忍慢链路（5s / 20s）。

**注意事项**：

- **update 与 install 的区别**：`install` 会追加安装（可装新 skill）；`update` 只更新已安装的 skill 版本，不追加新 skill。
- **同步范围（多仓库管理源）**：管理源是多仓库共享池，但同步到目标时按其来源圈定范围——**`install`** 未指定 `--repo` 时 = 默认仓库 `HACK-WU/skills`（不会带其他仓库的 skill）；**`update`** 指定了 `--repo` / `-n` 时按该范围同步，都未指定时 = **各目标自己的来源记录**。要把多个仓库的 skill 装进同一目标，就把它们都写进 `--repo`（如 `--repo HACK-WU/skills --optional`）。同一仓库的不同子目录按 `--repo` 的 tree 子路径区分（如 `skills-optional` 不会被整仓库安装收录）。若本次安装源在管理源中一个 skill 都匹配不到，脚本会警告并跳过同步——**不会退化成"把管理源全量复制"**。
- **`-n` 语义**：`-n` 决定往管理源追加哪些 skill，并同时收窄目标端的同步范围——`-n code-review` 时目标只出现 code-review（管理源中其他 skill 不受影响，也不会进目标）。需要清理管理源内容时用 `remove`。
- **增量同步不删除多余文件**：同步采用增量覆盖（如 rsync 不带 `--delete`），目标 `skills/` 中管理源没有的文件（如手动添加的自定义 skill 或本地修改）**不会被删除**，同名文件会被管理源版本覆盖更新。目标中的手动修改会被覆盖，如需保留请勿放在同名路径下。
- **运行时依赖**：安装器需要 **Node.js >= 22** + npx。`npx skills` 依赖 Node 22（`node:util` 的 `styleText` 自 21.7 起可用，skills 包 engines 声明 ≥22.20.0）。`update` / `list` 解析管理源 `skills-lock.json` 也用 node 内置 `JSON.parse`（复用既有 node 依赖，**无需 python3**）。未检测到 npx 或 Node 版本过低时脚本会报错并给出升级指引（Linux/macOS：nvm 或官网 LTS；Windows：winget/Chocolatey 或官网 LTS）。

## 目标目录

目标目录三选一（优先级从高到低）：

| 方式 | 示例 |
|------|------|
| `-t` 直接指定（支持多个） | bash: `-t ~/projects/app -t ~/projects/api`；PowerShell: `-Target C:\a,C:\b`（不可重复传参） |
| `--file` 配置文件 | `--file ~/my-targets.txt`（每行一个目录，`#` 注释） |
| 不指定，读默认配置 | 家目录 `~/.skill-targets` |

> 直接执行脚本（未指定 `-t` / `--file`）时，默认配置文件为家目录 `~/.skill-targets`。该文件为每行一个目录、`#` 注释的文本文件。

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
