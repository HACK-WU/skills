# ============================================================
# Skills 安装器 — 从 GitHub 下载 Scripts / Skills / Rules（PowerShell）
#
# 用法:
#   .\skill-install.ps1 -Skills -Target C:\projects\app -Target C:\projects\api
#   .\skill-install.ps1 -Rules -ConfigFile C:\targets.txt
#   .\skill-install.ps1 C:\projects\my-app -Scripts          # 旧用法，兼容
#   .\skill-install.ps1 C:\projects\my-app -Scripts -Skills -Rules  # 多模式
# ============================================================

param(
    [Parameter(Position=0)]
    [string]$TargetPath,

    [string[]]$Target,

    [string]$ConfigFile,

    [switch]$Scripts,
    [switch]$Skills,
    [switch]$Rules
)

$ErrorActionPreference = "Stop"

$GITHUB_REPO = "HACK-WU/skills"
$GITHUB_BRANCH = "master"
$RawBase = "https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}"
$ApiBase = "https://api.github.com/repos/${GITHUB_REPO}/contents"
$DefaultSkillsTargets = "$env:USERPROFILE\.skill-targets"
$DefaultRulesTargets = "$env:USERPROFILE\.rule-targets"
$DefaultScriptsTargets = "$env:USERPROFILE\.script-targets"

# ============================================================
# 收集安装模式
# ============================================================
$Modes = @()
if ($Scripts) { $Modes += "scripts" }
if ($Skills)  { $Modes += "skills" }
if ($Rules)   { $Modes += "rules" }

if ($Modes.Count -eq 0) {
    Write-Host @"
用法: .\skill-install.ps1 [-Scripts] [-Skills] [-Rules] [-Target <path>...] [-ConfigFile <path>]

  -Scripts         安装 CRUD 管理脚本（scripts/）
  -Skills          安装 AI Skill 定义（skills/）
  -Rules           安装 AI 规则（rules/）
  -Target <path>   指定目标目录（可多次使用，与 -ConfigFile 互斥）
  -ConfigFile <path> 指定目标目录配置文件（与 -Target 互斥）

兼容旧用法:
  .\skill-install.ps1 C:\projects\my-app -Scripts
  .\skill-install.ps1 C:\projects\my-app -Scripts -Skills -Rules

示例:
  .\skill-install.ps1 -Skills -Target C:\projects\app -Target C:\projects\api
  .\skill-install.ps1 -Rules -ConfigFile C:\my-targets.txt
  .\skill-install.ps1 -Scripts -Skills -Rules -Target C:\projects\my-app

默认配置文件（不指定 -Target / -ConfigFile 时自动读取）:
  -Skills   → $env:USERPROFILE\.skill-targets
  -Rules    → $env:USERPROFILE\.rule-targets
  -Scripts  → $env:USERPROFILE\.script-targets

一键安装:
  iex (irm https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.ps1)
"@
    exit 1
}

# ============================================================
# 互斥检查 & 解析目标目录
# ============================================================
if ($Target -and $ConfigFile) {
    Write-Host "错误：-Target 和 -ConfigFile 不能同时使用"
    exit 1
}

$TargetDirs = @()
$SourceDesc = ""

if ($Target) {
    $TargetDirs = @($Target)
    $SourceDesc = "命令行参数 (-Target x $($TargetDirs.Count))"
} elseif ($ConfigFile) {
    if (-not (Test-Path $ConfigFile)) {
        Write-Host "错误：配置文件不存在: $ConfigFile"
        exit 1
    }
    foreach ($line in (Get-Content $ConfigFile -ErrorAction Stop)) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
        $TargetDirs += $trimmed
    }
    if ($TargetDirs.Count -eq 0) {
        Write-Host "错误：配置文件为空: $ConfigFile"
        exit 1
    }
    $SourceDesc = "配置文件: $ConfigFile"
} elseif ($Modes.Count -gt 0) {
    # 模式特定的默认配置文件
    $modeFiles = @()
    foreach ($mode in $Modes) {
        switch ($mode) {
            "scripts" { $modeFiles += $DefaultScriptsTargets }
            "skills"  { $modeFiles += $DefaultSkillsTargets }
            "rules"   { $modeFiles += $DefaultRulesTargets }
        }
    }
    $seen = @{}
    foreach ($cf in $modeFiles) {
        if (Test-Path $cf) {
            foreach ($line in (Get-Content $cf -ErrorAction SilentlyContinue)) {
                $trimmed = $line.Trim()
                if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
                if (-not $seen.ContainsKey($trimmed)) {
                    $TargetDirs += $trimmed
                    $seen[$trimmed] = $true
                }
            }
        }
    }
    if ($TargetDirs.Count -gt 0) {
        $SourceDesc = "默认配置（模式区分）"
    }
} elseif ($TargetPath) {
    $TargetDirs = @($TargetPath)
    $SourceDesc = "位置参数"
}

if ($TargetDirs.Count -eq 0) {
    Write-Host "错误：未指定目标目录"
    Write-Host "使用 -Target <path> 或 -ConfigFile <path> 指定目标目录"
    exit 1
}

# ============================================================
# 通用函数
# ============================================================
function Download-File {
    param([string]$Url, [string]$Dest)
    $dir = Split-Path $Dest -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing -ErrorAction Stop
        return $true
    } catch {
        if (Test-Path $Dest) { Remove-Item $Dest -Force -ErrorAction SilentlyContinue }
        return $false
    }
}

# 通过 GitHub API 递归发现目录下所有文件
function Discover-FilesRecursive {
    param([string]$ApiPath, [string]$Prefix)
    $files = @()
    try {
        $items = Invoke-RestMethod -Uri "$ApiBase/$ApiPath" -UseBasicParsing -ErrorAction Stop
    } catch {
        return $files
    }
    foreach ($item in $items) {
        if ($item.type -eq "dir") {
            $files += Discover-FilesRecursive -ApiPath "$($item.path)" -Prefix "$Prefix$($item.name)/"
        } elseif ($item.type -eq "file") {
            $files += "$Prefix$($item.name)"
        }
    }
    return $files
}

# 通过 GitHub API 发现目录下的直接子目录或文件
function Discover-DirectItems {
    param([string]$ApiPath, [string]$Filter)
    $results = @()
    try {
        $items = Invoke-RestMethod -Uri "$ApiBase/$ApiPath" -UseBasicParsing -ErrorAction Stop
    } catch {
        return $results
    }
    foreach ($item in $items) {
        switch ($Filter) {
            "dirs"  { if ($item.type -eq "dir")  { $results += $item.name } }
            "files" { if ($item.type -eq "file") { $results += $item.name } }
            "md"    { if ($item.type -eq "file" -and $item.name -like "*.md") { $results += $item.name } }
            "py"    { if ($item.type -eq "file" -and $item.name -like "*.py") { $results += $item.name } }
        }
    }
    return $results
}

# ============================================================
# 安装函数
# ============================================================
function Install-Scripts {
    param([string]$NormalizedDir)
    $leaf = Split-Path $NormalizedDir -Leaf
    $dest = if ($leaf -eq "scripts") { $NormalizedDir } else { Join-Path $NormalizedDir "scripts" }
    New-Item -ItemType Directory -Path $dest -Force | Out-Null

    # 动态发现：优先 GitHub API，降级为硬编码
    $files = @(Discover-DirectItems -ApiPath "scripts/requirement-mgr" -Filter "py")
    if ($files.Count -eq 0) {
        Write-Host "⚠️  GitHub API 不可用，使用静态脚本列表（可能不是最新）" -ForegroundColor Yellow
        $files = @(
            "config_loader.py", "create-requirement.py", "delete-requirement.py",
            "file_lock.py", "id_generator.py", "list-requirements.py",
            "meta_store.py", "requirement_utils.py", "update-requirement.py"
        )
    }

    Write-Host "📦 安装 CRUD 脚本 → $dest"
    Write-Host ""

    $count = 0
    foreach ($f in $files) {
        $url  = "$RawBase/scripts/requirement-mgr/$f"
        $destFile = Join-Path $dest $f
        if (Download-File -Url $url -Dest $destFile) {
            Write-Host "  [OK] $f"
            $count++
        } else {
            Write-Host "  [FAIL] $f"
        }
    }
    Write-Host ""
    Write-Host "已安装: $count/$($files.Count)"
    if ($count -gt 0) {
        Write-Host ""
        Write-Host "使用:"
        Write-Host "  uv run python scripts/list-requirements.py"
        Write-Host "  uv run python scripts/create-requirement.py --feature '名称' --tags feat"
    }
}

function Install-Skills {
    param([string]$NormalizedDir)
    $leaf = Split-Path $NormalizedDir -Leaf
    $dest = if ($leaf -eq "skills") { $NormalizedDir } else { Join-Path $NormalizedDir "skills" }
    New-Item -ItemType Directory -Path $dest -Force | Out-Null

    # 动态发现：优先 GitHub API 递归获取，降级为硬编码
    $files = @()
    $skillDirs = @(Discover-DirectItems -ApiPath "skills" -Filter "dirs")
    if ($skillDirs.Count -gt 0) {
        foreach ($skillName in $skillDirs) {
            if ($skillName -eq "skill-updater") { continue }
            $subFiles = Discover-FilesRecursive -ApiPath "skills/$skillName" -Prefix ""
            foreach ($rel in $subFiles) {
                $files += "$skillName/$rel"
            }
        }
    }

    if ($files.Count -eq 0) {
        Write-Host "⚠️  GitHub API 不可用，使用静态 skill 列表（可能不是最新）" -ForegroundColor Yellow
        $files = @(
            "auto-review/SKILL.md",
            "challenger/SKILL.md", "challenger/strategies/bug-fix.md",
            "challenger/strategies/feature.md", "challenger/strategies/optimization.md",
            "challenger/templates/report.md", "code-review/SKILL.md",
            "create-rules/SKILL.md", "create-skill/SKILL.md", "data-flow-model/SKILL.md",
            "demo-verify/SKILL.md", "design-craft/SKILL.md",
            "design-craft/SUB_TEMPLATE.md", "design-craft/reference.md",
            "design-review/SKILL.md", "design-review/reference.md",
            "document-writer/SKILL.md", "document-writer/references/quality-rules.md",
            "document-writer/references/strategies.md", "document-writer/references/examples/example-1-library.md",
            "document-writer/references/examples/example-2-cli.md", "document-writer/references/examples/README.md",
            "expert-panel/SKILL.md", "expert-panel/references/review-panel.md",
            "implementation-report/SKILL.md",
            "interaction-design/SKILL.md",
            "memory-creator/SKILL.md", "migrate-to-codehub/SKILL.md", "requirement-doc-store/SKILL.md",
            "requirement-mining/SKILL.md", "requirement-mining/references/example.md",
            "test-planner/SKILL.md", "test-planner/references/test-strategies.md",
            "test-planner/references/examples/example-1-registration.md", "work-breakdown/SKILL.md"
        )
    }

    Write-Host "🧠 安装 AI Skills → $dest"
    Write-Host ""

    $count = 0
    foreach ($f in $files) {
        $url  = "$RawBase/skills/$f"
        $destFile = Join-Path $dest $f
        if (Download-File -Url $url -Dest $destFile) {
            Write-Host "  [OK] $f"
            $count++
        } else {
            Write-Host "  [FAIL] $f"
        }
    }
    Write-Host ""
    Write-Host "已安装: $count/$($files.Count) 个 skill 文件"
}

function Install-Rules {
    param([string]$NormalizedDir)
    $leaf = Split-Path $NormalizedDir -Leaf
    $dest = if ($leaf -eq "rules") { $NormalizedDir } else { Join-Path $NormalizedDir "rules" }
    New-Item -ItemType Directory -Path $dest -Force | Out-Null

    # 动态发现：优先 GitHub API，降级为硬编码
    $files = @(Discover-DirectItems -ApiPath "rules" -Filter "md")
    if ($files.Count -eq 0) {
        Write-Host "⚠️  GitHub API 不可用，使用静态 rule 列表（可能不是最新）" -ForegroundColor Yellow
        $files = @(
            "gitnexus-mcp-rules.md",
            "writing-pipeline.md"
        )
    }

    Write-Host "📏 安装 AI Rules → $dest"
    Write-Host ""

    $count = 0
    foreach ($f in $files) {
        $url  = "$RawBase/rules/$f"
        $destFile = Join-Path $dest $f
        if (Download-File -Url $url -Dest $destFile) {
            Write-Host "  [OK] $f"
            $count++
        } else {
            Write-Host "  [FAIL] $f"
        }
    }
    Write-Host ""
    Write-Host "已安装: $count/$($files.Count) 个规则文件"
}

# ============================================================
# 主流程
# ============================================================
Write-Host "🚀 skill-install.ps1"
Write-Host "   目标来源: $SourceDesc"
Write-Host "   目标数量: $($TargetDirs.Count)"
Write-Host "   安装模式: $($Modes -join ', ')"
Write-Host ""

for ($i = 0; $i -lt $TargetDirs.Count; $i++) {
    $dir = $TargetDirs[$i]
    $label = "[$($i + 1)/$($TargetDirs.Count)]"

    if (-not (Test-Path $dir)) {
        Write-Host "$label 创建目标目录: $dir"
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $normalizedDir = $dir.TrimEnd('\').TrimEnd('/')

    foreach ($mode in $Modes) {
        switch ($mode) {
            "scripts" { Install-Scripts $normalizedDir }
            "skills"  { Install-Skills $normalizedDir }
            "rules"   { Install-Rules $normalizedDir }
        }
        Write-Host ""
    }
}

Write-Host "✅ 完成"
