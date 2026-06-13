#!/usr/bin/env bash
# ============================================================
# Skills 安装器 — 从 GitHub 下载脚本或 Skill 定义
#
# 用法:
#   curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.sh | bash -s -- /path/to/target --scripts
#   curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.sh | bash -s -- /path/to/target --skills
#
#   或:
#   curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.sh -o skill-install.sh
#   bash skill-install.sh /path/to/target --scripts
# ============================================================
set -euo pipefail

GITHUB_REPO="HACK-WU/skills"
GITHUB_BRANCH="master"
RAW_BASE="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}"

TARGET_DIR=""
MODE=""

for arg in "$@"; do
    case "$arg" in
        --scripts) MODE="scripts" ;;
        --skills)  MODE="skills" ;;
        --rules)   MODE="rules" ;;
        -*)        echo "未知选项: $arg"; exit 1 ;;
        *)         TARGET_DIR="$arg" ;;
    esac
done

if [ -z "$TARGET_DIR" ] || [ -z "$MODE" ]; then
    echo "用法: bash skill-install.sh <目标项目路径> --scripts|--skills|--rules"
    echo ""
    echo "  目标项目路径    安装到的项目根目录"
    echo "  --scripts       安装 CRUD 管理脚本（scripts/）"
    echo "  --skills        安装 AI Skill 定义（skills/）"
    echo "  --rules         安装 AI 规则（rules/）"
    echo ""
    echo "示例:"
    echo "  bash skill-install.sh ~/projects/my-app --scripts"
    echo "  bash skill-install.sh ~/projects/my-app --skills"
    echo "  bash skill-install.sh ~/projects/my-app --rules"
    echo ""
    echo "一键安装:"
    echo "  curl -fsSL ${RAW_BASE}/scripts/skill-install.sh | bash -s -- ~/projects/my-app --scripts"
    exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "创建目标目录: $TARGET_DIR"
    mkdir -p "$TARGET_DIR"
fi

download() {
    local url="$1" dest="$2"
    mkdir -p "$(dirname "$dest")"
    curl -fsSL "$url" -o "$dest"
}

# ============================================================
# 计算安装目标路径：如果传入路径已以子目录名结尾，则直接使用，避免嵌套
# ============================================================
NORMALIZED_DIR="${TARGET_DIR%/}"

if [ "$MODE" = "scripts" ]; then
    if [ "${NORMALIZED_DIR##*/}" = "scripts" ]; then
        DEST="$NORMALIZED_DIR"
    else
        DEST="$NORMALIZED_DIR/scripts"
    fi
    mkdir -p "$DEST"

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

    echo "📦 安装 CRUD 脚本 → ${DEST}"
    echo ""

    count=0
    for f in "${FILES[@]}"; do
        url="${RAW_BASE}/scripts/requirement-mgr/${f}"
        dest="${DEST}/${f}"
        if download "$url" "$dest"; then
            echo "  [OK] ${f}"
            count=$((count + 1))
        else
            echo "  [FAIL] ${f}"
        fi
    done
    echo ""
    echo "已安装: ${count}/${#FILES[@]}"
    echo ""
    echo "使用:"
    echo "  uv run python scripts/list-requirements.py"
    echo "  uv run python scripts/create-requirement.py --feature '名称' --tags feat"
fi

# ============================================================
# --skills: AI Skill 定义
# ============================================================
if [ "$MODE" = "skills" ]; then
    if [ "${NORMALIZED_DIR##*/}" = "skills" ]; then
        DEST="$NORMALIZED_DIR"
    else
        DEST="$NORMALIZED_DIR/skills"
    fi
    mkdir -p "$DEST"

    # 注意: skill-updater 是内部维护工具，不包含在用户安装列表中
    FILES=(
        "auto-review/SKILL.md"
        "challenger/SKILL.md"
        "challenger/strategies/bug-fix.md"
        "challenger/strategies/feature.md"
        "challenger/strategies/optimization.md"
        "challenger/templates/report.md"
        "code-review/SKILL.md"
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

    echo "🧠 安装 AI Skills → ${DEST}"
    echo ""

    count=0
    for f in "${FILES[@]}"; do
        url="${RAW_BASE}/skills/${f}"
        dest="${DEST}/${f}"
        if download "$url" "$dest"; then
            echo "  [OK] ${f}"
            count=$((count + 1))
        else
            echo "  [FAIL] ${f}"
        fi
    done
    echo ""
    echo "已安装: ${count}/${#FILES[@]} 个 skill 文件"
    echo "  共 $(echo "${FILES[@]}" | wc -w) 个 skill"
fi

# ============================================================
# --rules: AI 规则
# ============================================================
if [ "$MODE" = "rules" ]; then
    if [ "${NORMALIZED_DIR##*/}" = "rules" ]; then
        DEST="$NORMALIZED_DIR"
    else
        DEST="$NORMALIZED_DIR/rules"
    fi
    mkdir -p "$DEST"

    FILES=(
        "writing-pipeline.md"
    )

    echo "📏 安装 AI Rules → ${DEST}"
    echo ""

    count=0
    for f in "${FILES[@]}"; do
        url="${RAW_BASE}/rules/${f}"
        dest="${DEST}/${f}"
        if download "$url" "$dest"; then
            echo "  [OK] ${f}"
            count=$((count + 1))
        else
            echo "  [FAIL] ${f}"
        fi
    done
    echo ""
    echo "已安装: ${count}/${#FILES[@]} 个规则文件"
fi

echo ""
echo "完成: ${TARGET_DIR}"
