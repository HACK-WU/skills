# ============================================================
# Skills 安装器 — 基于 npx skills 管理本仓库的 AI Skills（PowerShell）
#
# 管理目录: $env:USERPROFILE\.hackwu-skills\
#   ├── skills\              # npx 安装的 skill（openclaw 映射 = cwd\skills\）
#   ├── skills-lock.json     # npx 生成的跟踪文件（update/remove/list 依据）
#   └── targets.list         # 已安装目标目录记录（update/remove 同步依据）
#
# 用法:
#   .\skill-install.ps1 install -Target C:\projects\app
#   .\skill-install.ps1 update [-Target ...] [-NameFilter names] [-Repo owner/repo]
#   .\skill-install.ps1 remove code-review
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
$Agent = "openclaw"
# 兼容 Windows（USERPROFILE）与 Unix（HOME）
$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $env:HOME }
$ManageDir = Join-Path $HomeDir ".hackwu-skills"
$ManageSkillsDir = Join-Path $ManageDir "skills"
$LockFile = Join-Path $ManageDir "skills-lock.json"
$TargetsFile = Join-Path $ManageDir "targets.list"
$DefaultTargetsFile = Join-Path $HomeDir ".skill-targets"

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

# ============================================================
# 帮助
# ============================================================
function Show-Help {
    Write-Host @"
Skills 安装器 — 基于 npx skills 管理 AI Skills

用法:
  .\skill-install.ps1 <操作> [选项]
  操作:
    install   安装 skill 到目标目录（默认操作，可省略）
    update    更新管理源中已安装的 skill 并同步到目标目录
    remove    从管理源删除指定 skill 并同步删除所有目标
    list      列出管理源中已安装的 skill（含来源仓库）
    -h, --help  显示此帮助

选项:
  -Target <path>      目标目录（可多次使用，与 -ConfigFile 互斥；update 时限定同步范围）
  -NameFilter <names> 指定 skill（逗号分隔，如 -NameFilter code-review,design-craft）
  -Repo <owner/repo>  指定仓库（可多次使用；install/update 指定安装源，list 按来源过滤）
  -ConfigFile <path>  从配置文件读取目标目录（与 -Target 互斥）

默认配置文件（不指定 -Target / -ConfigFile 时读取）:
  $DefaultTargetsFile

管理目录:
  $ManageDir

示例:
  .\skill-install.ps1 -Target C:\projects\app
  .\skill-install.ps1 install -NameFilter code-review,design-craft -Target C:\projects\app
  .\skill-install.ps1 update -Target C:\projects\app
  .\skill-install.ps1 update -NameFilter code-review -Repo HACK-WU/skills
  .\skill-install.ps1 remove code-review
  .\skill-install.ps1 list
  .\skill-install.ps1 list -Repo anthropics/skills
"@
    exit 0
}

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
        "update" { $Action = "update" }
        "remove" {
            $Action = "remove"
            # remove 的 skill 名可从位置参数（第二个）或 -NameFilter 获取
            if (-not $NameFilter -and $TargetPath) { $NameFilter = $TargetPath }
            if (-not $NameFilter) { Write-Err "remove 需要指定 skill 名称（如 remove code-review 或 -NameFilter code-review）" }
        }
        "list"   { $Action = "list" }
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
# 同步：管理源 → 目标（增量同步）
# 只覆盖更新同名文件，不删除目标中管理源没有的文件（保护本地手动修改）
# ============================================================
function Sync-ToTarget($target) {
    $leaf = Split-Path $target.TrimEnd('\').TrimEnd('/') -Leaf
    $dest = if ($leaf -eq "skills") { $target } else { Join-Path $target "skills" }
    if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }

    if (-not (Test-Path $ManageSkillsDir) -or -not (Get-ChildItem $ManageSkillsDir -ErrorAction SilentlyContinue)) {
        # 管理源为空，跳过同步（不删除目标中已有文件）
        return
    }

    # 增量同步：直接覆盖复制（不先清空目标）
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
    Write-Host "   安装源: $($Repo -join ', ')"
    Write-Host "   目标数量: $($script:TargetDirs.Count)"
    if ($NameList.Count -gt 0) { Write-Host "   名称过滤: $($NameList -join ', ')" }
    Write-Host ""

    Write-Info "通过 npx skills 安装到管理源..."
    Push-Location $ManageDir
    try {
        foreach ($repo in $Repo) {
            Write-Info "  安装源: $repo"
            $npxArgs = @("skills", "add", $repo, "--agent", $Agent, "-y")
            if ($NameList.Count -gt 0) {
                $npxArgs += @("--skill") + $NameList
            }
            & npx @npxArgs
            if ($LASTEXITCODE -ne 0) { Write-Err "npx skills add 失败: $repo" }
        }
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
    Write-Info "管理命令: update（更新）/ remove <names>（删除）/ list（查看）"
}


# 从 lock 文件读取已安装 skill 的来源仓库（去重）
# 用 node 解析（node 是本安装器的既有依赖，无需 python3）
function Get-InstalledRepos {
    if (-not (Test-Path $LockFile)) { return }
    $env:LOCK_FILE = $LockFile
    & node -e @'
const fs=require("fs");
try{
  const d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,"utf8"));
  const r=new Set();
  for(const i of Object.values(d.skills||{})){ if(i.source) r.add(i.source); }
  console.log([...r].sort().join("\n"));
}catch(e){}
'@
    Remove-Item Env:LOCK_FILE -ErrorAction SilentlyContinue
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
const fs=require("fs");
try{
  const d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,"utf8"));
  const r=new Set();
  for(const i of Object.values(d.skills||{})){ if(i.source) r.add(i.source); }
  console.log([...r].sort().join("\n"));
}catch(e){}
'@) | Where-Object { $_ -ne "" }
        Remove-Item Env:LOCK_FILE -ErrorAction SilentlyContinue
        if ($repos.Count -eq 0) { Write-Err "管理源中未找到已安装的仓库来源，无法更新。" }
    }

    Write-Host "🚀 skill-install.ps1 update"
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
const fs=require("fs");
const d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,"utf8"));
const wanted=(process.env.NAME_WANTED||"").split(" ").filter(Boolean);
const wantSet=wanted.length?new Set(wanted):null;
const scope=new Set((process.env.REPO_SCOPE||"").split(" "));
const out={};
for(const[name,i]of Object.entries(d.skills||{})){
  const s=i.source||"";
  if(!scope.has(s)) continue;
  if(wantSet&&!wantSet.has(name)) continue;
  (out[s]=out[s]||[]).push(name);
}
for(const s of Object.keys(out).sort()){
  console.log(s+"|"+out[s].sort().join(" "));
}
'@
    Remove-Item Env:LOCK_FILE, Env:NAME_WANTED, Env:REPO_SCOPE -ErrorAction SilentlyContinue

    Push-Location $ManageDir
    try {
        $updatedAny = $false
        foreach ($line in $mapOutput) {
            $parts = $line -split '\|', 2
            if ($parts.Count -lt 2 -or -not $parts[0]) { continue }
            $repo = $parts[0]
            $skillNames = $parts[1]
            Write-Info "  更新源: $repo → $skillNames"
            $npxArgs = @("skills", "add", $repo, "--agent", $Agent, "-y", "--skill") + ($skillNames -split ' ')
            & npx @npxArgs
            if ($LASTEXITCODE -ne 0) { Write-Err "npx skills add 失败: $repo" }
            $updatedAny = $true
        }
        if (-not $updatedAny) {
            if ($NameList.Count -gt 0) { Write-Warn "未在管理源中找到匹配的 skill：$($NameList -join ', ')" }
            Write-Warn "管理源中没有可更新的 skill。"
        }
    } finally {
        Pop-Location
    }

    Write-Host ""
    Write-Info "同步到目标目录..."
    if ($Target -or $ConfigFile -or $TargetPath) {
        # 用户显式指定了目标（-Target / -ConfigFile / 位置参数），只同步这些
        Resolve-Targets
        foreach ($t in $script:TargetDirs) {
            if (-not (Test-Path $t)) { New-Item -ItemType Directory -Path $t -Force | Out-Null }
            Sync-ToTarget $t
            Record-Target $t
            Write-Host "  [SYNC] $t"
        }
    } else {
        # 未指定目标，同步所有已记录目标
        Sync-AllRecorded
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

    Write-Host ""
    Write-Info "同步删除到所有已记录目标..."
    # 因 Sync-ToTarget 为增量同步（不删多余文件），此处显式删除目标中对应的 skill 目录
    foreach ($t in (Get-RecordedTargets)) {
        if (-not (Test-Path $t)) { continue }
        $leaf = Split-Path $t.TrimEnd('\').TrimEnd('/') -Leaf
        $dest = if ($leaf -eq "skills") { $t } else { Join-Path $t "skills" }
        foreach ($name in $NameList) {
            Remove-Item -Path (Join-Path $dest $name) -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
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
        Write-Warn "使用 install 安装"
        exit 0
    }

    # --repo 过滤（仅当用户显式指定 -Repo 时）
    $env:LOCK_FILE = $LockFile
    $env:REPO_FILTER = if ($RepoSpecified) { ($Repo -join ' ') } else { "" }
    & node -e @'
const fs=require("fs");
const d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,"utf8"));
const skills=d.skills||{};
const rf=(process.env.REPO_FILTER||"").split(" ").filter(Boolean);
const repoFilter=rf.length?new Set(rf):null;
const items={};
for(const[name,i]of Object.entries(skills)){
  const src=i.source||"unknown";
  if(repoFilter&&!repoFilter.has(src)) continue;
  (items[src]=items[src]||[]).push(name);
}
console.log("管理源已安装的 skill:");
console.log("");
console.log("仓库来源:");
for(const src of Object.keys(items).sort()){
  console.log(`  <- ${src}  (${items[src].length} 个)`);
}
console.log("");
let total=0;
for(const src of Object.keys(items).sort()){
  console.log(`${src}:`);
  for(const name of items[src].sort()){
    console.log(`  ${name}`);
    total++;
  }
  console.log("");
}
if(total===0) console.log("  （无匹配的 skill）");
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
switch ($Action) {
    "install" { Do-Install }
    "update"  { Do-Update }
    "remove"  { Do-Remove }
    "list"    { Do-List }
}

Write-Host ""
Write-Host "✅ 完成"
