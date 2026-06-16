#!/usr/bin/env bash
# ============================================================
# requirement-mgr 自动安装/更新脚本
# 从 GitHub Release 获取最新版本并通过 uv tool install 安装
#
# 用法:
#   bash install-latest.sh              # 自动安装最新版本
#   bash install-latest.sh --pre        # 包含预发布版本
#   bash install-latest.sh --help       # 查看帮助
# ============================================================
set -euo pipefail

REPO="HACK-WU/skills"
TAG_PREFIX="requirement-mgr-v"
PKG_CMD="req"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

INCLUDE_PRE=false
INSTALL_CMD="uv tool install --force"

# ============================================================
# 参数解析
# ============================================================
case "${1:-}" in
    --help|-h)
        cat << 'EOF'
用法: install-latest.sh [选项]

从 GitHub Release 自动获取 requirement-mgr 最新版本并安装。

选项:
  --pre         包含预发布版本（默认只安装正式版）
  --help        显示此帮助信息

示例:
  bash install-latest.sh            # 安装最新正式版
  bash install-latest.sh --pre      # 包含预发布版

EOF
        exit 0
        ;;
    --pre)   INCLUDE_PRE=true ;;
    "")      ;;
    *)       error "未知选项: $1，使用 --help 查看帮助" ;;
esac

# ============================================================
# 前置检查
# ============================================================
if ! command -v uv &>/dev/null; then
    error "uv 未安装。请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

if ! command -v curl &>/dev/null; then
    error "curl 未安装"
fi

# ============================================================
# 获取最新版本
# ============================================================
get_latest_release() {
    info "正在查询最新版本..."

    local api_url="https://api.github.com/repos/${REPO}/releases"
    local response http_code body

    response=$(curl -sL -w "\n%{http_code}" \
        -H "Accept: application/vnd.github.v3+json" \
        ${GITHUB_TOKEN:+-H "Authorization: token ${GITHUB_TOKEN}"} \
        "$api_url?per_page=30")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" != "200" ]; then
        # 降级：gh CLI
        if command -v gh &>/dev/null; then
            info "GitHub API 失败，尝试 gh CLI..."
            get_latest_via_gh
            return $?
        fi
        if [ "$http_code" = "403" ]; then
            error "GitHub API 速率限制 (HTTP 403)。\n  解决方案（任选其一）：\n    1. 安装 gh CLI: https://cli.github.com/\n    2. 设置 GITHUB_TOKEN 环境变量后重试\n    3. 使用指定版本安装: uv tool install https://github.com/${REPO}/releases/download/<TAG>/<WHEEL>"
        fi
        error "GitHub API 请求失败 (HTTP $http_code)"
    fi

    # 筛选 requirement-mgr 的 release
    local tag_name download_url

    if command -v python3 &>/dev/null || command -v python &>/dev/null; then
        local py_cmd
        py_cmd=$(command -v python3 || command -v python)

        read -r tag_name download_url < <(INCLUDE_PRE="$INCLUDE_PRE" "$py_cmd" -c "
import sys, json, os
data = json.loads(sys.stdin.read())
include_pre = os.environ.get('INCLUDE_PRE', 'false') == 'true'
for r in data:
    tag = r.get('tag_name', '')
    if not tag.startswith('${TAG_PREFIX}'):
        continue
    if not include_pre and r.get('prerelease', False):
        continue
    for a in r.get('assets', []):
        if a['name'].endswith('.whl'):
            print(tag, a['browser_download_url'])
            sys.exit(0)
sys.exit(1)
" <<< "$body" 2>/dev/null) || true
    fi

    # 降级：纯 grep/sed（无 python 时）
    if [ -z "${tag_name:-}" ]; then
        warn "Python 不可用，使用 grep 降级解析..."
        get_latest_via_grep "$body"
    fi

    if [ -n "${tag_name:-}" ] && [ -n "${download_url:-}" ]; then
        LATEST_TAG="$tag_name"
        LATEST_VERSION="${tag_name#${TAG_PREFIX}}"
        DOWNLOAD_URL="$download_url"
        info "找到最新版本: ${LATEST_VERSION} (${LATEST_TAG})"
        return 0
    fi

    error "未找到可用的 requirement-mgr release（可能尚未发布或无 .whl 资产）"
}

# gh CLI 备用方案
get_latest_via_gh() {
    local tag_name download_url
    # 使用 gh --jq 解析，避免依赖 grep -P
    tag_name=$(gh release list --repo "$REPO" --limit 30 --json tagName,isPrerelease \
        --jq "[.[] | select(.tagName | startswith(\"${TAG_PREFIX}\")) | select(.isPrerelease == ${INCLUDE_PRE} or .isPrerelease == false)] | first | .tagName" 2>/dev/null) || true

    if [ -z "${tag_name:-}" ]; then
        return 1
    fi

    download_url=$(gh release view "$tag_name" --repo "$REPO" --json assets \
        --jq '.assets[] | select(.name | endswith(".whl")) | .url' 2>/dev/null | head -1) || true

    if [ -n "${tag_name:-}" ] && [ -n "${download_url:-}" ]; then
        LATEST_TAG="$tag_name"
        LATEST_VERSION="${tag_name#${TAG_PREFIX}}"
        DOWNLOAD_URL="$download_url"
        return 0
    fi
    return 1
}

# grep/sed 降级解析（无 python/gh 时）
get_latest_via_grep() {
    local body="$1"

    # 提取所有 tag_name，筛选 requirement-mgr 前缀
    local tags
    tags=$(echo "$body" | grep -o '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"tag_name"[[:space:]]*:[[:space:]]*"//;s/"$//' | grep "^${TAG_PREFIX}")

    for tag in $tags; do
        # 跳过预发布（简单检查 tag 是否包含 -beta/-rc/-alpha）
        if [ "$INCLUDE_PRE" = false ]; then
            echo "$tag" | grep -qiE '(-beta|-rc|-alpha|\.dev|[0-9]+(a|b|c|rc)[0-9]*)' && continue
        fi

        local url
        url=$(echo "$body" | grep -o "\"browser_download_url\"[[:space:]]*:[[:space:]]*\"[^\"]*${tag}[^\"]*\.whl" | sed 's/.*"browser_download_url"[[:space:]]*:[[:space:]]*"//;s/"$//' | head -1) || true

        if [ -n "${url:-}" ]; then
            LATEST_TAG="$tag"
            LATEST_VERSION="${tag#${TAG_PREFIX}}"
            DOWNLOAD_URL="$url"
            return 0
        fi
    done
    return 1
}

# ============================================================
# 检查当前版本
# ============================================================
check_current_version() {
    if command -v "$PKG_CMD" &>/dev/null; then
        CURRENT_VERSION=$("$PKG_CMD" --version 2>/dev/null | sed 's/.*[[:space:]]//;s/,.*//' || echo "unknown")
        info "当前已安装: ${CURRENT_VERSION}"
    else
        CURRENT_VERSION=""
        info "当前未安装 ${PKG_CMD}"
    fi
}

# ============================================================
# 安装
# ============================================================
do_install() {
    info "目标版本: ${LATEST_VERSION}"
    info "下载地址: ${DOWNLOAD_URL}"

    if [ -n "$CURRENT_VERSION" ] && [ "$CURRENT_VERSION" = "$LATEST_VERSION" ]; then
        info "已是最新版本 (${CURRENT_VERSION})，无需更新"
        exit 0
    fi

    info "正在安装..."
    $INSTALL_CMD "$DOWNLOAD_URL"

    echo ""
    if command -v "$PKG_CMD" &>/dev/null; then
        info "安装成功！"
        "$PKG_CMD" --version 2>/dev/null && true
    else
        warn "安装完成，但 ${PKG_CMD} 命令不可用，请检查 PATH"
    fi
}

# ============================================================
# 主流程
# ============================================================
main() {
    info "requirement-mgr 安装器"
    echo "========================================"

    check_current_version
    get_latest_release
    do_install
}

main
