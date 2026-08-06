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
#   bash skill-install.sh -t /path/to/target
#   bash skill-install.sh -n code-review,design-craft -t /path/to/target
#   bash skill-install.sh -t /path/a -t /path/b
#   bash skill-install.sh --update          # 更新管理源 + 同步所有已记录目标
#   bash skill-install.sh --remove names    # 删除 skill + 同步
#   bash skill-install.sh --list            # 列出已装 skill
#   bash skill-install.sh --help
#
# 兼容旧用法:
#   bash skill-install.sh /path/to/target
# ============================================================
set -euo pipefail

REPO="HACK-WU/skills"
AGENT="openclaw"
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

show_help() {
    cat << EOF
Skills 安装器 — 基于 npx skills 管理 AI Skills

用法:
  bash skill-install.sh [-t <path>...] [-n <names>] [--file <path>]
  bash skill-install.sh --update
  bash skill-install.sh --remove <names>
  bash skill-install.sh --list
  bash skill-install.sh --help

操作:
  （默认）             安装 skill 到目标目录
  --update             更新管理源并同步到所有已记录的目标
  --remove <names>     从管理源删除指定 skill 并同步（逗号分隔）
  --list               列出管理源中已安装的 skill
  --help, -h           显示此帮助

安装选项:
  -t <path>            目标目录（可多次使用，与 --file 互斥）
  -n <names>           只安装指定 skill（逗号分隔，如 -n code-review,design-craft）
  --file <path>        从配置文件读取目标目录（与 -t 互斥）

默认配置文件（不指定 -t / --file 时读取）:
  $DEFAULT_TARGETS_FILE

管理目录:
  $MANAGE_DIR
  （npx skills 的安装/跟踪工作目录，update/remove/list 基于此持续管理）

示例:
  bash skill-install.sh -t ~/projects/app
  bash skill-install.sh -n code-review,design-craft -t ~/projects/app
  bash skill-install.sh -t ~/projects/a -t ~/projects/b
  bash skill-install.sh --update
  bash skill-install.sh --remove code-review
  bash skill-install.sh --list

一键安装:
  curl -fsSL https://raw.githubusercontent.com/${REPO}/master/scripts/skill-install.sh | \\
    bash -s -- -t ~/projects/my-app
EOF
    exit 0
}

while [ $# -gt 0 ]; do
    arg="$1"
    case "$arg" in
        --help|-h) show_help ;;
        --update)  ACTION="update" ;;
        --list)    ACTION="list" ;;
        --remove)
            ACTION="remove"
            shift
            [ $# -eq 0 ] && error "--remove 需要参数（skill 名称）"
            NAME_FILTER="$1"
            ;;
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
        --file)
            shift
            [ $# -eq 0 ] && error "--file 需要参数"
            CONFIG_FILE="$1"
            ;;
        --file=*) CONFIG_FILE="${arg#*=}" ;;
        -*) error "未知选项: $arg（使用 --help 查看帮助）" ;;
        *) POSITIONAL_TARGET="$arg" ;;
    esac
    shift
done

# 默认操作：安装
[ -z "$ACTION" ] && ACTION="install"

# ============================================================
# 前置检查
# ============================================================
if ! command -v npx &>/dev/null; then
    error "未检测到 npx（本安装器基于 'npx skills' 管理技能，需 Node.js >= 18）。\n\n  请先安装 Node.js，任选其一：\n    1. 官方安装包: https://nodejs.org/ （选择 LTS 版本）\n    2. Linux (apt):  sudo apt install nodejs npm\n    3. Linux/macOS (nvm):  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash\n    4. macOS (Homebrew):  brew install node\n\n  安装完成后重试本脚本。"
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
# 同步：管理源 → 目标（镜像同步，管理源是唯一真相）
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
        # 管理源为空，清空目标
        rm -rf "${dest:?}/"* 2>/dev/null || true
        return 0
    fi

    # 优先 rsync（镜像同步，删除目标中多余文件）
    if command -v rsync &>/dev/null; then
        rsync -a --delete "$MANAGE_SKILLS_DIR/" "$dest/"
    else
        # 降级 cp：先清空目标再复制
        rm -rf "${dest:?}/"* 2>/dev/null || true
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
    echo "   目标数量: ${#TARGETS[@]}"
    [ -n "$NAME_FILTER" ] && echo "   名称过滤: $NAME_FILTER"
    echo ""

    info "通过 npx skills 安装到管理源..."
    local npx_args=(add "$REPO" --agent "$AGENT" -y)
    if [ -n "$NAME_FILTER" ]; then
        # 逗号分隔转空格分隔，作为 --skill 的多值
        local names="${NAME_FILTER//,/ }"
        npx_args+=(--skill $names)
    fi

    (cd "$MANAGE_DIR" && npx skills "${npx_args[@]}") || error "npx skills add 失败"

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
    info "管理命令: --update（更新）/ --remove <names>（删除）/ --list（查看）"
}

# ============================================================
# 更新
# ============================================================
do_update() {
    ensure_manage_dir
    [ ! -f "$LOCK_FILE" ] && error "管理源为空，请先安装技能"

    info "更新管理源..."
    (cd "$MANAGE_DIR" && npx skills update -y) || error "npx skills update 失败"

    echo ""
    info "同步到所有已记录目标..."
    sync_all_recorded
    echo ""
    info "更新完成"
}

# ============================================================
# 删除
# ============================================================
do_remove() {
    ensure_manage_dir
    [ ! -f "$LOCK_FILE" ] && error "管理源为空，无可删除项"
    [ -z "$NAME_FILTER" ] && error "--remove 需要指定 skill 名称"

    info "从管理源删除: $NAME_FILTER"
    # 逗号分隔转空格分隔
    local names="${NAME_FILTER//,/ }"
    (cd "$MANAGE_DIR" && npx skills remove $names -y) || error "npx skills remove 失败"

    echo ""
    info "同步删除到所有已记录目标..."
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
        warn "使用 -t <path> 安装"
        exit 0
    fi

    info "管理源已安装的 skill:"
    echo ""

    # 优先 npx skills list
    if (cd "$MANAGE_DIR" && npx skills list 2>/dev/null); then
        :
    else
        # 降级：从 lock 文件解析
        warn "npx skills list 不可用，从 lock 文件读取..."
        local py_cmd
        py_cmd=$(command -v python3 || command -v python || true)
        if [ -n "$py_cmd" ]; then
            LOCK_FILE="$LOCK_FILE" "$py_cmd" -c "
import json, os
with open(os.environ['LOCK_FILE']) as f:
    data = json.load(f)
skills = data.get('skills', {})
for name in sorted(skills.keys()):
    print(f'  {name}')
print(f\"\n  共 {len(skills)} 个 skill\")
"
        else
            echo "  （无法解析，lock 文件: $LOCK_FILE）"
        fi
    fi

    echo ""
    if [ -f "$TARGETS_FILE" ]; then
        local tcount
        tcount=$(grep -c . "$TARGETS_FILE" 2>/dev/null || echo 0)
        info "已记录 $tcount 个目标目录（--update / --remove 时自动同步）"
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
