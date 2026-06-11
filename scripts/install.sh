#!/usr/bin/env bash
# ============================================================
# 需求管理脚本 — 一键安装器（从 GitHub 下载）
#
# 用法:
#   curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/install.sh | bash -s -- /path/to/target
#
#   或:
#   curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/install.sh -o install.sh
#   bash install.sh /path/to/target
# ============================================================
set -euo pipefail

GITHUB_REPO="HACK-WU/skills"
GITHUB_BRANCH="master"
BASE_URL="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}/scripts"

TARGET_DIR="${1:-}"

if [ -z "$TARGET_DIR" ]; then
    echo "用法: bash install.sh <目标项目路径>"
    echo ""
    echo "示例:"
    echo "  bash install.sh ~/projects/my-app"
    echo ""
    echo "一键安装:"
    echo "  curl -fsSL ${BASE_URL}/install.sh | bash -s -- ~/projects/my-app"
    exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "创建目标目录: $TARGET_DIR"
    mkdir -p "$TARGET_DIR"
fi

DEST="$TARGET_DIR/scripts"
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

echo "正在从 GitHub 下载需求管理脚本..."
echo "  仓库: ${GITHUB_REPO}"
echo "  目标: ${DEST}"
echo ""

count=0
for f in "${FILES[@]}"; do
    url="${BASE_URL}/${f}"
    if curl -fsSL "$url" -o "${DEST}/${f}"; then
        echo "  [OK] ${f}"
        count=$((count + 1))
    else
        echo "  [FAIL] ${f}"
    fi
done

echo ""
echo "已完成: ${count}/${#FILES[@]} 个脚本安装到 ${DEST}"
echo ""
echo "使用方式:"
echo "  uv run python scripts/list-requirements.py"
echo "  uv run python scripts/create-requirement.py --feature '功能名称' --tags feat"
