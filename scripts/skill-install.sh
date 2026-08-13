#!/usr/bin/env bash
# ============================================================
# Skills 安装器 — 基于 npx skills 管理本仓库的 AI Skills
#
# 管理目录: ~/.hackwu-skills/
#   ├── skills/              # npx 安装的 skill（openclaw 映射 = cwd/skills/）
#   ├── skills-lock.json     # npx 生成的跟踪文件（update/remove/list 依据）
#   └── targets.list         # 已安装目标目录记录（update/remove 同步依据）
#
# 用法:
#   bash skill-install.sh install -t /path/to/target     # 安装（默认）
#   bash skill-install.sh update [-t ...] [-n names] [--repo ...]  # 更新并同步
#   bash skill-install.sh remove <names>                  # 删除 + 同步
#   bash skill-install.sh list [--repo ...]               # 列出已装 skill
#   bash skill-install.sh --help
#
# 兼容旧用法:
#   bash skill-install.sh -t /path/to/target
# ============================================================
set -euo pipefail

AGENT="openclaw"
REPOS=()
MANAGE_DIR="${HOME}/.hackwu-skills"
MANAGE_SKILLS_DIR="${MANAGE_DIR}/skills"
LOCK_FILE="${MANAGE_DIR}/skills-lock.json"
TARGETS_FILE="${MANAGE_DIR}/targets.list"
DEFAULT_TARGETS_FILE="$HOME/.skill-targets"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

# ============================================================
# 参数解析
# ============================================================
ACTION=""
TARGETS=()
NAME_FILTER=""
CONFIG_FILE=""
POSITIONAL_TARGET=""
REPOS_SPECIFIED=0

show_help() {
    cat << EOF
Skills 安装器 — 基于 npx skills 管理 AI Skills

用法:
  bash skill-install.sh <操作> [选项]
  操作:
    install   安装 skill 到目标目录（默认操作，可省略）
    update    更新管理源中已安装的 skill 并同步到目标目录
    remove    从管理源删除指定 skill 并同步删除所有目标
    list      列出管理源中已安装的 skill（含来源仓库）
    --help    显示此帮助

选项:
  -t <path>            目标目录（可多次使用，与 --file 互斥；update 时限定同步范围）
  -n <names>           指定 skill（逗号分隔，如 -n code-review,design-craft）
  --repo <owner/repo>  指定仓库（可多次使用；install/update 指定安装源，list 按来源过滤）
  --file <path>        从配置文件读取目标目录（与 -t 互斥）
  -h, --help           显示此帮助

默认配置文件（不指定 -t / --file 时读取）:
  $DEFAULT_TARGETS_FILE

管理目录:
  $MANAGE_DIR
  （npx skills 的安装/跟踪工作目录，update/remove/list 基于此持续管理）

示例:
  bash skill-install.sh -t ~/projects/app
  bash skill-install.sh install -n code-review,design-craft -t ~/projects/app
  bash skill-install.sh update -t ~/projects/app
  bash skill-install.sh update -n code-review --repo HACK-WU/skills
  bash skill-install.sh remove code-review
  bash skill-install.sh list
  bash skill-install.sh list --repo anthropics/skills

一键安装（默认安装 HACK-WU/skills）:
  curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.sh | \\
    bash -s -- -t ~/projects/my-app
EOF
    exit 0
}

REMOVE_PENDING=0
while [ $# -gt 0 ]; do
    arg="$1"
    case "$arg" in
        -h|--help) show_help ;;
        -t)
            shift
            [ $# -eq 0 ] && error "-t 需要参数"
            TARGETS+=("$1")
            ;;
        -n)
            shift
            [ $# -eq 0 ] && error "-n 需要参数"
            NAME_FILTER="${NAME_FILTER:+$NAME_FILTER,}$1"
            ;;
        --repo)
            shift
            [ $# -eq 0 ] && error "--repo 需要参数"
            REPOS+=("$1")
            REPOS_SPECIFIED=1
            ;;
        --repo=*) REPOS+=("${arg#*=}"); REPOS_SPECIFIED=1 ;;
        --file)
            shift
            [ $# -eq 0 ] && error "--file 需要参数"
            CONFIG_FILE="$1"
            ;;
        --file=*) CONFIG_FILE="${arg#*=}" ;;
        install|update|remove|list)
            [ -n "$ACTION" ] && error "已指定操作 $ACTION，不能同时指定 $arg"
            ACTION="$arg"
            if [ "$arg" = "remove" ]; then
                # remove 后第一个非选项参数是 skill 名称
                REMOVE_PENDING=1
            fi
            ;;
        -*) error "未知选项: $arg（使用 --help 查看帮助）" ;;
        *)
            if [ "$REMOVE_PENDING" = "1" ]; then
                NAME_FILTER="$arg"
                REMOVE_PENDING=0
            elif [ -z "$POSITIONAL_TARGET" ]; then
                POSITIONAL_TARGET="$arg"
            else
                error "无法识别的参数: $arg"
            fi
            ;;
    esac
    shift
done

# 默认操作：安装
[ -z "$ACTION" ] && ACTION="install"

# 默认安装源：未指定 --repo 时使用 HACK-WU/skills
[ ${#REPOS[@]} -eq 0 ] && REPOS=("HACK-WU/skills")

# ============================================================
# 前置检查
# ============================================================
if ! command -v npx &>/dev/null; then
    error "未检测到 npx（本安装器基于 'npx skills' 管理技能，需 Node.js >= 22）。\n\n  请先安装 Node.js，任选其一：\n    1. 官方安装包: https://nodejs.org/ （选择 LTS 版本）\n    2. Linux (apt):  sudo apt install nodejs npm\n    3. Linux/macOS (nvm):  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash\n    4. macOS (Homebrew):  brew install node\n\n  安装完成后重试本脚本。"
fi

# 检查 Node.js 版本（npx skills 依赖 Node >= 22）
if command -v node &>/dev/null; then
    NODE_MAJOR=$(node -v 2>/dev/null | sed 's/^v//;s/\..*$//')
    if [ -z "${NODE_MAJOR:-}" ] || [ "$NODE_MAJOR" -lt 22 ] 2>/dev/null; then
        error "Node.js 版本过低（当前 v${NODE_MAJOR:-未知}，需 >= 22）。\n\n  npx skills 依赖 Node >= 22，请升级 Node.js：\n    1. Linux/macOS (nvm):  nvm install 22 && nvm use 22\n    2. 官方安装包: https://nodejs.org/ （选择 LTS 版本）\n    3. macOS (Homebrew):  brew install node@22\n\n  升级后重试本脚本。"
    fi
fi

ensure_manage_dir() {
    mkdir -p "$MANAGE_DIR"
    [ -f "$TARGETS_FILE" ] || touch "$TARGETS_FILE"
}

# ============================================================
# 目标目录解析
# ============================================================
resolve_targets() {
    if [ ${#TARGETS[@]} -gt 0 ] && [ -n "$CONFIG_FILE" ]; then
        error "-t 和 --file 不能同时使用"
    fi

    if [ ${#TARGETS[@]} -gt 0 ]; then
        return 0
    fi

    if [ -n "$CONFIG_FILE" ]; then
        [ ! -f "$CONFIG_FILE" ] && error "配置文件不存在: $CONFIG_FILE"
        while IFS= read -r line; do
            line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
            [ -z "$line" ] && continue
            [[ "$line" =~ ^# ]] && continue
            TARGETS+=("$line")
        done < "$CONFIG_FILE"
        return 0
    fi

    if [ -n "$POSITIONAL_TARGET" ]; then
        TARGETS+=("$POSITIONAL_TARGET")
        return 0
    fi

    # 默认配置文件
    if [ -f "$DEFAULT_TARGETS_FILE" ]; then
        while IFS= read -r line; do
            line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
            [ -z "$line" ] && continue
            [[ "$line" =~ ^# ]] && continue
            TARGETS+=("$line")
        done < "$DEFAULT_TARGETS_FILE"
    fi
}

# 记录目标到 targets.list（去重，bash 3.2 兼容）
record_target() {
    local t="$1"
    [ -f "$TARGETS_FILE" ] || touch "$TARGETS_FILE"
    while IFS= read -r existing; do
        [ "$existing" = "$t" ] && return 0
    done < "$TARGETS_FILE"
    echo "$t" >> "$TARGETS_FILE"
}

# 输出所有已记录目标（每行一个）
get_recorded_targets() {
    [ ! -f "$TARGETS_FILE" ] && return 0
    local t
    while IFS= read -r t; do
        [ -z "$t" ] && continue
        echo "$t"
    done < "$TARGETS_FILE"
}

# ============================================================
# 同步：管理源 → 目标（增量同步，管理源是更新来源）
# 只覆盖更新同名文件，不删除目标中管理源没有的文件（保护本地手动修改）
# ============================================================
sync_to_target() {
    local target="$1"
    local dest
    local leaf="${target%/}"
    leaf="${leaf##*/}"
    if [ "$leaf" = "skills" ]; then
        dest="$target"
    else
        dest="$target/skills"
    fi

    mkdir -p "$dest"

    if [ ! -d "$MANAGE_SKILLS_DIR" ] || [ -z "$(ls -A "$MANAGE_SKILLS_DIR" 2>/dev/null)" ]; then
        # 管理源为空，跳过同步（不删除目标中已有文件）
        return 0
    fi

    # 优先 rsync（增量同步：覆盖更新，不删除多余文件）
    if command -v rsync &>/dev/null; then
        rsync -a "$MANAGE_SKILLS_DIR/" "$dest/"
    else
        # 降级 cp：直接覆盖复制（不先清空目标）
        cp -r "$MANAGE_SKILLS_DIR/"* "$dest/" 2>/dev/null || true
    fi
}

sync_all_recorded() {
    local count=0 total=0
    while IFS= read -r t; do
        [ -z "$t" ] && continue
        total=$((total + 1))
        if [ ! -d "$t" ]; then
            warn "目标目录不存在，跳过: $t"
            continue
        fi
        sync_to_target "$t"
        count=$((count + 1))
        echo "  [SYNC] $t"
    done < <(get_recorded_targets)
    info "已同步 $count/$total 个目标目录"
}

# ============================================================
# 安装
# ============================================================
do_install() {
    resolve_targets
    if [ ${#TARGETS[@]} -eq 0 ]; then
        error "未指定目标目录。使用 -t <path>、--file <path>，或在 $DEFAULT_TARGETS_FILE 配置。"
    fi

    ensure_manage_dir

    echo "🚀 skill-install.sh"
    echo "   管理目录: $MANAGE_DIR"
    echo "   安装源: ${REPOS[*]}"
    echo "   目标数量: ${#TARGETS[@]}"
    [ -n "$NAME_FILTER" ] && echo "   名称过滤: $NAME_FILTER"
    echo ""

    info "通过 npx skills 安装到管理源..."
    for repo in "${REPOS[@]}"; do
        info "  安装源: $repo"
        local npx_args=(add "$repo" --agent "$AGENT" -y)
        if [ -n "$NAME_FILTER" ]; then
            # 逗号分隔转空格分隔，作为 --skill 的多值
            local names="${NAME_FILTER//,/ }"
            npx_args+=(--skill $names)
        fi

        (cd "$MANAGE_DIR" && npx skills "${npx_args[@]}") </dev/null || error "npx skills add 失败: $repo"
    done

    echo ""
    info "同步到目标目录..."
    for t in "${TARGETS[@]}"; do
        mkdir -p "$t"
        sync_to_target "$t"
        record_target "$t"
        echo "  [SYNC] $t"
    done

    echo ""
    info "已安装并同步到 ${#TARGETS[@]} 个目标"
    info "管理命令: update（更新）/ remove <names>（删除）/ list（查看）"
}


# 从 lock 文件读取已安装 skill 的来源仓库（去重）
# 用 node 解析（node 是本安装器的既有依赖，无需 python3）
get_installed_repos() {
    [ ! -f "$LOCK_FILE" ] && return 0
    LOCK_FILE="$LOCK_FILE" node -e '
const fs=require("fs");
try{
  const d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,"utf8"));
  const r=new Set();
  for(const i of Object.values(d.skills||{})){ if(i.source) r.add(i.source); }
  console.log([...r].sort().join("\n"));
}catch(e){}
'
}

# ============================================================
# 更新：重新拉取已安装 skill 的最新版本并同步到目标
# ============================================================
do_update() {
    ensure_manage_dir
    [ ! -f "$LOCK_FILE" ] && error "管理源为空，无可更新项。请先 install。"
    if [ ! -s "$LOCK_FILE" ]; then
        error "管理源为空，无可更新项。请先 install。"
    fi

    # 更新范围：--repo 指定则用指定仓库，否则取管理源中已安装的所有仓库
    local repos=()
    if [ "$REPOS_SPECIFIED" = "1" ]; then
        repos=("${REPOS[@]}")
    else
        while IFS= read -r r; do
            [ -z "$r" ] && continue
            repos+=("$r")
        done < <(get_installed_repos)
        if [ ${#repos[@]} -eq 0 ]; then
            error "管理源中未找到已安装的仓库来源，无法更新。"
        fi
    fi

    echo "🚀 skill-install.sh update"
    echo "   管理目录: $MANAGE_DIR"
    echo "   更新仓库: ${repos[*]}"
    [ -n "$NAME_FILTER" ] && echo "   名称过滤: $NAME_FILTER"
    echo ""

    # 生成"按仓库分组"的 skill 清单：无 -n 时取管理源中已安装的全部 skill，
    # 有 -n 时只取指定的 skill；随后对每个仓库用 --skill 精确更新，
    # 避免 update 误把仓库全部 skill 全量重装进管理源。
    local wanted=""
    [ -n "$NAME_FILTER" ] && wanted="${NAME_FILTER//,/ }"
    local repo_scope="${repos[*]}"

    info "通过 npx skills 重新拉取最新版本..."
    local updated_any=0
    while IFS=$'\t' read -r repo skill_names; do
        [ -z "$repo" ] && continue
        info "  更新源: $repo → $skill_names"
        local npx_args=(add "$repo" --agent "$AGENT" -y)
        npx_args+=(--skill $skill_names)
        (cd "$MANAGE_DIR" && npx skills "${npx_args[@]}") </dev/null || error "npx skills add 失败: $repo"
        updated_any=1
    done < <(LOCK_FILE="$LOCK_FILE" NAME_WANTED="$wanted" REPO_SCOPE="$repo_scope" node -e '
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
  console.log(s+"\t"+out[s].sort().join(" "));
}
')
    if [ "$updated_any" = "0" ]; then
        [ -n "$NAME_FILTER" ] && warn "未在管理源中找到匹配的 skill：$NAME_FILTER（可能未安装）"
        warn "管理源中没有可更新的 skill。"
    fi

    echo ""
    info "同步到目标目录..."
    if [ ${#TARGETS[@]} -gt 0 ]; then
        # -t 指定了目标，只同步这些
        for t in "${TARGETS[@]}"; do
            mkdir -p "$t"
            sync_to_target "$t"
            record_target "$t"
            echo "  [SYNC] $t"
        done
    else
        # 未指定 -t，同步所有已记录目标
        sync_all_recorded
    fi

    echo ""
    info "更新完成"
}


# ============================================================
# 删除
# ============================================================
do_remove() {
    ensure_manage_dir
    [ ! -f "$LOCK_FILE" ] && error "管理源为空，无可删除项"
    [ -z "$NAME_FILTER" ] && error "remove 需要指定 skill 名称"

    info "从管理源删除: $NAME_FILTER"
    # 逗号分隔转空格分隔
    local names="${NAME_FILTER//,/ }"
    (cd "$MANAGE_DIR" && npx skills remove $names -y) || error "npx skills remove 失败"

    echo ""
    info "同步删除到所有已记录目标..."
    # 因 sync_to_target 为增量同步（不删多余文件），此处显式删除目标中对应的 skill 目录
    while IFS= read -r t; do
        [ -z "$t" ] && continue
        [ ! -d "$t" ] && continue
        local leaf="${t%/}"
        leaf="${leaf##*/}"
        local dest
        if [ "$leaf" = "skills" ]; then
            dest="$t"
        else
            dest="$t/skills"
        fi
        for name in $names; do
            rm -rf "${dest:?}/$name" 2>/dev/null || true
        done
    done < <(get_recorded_targets)
    sync_all_recorded
    echo ""
    info "删除完成"
}

# ============================================================
# 列表
# ============================================================
do_list() {
    ensure_manage_dir
    if [ ! -f "$LOCK_FILE" ]; then
        warn "管理源为空，尚未安装任何 skill"
        warn "使用 install 安装"
        exit 0
    fi

    # 传递 --repo 过滤（仅当用户显式指定 --repo 时）
    local repo_filter=""
    if [ "$REPOS_SPECIFIED" = "1" ]; then
        repo_filter="${REPOS[*]}"
    fi

    LOCK_FILE="$LOCK_FILE" REPO_FILTER="$repo_filter" node -e '
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
  console.log(`  ← ${src}  (${items[src].length} 个)`);
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
'

    echo ""
    if [ -f "$TARGETS_FILE" ]; then
        local tcount
        tcount=$(grep -c . "$TARGETS_FILE" 2>/dev/null || echo 0)
        info "已记录 $tcount 个目标目录（remove 时自动同步）"
    fi
}

# ============================================================
# 主流程
# ============================================================
case "$ACTION" in
    install) do_install ;;
    update)  do_update ;;
    remove)  do_remove ;;
    list)    do_list ;;
    *)       error "未知操作: $ACTION" ;;
esac

echo ""
echo "✅ 完成"