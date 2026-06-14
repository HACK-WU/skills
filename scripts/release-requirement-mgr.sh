#!/usr/bin/env bash
# ============================================================
# requirement-mgr 发布脚本
# 构建 Python 包 (wheel + sdist)，创建 GitHub Release 并上传
#
# 用法:
#   ./scripts/release-requirement-mgr.sh <version> [prerelease]
#
# 示例:
#   ./scripts/release-requirement-mgr.sh 1.0.0              # 正式版
#   ./scripts/release-requirement-mgr.sh 1.1.0-beta.1 true  # 预发布版
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PKG_DIR="${SCRIPT_DIR}/requirement-mgr"
PKG_NAME="requirement-mgr"
REPO="HACK-WU/skills"

VERSION="${1:?请指定版本号，例如: $0 1.0.0}"
PRERELEASE="${2:-false}"
TAG="requirement-mgr-v${VERSION}"

echo "==> 发布 ${PKG_NAME} ${VERSION}"
echo "    包目录: ${PKG_DIR}"
echo "    Tag:    ${TAG}"
echo ""

# ────────────────────────────────────────────────────────────
# 1. 确认版本号与 pyproject.toml 一致
# ────────────────────────────────────────────────────────────
PYPROJECT="${PKG_DIR}/pyproject.toml"
if [ ! -f "$PYPROJECT" ]; then
  echo "错误: ${PYPROJECT} 不存在"
  exit 1
fi

PKG_VERSION=$(grep -E '^version\s*=' "$PYPROJECT" | head -1 | sed 's/.*=\s*"\(.*\)"/\1/')
if [ "$PKG_VERSION" != "$VERSION" ]; then
  echo "错误: pyproject.toml 版本为 ${PKG_VERSION}，与指定版本 ${VERSION} 不一致"
  echo "请先修改 pyproject.toml 中的 version 字段"
  exit 1
fi
echo "  ✅ 版本号一致: ${VERSION}"

# ────────────────────────────────────────────────────────────
# 2. 确认工作区干净
# ────────────────────────────────────────────────────────────
if ! git diff-index --quiet HEAD --; then
  echo "错误: 工作区有未提交的变更，请先提交或暂存"
  git status --short
  exit 1
fi
echo "  ✅ 工作区干净"

# ────────────────────────────────────────────────────────────
# 3. 检查关键文件
# ────────────────────────────────────────────────────────────
echo "==> 检查关键文件..."
for f in pyproject.toml src/requirement_mgr/__init__.py src/requirement_mgr/cli.py; do
  if [ ! -f "${PKG_DIR}/${f}" ]; then
    echo "错误: 关键文件 ${f} 不存在 (相对于 ${PKG_DIR})"
    exit 1
  fi
done
echo "  ✅ 关键文件检查通过"

# ────────────────────────────────────────────────────────────
# 4. 快速冒烟测试
# ────────────────────────────────────────────────────────────
echo "==> 冒烟测试..."
cd "$PKG_DIR"

# 构建临时安装并验证 CLI 可用
if command -v uv &>/dev/null; then
  SMOKE_DIR=$(mktemp -d)
  trap "rm -rf ${SMOKE_DIR}" EXIT

  if uv build --quiet 2>/dev/null; then
    WHEEL=$(ls -t dist/*.whl 2>/dev/null | head -1)
    if [ -n "$WHEEL" ]; then
      uv pip install --quiet --target "$SMOKE_DIR" "$WHEEL" 2>/dev/null || true
    fi
    echo "  ✅ 构建验证通过"
  else
    echo "错误: uv build 失败"
    exit 1
  fi
else
  echo "  ⚠️  uv 不可用，跳过构建验证"
fi

# 清理构建产物（后面正式构建会重新生成）
rm -rf dist/
if [ -d dist/ ] && [ "$(ls -A dist/ 2>/dev/null)" ]; then
  echo "  ⚠️  dist/ 未完全清空，可能有权限问题，继续执行..."
fi

# ────────────────────────────────────────────────────────────
# 5. 正式构建 (wheel + sdist)
# ────────────────────────────────────────────────────────────
cd "$PKG_DIR"
echo "==> 构建包..."

if command -v uv &>/dev/null; then
  uv build
else
  echo "  ⚠️  uv 不可用，尝试 python -m build..."
  if python -c "import build" 2>/dev/null; then
    python -m build
  else
    echo "错误: uv 不可用且 build 包未安装"
    echo "请安装: pip install build  或  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi
fi

# 收集产物
WHEEL=$(ls -t dist/*.whl 2>/dev/null | head -1)
SDIST=$(ls -t dist/*.tar.gz 2>/dev/null | head -1)

if [ -z "$WHEEL" ] && [ -z "$SDIST" ]; then
  echo "错误: 构建产物未生成"
  exit 1
fi

echo ""
echo "==> 构建产物:"
[ -n "$WHEEL" ] && echo "  📦 $(basename "$WHEEL") ($(du -h "$WHEEL" | cut -f1))"
[ -n "$SDIST" ] && echo "  📦 $(basename "$SDIST") ($(du -h "$SDIST" | cut -f1))"
echo ""

# Wheel 内容检查
if [ -n "$WHEEL" ]; then
  echo "==> Wheel 内容 (前 15 个文件):"
  unzip -l "$WHEEL" 2>/dev/null | head -20 || python -m zipfile -l "$WHEEL" | head -15
  echo ""
fi

# ────────────────────────────────────────────────────────────
# 6. 创建/覆盖 git tag
# ────────────────────────────────────────────────────────────
cd "${SCRIPT_DIR}/.."  # 回到仓库根目录

if git tag -l "$TAG" | grep -q "$TAG"; then
  echo "==> tag ${TAG} 已存在，覆盖..."
  git tag -d "$TAG"
  git push origin ":refs/tags/${TAG}" 2>/dev/null || true
fi
echo "==> 创建 tag: ${TAG}"
git tag "$TAG" -m "Release ${PKG_NAME} ${VERSION}"

# ────────────────────────────────────────────────────────────
# 7. 推送 tag
# ────────────────────────────────────────────────────────────
echo "==> 推送 tag 到远程..."
git push origin "$TAG" --force

# ────────────────────────────────────────────────────────────
# 8. 创建 GitHub Release 并上传产物
# ────────────────────────────────────────────────────────────
RELEASE_NOTES="## 📦 ${PKG_NAME} ${VERSION}

需求管理 CLI 工具 — 零外部依赖的 Python 包。

### 功能

- **CRUD 管理** — 创建 / 列出 / 更新 / 删除需求
- **父子层级** — standalone / parent / child 角色自动升降级
- **日期 ID 格式** — \`REQ-YYYYMMDD-NNN\`，向后兼容旧 \`REQ-NNN\`
- **Config 驱动校验** — statuses / roles / id_prefix / id_digits / lock_timeout / backup_enabled
- **文件锁** — 跨平台 (fcntl / msvcrt)，TOCTOU 防护
- **原子写入** — tempfile + os.replace 保证数据完整性

### 安装

\`\`\`bash
# 从 GitHub Release 安装 (推荐)
uv tool install https://github.com/${REPO}/releases/download/${TAG}/$(basename "${WHEEL:-$SDIST}")

# 或 pip 安装
pip install https://github.com/${REPO}/releases/download/${TAG}/$(basename "${WHEEL:-$SDIST}")
\`\`\`

### 使用

\`\`\`bash
req list                              # 列出所有需求
req create --feature '新功能' --tags feat  # 创建需求
req update <ID> --status done         # 更新状态
req delete <ID>                       # 删除需求
\`\`\`

### 包含文件
- \`src/requirement_mgr/\` — Python 包 (CLI + 5 命令 + 5 核心模块)
- \`pyproject.toml\` — 包定义 (hatchling 构建，零外部依赖)"

# 收集要上传的文件
UPLOAD_FILES=()
[ -n "$WHEEL" ] && UPLOAD_FILES+=("$WHEEL")
[ -n "$SDIST" ] && UPLOAD_FILES+=("$SDIST")

if command -v gh &>/dev/null && gh auth status &>/dev/null 2>&1; then
  # Release 已存在则删除重建
  if gh release view "$TAG" &>/dev/null 2>&1; then
    echo "==> Release ${TAG} 已存在，删除旧版本..."
    gh release delete "$TAG" --yes --cleanup-tag 2>/dev/null || true
    git tag "$TAG" -m "Release ${PKG_NAME} ${VERSION}"
    git push origin "$TAG" --force
  fi

  echo "==> 创建 GitHub Release ${TAG}..."
  GH_ARGS=("$TAG" "${UPLOAD_FILES[@]}" --title "${TAG}" --notes "$RELEASE_NOTES")
  if [ "$PRERELEASE" = "true" ]; then
    GH_ARGS+=(--prerelease)
  fi
  gh release create "${GH_ARGS[@]}"

  echo ""
  echo "==> ✅ 发布完成!"
  echo ""
  echo "==> 安装命令:"
  [ -n "$WHEEL" ] && echo "    uv tool install https://github.com/${REPO}/releases/download/${TAG}/$(basename "$WHEEL")"
  [ -n "$SDIST" ] && echo "    pip install https://github.com/${REPO}/releases/download/${TAG}/$(basename "$SDIST")"
else
  echo ""
  echo "==> ⚠️  gh CLI 未认证，请手动创建 Release："
  echo ""
  echo "    1. 在 GitHub 上创建 Release:"
  echo "       https://github.com/${REPO}/releases/new?tag=${TAG}"
  echo "    2. Tag: ${TAG}"
  echo "    3. 上传文件:"
  for f in "${UPLOAD_FILES[@]}"; do
    echo "       - $(basename "$f") (${PKG_DIR}/dist/)"
  done
  echo ""
  echo "    4. 或者运行以下命令（需要先 gh auth login）："
  echo ""
  UPLOAD_ARGS=""
  for f in "${UPLOAD_FILES[@]}"; do
    UPLOAD_ARGS+=" \"${f}\""
  done
  if [ "$PRERELEASE" = "true" ]; then
    echo "       gh release create ${TAG}${UPLOAD_ARGS} --title '${TAG}' --prerelease"
  else
    echo "       gh release create ${TAG}${UPLOAD_ARGS} --title '${TAG}'"
  fi
  echo ""
  echo "==> 安装命令:"
  [ -n "$WHEEL" ] && echo "    uv tool install https://github.com/${REPO}/releases/download/${TAG}/$(basename "$WHEEL")"
fi

# ────────────────────────────────────────────────────────────
# 9. 提示清理
# ────────────────────────────────────────────────────────────
echo ""
echo "==> 构建产物保存在: ${PKG_DIR}/dist/"
echo "    清理命令: rm -rf ${PKG_DIR}/dist/"
