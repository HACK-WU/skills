# 安装指南

本指南说明如何将本技能集安装到目标项目，以及 `req` CLI 的安装方式。

## 一键安装（Linux / macOS）

```bash
curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.sh | \
  bash -s -- --skills -t /path/to/your-project
```

> 也可以先下载脚本后执行：
> ```bash
> git clone https://github.com/HACK-WU/skills.git && cd skills
> # 或 curl -fsSL .../skill-install.sh -o skill-install.sh
> bash scripts/skill-install.sh --skills -t /path/to/your-project
> ```

**效果**：将 `skills/` 下的全部技能写入 `/path/to/your-project/.codebuddy/skills/`。

## 安装（Windows / PowerShell）

参数映射：`--skills` → `-Skills`，`--rules` → `-Rules`，`-t` → `-Target`，`--file` → `-ConfigFile`。

一键下载并执行（PowerShell 中 `curl` 是 `Invoke-WebRequest` 的别名，需使用 `curl.exe` 调用真正的 curl）：

```powershell
curl.exe -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.ps1 -o skill-install.ps1; .\skill-install.ps1 -Skills -Target C:\projects\my-app
```

若已下载脚本到本地，可直接执行：

```powershell
.\skill-install.ps1 -Skills -Target C:\projects\my-app
.\skill-install.ps1 -Rules -Target C:\projects\my-app
```

## 参数说明

| 参数 | 作用 |
|------|------|
| `--skills` | 安装 AI 技能定义（`skills/`） |
| `--rules` | 安装 AI 规则（`rules/`），与 `--skills` 可组合 |
| `-n <names>` | 只安装指定技能/规则，多个用逗号分隔（如 `-n code-review,design-craft`），需配合 `--skills` 或 `--rules` |
| `-t <path>` | 指定目标目录，可多次使用（与 `--file` 互斥） |
| `--file <path>` | 从配置文件读取目标目录（与 `-t` 互斥） |

> 未指定 `--skills`/`--rules` 或目标目录为空时运行，即显示完整帮助。

## 目标目录

目标目录三选一（优先级从高到低）：

| 方式 | 示例 |
|------|------|
| `-t` 直接指定（支持多个） | `-t ~/projects/app -t ~/projects/api` |
| `--file` 配置文件 | `--file ~/my-targets.txt`（每行一个目录，`#` 注释） |
| 不指定，读默认配置 | `--skills` → `~/.skill-targets`，`--rules` → `~/.rule-targets` |

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

3. **串联完整流程**：技能可组合成完整流水线，参考根 README 的[设计流程](../README.md#🔄-设计流程)图。
