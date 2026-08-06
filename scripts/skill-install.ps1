# ============================================================
# Skills 安装器 — 基于 npx skills 管理本仓库的 AI Skills（PowerShell）
#
# 管理目录: $env:USERPROFILE\.hackwu-skills\
#   ├── skills\              # npx 安装的 skill（openclaw 映射 = cwd\skills\）
#   ├── skills-lock.json     # npx 生成的跟踪文件（update/remove/list 依据）
#   └── targets.list         # 已安装目标目录记录（update/remove 同步依据）
#
# 用法:
#   .\skill-install.ps1 -Target C:\projects\app
#   .\skill-install.ps1 -NameFilter code-review,design-craft -Target C:\projects\app
#   .\skill-install.ps1 -Target C:\projects\a -Target C:\projects\b
#   .\skill-install.ps1 -Update
#   .\skill-install.ps1 -Remove code-review
#   .\skill-install.ps1 -List
#
# 兼容旧用法:
#   .\skill-install.ps1 C:\projects\my-app
# ============================================================

param(
    [Parameter(Position=0)]
    [string]$TargetPath,

    [string[]]$Target,

    [string]$ConfigFile,

    [string[]]$NameFilter,

    [switch]$Update,
    [switch]$Remove,
    [switch]$List,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

$Repo = "HACK-WU/skills"
$Agent = "openclaw"
$ManageDir = Join-Path $env:USERPROFILE ".hackwu-skills"
$ManageSkillsDir = Join-Path $ManageDir "skills"
$LockFile = Join-Path $ManageDir "skills-lock.json"
$TargetsFile = Join-Path $ManageDir "targets.list"
$DefaultTargetsFile = Join-Path $env:USERPROFILE ".skill-targets"

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

# ============================================================
# 帮助
# ============================================================
if ($Help) {
    Write-Host @"
Skills 安装器 — 基于 npx skills 管理 AI Skills

用法:
  .\skill-install.ps1 [-Target <path>...] [-NameFilter <names>] [-ConfigFile <path>]
  .\skill-install.ps1 -Update
  .\skill-install.ps1 -Remove <names>
  .\skill-install.ps1 -List
  .\skill-install.ps1 -Help

操作:
  （默认）             安装 skill 到目标目录
  -Update             更新管理源并同步到所有已记录的目标
  -Remove <names>     从管理源删除指定 skill 并同步（逗号分隔）
  -List               列出管理源中已安装的 skill
  -Help               显示此帮助

安装选项:
  -Target <path>      目标目录（可多次使用，与 -ConfigFile 互斥）
  -NameFilter <names> 只安装指定 skill（逗号分隔，如 -NameFilter code-review,design-craft）
  -ConfigFile <path>  从配置文件读取目标目录（与 -Target 互斥）

默认配置文件（不指定 -Target / -ConfigFile 时读取）:
  $DefaultTargetsFile

管理目录:
  $ManageDir

示例:
  .\skill-install.ps1 -Target C:\projects\app
  .\skill-install.ps1 -NameFilter code-review,design-craft -Target C:\projects\app
  .\skill-install.ps1 -Target C:\projects\a -Target C:\projects\b
  .\skill-install.ps1 -Update
  .\skill-install.ps1 -Remove code-review
  .\skill-install.ps1 -List
"@
    exit 0
}

# ============================================================
# 确定操作
# ============================================================
$Action = ""
if ($Update) { $Action = "update" }
elseif ($Remove) {
    $Action = "remove"
    if (-not $NameFilter -or $NameFilter.Count -eq 0) { Write-Err "-Remove 需要指定 skill 名称（-NameFilter）" }
}
elseif ($List) { $Action = "list" }
else { $Action = "install" }  # 默认安装

# ============================================================
# 前置检查
# ============================================================
$npxCmd = Get-Command npx -ErrorAction SilentlyContinue
if (-not $npxCmd) {
    Write-Err "未检测到 npx（本安装器基于 'npx skills' 管理技能，需 Node.js >= 18）。`n`n  请先安装 Node.js，任选其一：`n    1. 官方安装包: https://nodejs.org/ （选择 LTS 版本）`n    2. winget: winget install OpenJS.NodeJS.LTS`n    3. Chocolatey: choco install nodejs-lts`n`n  安装完成后重试本脚本。"
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

# 记录目标（去重）
function Record-Target($t) {
    if (Test-Path $TargetsFile) {
        $existing = Get-Content $TargetsFile -ErrorAction SilentlyContinue
        if ($existing -contains $t) { return }
    }
    Add-Content -Path $TargetsFile -Value $t
}

# 读取所有已记录目标
function Get-RecordedTargets {
    if (-not (Test-Path $TargetsFile)) { return @() }
    $result = @()
    foreach ($line in (Get-Content $TargetsFile -ErrorAction SilentlyContinue)) {
        $trimmed = $line.Trim()
        if ($trimmed -ne "") { $result += $trimmed }
    }
    return $result
}

# ============================================================
# 同步：管理源 → 目标（镜像同步）
# ============================================================
function Sync-ToTarget($target) {
    $leaf = Split-Path $target.TrimEnd('\').TrimEnd('/') -Leaf
    $dest = if ($leaf -eq "skills") { $target } else { Join-Path $target "skills" }
    if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }

    if (-not (Test-Path $ManageSkillsDir) -or -not (Get-ChildItem $ManageSkillsDir -ErrorAction SilentlyContinue)) {
        # 管理源为空，清空目标
        Get-ChildItem $dest -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        return
    }

    # 镜像同步：先清空目标，再复制管理源
    Get-ChildItem $dest -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -Path (Join-Path $ManageSkillsDir "*") -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue
}

function Sync-AllRecorded {
    $targets = Get-RecordedTargets
    $total = $targets.Count
    $count = 0
    foreach ($t in $targets) {
        if (-not (Test-Path $t)) { Write-Warn "目标目录不存在，跳过: $t"; continue }
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

    Write-Host "🚀 skill-install.ps1"
    Write-Host "   管理目录: $ManageDir"
    Write-Host "   目标数量: $($script:TargetDirs.Count)"
    if ($NameList.Count -gt 0) { Write-Host "   名称过滤: $($NameList -join ', ')" }
    Write-Host ""

    Write-Info "通过 npx skills 安装到管理源..."
    Push-Location $ManageDir
    try {
        $npxArgs = @("skills", "add", $Repo, "--agent", $Agent, "-y")
        if ($NameList.Count -gt 0) {
            $npxArgs += @("--skill") + $NameList
        }
        & npx @npxArgs
        if ($LASTEXITCODE -ne 0) { Write-Err "npx skills add 失败" }
    } finally {
        Pop-Location
    }

    Write-Host ""
    Write-Info "同步到目标目录..."
    foreach ($t in $script:TargetDirs) {
        if (-not (Test-Path $t)) { New-Item -ItemType Directory -Path $t -Force | Out-Null }
        Sync-ToTarget $t
        Record-Target $t
        Write-Host "  [SYNC] $t"
    }

    Write-Host ""
    Write-Info "已安装并同步到 $($script:TargetDirs.Count) 个目标"
    Write-Info "管理命令: -Update（更新）/ -Remove <names>（删除）/ -List（查看）"
}

# ============================================================
# 更新
# ============================================================
function Do-Update {
    Ensure-ManageDir
    if (-not (Test-Path $LockFile)) { Write-Err "管理源为空，请先安装技能" }

    Write-Info "更新管理源..."
    Push-Location $ManageDir
    try {
        & npx skills update -y
        if ($LASTEXITCODE -ne 0) { Write-Err "npx skills update 失败" }
    } finally {
        Pop-Location
    }

    Write-Host ""
    Write-Info "同步到所有已记录目标..."
    Sync-AllRecorded
    Write-Host ""
    Write-Info "更新完成"
}

# ============================================================
# 删除
# ============================================================
function Do-Remove {
    Ensure-ManageDir
    if (-not (Test-Path $LockFile)) { Write-Err "管理源为空，无可删除项" }
    if ($NameList.Count -eq 0) { Write-Err "-Remove 需要指定 skill 名称（-NameFilter）" }

    Write-Info "从管理源删除: $($NameList -join ', ')"
    Push-Location $ManageDir
    try {
        $npxArgs = @("skills", "remove") + $NameList + @("-y")
        & npx @npxArgs
        if ($LASTEXITCODE -ne 0) { Write-Err "npx skills remove 失败" }
    } finally {
        Pop-Location
    }

    Write-Host ""
    Write-Info "同步删除到所有已记录目标..."
    Sync-AllRecorded
    Write-Host ""
    Write-Info "删除完成"
}

# ============================================================
# 列表
# ============================================================
function Do-List {
    Ensure-ManageDir
    if (-not (Test-Path $LockFile)) {
        Write-Warn "管理源为空，尚未安装任何 skill"
        Write-Warn "使用 -Target <path> 安装"
        exit 0
    }

    Write-Info "管理源已安装的 skill:"
    Write-Host ""

    Push-Location $ManageDir
    try {
        & npx skills list
    } finally {
        Pop-Location
    }

    if ($LASTEXITCODE -ne 0) {
        # 降级：从 lock 文件解析
        Write-Warn "npx skills list 不可用，从 lock 文件读取..."
        try {
            $data = Get-Content $LockFile -Raw | ConvertFrom-Json
            $skills = $data.skills.PSObject.Properties.Name | Sort-Object
            foreach ($name in $skills) { Write-Host "  $name" }
            Write-Host "`n  共 $($skills.Count) 个 skill"
        } catch {
            Write-Host "  （无法解析，lock 文件: $LockFile）"
        }
    }

    Write-Host ""
    if (Test-Path $TargetsFile) {
        $tcount = (Get-Content $TargetsFile | Where-Object { $_.Trim() -ne "" }).Count
        Write-Info "已记录 $tcount 个目标目录（-Update / -Remove 时自动同步）"
    }
}

# ============================================================
# 主流程
# ============================================================
switch ($Action) {
    "install" { Do-Install }
    "update"  { Do-Update }
    "remove"  { Do-Remove }
    "list"    { Do-List }
}

Write-Host ""
Write-Host "✅ 完成"
