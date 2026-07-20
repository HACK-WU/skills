# ============================================================
# Skills 安装器 — 从 GitHub 下载 Skills / Rules（PowerShell）
#
# 用法:
#   .\skill-install.ps1 -Skills -Target C:\projects\app -Target C:\projects\api
#   .\skill-install.ps1 -Rules -ConfigFile C:\targets.txt
#   .\skill-install.ps1 -Skills -NameFilter code-review,design-craft -Target C:\projects\app
#   .\skill-install.ps1 C:\projects\my-app -Skills   # 旧用法，兼容
#   .\skill-install.ps1 C:\projects\my-app -Skills -Rules  # 多模式
#
#   或:
#   iex (irm https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.ps1)
# ============================================================

param(
    [Parameter(Position=0)]
    [string]$TargetPath,

    [string[]]$Target,

    [string]$ConfigFile,

    [string[]]$NameFilter,

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

# 文件列表缓存（跨目标目录复用，避免重复调用 GitHub API）
$script:SkillsFiles = @()
$script:RulesFiles = @()
$script:SkillsDiscovered = $false
$script:RulesDiscovered = $false

# ============================================================
# 收集安装模式
# ============================================================
$Modes = @()
if ($Skills) { $Modes += "skills" }
if ($Rules)  { $Modes += "rules" }

if ($Modes.Count -eq 0) {
    Write-Host @"
用法: .\skill-install.ps1 [-Skills] [-Rules] [-Target <path>...] [-ConfigFile <path>] [-NameFilter <names>]

  -Skills          安装 AI Skill 定义（skills/）
  -Rules           安装 AI 规则（rules/）
  -NameFilter <names> 指定要安装的 skill/rule 名称（可多次使用，逗号分隔，如 -NameFilter code-review,design-craft 或 -NameFilter code-review -NameFilter design-craft）
  -Target <path>   指定目标目录（可多次使用，与 -ConfigFile 互斥）
  -ConfigFile <path> 指定目标目录配置文件（与 -Target 互斥）

兼容旧用法:
  .\skill-install.ps1 C:\projects\my-app -Skills
  .\skill-install.ps1 C:\projects\my-app -Skills -Rules

示例:
  .\skill-install.ps1 -Skills -Target C:\projects\app -Target C:\projects\api
  .\skill-install.ps1 -Skills -NameFilter code-review,design-craft -Target C:\projects\app
  .\skill-install.ps1 -Rules -ConfigFile C:\my-targets.txt
  .\skill-install.ps1 -Skills -Rules -Target C:\projects\my-app

默认配置文件（不指定 -Target / -ConfigFile 时自动读取）:
  -Skills  → $env:USERPROFILE\.skill-targets
  -Rules   → $env:USERPROFILE\.rule-targets

一键安装:
  iex (irm https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.ps1)
"@
    exit 1
}

# ============================================================
# 解析名称过滤（支持多参数和逗号分隔：-NameFilter a -NameFilter b 或 -NameFilter "a,b"）
# ============================================================
$NameList = @()
if ($NameFilter) {
    foreach ($filter in $NameFilter) {
        $NameList += $filter -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }
    }
}

function Test-NameMatches {
    param([string]$Name)
    if ($NameList.Count -eq 0) { return $true }
    return $NameList -contains $Name
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
        }
    }
    return $results
}

# ============================================================
# 安装函数
# ============================================================
function Install-Skills {
    param([string]$NormalizedDir)
    $leaf = Split-Path $NormalizedDir -Leaf
    $dest = if ($leaf -eq "skills") { $NormalizedDir } else { Join-Path $NormalizedDir "skills" }
    New-Item -ItemType Directory -Path $dest -Force | Out-Null

    # 动态发现：优先 GitHub API 递归获取，降级为硬编码；使用缓存避免重复 API 调用
    $files = @()
    if ($script:SkillsDiscovered) {
        $files = $script:SkillsFiles
    } else {
        Write-Host "🔍 正在通过 GitHub API 发现 skill 文件列表..." -NoNewline
        $skillDirs = @(Discover-DirectItems -ApiPath "skills" -Filter "dirs")
        if ($skillDirs.Count -gt 0) {
            foreach ($skillName in $skillDirs) {
                if ($skillName -eq "skill-updater") { continue }
                $subFiles = Discover-FilesRecursive -ApiPath "skills/$skillName" -Prefix ""
                foreach ($rel in $subFiles) {
                    $files += "$skillName/$rel"
                }
                Write-Host "." -NoNewline
            }
        }
        Write-Host ""
    }

    if ($files.Count -eq 0 -and -not $script:SkillsDiscovered) {
        Write-Host "⚠️  GitHub API 不可用，使用静态 skill 列表（可能不是最新）" -ForegroundColor Yellow
        $files = @(
            "api-design/SKILL.md",
            "api-testing/SKILL.md",
            "api-testing/examples.md",
            "api-testing/reference.md",
            "auto-review/SKILL.md",
            "bug-impact-analysis/SKILL.md",
            "challenger/SKILL.md",
            "challenger/strategies/bug-fix.md",
            "challenger/strategies/feature.md",
            "challenger/strategies/optimization.md",
            "challenger/strategies/design.md",
            "challenger/templates/report.md",
            "code-implement/SKILL.md",
            "code-review/SKILL.md",
            "code-survey/SKILL.md",
            "content-simplifier/SKILL.md",
            "create-rules/SKILL.md",
            "create-skill/SKILL.md",
            "data-flow-model/SKILL.md",
            "demo-verify/SKILL.md",
            "dependency-docs/SKILL.md",
            "design-craft/CHALLENGER_REPORT.md",
            "design-craft/SINGLE_DOC.md",
            "design-craft/SKILL.md",
            "design-craft/SUB_TEMPLATE.md",
            "design-craft/reference.md",
            "design-review/SKILL.md",
            "design-review/reference.md",
            "design-to-code/SKILL.md",
            "e2e-testing/SKILL.md",
            "e2e-testing/examples.md",
            "e2e-testing/reference.md",
            "document-writer/SKILL.md",
            "document-writer/references/examples/README.md",
            "document-writer/references/examples/example-1-library.md",
            "document-writer/references/examples/example-2-cli.md",
            "document-writer/references/quality-rules.md",
            "document-writer/references/strategies.md",
            "review-panel/SKILL.md",
            "review-panel/references/review-panel.md",
            "frontend-api-guide/SKILL.md",
            "frontend-api-guide/reference.md",
            "implementation-report/SKILL.md",
            "interaction-design/SKILL.md",
            "memory-creator/SKILL.md",
            "migrate-to-codehub/SKILL.md",
            "negative-requirement/SKILL.md",
            "request-guard/SKILL.md",
            "requirement-doc-store/SKILL.md",
            "requirement-mining/SKILL.md",
            "requirement-mining/references/example.md",
            "scenario-rehearsal/SKILL.md",
            "scenario-rehearsal/reference.md",
            "scenario-rehearsal/strategies/crud-api.md",
            "scenario-rehearsal/strategies/transaction-state-machine.md",
            "scenario-rehearsal/strategies/batch-sync.md",
            "scenario-rehearsal/strategies/realtime-messaging.md",
            "scenario-rehearsal/strategies/refactor-migration.md",
            "scenario-rehearsal/strategies/concurrency.md",
            "solution-capture/SKILL.md",
            "solution-lookup/SKILL.md",
            "task-dispatch/SKILL.md",
            "task-dispatch/reference.md",
            "test-planner/SKILL.md",
            "test-planner/references/examples/example-1-registration.md",
            "test-planner/references/test-strategies.md",
            "work-breakdown/SKILL.md"
        )
    }

    # 缓存首次发现的文件列表
    if (-not $script:SkillsDiscovered -and $files.Count -gt 0) {
        $script:SkillsFiles = $files
        $script:SkillsDiscovered = $true
    }

    Write-Host "🧠 安装 AI Skills → $dest"
    Write-Host ""

    # 以“目录(第一级)”为粒度统计 skill，而非按文件计数
    $fileCount = 0
    $fileTotal = 0
    $skippedSkills = @{}
    $matchedSkills = @{}
    $installedSkills = @{}
    foreach ($f in $files) {
        # 提取 skill 名称用于过滤（取第一级目录名）
        $skillName = $f.Split('/')[0]
        if (-not (Test-NameMatches -Name $skillName)) {
            $skippedSkills[$skillName] = $true
            continue
        }
        $matchedSkills[$skillName] = $true
        $fileTotal++
        $url  = "$RawBase/skills/$f"
        $destFile = Join-Path $dest $f
        if (Download-File -Url $url -Dest $destFile) {
            Write-Host "  [OK] $f"
            $fileCount++
            $installedSkills[$skillName] = $true
        } else {
            Write-Host "  [FAIL] $f"
        }
    }
    if ($skippedSkills.Count -gt 0) { Write-Host "  跳过: $($skippedSkills.Count) 个未匹配的 skill" }
    Write-Host ""
    $skillTotal = $matchedSkills.Count
    $skillInstalled = $installedSkills.Count
    Write-Host "已安装: $skillInstalled/$skillTotal 个 skill（$fileCount/$fileTotal 个文件）"
    if ($skillInstalled -gt 0) { $script:AnyInstalled = $true }
}

function Install-Rules {
    param([string]$NormalizedDir)
    $leaf = Split-Path $NormalizedDir -Leaf
    $dest = if ($leaf -eq "rules") { $NormalizedDir } else { Join-Path $NormalizedDir "rules" }
    New-Item -ItemType Directory -Path $dest -Force | Out-Null

    # 动态发现：优先 GitHub API，降级为硬编码；使用缓存避免重复 API 调用
    $files = @()
    if ($script:RulesDiscovered) {
        $files = $script:RulesFiles
    } else {
        Write-Host "🔍 正在通过 GitHub API 发现规则文件列表..."
        $files = @(Discover-DirectItems -ApiPath "rules" -Filter "md")
        Write-Host "   已发现 $($files.Count) 个规则文件"
    }

    if ($files.Count -eq 0 -and -not $script:RulesDiscovered) {
        Write-Host "⚠️  GitHub API 不可用，使用静态 rule 列表（可能不是最新）" -ForegroundColor Yellow
$files = @(
    "gitnexus-mcp-rules.md",
    "agents-memory.md",
    "writing-pipeline.md",
    "solution-workflow.md"
)
    }

    # 缓存首次发现的文件列表
    if (-not $script:RulesDiscovered -and $files.Count -gt 0) {
        $script:RulesFiles = $files
        $script:RulesDiscovered = $true
    }

    Write-Host "📏 安装 AI Rules → $dest"
    Write-Host ""

    $count = 0
    $total = 0
    $skipped = 0
    foreach ($f in $files) {
        # 提取规则名称用于过滤（去掉 .md 后缀）
        $ruleName = $f -replace '\.md$', ''
        if (-not (Test-NameMatches -Name $ruleName)) {
            $skipped++
            continue
        }
        $total++
        $url  = "$RawBase/rules/$f"
        $destFile = Join-Path $dest $f
        if (Download-File -Url $url -Dest $destFile) {
            Write-Host "  [OK] $f"
            $count++
        } else {
            Write-Host "  [FAIL] $f"
        }
    }
    if ($skipped -gt 0) { Write-Host "  跳过: $skipped 个未匹配的 rule" }
    Write-Host ""
    Write-Host "已安装: $count/$total 个规则文件"
    if ($count -gt 0) { $script:AnyInstalled = $true }
}

# ============================================================
# 主流程
# ============================================================
Write-Host "🚀 skill-install.ps1"
Write-Host "   目标来源: $SourceDesc"
Write-Host "   目标数量: $($TargetDirs.Count)"
Write-Host "   安装模式: $($Modes -join ', ')"
if ($NameList.Count -gt 0) { Write-Host "   名称过滤: $($NameList -join ', ')" }
Write-Host ""

$script:AnyInstalled = $false

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
            "skills"  { Install-Skills $normalizedDir }
            "rules"   { Install-Rules $normalizedDir }
        }
        Write-Host ""
    }
}

Write-Host ""
if (-not $script:AnyInstalled -and $NameList.Count -gt 0) {
    Write-Host "⚠️ 未找到匹配的项，请检查名称是否正确"
    exit 1
}
Write-Host "✅ 完成"
