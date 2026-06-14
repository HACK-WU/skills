#!/usr/bin/env bash
# ============================================================
# Skills 安装器 — 从 GitHub 下载 Scripts / Skills / Rules
#
# 用法:
#   bash skill-install.sh --skills -t /path/to/target -t /path/to/target2
#   bash skill-install.sh --rules --file /path/to/targets.txt
#   bash skill-install.sh /path/to/target --scripts   # 旧用法，兼容
#
#   或:
#   curl -fsSL ... -o skill-install.sh
#   bash skill-install.sh --skills -t /path/to/target
# ============================================================
set -euo pipefail

GITHUB_REPO="HACK-WU/skills"
GITHUB_BRANCH="master"
RAW_BASE="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}"

DEFAULT_TARGETS_FILE="$HOME/.skill-targets"
POSITIONAL_TARGET=""
TARGETS=()
CONFIG_FILE=""
MODES=()

# ============================================================
# 参数解析
# ============================================================
while [ $# -gt 0 ]; do
    arg="$1"
    case "$arg" in
        --scripts) MODES+=("scripts") ;;
        --skills)  MODES+=("skills") ;;
        --rules)   MODES+=("rules") ;;
        -t)
            shift
            [ $# -eq 0 ] && { echo "错误：-t 需要参数"; exit 1; }
            TARGETS+=("$1")
            ;;
        --file)
            shift
            [ $# -eq 0 ] && { echo "错误：--file 需要参数"; exit 1; }
            CONFIG_FILE="$1"
            ;;
        --file=*) CONFIG_FILE="${arg#*=}" ;;
        -*)
            echo "未知选项: $arg"
            exit 1
            ;;
        *)
            POSITIONAL_TARGET="$arg"
            ;;
    esac
    shift
done

# 互斥检查
if [ ${#TARGETS[@]} -gt 0 ] && [ -n "$CONFIG_FILE" ]; then
    echo "错误：-t 和 --file 不能同时使用"
    exit 1
fi

# ============================================================
# 解析目标目录
# ============================================================
if [ ${#TARGETS[@]} -gt 0 ]; then
    TARGET_DIRS=("${TARGETS[@]}")
    SOURCE_DESC="命令行参数 (-t × ${#TARGET_DIRS[@]})"
elif [ -n "$CONFIG_FILE" ]; then
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "错误：配置文件不存在: $CONFIG_FILE"
        exit 1
    fi
    TARGET_DIRS=()
    while IFS= read -r line; do
        line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -z "$line" ] && continue
        [[ "$line" =~ ^# ]] && continue
        TARGET_DIRS+=("$line")
    done < "$CONFIG_FILE"
    if [ ${#TARGET_DIRS[@]} -eq 0 ]; then
        echo "错误：配置文件为空: $CONFIG_FILE"
        exit 1
    fi
    SOURCE_DESC="配置文件: $CONFIG_FILE"
elif [ -f "$DEFAULT_TARGETS_FILE" ]; then
    TARGET_DIRS=()
    while IFS= read -r line; do
        line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -z "$line" ] && continue
        [[ "$line" =~ ^# ]] && continue
        TARGET_DIRS+=("$line")
    done < "$DEFAULT_TARGETS_FILE"
    SOURCE_DESC="默认配置: $DEFAULT_TARGETS_FILE"
elif [ -n "$POSITIONAL_TARGET" ]; then
    TARGET_DIRS=("$POSITIONAL_TARGET")
    SOURCE_DESC="位置参数"
else
    TARGET_DIRS=()
fi

if [ ${#TARGET_DIRS[@]} -eq 0 ] || [ ${#MODES[@]} -eq 0 ]; then
    echo "用法: bash skill-install.sh [--scripts|--skills|--rules] [-t <path>... | --file <path>]"
    echo ""
    echo "  --scripts       安装 CRUD 管理脚本（scripts/）"
    echo "  --skills        安装 AI Skill 定义（skills/）"
    echo "  --rules         安装 AI 规则（rules/）"
    echo "  -t <path>       指定目标目录（可多次使用，与 --file 互斥）"
    echo "  --file <path>   指定目标目录配置文件（与 -t 互斥）"
    echo ""
    echo "兼容旧用法:"
    echo "  bash skill-install.sh <目标路径> --scripts"
    echo ""
    echo "示例:"
    echo "  bash skill-install.sh --skills -t ~/projects/app -t ~/projects/api"
    echo "  bash skill-install.sh --rules --file ~/my-targets.txt"
    echo "  bash skill-install.sh --scripts --skills --rules -t ~/projects/my-app"
    echo ""
    echo "一键安装:"
    echo "  curl -fsSL ${RAW_BASE}/scripts/skill-install.sh | \\"
    echo "    bash -s -- --skills --rules -t ~/projects/my-app"
    exit 1
fi

# ============================================================
# 通用函数
# ============================================================
download() {
    local url="$1" dest="$2"
    mkdir -p "$(dirname "$dest")"
    if curl -fsSL "$url" -o "$dest" 2>/dev/null; then
        return 0
    else
        rm -f "$dest" 2>/dev/null
        return 1
    fi
}

# 递归发现 GitHub 仓库目录下的文件列表
# 用法: discover_files_recursive <api_path> <prefix>
# 输出: 每行一个相对路径（如 challenger/strategies/bug-fix.md）
discover_files_recursive() {
    local path="$1" prefix="$2"
    local items
    items=$(gh api "repos/${GITHUB_REPO}/contents/${path}" \
        --jq '.[] | "\(.type) \(.name)"' 2>/dev/null) || return 1

    while IFS= read -r item; do
        [ -z "$item" ] && continue
        local type="${item%% *}"
        local name="${item#* }"
        case "$type" in
            dir)  discover_files_recursive "${path}/${name}" "${prefix}${name}/" ;;
            file) echo "${prefix}${name}" ;;
        esac
    done <<< "$items"
}

# 从配置文件行列表读取目标目录（去空去注释）
read_targets_from_file() {
    local file="$1"
    while IFS= read -r line; do
        line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -z "$line" ] && continue
        [[ "$line" =~ ^# ]] && continue
        echo "$line"
    done < "$file"
}

# ============================================================
# --scripts: CRUD 管理脚本
# ============================================================
install_scripts() {
    if [ "${NORMALIZED_DIR##*/}" = "scripts" ]; then
        DEST="$NORMALIZED_DIR"
    else
        DEST="$NORMALIZED_DIR/scripts"
    fi
    mkdir -p "$DEST"

    # 动态发现：优先 gh，降级为硬编码
    local FILES=()
    if command -v gh &> /dev/null; then
        while IFS= read -r name; do
            [ -z "$name" ] && continue
            FILES+=("$name")
        done < <(gh api "repos/${GITHUB_REPO}/contents/scripts/requirement-mgr" \
            --jq '.[] | select(.name | endswith(".py")) | .name' 2>/dev/null)
    fi

    if [ ${#FILES[@]} -eq 0 ]; then
        echo "⚠️  gh 不可用，使用静态脚本列表（可能不是最新）" >&2
        FILES=(
            "config_loader.py"
            "create-requirement.py"
            "delete-requirement.py"
            "file_lock.py"
            "id_generator.py"
            "list-requirements.py"
            "meta_store.py"
            "requirement_utils.py"
            "update-requirement.py"
        )
    fi

    echo "📦 安装 CRUD 脚本 → ${DEST}"
    echo ""

    local count=0 total=0
    for f in "${FILES[@]}"; do
        total=$((total + 1))
        local url="${RAW_BASE}/scripts/requirement-mgr/${f}"
        local dest="${DEST}/${f}"
        if download "$url" "$dest"; then
            echo "  [OK] ${f}"
            count=$((count + 1))
        else
            echo "  [FAIL] ${f}"
        fi
    done
    echo ""
    echo "已安装: ${count}/${total}"

    if [ "$count" -gt 0 ]; then
        echo ""
        echo "使用:"
        echo "  uv run python scripts/list-requirements.py"
        echo "  uv run python scripts/create-requirement.py --feature '名称' --tags feat"
    fi
}

# ============================================================
# --skills: AI Skill 定义
# ============================================================
install_skills() {
    if [ "${NORMALIZED_DIR##*/}" = "skills" ]; then
        DEST="$NORMALIZED_DIR"
    else
        DEST="$NORMALIZED_DIR/skills"
    fi
    mkdir -p "$DEST"

    # 动态发现：优先 gh 递归获取，降级为硬编码
    local FILES=()
    if command -v gh &> /dev/null; then
        # 先列出 skill 目录
        local SKILL_DIRS
        SKILL_DIRS=$(gh api "repos/${GITHUB_REPO}/contents/skills" \
            --jq '.[] | select(.type=="dir") | .name' 2>/dev/null)

        if [ -n "$SKILL_DIRS" ]; then
            while IFS= read -r skill_name; do
                [ -z "$skill_name" ] && continue
                # 跳过内部维护工具
                [ "$skill_name" = "skill-updater" ] && continue
                # 递归发现该 skill 下的所有文件
                while IFS= read -r rel; do
                    [ -z "$rel" ] && continue
                    FILES+=("${skill_name}/${rel}")
                done < <(discover_files_recursive "skills/${skill_name}" "")
            done <<< "$SKILL_DIRS"
        fi
    fi

    if [ ${#FILES[@]} -eq 0 ]; then
        echo "⚠️  gh 不可用，使用静态 skill 列表（可能不是最新）" >&2
        FILES=(
            "auto-review/SKILL.md"
            "challenger/SKILL.md"
            "challenger/strategies/bug-fix.md"
            "challenger/strategies/feature.md"
            "challenger/strategies/optimization.md"
            "challenger/templates/report.md"
            "code-review/SKILL.md"
            "content-simplifier/SKILL.md"
            "create-rules/SKILL.md"
            "create-skill/SKILL.md"
            "data-flow-model/SKILL.md"
            "demo-verify/SKILL.md"
            "design-craft/SKILL.md"
            "design-craft/SUB_TEMPLATE.md"
            "design-craft/reference.md"
            "design-review/SKILL.md"
            "design-review/reference.md"
            "document-writer/SKILL.md"
            "document-writer/references/quality-rules.md"
            "document-writer/references/strategies.md"
            "document-writer/references/examples/example-1-library.md"
            "document-writer/references/examples/example-2-cli.md"
            "document-writer/references/examples/README.md"
            "expert-panel/SKILL.md"
            "expert-panel/references/review-panel.md"
            "implementation-report/SKILL.md"
            "interaction-design/SKILL.md"
            "memory-creator/SKILL.md"
            "migrate-to-codehub/SKILL.md"
            "requirement-doc-store/SKILL.md"
            "requirement-mining/SKILL.md"
            "requirement-mining/references/example.md"
            "test-planner/SKILL.md"
            "test-planner/references/test-strategies.md"
            "test-planner/references/examples/example-1-registration.md"
            "work-breakdown/SKILL.md"
        )
    fi

    echo "🧠 安装 AI Skills → ${DEST}"
    echo ""

    local count=0 total=0
    for f in "${FILES[@]}"; do
        total=$((total + 1))
        local url="${RAW_BASE}/skills/${f}"
        local dest="${DEST}/${f}"
        if download "$url" "$dest"; then
            echo "  [OK] ${f}"
            count=$((count + 1))
        else
            echo "  [FAIL] ${f}"
        fi
    done
    echo ""
    echo "已安装: ${count}/${total} 个 skill 文件"
}

# ============================================================
# --rules: AI 规则
# ============================================================
install_rules() {
    if [ "${NORMALIZED_DIR##*/}" = "rules" ]; then
        DEST="$NORMALIZED_DIR"
    else
        DEST="$NORMALIZED_DIR/rules"
    fi
    mkdir -p "$DEST"

    # 动态发现：优先 gh，降级为硬编码
    local FILES=()
    if command -v gh &> /dev/null; then
        while IFS= read -r name; do
            [ -z "$name" ] && continue
            FILES+=("$name")
        done < <(gh api "repos/${GITHUB_REPO}/contents/rules" \
            --jq '.[] | select(.name | endswith(".md")) | .name' 2>/dev/null)
    fi

    if [ ${#FILES[@]} -eq 0 ]; then
        echo "⚠️  gh 不可用，使用静态 rule 列表（可能不是最新）" >&2
        FILES=(
            "gitnexus-mcp-rules.md"
            "writing-pipeline.md"
        )
    fi

    echo "📏 安装 AI Rules → ${DEST}"
    echo ""

    local count=0 total=0
    for f in "${FILES[@]}"; do
        total=$((total + 1))
        local url="${RAW_BASE}/rules/${f}"
        local dest="${DEST}/${f}"
        if download "$url" "$dest"; then
            echo "  [OK] ${f}"
            count=$((count + 1))
        else
            echo "  [FAIL] ${f}"
        fi
    done
    echo ""
    echo "已安装: ${count}/${total} 个规则文件"
}

# ============================================================
# 按模式执行（支持多目标目录）
# ============================================================
echo "🚀 skill-install.sh"
echo "   目标来源: ${SOURCE_DESC}"
echo "   目标数量: ${#TARGET_DIRS[@]}"
echo "   安装模式: ${MODES[*]}"
echo ""

for i in "${!TARGET_DIRS[@]}"; do
    TARGET_DIR="${TARGET_DIRS[$i]}"
    LABEL="[$(($i + 1))/${#TARGET_DIRS[@]}]"

    if [ ! -d "$TARGET_DIR" ]; then
        echo "${LABEL} 创建目标目录: $TARGET_DIR"
        mkdir -p "$TARGET_DIR"
    fi

    NORMALIZED_DIR="${TARGET_DIR%/}"

    for mode in "${MODES[@]}"; do
        case "$mode" in
            scripts) install_scripts ;;
            skills)  install_skills  ;;
            rules)   install_rules  ;;
        esac
        echo ""
    done
done

echo "✅ 完成"
