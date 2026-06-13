# ============================================================
# Skills 安装器 — 从 GitHub 下载脚本或 Skill 定义（Windows PowerShell）
#
# 用法:
#   .\skill-install.ps1 C:\projects\my-app -Scripts
#   powershell -ExecutionPolicy Bypass -File skill-install.ps1 C:\projects\my-app -Skills
# ============================================================
param(
    [Parameter(Position=0, Mandatory=$true, ParameterSetName="Scripts")]
    [Parameter(Position=0, Mandatory=$true, ParameterSetName="Skills")]
    [Parameter(Position=0, Mandatory=$true, ParameterSetName="Rules")]
    [string]$TargetPath,

    [Parameter(Mandatory=$true, ParameterSetName="Scripts")]
    [switch]$Scripts,

    [Parameter(Mandatory=$true, ParameterSetName="Skills")]
    [switch]$Skills,

    [Parameter(Mandatory=$true, ParameterSetName="Rules")]
    [switch]$Rules
)

$RawBase = "https://raw.githubusercontent.com/HACK-WU/skills/master"

# 去掉末尾斜杠，计算归一化路径
$NormalizedPath = $TargetPath.TrimEnd('\').TrimEnd('/')
$LeafName = Split-Path $NormalizedPath -Leaf

if (-not (Test-Path $NormalizedPath)) {
    Write-Host "Creating: $NormalizedPath"
    New-Item -ItemType Directory -Path $NormalizedPath -Force | Out-Null
}

function Install-Files {
    param([string]$SubPath, [string[]]$Files, [string]$DestDir)
    New-Item -ItemType Directory -Path $DestDir -Force | Out-Null

    $count = 0
    foreach ($f in $Files) {
        $url  = "$RawBase/$SubPath/$f"
        $dest = Join-Path $DestDir $f
        $dir  = Split-Path $dest -Parent
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }

        # 每次启动独立子进程下载，避免连接池复用问题
        $ok = Start-Process powershell -ArgumentList @(
            "-NoProfile", "-NonInteractive", "-Command",
            "`$wc=New-Object System.Net.WebClient;",
            "try{`$wc.DownloadFile('$url','$dest');exit 0}catch{exit 1}"
        ) -Wait -NoNewWindow -PassThru

        if ($ok.ExitCode -eq 0) {
            Write-Host "  [OK] $f"
            $count++
        } else {
            Write-Host "  [FAIL] $f"
        }
    }
    Write-Host "Done: $count/$($Files.Count)`n"
}

if ($Scripts) {
    # 如果传入路径已以 scripts 结尾，直接使用，避免嵌套
    $ScriptsDest = if ($LeafName -eq "scripts") { $NormalizedPath } else { Join-Path $NormalizedPath "scripts" }
    Write-Host "Scripts -> $ScriptsDest"
    Install-Files "scripts/requirement-mgr" @(
        "config_loader.py", "create-requirement.py", "delete-requirement.py",
        "file_lock.py", "id_generator.py", "list-requirements.py",
        "meta_store.py", "requirement_utils.py", "update-requirement.py"
    ) $ScriptsDest
}

if ($Skills) {
    # 如果传入路径已以 skills 结尾，直接使用，避免嵌套
    $SkillsDest = if ($LeafName -eq "skills") { $NormalizedPath } else { Join-Path $NormalizedPath "skills" }
    # 注意: skill-updater 是内部维护工具，不包含在用户安装列表中
    Write-Host "Skills -> $SkillsDest"
    Install-Files "skills" @(
        "auto-review/SKILL.md",
        "challenger/SKILL.md", "challenger/strategies/bug-fix.md",
        "challenger/strategies/feature.md", "challenger/strategies/optimization.md",
        "challenger/templates/report.md", "code-review/SKILL.md",
        "create-skill/SKILL.md", "data-flow-model/SKILL.md",
        "demo-verify/SKILL.md", "design-craft/SKILL.md",
        "design-craft/SUB_TEMPLATE.md", "design-craft/reference.md",
        "design-review/SKILL.md", "design-review/reference.md",
        "document-writer/SKILL.md", "document-writer/references/quality-rules.md",
        "document-writer/references/strategies.md", "document-writer/references/examples/example-1-library.md",
        "document-writer/references/examples/example-2-cli.md", "document-writer/references/examples/README.md",
        "expert-panel/SKILL.md", "expert-panel/references/review-panel.md",
        "implementation-report/SKILL.md",
        "interaction-design/SKILL.md",
        "migrate-to-codehub/SKILL.md", "requirement-doc-store/SKILL.md",
        "requirement-mining/SKILL.md", "requirement-mining/references/example.md",
        "test-planner/SKILL.md", "test-planner/references/test-strategies.md",
        "test-planner/references/examples/example-1-registration.md", "work-breakdown/SKILL.md"
    ) $SkillsDest
}

if ($Rules) {
    # 如果传入路径已以 rules 结尾，直接使用，避免嵌套
    $RulesDest = if ($LeafName -eq "rules") { $NormalizedPath } else { Join-Path $NormalizedPath "rules" }
    Write-Host "Rules -> $RulesDest"
    Install-Files "rules" @(
        "writing-pipeline.md"
    ) $RulesDest
}

Write-Host "Complete: $TargetPath"
