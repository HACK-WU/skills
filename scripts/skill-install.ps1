# ============================================================
# Skills 安装器 — 从 GitHub 下载脚本或 Skill 定义（Windows PowerShell）
#
# 用法:
#   .\skill-install.ps1 C:\projects\my-app -Scripts
#   powershell -ExecutionPolicy Bypass -File skill-install.ps1 C:\projects\my-app -Skills
# ============================================================
param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$TargetPath,

    [Parameter(Mandatory=$true, ParameterSetName="Scripts")]
    [switch]$Scripts,

    [Parameter(Mandatory=$true, ParameterSetName="Skills")]
    [switch]$Skills
)

$RawBase = "https://raw.githubusercontent.com/HACK-WU/skills/master"

if (-not (Test-Path $TargetPath)) {
    Write-Host "Creating: $TargetPath"
    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
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
    Write-Host "Scripts -> $(Join-Path $TargetPath 'scripts')"
    Install-Files "scripts" @(
        "config_loader.py", "create-requirement.py", "delete-requirement.py",
        "file_lock.py", "id_generator.py", "list-requirements.py",
        "meta_store.py", "requirement_utils.py", "update-requirement.py"
    ) (Join-Path $TargetPath "scripts")
}

if ($Skills) {
    Write-Host "Skills -> $(Join-Path $TargetPath 'skills')"
    Install-Files "skills" @(
        "challenger/SKILL.md", "challenger/strategies/bug-fix.md",
        "challenger/strategies/feature.md", "challenger/strategies/optimization.md",
        "challenger/templates/report.md", "code-review/SKILL.md",
        "create-skill/SKILL.md", "data-flow-model/SKILL.md",
        "demo-verify/SKILL.md", "design-craft/SKILL.md",
        "design-craft/SUB_TEMPLATE.md", "design-craft/reference.md",
        "design-review/SKILL.md", "design-review/reference.md",
        "expert-panel/SKILL.md", "expert-panel/references/review-panel.md",
        "implementation-report/SKILL.md", "interaction-design/SKILL.md",
        "migrate-to-codehub/SKILL.md", "requirement-mining/SKILL.md",
        "requirement-mining/references/example.md", "work-breakdown/SKILL.md"
    ) (Join-Path $TargetPath "skills")
}

Write-Host "Complete: $TargetPath"
