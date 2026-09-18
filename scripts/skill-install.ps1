# ============================================================
# Skills 安装器 — 基于 npx skills 管理本仓库的 AI Skills（PowerShell）
#
# 管理目录: $env:USERPROFILE\.hackwu-skills\
#   ├── skills\              # npx 安装的 skill（openclaw 映射 = cwd\skills\）
#   ├── skills-lock.json     # npx 生成的跟踪文件（update/remove/list 依据）
#   └── targets.list         # 目标目录记录: <目标目录>[\t<仓库1> <仓库2> ...]
#                            #   仓库列 = 该目标的来源意图（install 写入/合并），
#                            #   update/prune 据此圈定范围；老记录（无仓库列）
#                            #   首次使用时按目标现有 skill 反查来源并写回
#
# 同步范围: 管理源是多仓库共享池（-Repo 只往池里追加），同步到目标时按
#           "本次操作的仓库"圈定范围，不会把其他仓库的 skill 带到目标。
#           （install 未指定 -Repo 时 = 默认仓库 HACK-WU/skills；
#             update 未指定 -Repo/-NameFilter 时 = 各目标自己的来源记录）
#
# 脚本自更新: 每次运行自检一次（TTL 节流）；发现新版默认只提示不覆盖，
#             用 self-update 子命令更新（SKILL_INSTALL_SELF_UPDATE=auto 可改全自动）。
#             拿不到自身路径（管道执行）与 git 工作树内的副本不覆盖（后者用 git pull）。
#
# 用法:
#   .\skill-install.ps1 install -Target C:\projects\app
#   .\skill-install.ps1 install -Optional -Target C:\projects\app    # 只装可选技能
#   .\skill-install.ps1 update [-Target ...] [-NameFilter names] [-Repo owner/repo]
#   .\skill-install.ps1 remove code-review
#   .\skill-install.ps1 prune [-Target ...] [-Yes]                   # 清理目标中外来的 skill
#   .\skill-install.ps1 self-update                                  # 更新脚本自身
#   .\skill-install.ps1 list [-Repo owner/repo]
#
# 兼容旧用法（默认 install）:
#   .\skill-install.ps1 C:\projects\my-app
# ============================================================

param(
    [Parameter(Position=0)]
    [string]$Command,

    [Parameter(Position=1)]
    [string]$TargetPath,

    [string[]]$Target,

    [string]$ConfigFile,

    [string[]]$NameFilter,

    [string[]]$Repo,

    [switch]$Optional,

    [switch]$Yes,

    [switch]$NoSelfUpdate,

    [switch]$Force,

    [switch]$Version,

    [switch]$Help
)

$ErrorActionPreference = "Stop"

$RepoSpecified = $false
if (-not $Repo -or $Repo.Count -eq 0) { $Repo = @("HACK-WU/skills") }
else {
    # 支持逗号分隔多仓库（-Repo a,b）
    $Repo = $Repo | ForEach-Object { $_ -split ',' } | Where-Object { $_ -ne '' }
    $RepoSpecified = $true
}

# -Optional 别名：等价于 -Repo <可选技能目录>（依赖第三方 skill/模块的技能）
$OptionalRepoUrl = "https://github.com/HACK-WU/skills/tree/master/skills-optional"
if ($Optional) {
    if ($RepoSpecified) { $Repo += $OptionalRepoUrl }
    else { $Repo = @($OptionalRepoUrl); $RepoSpecified = $true }
}
$Agent = "openclaw"
# 兼容 Windows（USERPROFILE）与 Unix（HOME）
$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $env:HOME }
$ManageDir = Join-Path $HomeDir ".hackwu-skills"
$ManageSkillsDir = Join-Path $ManageDir "skills"
$LockFile = Join-Path $ManageDir "skills-lock.json"
$TargetsFile = Join-Path $ManageDir "targets.list"
$DefaultTargetsFile = Join-Path $HomeDir ".skill-targets"

# 脚本自身版本（自更新比较用）。格式固定为 YYYY-MM-DD[.N]：前缀定宽 → 序数比较即版本序
$ScriptVersion = "2026-09-18.1"
# 自更新来源（可用 SKILL_INSTALL_SCRIPT_URL 覆盖为镜像/内网地址；默认 raw + jsDelivr 兜底）
$SelfUrlDefault = "https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.ps1"
$SelfUrlMirror = "https://cdn.jsdelivr.net/gh/HACK-WU/skills@master/scripts/skill-install.ps1"
# 自检间隔（秒，默认 24h；0 = 每次都查）；SKILL_INSTALL_NO_SELF_UPDATE=1 可整体关闭
$SelfUpdateTtl = if ($env:SKILL_INSTALL_SELF_UPDATE_TTL) { $env:SKILL_INSTALL_SELF_UPDATE_TTL } else { 86400 }

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

# ============================================================
# 帮助
# ============================================================
function Show-Help {
    Write-Host @"
Skills 安装器 — 基于 npx skills 管理 AI Skills（脚本版本 $ScriptVersion）

用法:
  .\skill-install.ps1 <操作> [选项]
  操作:
    install      安装 skill 到目标目录（默认操作，可省略）
    update       更新管理源中已安装的 skill 并同步到目标目录
    remove       从管理源删除指定 skill 并同步删除所有目标
    prune        清理目标中"安装器装过但不属于该目标来源"的 skill（默认预演，-Yes 执行）
    self-update  更新脚本本身到最新版本（默认每次运行已自动自检，见下）
    list         列出管理源中已安装的 skill（含来源仓库）
    -h, --help   显示此帮助
    --version    显示脚本版本

选项:
  -Target <paths>     目标目录，多个用逗号分隔（如 -Target C:\a,C:\b；与 -ConfigFile 互斥；update/prune 时限定处理的目标目录）
  -NameFilter <names> 指定 skill（逗号分隔，如 -NameFilter code-review,design-craft）
  -Repo <owner/repo>  指定仓库，多个用逗号分隔（如 -Repo r1/skills,r2/skills；install/update 指定安装源，prune 指定期望来源，list 按来源过滤）
  -Optional           别名，等价于 -Repo $OptionalRepoUrl
                      （可选技能目录：依赖第三方 skill/模块的技能）
  -ConfigFile <path>  从配置文件读取目标目录（与 -Target 互斥）
  -Yes                prune 时真正执行删除（不加则只预演列出）
  -NoSelfUpdate       本次不检查脚本自身版本
  -Force              self-update 时允许降级 / 覆盖 git 工作树内的副本

同步范围:
  管理源是多仓库共享池，同步到目标时按"本次操作的仓库"圈定范围：
  指定 -Repo 时只同步这些仓库的 skill（可再叠加 -NameFilter 收窄名称）；
  install 未指定 -Repo 时 = 默认仓库 HACK-WU/skills；
  update 未指定 -Repo / -NameFilter 时 = 各目标自己的来源记录
  （记录在 $ManageDir\targets.list 每行的仓库列；老记录首次使用时按
   目标现有 skill 反查来源并写回；判定不出则跳过，不做全量复制）。

脚本自更新:
  每次运行做一次自检（默认 24h 一次，节流戳记 $SelfCheckFile）；
  发现新版本默认只提示（不覆盖自身），用 self-update 子命令更新到最新版。
  拿不到自身路径（管道执行）与 git 工作树内的副本不覆盖（后者请用 git pull）。
  关闭提示: -NoSelfUpdate 或 SKILL_INSTALL_NO_SELF_UPDATE=1
  自动更新: SKILL_INSTALL_SELF_UPDATE=auto（覆盖自身并留 <脚本>.bak）
  间隔: SKILL_INSTALL_SELF_UPDATE_TTL=<秒>（0 = 每次检查）
  来源: SKILL_INSTALL_SCRIPT_URL=<脚本 URL>（默认 GitHub raw + jsDelivr 镜像兜底）

默认配置文件（不指定 -Target / -ConfigFile 时读取）:
  $DefaultTargetsFile

管理目录:
  $ManageDir

示例:
  .\skill-install.ps1 -Target C:\projects\app
  .\skill-install.ps1 install -NameFilter code-review,design-craft -Target C:\projects\app
  .\skill-install.ps1 install -Optional -Target C:\projects\app    # 只装可选技能
  .\skill-install.ps1 install -Repo HACK-WU/skills -Optional -Target C:\projects\app  # 主技能+可选技能
  .\skill-install.ps1 update -Target C:\projects\app
  .\skill-install.ps1 update -NameFilter code-review -Repo HACK-WU/skills
  .\skill-install.ps1 remove code-review
  .\skill-install.ps1 prune                       # 预演：列出各目标中外来的 skill
  .\skill-install.ps1 prune -Target C:\app -Yes    # 执行清理指定目标
  .\skill-install.ps1 prune -Target C:\app -Repo HACK-WU/skills -Yes
                      # 以 -Repo 为期望来源清理，并纠正该目标记录
  .\skill-install.ps1 list
  .\skill-install.ps1 list -Repo anthropics/skills
  .\skill-install.ps1 self-update                  # 手动检查并更新脚本自身
  .\skill-install.ps1 --version                    # 显示脚本版本
"@
    exit 0
}

if ($Version) { Write-Host "skill-install.ps1 $ScriptVersion"; exit 0 }
if ($Help) { Show-Help }

# ============================================================
# 确定操作（子命令：install/update/remove/list）
# ============================================================
$Action = "install"  # 默认安装
if ($Command) {
    switch ($Command.ToLower()) {
        "--help" { Show-Help }
        "-help"  { Show-Help }
        "-h"     { Show-Help }
        "help"   { Show-Help }
        "--version" { Write-Host "skill-install.ps1 $ScriptVersion"; exit 0 }
        "-version"  { Write-Host "skill-install.ps1 $ScriptVersion"; exit 0 }
        "update" { $Action = "update" }
        "remove" {
            $Action = "remove"
            # remove 的 skill 名可从位置参数（第二个）或 -NameFilter 获取
            if (-not $NameFilter -and $TargetPath) { $NameFilter = $TargetPath }
            if (-not $NameFilter) { Write-Err "remove 需要指定 skill 名称（如 remove code-review 或 -NameFilter code-review）" }
        }
        "list"   { $Action = "list" }
        "prune"  { $Action = "prune" }
        "self-update" { $Action = "self-update" }
        "install" { $Action = "install" }
        default {
            # 非子命令 → 兼容旧用法：当作目标路径
            $Action = "install"
            if (-not $TargetPath) { $TargetPath = $Command }
        }
    }
}

# ============================================================
# 前置检查
# ============================================================
$npxCmd = Get-Command npx -ErrorAction SilentlyContinue
if (-not $npxCmd) {
    Write-Err "未检测到 npx（本安装器基于 'npx skills' 管理技能，需 Node.js >= 22）。`n`n  请先安装 Node.js，任选其一：`n    1. 官方安装包: https://nodejs.org/ （选择 LTS 版本）`n    2. winget: winget install OpenJS.NodeJS.LTS`n    3. Chocolatey: choco install nodejs-lts`n`n  安装完成后重试本脚本。"
}

# 检查 Node.js 版本（npx skills 依赖 Node >= 22）
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCmd) {
    try {
        $nodeVer = (& node -v) -replace '^v', ''
        $nodeMajor = [int]($nodeVer -split '\.')[0]
        if ($nodeMajor -lt 22) {
            Write-Err "Node.js 版本过低（当前 v$nodeVer，需 >= 22）。`n`n  npx skills 依赖 Node >= 22，请升级 Node.js：`n    1. winget: winget install OpenJS.NodeJS.LTS`n    2. 官方安装包: https://nodejs.org/ （选择 LTS 版本）`n`n  升级后重试本脚本。"
        }
    } catch {
        # node 存在但无法读取版本，不阻塞
    }
}

function Ensure-ManageDir {
    if (-not (Test-Path $ManageDir)) { New-Item -ItemType Directory -Path $ManageDir -Force | Out-Null }
    if (-not (Test-Path $TargetsFile)) { New-Item -ItemType File -Path $TargetsFile -Force | Out-Null }
}

# ============================================================
# 名称过滤解析（支持多参数和逗号分隔）
# ============================================================
$NameList = @()
if ($NameFilter) {
    foreach ($filter in $NameFilter) {
        $NameList += $filter -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }
    }
}

# ============================================================
# 脚本自更新（self-update）
# ============================================================
# 原则：宁可不动，也不许把用户本地的东西搞坏。
#   ⓪ 默认「只提示、不覆盖」：自检发现新版即打印更新指引（静默改写用户正在用的脚本
#      超出预期，且可能存在内网 fork / 本地改动）；要全自动需 SKILL_INSTALL_SELF_UPDATE=auto
#   ① 拿不到自身路径（管道执行等）不覆盖、也不提示；② git 工作树内一律不覆盖（提示 git pull）
#   ③ 下载物必须先过「哨兵 + PowerShell 语法校验」；④ 禁止降级（-Force 才强制）
#   ⑤ 可关：-NoSelfUpdate / SKILL_INSTALL_NO_SELF_UPDATE=1；节流见 SKILL_INSTALL_SELF_UPDATE_TTL
# 落盘用「备份 + 同目录 Move-Item 替换」；PowerShell 启动时已把脚本整体读入内存，
# 替换正在运行的 .ps1 是安全的（不要用 Set-Content 直接覆写）。
$SelfCheckFile = Join-Path $ManageDir ".last-self-check"

# 脚本自身路径（拿不到则输出空）
function Get-SelfPath {
    $p = $PSCommandPath
    if (-not $p) { return "" }
    if (-not (Test-Path -Path $p -PathType Leaf)) { return "" }
    return $p
}

# 脚本文件里的 $ScriptVersion 值
function Get-ScriptVersionOf($file) {
    if (-not (Test-Path $file)) { return "" }
    foreach ($line in (Get-Content $file -ErrorAction SilentlyContinue)) {
        if ($line -match '^\$ScriptVersion\s*=\s*"([^"]*)"') { return $Matches[1] }
    }
    return ""
}

# 下载远程脚本（Invoke-WebRequest 主路径；curl.exe/curl 兜底）
# 超时可调：自检（courtesy）用短超时快速失败，显式 self-update 才容忍慢链路
function Get-RemoteScript($url, $out, $ConnectSec = 5, $MaxSec = 20) {
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -TimeoutSec $MaxSec -UseBasicParsing -ErrorAction Stop
        return $true
    } catch {
        foreach ($c in @("curl.exe", "curl")) {
            if (Get-Command $c -ErrorAction SilentlyContinue) {
                & $c -fsSL --connect-timeout $ConnectSec --max-time $MaxSec $url -o $out 2>$null
                if ($LASTEXITCODE -eq 0) { return $true }
            }
        }
        return $false
    }
}

# 下载物校验：非空 + 含版本哨兵 + PowerShell 语法通过（任何异常都视为"校验不过"，不终止主流程）
function Test-ScriptFile($file) {
    try {
        if (-not (Test-Path -Path $file)) { return $false }
        if ((Get-Item -Path $file -Force).Length -le 0) { return $false }
        $txt = Get-Content -Raw -Path $file -Force -ErrorAction Stop
        if ($txt -notmatch '(?m)^\$ScriptVersion\s*=\s*"') { return $false }
        $err = $null
        [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path -Path $file).Path, [ref]$null, [ref]$err) > $null
        return (-not ($err -and $err.Count))
    } catch {
        return $false
    }
}

# 版本比较：$a > $b（定宽日期前缀 → 序数比较即版本序）
function Test-VersionGt($a, $b) {
    if ($a -eq $b) { return $false }
    return ([System.String]::CompareOrdinal($a, $b) -gt 0)
}

# 脚本是否位于 git 工作树内（是 → 不自动覆盖，提示 git pull）
function Test-InGitWorktree($dir) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { return $false }
    $out = & git -C $dir rev-parse --is-inside-work-tree 2>$null
    return ("$out".Trim() -eq "true")
}

# 自动模式下用新脚本重跑本次操作（按已绑定参数重建命令行）
function Get-ReExecArgs {
    $a = @()
    if ($Command) { $a += $Command }
    if ($TargetPath) { $a += $TargetPath }
    if ($Target) { $a += @("-Target", ($Target -join ',')) }
    if ($ConfigFile) { $a += @("-ConfigFile", $ConfigFile) }
    if ($NameFilter) { $a += @("-NameFilter", ($NameFilter -join ',')) }
    if ($RepoSpecified) { $a += @("-Repo", ($Repo -join ',')) }
    if ($Optional) { $a += "-Optional" }
    if ($Yes) { $a += "-Yes" }
    return $a
}

# 自更新主流程
#   auto     —— 每次运行的自检（受 TTL / 开关约束）。默认只提示不覆盖；
#               SKILL_INSTALL_SELF_UPDATE=auto 时才覆盖并用新脚本重跑本次操作
#   explicit —— self-update 子命令（忽略 TTL，直接覆盖；$Force 允许降级 / 覆盖 git 工作树内副本）
function Invoke-SelfUpdate($Mode, $Force) {
    $path = Get-SelfPath
    if (-not $path) {
        if ($Mode -eq "explicit") {
            Write-Warn "拿不到脚本自身路径，无法自更新"
            Write-Info "请重新下载脚本，或执行一键安装命令获取最新版"
            return $false
        }
        return $true
    }

    # 自检节流：TTL 内不重复检查（explicit 忽略）
    $ttl = 0
    if (-not [int64]::TryParse("$SelfUpdateTtl", [ref]$ttl)) { $ttl = 86400 }
    if ($Mode -eq "auto" -and $ttl -gt 0 -and (Test-Path $SelfCheckFile)) {
        $last = [int64]0
        [void][int64]::TryParse((Get-Content $SelfCheckFile -ErrorAction SilentlyContinue | Select-Object -First 1), [ref]$last)
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        if ($last -gt 0 -and ($now - $last) -lt $ttl) { return $true }
    }
    if (-not (Test-Path $ManageDir)) { New-Item -ItemType Directory -Path $ManageDir -Force | Out-Null }
    try {
        Set-Content -Path $SelfCheckFile -Value ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) -ErrorAction Stop
    } catch { }

    $lver = Get-ScriptVersionOf $path
    # 本地没有版本号（更早的版本/被改过）→ 不猜，静默跳过（可用 self-update 手动确认）
    if (-not $lver) { return $true }

    # 依次尝试：显式指定的源（唯一）→ 默认 raw → jsDelivr 镜像
    $urls = @()
    if ($env:SKILL_INSTALL_SCRIPT_URL) { $urls = @($env:SKILL_INSTALL_SCRIPT_URL) }
    else { $urls = @($SelfUrlDefault, $SelfUrlMirror) }
    # 非 https 源（本地回环/测试除外）没有传输加密：明确提示，不静默
    foreach ($u in $urls) {
        if ($u -match '^https://') { continue }
        if ($u -match '^https?://(127\.0\.0\.1|localhost)') { continue }
        if ($u -match '^file:') { continue }
        Write-Warn "自更新源不是 https（$u）：下载内容无传输加密保护"
    }

    # 注意两个坑：① 不要用点开头的临时名 —— pwsh 在 Linux 上把点前缀文件当 Hidden，
    # Get-Item/Get-Content 默认看不到（本轮实测踩到）；② 随机名而非 PID（防预置符号链接劫持）
    $tmp = [System.IO.Path]::GetTempFileName()
    # 自检（auto）快失败：断网/被墙时不要让用户白等；显式 self-update 才容忍慢链路
    if ($Mode -eq "explicit") { $ct = 5; $max = 20 } else { $ct = 3; $max = 8 }
    $rver = ""
    foreach ($u in $urls) {
        if ((Get-RemoteScript $u $tmp $ct $max) -and (Test-ScriptFile $tmp)) {
            $rver = Get-ScriptVersionOf $tmp
            if ($rver) { break }
        }
    }
    if (-not $rver) {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        if ($Mode -eq "explicit") {
            Write-Warn "无法获取远端脚本（网络不可达，或返回内容未通过校验）"
            return $false
        }
        return $true
    }

    if ($rver -eq $lver) {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        if ($Mode -eq "explicit") { Write-Info "已是最新版本（$lver）" }
        return $true
    }

    if (-not (Test-VersionGt $rver $lver)) {
        if ($Mode -eq "explicit" -and $Force) {
            Write-Info "远端版本（$rver）不高于本地（$lver），-Force 指定：仍按远端覆盖"
        } else {
            Remove-Item $tmp -Force -ErrorAction SilentlyContinue
            if ($Mode -eq "explicit") {
                Write-Warn "远端版本（$rver）不高于本地（$lver），未覆盖（确需强制加 -Force）"
                return $false
            }
            return $true
        }
    }

    # ---- 到这里的语义：远端版本更高 ----
    # 默认（自检）只提示、不覆盖：静默改写"用户正在用的脚本"超出预期，
    # 且可能存在内网 fork / 本地改动。要全自动可显式设 SKILL_INSTALL_SELF_UPDATE=auto。
    if ($Mode -eq "auto" -and ($env:SKILL_INSTALL_SELF_UPDATE -ne "auto")) {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        if (Test-InGitWorktree (Split-Path -Parent $path)) {
            Write-Warn "脚本有新版本（$lver → $rver）：当前副本在 git 工作树内，请在该仓库执行 git pull 更新"
        } else {
            Write-Warn "脚本有新版本：$lver → $rver（本次仍按旧版本执行）"
            Write-Info "  更新: .\skill-install.ps1 self-update    （或重新执行一键安装命令）"
        }
        Write-Info "  关闭提示: -NoSelfUpdate 或 SKILL_INSTALL_NO_SELF_UPDATE=1；"
        Write-Info "  自动更新: SKILL_INSTALL_SELF_UPDATE=auto"
        return $true
    }

    # git 工作树内的副本：不覆盖（保护未提交改动），提示 git pull；显式模式需 -Force
    if (Test-InGitWorktree (Split-Path -Parent $path)) {
        if ($Mode -eq "auto") {
            Remove-Item $tmp -Force -ErrorAction SilentlyContinue
            Write-Warn "脚本有新版本（$lver → $rver），但当前副本在 git 工作树内，不做自动覆盖"
            Write-Warn "  请在该仓库执行 git pull 更新"
            return $true
        }
        if (-not $Force) {
            Remove-Item $tmp -Force -ErrorAction SilentlyContinue
            Write-Warn "脚本位于 git 工作树内（$path），未覆盖：请用 git pull 更新；确需覆盖加 -Force"
            return $false
        }
    }

    # 落盘：备份 + 同目录随机名替换（随机名防预置符号链接；同卷 Move-Item 才是替换）
    $tmpLocal = Join-Path (Split-Path -Parent $path) ("skill-install.tmp." + [System.IO.Path]::GetRandomFileName())
    try {
        Copy-Item -Path $tmp -Destination $tmpLocal -Force -ErrorAction Stop
        Copy-Item -Path $path -Destination "$path.bak" -Force -ErrorAction Stop
        Move-Item -Path $tmpLocal -Destination $path -Force -ErrorAction Stop
    } catch {
        Remove-Item $tmpLocal -Force -ErrorAction SilentlyContinue
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        Write-Warn "脚本无法自动更新（目录不可写？）：$path"
        if ($Mode -eq "explicit") { Write-Info "可换有写权限的账号，或重新执行一键安装命令" }
        return $false
    }
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue

    Write-Info "脚本已更新：$lver → $rver（旧版备份 $path.bak）"
    if ($Mode -eq "explicit") { return $true }
    # 自动模式：用新脚本重跑本次操作（置防重入标记，避免再次自检）
    $env:SKILL_INSTALL_SELF_UPDATED = "1"
    & $path @(Get-ReExecArgs)
    exit 0
}

function Do-SelfUpdate {
    Write-Host "🔄 skill-install.ps1 self-update"
    Write-Host "   当前版本: $ScriptVersion"
    Write-Host "   脚本路径: $(Get-SelfPath)"
    $srcDesc = if ($env:SKILL_INSTALL_SCRIPT_URL) { $env:SKILL_INSTALL_SCRIPT_URL } else { "$SelfUrlDefault (+ $SelfUrlMirror)" }
    Write-Host "   来源: $srcDesc"
    Write-Host ""
    [void](Invoke-SelfUpdate "explicit" $Force)
    Write-Host ""
    Write-Info "当前版本: $(Get-ScriptVersionOf (Get-SelfPath))"
}

# ============================================================
# 目标目录解析
# ============================================================
$TargetDirs = @()

function Resolve-Targets {
    if ($Target -and $ConfigFile) { Write-Err "-Target 和 -ConfigFile 不能同时使用" }

    if ($Target) {
        $script:TargetDirs = @($Target)
        return
    }

    if ($ConfigFile) {
        if (-not (Test-Path $ConfigFile)) { Write-Err "配置文件不存在: $ConfigFile" }
        foreach ($line in (Get-Content $ConfigFile -ErrorAction Stop)) {
            $trimmed = $line.Trim()
            if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
            $script:TargetDirs += $trimmed
        }
        if ($script:TargetDirs.Count -eq 0) { Write-Err "配置文件为空: $ConfigFile" }
        return
    }

    if ($TargetPath) {
        $script:TargetDirs = @($TargetPath)
        return
    }

    # 默认配置文件
    if (Test-Path $DefaultTargetsFile) {
        foreach ($line in (Get-Content $DefaultTargetsFile -ErrorAction SilentlyContinue)) {
            $trimmed = $line.Trim()
            if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
            $script:TargetDirs += $trimmed
        }
    }
}

# 目标目录 → 实际落盘目录（目标名以 skills 结尾时直接用，否则拼 skills\）
function Target-Dest($t) {
    $leaf = Split-Path $t.TrimEnd('\').TrimEnd('/') -Leaf
    if ($leaf -eq "skills") { return $t }
    return (Join-Path $t "skills")
}

# ============================================================
# 目标记录（targets.list）
# 格式: <目标目录>[\t<仓库1> <仓库2> ...]
#   仓库列 = "这个目标要装哪些仓库"的意图记录（install 写入 / 合并），
#   也是 update / prune 圈定范围的依据 —— 管理源是多仓库共享池，
#   不按目标记来源就只能全量复制（会把其他仓库的 skill 带进目标）。
#   老记录（无 \t）视为来源未知：首次使用时按目标现有 skill 反查 lock
#   来源并写回（见 Resolve-TargetRepos），判定不出则跳过同步。
# ============================================================
# 仓库列表并集（保持原顺序；仓库标识不含空格）
function Merge-RepoList($a, $b) {
    $out = @()
    foreach ($w in (("" + $a + " " + $b) -split '\s+' | Where-Object { $_ -ne "" })) {
        if ($out -notcontains $w) { $out += $w }
    }
    return (($out -join ' ').Trim())
}

# 写入/更新某目标的仓库列：Mode = merge（合并，记录意图）| set（覆盖，纠正记录）
# merge 且仓库无变化时不重写文件（少动状态文件，收敛并发写窗口）；UTF8 无 BOM，供两平台共用
function Write-TargetRecord($t, $Repos, $Mode) {
    $add = Merge-RepoList "" ($Repos -join ' ')
    $cur = Get-TargetReposFromFile $t
    if ($Mode -eq "set" -and $cur -eq $add) { return }
    if ($Mode -eq "merge" -and $cur -ne "" -and (Merge-RepoList $cur $add) -eq $cur) { return }

    $out = @()
    $found = $false
    if (Test-Path $TargetsFile) {
        foreach ($line in (Get-Content $TargetsFile -ErrorAction SilentlyContinue)) {
            $raw = $line.Trim()
            if ($raw -eq "") { continue }
            $parts = $raw -split "`t", 2
            $p = $parts[0]
            $rest = if ($parts.Count -gt 1) { $parts[1] } else { "" }
            if ($p -eq $t) {
                $found = $true
                $newv = if ($Mode -eq "set") { $add } else { Merge-RepoList $rest $add }
                if ($newv -ne "") { $out += ($p + "`t" + $newv) } else { $out += $p }
            } else {
                if ($rest -ne "") { $out += ($p + "`t" + $rest) } else { $out += $p }
            }
        }
    }
    if (-not $found) {
        if ($add -ne "") { $out += ($t + "`t" + $add) } else { $out += $t }
    }
    [System.IO.File]::WriteAllLines($TargetsFile, [string[]]$out)
}

# 记录/合并目标及其仓库来源
function Record-Target($t, $Repos = @()) {
    Write-TargetRecord $t $Repos "merge"
}

# 覆盖写入目标的仓库来源（prune -Repo 纠正记录用）
function Set-TargetRepos($t, $Repos = @()) {
    Write-TargetRecord $t $Repos "set"
}

# 读取所有已记录目标路径（去掉仓库列）
function Get-RecordedTargets {
    if (-not (Test-Path $TargetsFile)) { return @() }
    $result = @()
    foreach ($line in (Get-Content $TargetsFile -ErrorAction SilentlyContinue)) {
        $raw = $line.Trim()
        if ($raw -eq "") { continue }
        $result += (($raw -split "`t", 2)[0])
    }
    return $result
}

# 读某目标记录中的仓库列表
function Get-TargetReposFromFile($t) {
    if (-not (Test-Path $TargetsFile)) { return "" }
    foreach ($line in (Get-Content $TargetsFile -ErrorAction SilentlyContinue)) {
        $raw = $line.Trim()
        if ($raw -eq "") { continue }
        $parts = $raw -split "`t", 2
        if ($parts[0] -eq $t) {
            if ($parts.Count -gt 1) { return $parts[1] }
            return ""
        }
    }
    return ""
}

# lock 中所有 skill 的 "name<TAB>source" 清单（供来源反查 / prune 分类）
function Get-LockNameSources {
    if (-not (Test-Path $LockFile)) { return @() }
    $env:LOCK_FILE = $LockFile
    $out = & node -e @'
const fs=require('fs');
let d;
try{ d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,'utf8')); }catch(e){ process.exit(0); }
for(const name of Object.keys(d.skills||{}).sort()){
  console.log(name+"\t"+((d.skills[name]||{}).source||'unknown'));
}
'@
    Remove-Item Env:LOCK_FILE -ErrorAction SilentlyContinue
    return @($out | Where-Object { $_ -ne "" })
}

# 反查：目标里已有哪些 skill → 它们在 lock 中的来源仓库（并集）
function Get-InferTargetRepos($dest) {
    if (-not (Test-Path $dest)) { return "" }
    $names = @(Get-ChildItem -Path $dest -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
    if ($names.Count -eq 0) { return "" }
    $map = Get-LockNameSources
    if ($map.Count -eq 0) { return "" }
    $out = ""
    foreach ($name in $names) {
        foreach ($line in $map) {
            $parts = $line -split "`t", 2
            if ($parts.Count -eq 2 -and $parts[0] -eq $name -and $parts[1] -ne "") {
                $out = Merge-RepoList $out $parts[1]
                break
            }
        }
    }
    return $out
}

# 解析目标的来源仓库：记录优先；老记录/无记录则反查并写回（自愈）
function Resolve-TargetRepos($t) {
    $repos = Get-TargetReposFromFile $t
    if ($repos -ne "") { return $repos }
    $repos = Get-InferTargetRepos (Target-Dest $t)
    if ($repos -ne "") {
        Record-Target $t @($repos -split '\s+' | Where-Object { $_ -ne "" })
        Write-Warn "目标记录缺少来源仓库，已按目标现有 skill 反查并写回: $t → $repos"
    }
    return $repos
}

# ============================================================
# 同步范围（scope）：只同步来源匹配本次操作仓库的 skill
# ============================================================
# 管理源 $ManageDir\skills\ 是多仓库共享池（-Repo 只是往里追加），
# 所以同步前必须按来源仓库圈定范围，否则会把池里其他仓库的 skill 一并复制到目标。
$script:SyncScopeActive = $false
$script:SyncNames = @()

# 计算范围内的 skill 名（依据 lock 的 source/skillPath 过滤；参数 = 允许的仓库列表）
function Get-SyncScopeNames($RepoSpecs) {
    if (-not (Test-Path $LockFile)) { return @() }
    $env:LOCK_FILE = $LockFile
    $env:REPO_SPECS = ($RepoSpecs -join ' ')
    $env:NAME_WANTED = ($NameList -join ' ')
    $names = & node -e @'
const fs=require('fs');
let d;
try{ d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,'utf8')); }catch(e){ process.exit(0); }
const skills=d.skills||{};
// 归一化仓库标识：抹平协议前缀/git@/scp 形式/.git/尾斜杠差异，并拆出 tree 子路径
function norm(s){
  let v=String(s||'').trim();
  if(!v) return null;
  v=v.replace(/^[a-z][a-z0-9+.-]*:\/\//i,'').replace(/^git@/i,'');
  v=v.replace(/^([^/]+):(?!\/)/,'$1/');
  v=v.replace(/\/-\/tree\//,'/tree/');
  let sub='';
  const m=v.match(/\/tree\/([^/]+)(?:\/(.*))?$/);
  if(m){ sub=m[2]||''; v=v.slice(0,m.index); }
  v=v.replace(/\.git$/i,'').replace(/\/+$/,'');
  return {repo:v.toLowerCase(),sub:sub.replace(/^\/+|\/+$/g,'').toLowerCase()};
}
function sameRepo(a,b){ return a===b||a.endsWith('/'+b)||b.endsWith('/'+a); }
// 整仓库安装（未指定子路径）时 npx 只收录这些容器下的 skill，
// 如 skills-optional/ 下的 skill 不会被 "npx skills add owner/repo" 收录
const CONTAINERS=['skills','plugins'];
function inPlainLayout(p){
  const seg=p.split('/');
  if(seg.length<=2) return true;
  if(CONTAINERS.indexOf(seg[0])>=0) return true;
  return seg[0].charAt(0)==='.'&&seg[1]==='skills';
}
const specs=String(process.env.REPO_SPECS||'').split(/\s+/).filter(Boolean).map(norm).filter(Boolean);
const wanted=(process.env.NAME_WANTED||'').split(/\s+/).filter(Boolean);
const wantSet=wanted.length?new Set(wanted):null;
const out=new Set();
for(const x of specs){
  const cand=[];
  for(const name of Object.keys(skills)){
    if(wantSet&&!wantSet.has(name)) continue;
    const e=skills[name]||{};
    const src=norm(e.source);
    if(!src||!sameRepo(src.repo,x.repo)) continue;
    const sp=String(e.skillPath||'').toLowerCase();
    if(x.sub){ if(sp.indexOf(x.sub+'/')===0) cand.push({name:name,plain:true}); }
    else cand.push({name:name,plain:inPlainLayout(sp)});
  }
  // 指定子路径的仓库：命中即为范围；整仓库：优先排除同仓库其他子目录的 skill，
  // 若据此筛空（第三方仓库的目录布局不在常见容器内）则退回该仓库全部命中，避免漏同步
  const pruned=cand.filter(function(c){ return c.plain; });
  for(const c of (pruned.length?pruned:cand)) out.add(c.name);
}
const names=[...out].sort();
process.stdout.write(names.length?names.join('\n')+'\n':'');
'@
    Remove-Item Env:LOCK_FILE, Env:REPO_SPECS, Env:NAME_WANTED -ErrorAction SilentlyContinue
    return @($names | Where-Object { $_ -ne "" })
}

# 圈定同步范围（参数 = 本次操作的仓库列表；未指定 -Repo 时传默认仓库）
function Set-SyncScope($RepoSpecs) {
    $script:SyncNames = @(Get-SyncScopeNames $RepoSpecs)
    $script:SyncScopeActive = $true
}

# ============================================================
# 同步：管理源 → 目标（增量同步）
# 只覆盖更新同名文件，不删除目标中管理源没有的文件（保护本地手动修改）
# ============================================================
function Sync-ToTarget($target) {
    $dest = Target-Dest $target
    if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }

    if (-not (Test-Path $ManageSkillsDir) -or -not (Get-ChildItem $ManageSkillsDir -ErrorAction SilentlyContinue)) {
        # 管理源为空，跳过同步（不删除目标中已有文件）
        return
    }

    if ($script:SyncScopeActive) {
        # 只同步范围内（本次操作仓库）的 skill：管理源是多仓库共享池，
        # 全量复制会把池里其他仓库的 skill 一并带到目标
        foreach ($name in $script:SyncNames) {
            $src = Join-Path $ManageSkillsDir $name
            if (-not (Test-Path $src)) { continue }
            $skillDest = Join-Path $dest $name
            if (-not (Test-Path $skillDest)) { New-Item -ItemType Directory -Path $skillDest -Force | Out-Null }
            Copy-Item -Path (Join-Path $src "*") -Destination $skillDest -Recurse -Force -ErrorAction SilentlyContinue
        }
        return
    }

    # 增量同步：直接覆盖复制（不先清空目标）
    Copy-Item -Path (Join-Path $ManageSkillsDir "*") -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue
}

# 按目标自己的来源记录圈定同步范围；返回 $false = 判定不出（调用方应跳过而非全量兜底）
function Scope-ForTarget($t) {
    $repos = Resolve-TargetRepos $t
    if ($repos -eq "") { return $false }
    Set-SyncScope @($repos -split '\s+' | Where-Object { $_ -ne "" })
    if ($script:SyncNames.Count -eq 0) { return $false }
    return $true
}

# 参数 "1" = 调用方已用 Set-SyncScope 设定显式范围（-Repo / -NameFilter），对所有目标适用；
# 否则按各目标自己的来源记录圈定范围（无记录则反查；判定不出则跳过，不做全量兜底）
function Sync-AllRecorded($Fixed = "0") {
    $targets = Get-RecordedTargets
    $total = $targets.Count
    $count = 0
    foreach ($t in $targets) {
        if (-not (Test-Path $t)) { Write-Warn "目标目录不存在，跳过: $t"; continue }
        if ($Fixed -eq "1") {
            if ($script:SyncNames.Count -eq 0) { Write-Warn "同步范围为 0，跳过: $t"; continue }
        } elseif (-not (Scope-ForTarget $t)) {
            Write-Warn "无法判定目标的来源仓库，跳过同步（避免把管理源全量复制）: $t"
            Write-Warn "  可用 'install -Repo <repo> -Target $t' 重建记录"
            continue
        }
        Sync-ToTarget $t
        $count++
        Write-Host "  [SYNC] $t"
    }
    Write-Info "已同步 $count/$total 个目标目录"
}

# ============================================================
# 安装
# ============================================================
function Do-Install {
    Resolve-Targets
    if ($script:TargetDirs.Count -eq 0) {
        Write-Err "未指定目标目录。使用 -Target <path>、-ConfigFile <path>，或在 $DefaultTargetsFile 配置。"
    }

    Ensure-ManageDir

    Write-Host "🚀 skill-install.ps1 v$ScriptVersion"
    Write-Host "   管理目录: $ManageDir"
    # 安装源列表先固化：PowerShell 变量名不区分大小写，循环变量 $repoUrl 之外的
    # 任何 $repo/$Repo 赋值都会覆盖它（历史坑：foreach ($repo in $Repo) 会把 $Repo 变成最后一个元素）
    $installRepos = @($Repo)
    Write-Host "   安装源: $($installRepos -join ', ')"
    Write-Host "   目标数量: $($script:TargetDirs.Count)"
    if ($NameList.Count -gt 0) { Write-Host "   名称过滤: $($NameList -join ', ')" }
    Write-Host ""

    Write-Info "通过 npx skills 安装到管理源..."
    Push-Location $ManageDir
    try {
        foreach ($repoUrl in $installRepos) {
            Write-Info "  安装源: $repoUrl"
            $npxArgs = @("skills", "add", $repoUrl, "--agent", $Agent, "-y")
            if ($NameList.Count -gt 0) {
                $npxArgs += @("--skill") + $NameList
            }
            & npx @npxArgs
            if ($LASTEXITCODE -ne 0) { Write-Err "npx skills add 失败: $repoUrl" }
        }
    } finally {
        Pop-Location
    }

    Write-Host ""
    # 圈定同步范围：只同步本次安装源（-Repo）的 skill
    Set-SyncScope @($installRepos)
    if ($script:SyncNames.Count -eq 0) {
        Write-Warn "同步范围为 0：管理源中没有匹配安装源（$($installRepos -join ', ')）的 skill，已跳过同步"
        Write-Warn "  管理源是多仓库共享池，全量同步会把其他仓库的 skill 复制到目标；可用 'list -Repo <repo>' 检查"
    } else {
        Write-Info "同步到目标目录（范围: $($script:SyncNames.Count) 个 skill · 来源 $($installRepos -join ', ')）..."
        foreach ($t in $script:TargetDirs) {
            if (-not (Test-Path $t)) { New-Item -ItemType Directory -Path $t -Force | Out-Null }
            Sync-ToTarget $t
            # 记录/合并该目标的来源仓库（供 update / prune 圈定范围）
            Record-Target $t @($installRepos)
            Write-Host "  [SYNC] $t"
        }

        Write-Host ""
        Write-Info "已安装并同步到 $($script:TargetDirs.Count) 个目标"
    }
    Write-Info "管理命令: update（更新）/ remove <names>（删除）/ prune（清理）/ list（查看）"
}


# ============================================================
# 更新：重新拉取已安装 skill 的最新版本并同步到目标
# ============================================================
function Do-Update {
    Ensure-ManageDir
    if (-not (Test-Path $LockFile)) { Write-Err "管理源为空，无可更新项。请先 install。" }
    if ((Get-Item $LockFile).Length -eq 0) { Write-Err "管理源为空，无可更新项。请先 install。" }

    # 更新范围：--repo 指定则用指定仓库，否则取管理源中已安装的所有仓库
    $repos = @()
    if ($RepoSpecified) {
        $repos = @($Repo)
    } else {
        $env:LOCK_FILE = $LockFile
        $repos = (& node -e @'
const fs=require('fs');
try{
  const d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,'utf8'));
  const r=new Set();
  for(const i of Object.values(d.skills||{})){ if(i.source) r.add(i.source); }
  console.log([...r].sort().join('\n'));
}catch(e){}
'@) | Where-Object { $_ -ne "" }
        Remove-Item Env:LOCK_FILE -ErrorAction SilentlyContinue
        if ($repos.Count -eq 0) { Write-Err "管理源中未找到已安装的仓库来源，无法更新。" }
    }

    Write-Host "🚀 skill-install.ps1 update（v$ScriptVersion）"
    Write-Host "   管理目录: $ManageDir"
    Write-Host "   更新仓库: $($repos -join ', ')"
    if ($NameList.Count -gt 0) { Write-Host "   名称过滤: $($NameList -join ', ')" }
    Write-Host ""

    Write-Info "通过 npx skills 重新拉取最新版本..."
    # 生成"按仓库分组"的 skill 清单：无 -NameFilter 时取管理源已安装的全部 skill，
    # 有 -NameFilter 时只取指定 skill；随后对每个仓库用 --skill 精确更新，
    # 避免 update 误把仓库全部 skill 全量重装进管理源。
    $env:LOCK_FILE = $LockFile
    $env:NAME_WANTED = if ($NameList.Count -gt 0) { ($NameList -join ' ') } else { "" }
    $env:REPO_SCOPE = ($repos -join ' ')
    $mapOutput = & node -e @'
const fs=require('fs');
const d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,'utf8'));
const wanted=(process.env.NAME_WANTED||'').split(' ').filter(Boolean);
const wantSet=wanted.length?new Set(wanted):null;
const scope=new Set((process.env.REPO_SCOPE||'').split(' '));
const out={};
for(const[name,i]of Object.entries(d.skills||{})){
  const s=i.source||'';
  if(!scope.has(s)) continue;
  if(wantSet&&!wantSet.has(name)) continue;
  (out[s]=out[s]||[]).push(name);
}
for(const s of Object.keys(out).sort()){
  console.log(s+'|'+out[s].sort().join(' '));
}
'@
    Remove-Item Env:LOCK_FILE, Env:NAME_WANTED, Env:REPO_SCOPE -ErrorAction SilentlyContinue

    Push-Location $ManageDir
    try {
        $updatedAny = $false
        foreach ($line in $mapOutput) {
            $parts = $line -split '\|', 2
            if ($parts.Count -lt 2 -or -not $parts[0]) { continue }
            $repoUrl = $parts[0]
            $skillNames = $parts[1]
            Write-Info "  更新源: $repoUrl → $skillNames"
            $npxArgs = @("skills", "add", $repoUrl, "--agent", $Agent, "-y", "--skill") + ($skillNames -split ' ')
            & npx @npxArgs
            if ($LASTEXITCODE -ne 0) { Write-Err "npx skills add 失败: $repoUrl" }
            $updatedAny = $true
        }
        if (-not $updatedAny) {
            if ($NameList.Count -gt 0) { Write-Warn "未在管理源中找到匹配的 skill：$($NameList -join ', ')" }
            Write-Warn "管理源中没有可更新的 skill。"
        }
    } finally {
        Pop-Location
    }

    # 同步范围：
    #   显式指定 -Repo / -NameFilter 时 = 该范围（对本次涉及的目标统一生效）
    #   否则 = 各目标自己的来源记录（无记录则反查自愈；判定不出则跳过，不做全量兜底）
    $explicitScope = $false
    if ($RepoSpecified -or $NameList.Count -gt 0) {
        $explicitScope = $true
        Set-SyncScope @($repos)
    }

    Write-Host ""
    Write-Info "同步到目标目录..."
    if ($Target -or $ConfigFile -or $TargetPath) {
        # 用户显式指定了目标（-Target / -ConfigFile / 位置参数），只同步这些
        Resolve-Targets
        foreach ($t in $script:TargetDirs) {
            if (-not (Test-Path $t)) { New-Item -ItemType Directory -Path $t -Force | Out-Null }
            if ((-not $explicitScope) -and (-not (Scope-ForTarget $t))) {
                Write-Warn "无法判定目标的来源仓库，跳过同步（避免把管理源全量复制）: $t"
                Write-Warn "  可用 'install -Repo <repo> -Target $t' 重建记录"
                continue
            }
            if ($script:SyncNames.Count -eq 0) {
                Write-Warn "同步范围为 0：管理源中没有匹配（$($repos -join ', ')$(if ($NameList.Count -gt 0) { ' · -NameFilter ' + ($NameList -join ',') })）的 skill，跳过: $t"
                continue
            }
            Sync-ToTarget $t
            Record-Target $t
            Write-Host "  [SYNC] $t"
        }
    } else {
        # 未指定目标，同步所有已记录目标（显式范围统一适用，否则按各目标记录）
        if ($explicitScope) { Sync-AllRecorded "1" } else { Sync-AllRecorded "0" }
    }

    Write-Host ""
    Write-Info "更新完成"
}


# ============================================================
# 删除
# ============================================================
function Do-Remove {
    Ensure-ManageDir
    if (-not (Test-Path $LockFile)) { Write-Err "管理源为空，无可删除项" }
    if ($NameList.Count -eq 0) { Write-Err "remove 需要指定 skill 名称（如 remove code-review 或 -NameFilter code-review）" }

    Write-Info "从管理源删除: $($NameList -join ', ')"
    Push-Location $ManageDir
    try {
        $npxArgs = @("skills", "remove") + $NameList + @("-y")
        & npx @npxArgs
        if ($LASTEXITCODE -ne 0) { Write-Err "npx skills remove 失败" }
    } finally {
        Pop-Location
    }

    # 兜底：npx skills remove 在 lock 与内部集合漂移时可能静默失败（退出码仍为 0），
    # 需主动校验并清理 lock 中残留条目 + 管理源目录，避免 list 仍显示、update 复活。
    $staleNames = @()
    foreach ($name in $NameList) {
        $env:LOCK_FILE = $LockFile
        $env:NAME = $name
        & node -e @'
const fs=require('fs');
const d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,'utf8'));
process.exit(d.skills && d.skills[process.env.NAME] ? 0 : 1);
'@
        if ($LASTEXITCODE -eq 0) { $staleNames += $name }
        Remove-Item Env:LOCK_FILE, Env:NAME -ErrorAction SilentlyContinue
    }
    if ($staleNames.Count -gt 0) {
        Write-Warn "npx 未删除 lock 条目（状态漂移），手动兜底清理: $($staleNames -join ', ')"
        $env:LOCK_FILE = $LockFile
        $env:STALE_NAMES = ($staleNames -join ' ')
        & node -e @'
const fs=require('fs');
const f=process.env.LOCK_FILE;
const d=JSON.parse(fs.readFileSync(f,'utf8'));
for(const n of process.env.STALE_NAMES.split(' ')){ delete d.skills[n]; }
fs.writeFileSync(f, JSON.stringify(d, null, 2) + '\n');
'@
        Remove-Item Env:LOCK_FILE, Env:STALE_NAMES -ErrorAction SilentlyContinue
        foreach ($name in $staleNames) {
            Remove-Item -Path (Join-Path $ManageSkillsDir $name) -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    Write-Host ""
    Write-Info "同步删除到所有已记录目标..."
    # 因 Sync-ToTarget 为增量同步（不删多余文件），此处显式删除目标中对应的 skill 目录
    foreach ($t in (Get-RecordedTargets)) {
        if (-not (Test-Path $t)) { continue }
        $dest = Target-Dest $t
        foreach ($name in $NameList) {
            Remove-Item -Path (Join-Path $dest $name) -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    # 此处不再全量重同步：管理源是多仓库共享池，全量同步会把池里其他仓库的
    # skill 复制进这些目标（删除已在上面的循环中逐目标完成）
    Write-Host ""
    Write-Info "删除完成"
}

# ============================================================
# 清理：删除目标中"安装器管理过、但不属于该目标来源范围"的 skill
# ============================================================
# 用于修复历史污染（早期版本按全量复制，目标里混进了其他仓库的 skill）。
# 只处理 lock 中登记过的 skill（＝安装器管理过的），手工新增目录一律保留；
# 默认预演只列出，加 -Yes 才真正删除；判定不出来源则拒绝执行（避免误删）。
function Do-Prune {
    Ensure-ManageDir
    if (-not (Test-Path $LockFile)) { Write-Err "管理源为空，无判定依据。请先 install。" }

    Resolve-Targets
    $targets = @($script:TargetDirs)
    if ($targets.Count -eq 0) { $targets = @(Get-RecordedTargets) }
    if ($targets.Count -eq 0) { Write-Err "未指定目标（-Target <path>），且无已记录目标" }

    Write-Host "🧹 skill-install.ps1 prune（v$ScriptVersion）"
    Write-Host "   管理目录: $ManageDir"
    Write-Host "   目标数量: $($targets.Count)"
    Write-Host "   模式: $(if ($Yes) { '执行删除' } else { '预演（仅列出，加 -Yes 执行）' })"
    Write-Host ""

    # 期望来源：显式 -Repo 时以它为准（可纠正老记录/被污染记录里的来源），
    # 否则按该目标自己的记录（无记录则反查自愈）
    $explicit = $RepoSpecified

    $map = Get-LockNameSources

    $totalRemoved = 0
    $totalTargets = 0
    foreach ($t in $targets) {
        $dest = Target-Dest $t
        if (-not (Test-Path $dest)) { Write-Warn "目标目录不存在，跳过: $t"; continue }
        if ($explicit) {
            $repos = ($Repo -join ' ')
            Set-SyncScope @($Repo)
            if ($script:SyncNames.Count -eq 0) {
                Write-Warn "指定的仓库（$repos）在管理源中没有匹配的 skill，跳过: $t"
                continue
            }
        } else {
            $repos = Resolve-TargetRepos $t
            if ($repos -eq "") {
                Write-Warn "无法判定目标的来源仓库，跳过（避免误删）: $t"
                Write-Warn "  可用 'prune -Target <目标> -Repo <期望仓库>' 指定期望来源后再清理"
                continue
            }
            Set-SyncScope @($repos -split '\s+' | Where-Object { $_ -ne "" })
        }
        $totalTargets++
        $removed = 0
        Write-Host "  $dest（保留来源: $repos）"
        foreach ($name in @(Get-ChildItem -Path $dest -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)) {
            # 只清理 lock 中登记过的 skill（安装器管理过的），手工目录一律保留
            $src = ""
            foreach ($line in $map) {
                $parts = $line -split "`t", 2
                if ($parts.Count -eq 2 -and $parts[0] -eq $name) { $src = $parts[1]; break }
            }
            if ($src -eq "") { continue }
            # 属于该目标来源范围 → 保留
            if ($script:SyncNames -contains $name) { continue }
            if ($Yes) {
                Remove-Item -Path (Join-Path $dest $name) -Recurse -Force -ErrorAction SilentlyContinue
                Write-Host "    [DEL]  $name  （来源: $src）"
            } else {
                Write-Host "    [待删] $name  （来源: $src）"
            }
            $removed++
        }
        if ($removed -eq 0) { Write-Host "    （无外来 skill）" }
        $totalRemoved += $removed
        # 显式指定期望来源时同步纠正记录（预演阶段只提示，-Yes 才写）
        if ($explicit) {
            if ($Yes) {
                Set-TargetRepos $t @($Repo)
                Write-Host "    [记录] 该目标来源已更新为: $repos"
            } else {
                Write-Host "    [记录] 加 -Yes 时会把该目标来源更新为: $repos"
            }
        }
    }

    Write-Host ""
    if ($Yes) {
        Write-Info "已从 $totalTargets 个目标清理 $totalRemoved 个不属于其来源范围的 skill"
    } else {
        Write-Info "预演：$totalTargets 个目标共 $totalRemoved 个外来 skill 待清理（确认后加 -Yes 执行）"
        if ($totalRemoved -eq 0 -and (-not $explicit)) {
            Write-Info "提示：若目标里混有历史污染、但反查把它算成了'目标自己的来源'，"
            Write-Info "  可用 'prune -Target <目标> -Repo <期望仓库> -Yes' 显式指定期望来源后再清理"
        }
    }
}

# ============================================================
# 列表
# ============================================================
function Do-List {
    Ensure-ManageDir
    if (-not (Test-Path $LockFile)) {
        Write-Warn "管理源为空，尚未安装任何 skill"
        Write-Warn "使用 install 安装"
        exit 0
    }

    # --repo 过滤（仅当用户显式指定 -Repo 时）
    $env:LOCK_FILE = $LockFile
    $env:REPO_FILTER = if ($RepoSpecified) { ($Repo -join ' ') } else { "" }
    & node -e @'
const fs=require('fs');
const d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,'utf8'));
const skills=d.skills||{};
const rf=(process.env.REPO_FILTER||'').split(' ').filter(Boolean);
const repoFilter=rf.length?new Set(rf):null;
const items={};
for(const[name,i]of Object.entries(skills)){
  const src=i.source||'unknown';
  if(repoFilter&&!repoFilter.has(src)) continue;
  (items[src]=items[src]||[]).push(name);
}
console.log('管理源已安装的 skill:');
console.log('');
console.log('仓库来源:');
for(const src of Object.keys(items).sort()){
  console.log(`  <- ${src}  (${items[src].length} 个)`);
}
console.log('');
let total=0;
for(const src of Object.keys(items).sort()){
  console.log(`${src}:`);
  for(const name of items[src].sort()){
    console.log(`  ${name}`);
    total++;
  }
  console.log('');
}
if(total===0) console.log('  （无匹配的 skill）');
console.log(`  共 ${total} 个 skill`);
'@
    Remove-Item Env:LOCK_FILE, Env:REPO_FILTER -ErrorAction SilentlyContinue

    Write-Host ""
    if (Test-Path $TargetsFile) {
        $tcount = (Get-Content $TargetsFile | Where-Object { $_.Trim() -ne "" }).Count
        Write-Info "已记录 $tcount 个目标目录（remove 时自动同步）"
    }
}

# ============================================================
# 主流程
# ============================================================
# 脚本自检（默认开启，TTL 节流；拿不到自身路径 / git 工作树内不覆盖，见 Invoke-SelfUpdate）
if ($Action -ne "self-update" -and (-not $NoSelfUpdate) -and ($env:SKILL_INSTALL_NO_SELF_UPDATE -ne "1") -and ($env:SKILL_INSTALL_SELF_UPDATED -ne "1")) {
    [void](Invoke-SelfUpdate "auto" $false)
}

switch ($Action) {
    "install"     { Do-Install }
    "update"      { Do-Update }
    "remove"      { Do-Remove }
    "prune"       { Do-Prune }
    "self-update" { Do-SelfUpdate }
    "list"        { Do-List }
}

Write-Host ""
Write-Host "✅ 完成"
