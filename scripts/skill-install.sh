#!/usr/bin/env bash
# ============================================================
# Skills 安装器 — 从 GitHub 下载 Skills / Rules
#
# 用法:
#   bash skill-install.sh --skills -t /path/to/target -t /path/to/target2
#   bash skill-install.sh --rules --file /path/to/targets.txt
#   bash skill-install.sh --skills -n code-review,design-craft -t ~/projects/app
#   bash skill-install.sh --skills -n code-review -n design-craft -t ~/projects/app
#   bash skill-install.sh /path/to/target --skills   # 旧用法，兼容
#
#   或:
#   curl -fsSL ... -o skill-install.sh
#   bash skill-install.sh --skills -t /path/to/target
# ============================================================
set -euo pipefail

GITHUB_REPO="HACK-WU/skills"
GITHUB_BRANCH="master"
RAW_BASE="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}"

DEFAULT_SKILLS_TARGETS="$HOME/.skill-targets"
DEFAULT_RULES_TARGETS="$HOME/.rule-targets"
POSITIONAL_TARGET=""
TARGETS=()
CONFIG_FILE=""
MODES=()
NAME_FILTER=""
GH_AUTH_OK=false

# 文件列表缓存（跨目标目录复用，避免重复调用 GitHub API）
SKILLS_FILES=()
RULES_FILES=()
SKILLS_DISCOVERED=false
RULES_DISCOVERED=false

# ============================================================
# 前置：gh 认证检查（缓存结果，避免各 install 函数重复调用）
# ============================================================
if command -v gh &> /dev/null && gh auth status &>/dev/null; then
    GH_AUTH_OK=true
fi

# ============================================================
# 参数解析
# ============================================================
while [ $# -gt 0 ]; do
    arg="$1"
    case "$arg" in
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
        -n)
            shift
            [ $# -eq 0 ] && { echo "错误：-n 需要参数"; exit 1; }
            NAME_FILTER="${NAME_FILTER:+$NAME_FILTER,}$1"
            ;;
        --file=*) CONFIG_FILE="${arg#*=}" ;;
        --all|--docs)
            echo "错误：${arg} 已废弃"
            exit 1
            ;;
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
elif [ ${#MODES[@]} -gt 0 ]; then
    # 模式特定的默认配置文件
    TARGET_DIRS=()
    MODE_FILES=()
    for mode in "${MODES[@]}"; do
        case "$mode" in
            skills)  MODE_FILES+=("$DEFAULT_SKILLS_TARGETS") ;;
            rules)   MODE_FILES+=("$DEFAULT_RULES_TARGETS") ;;
        esac
    done
    for cf in "${MODE_FILES[@]}"; do
        if [ -f "$cf" ]; then
            while IFS= read -r line; do
                line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                [ -z "$line" ] && continue
                [[ "$line" =~ ^# ]] && continue
                # bash 3.2 兼容的去重：遍历已有数组检查重复
                found=0
                if [ ${#TARGET_DIRS[@]} -gt 0 ]; then
                    for existing in "${TARGET_DIRS[@]}"; do
                        [ "$existing" = "$line" ] && { found=1; break; }
                    done
                fi
                [ "$found" -eq 0 ] && TARGET_DIRS+=("$line")
            done < "$cf"
        fi
    done
    if [ ${#TARGET_DIRS[@]} -gt 0 ]; then
        SOURCE_DESC="默认配置（模式区分）"
    fi
elif [ -n "$POSITIONAL_TARGET" ]; then
    TARGET_DIRS=("$POSITIONAL_TARGET")
    SOURCE_DESC="位置参数"
else
    TARGET_DIRS=()
fi

if [ ${#TARGET_DIRS[@]} -eq 0 ] || [ ${#MODES[@]} -eq 0 ]; then
    if [ -n "$NAME_FILTER" ] && [ ${#MODES[@]} -eq 0 ]; then
        echo "错误：-n 参数必须配合 --skills 或 --rules 使用"
        exit 1
    fi
    echo "用法: bash skill-install.sh [--skills|--rules] [-t <path>... | --file <path>]"
    echo ""
    echo "  --skills        安装 AI Skill 定义（skills/）"
    echo "  --rules         安装 AI 规则（rules/）"
    echo "  -n <names>      指定要安装的 skill/rule 名称（逗号分隔或多次使用，如 -n code-review,design-craft 或 -n code-review -n design-craft）"
    echo "  -t <path>       指定目标目录（可多次使用，与 --file 互斥）"
    echo "  --file <path>   指定目标目录配置文件（与 -t 互斥）"
    echo ""
    echo "兼容旧用法:"
    echo "  bash skill-install.sh <目标路径> --skills"
    echo ""
    echo "示例:"
    echo "  bash skill-install.sh --skills -t ~/projects/app -t ~/projects/api"
    echo "  bash skill-install.sh --skills -n code-review,design-craft -t ~/projects/app"
    echo "  bash skill-install.sh --rules --file ~/my-targets.txt"
    echo "  bash skill-install.sh --skills --rules -t ~/projects/my-app"
    echo ""
    echo "默认配置文件（不指定 -t / --file 时自动读取）:"
    echo "  --skills  → $HOME/.skill-targets"
    echo "  --rules   → $HOME/.rule-targets"
    echo ""
    echo "一键安装:"
    echo "  curl -fsSL ${RAW_BASE}/scripts/skill-install.sh | \\"
    echo "    bash -s -- --skills --rules -t ~/projects/my-app"
    echo ""
    echo "  # 使用默认配置文件（~/.skill-targets / ~/.rule-targets）"
    echo "  curl -fsSL ${RAW_BASE}/scripts/skill-install.sh | bash -s -- --skills"
    echo ""
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

# 解析名称过滤器
if [ -n "$NAME_FILTER" ]; then
    IFS=',' read -ra NAME_LIST <<< "$NAME_FILTER"
    # 去除空格
    for i in "${!NAME_LIST[@]}"; do
        NAME_LIST[$i]="$(echo "${NAME_LIST[$i]}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    done
else
    NAME_LIST=()
fi

# 检查名称是否在过滤列表中（空列表表示全部匹配）
name_matches() {
    local name="$1"
    [ ${#NAME_LIST[@]} -eq 0 ] && return 0
    for filter_name in "${NAME_LIST[@]}"; do
        [ "$name" = "$filter_name" ] && return 0
    done
    return 1
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

    # 动态发现：优先 gh 递归获取，降级为硬编码；使用缓存避免重复 API 调用
    # gh 需已登录才能使用 API；未登录则直接走硬编码避免 API 调用延迟
    local FILES=()
    if [ "$SKILLS_DISCOVERED" = true ]; then
        FILES=("${SKILLS_FILES[@]}")
    elif [ "$GH_AUTH_OK" = true ]; then
        echo "🔍 正在通过 GitHub API 发现 skill 文件列表..." >&2
        # 先列出 skill 目录；临时关闭 set -e 防止 gh api 失败导致脚本静默退出
        local SKILL_DIRS
        set +e
        SKILL_DIRS=$(gh api "repos/${GITHUB_REPO}/contents/skills" \
            --jq '.[] | select(.type=="dir") | .name' 2>/dev/null)
        local api_rc=$?
        set -e

        if [ $api_rc -ne 0 ] || [ -z "$SKILL_DIRS" ]; then
            echo "   ⚠️ GitHub API 调用失败，将使用静态 skill 列表" >&2
        else
            while IFS= read -r skill_name; do
                [ -z "$skill_name" ] && continue
                # 跳过内部维护工具
                [ "$skill_name" = "skill-updater" ] && continue
                # 递归发现该 skill 下的所有文件
                while IFS= read -r rel; do
                    [ -z "$rel" ] && continue
                    FILES+=("${skill_name}/${rel}")
                done < <(discover_files_recursive "skills/${skill_name}" "")
                printf "." >&2
            done <<< "$SKILL_DIRS"
        fi
        echo "" >&2
    fi

    if [ ${#FILES[@]} -eq 0 ]; then
        echo "⚠️  gh 不可用，使用静态 skill 列表（可能不是最新）" >&2
        FILES=(
            "api-design/SKILL.md"
            "auto-review/SKILL.md"
            "bug-impact-analysis/SKILL.md"
            "challenger/SKILL.md"
            "challenger/strategies/bug-fix.md"
            "challenger/strategies/feature.md"
            "challenger/strategies/optimization.md"
            "challenger/templates/report.md"
            "code-implement/SKILL.md"
            "code-review/SKILL.md"
            "code-survey/SKILL.md"
            "content-simplifier/SKILL.md"
            "create-rules/SKILL.md"
            "create-skill/SKILL.md"
            "data-flow-model/SKILL.md"
            "demo-verify/SKILL.md"
            "dependency-docs/SKILL.md"
            "design-craft/CHALLENGER_REPORT.md"
            "design-craft/SINGLE_DOC.md"
            "design-craft/SKILL.md"
            "design-craft/SUB_TEMPLATE.md"
            "design-craft/reference.md"
            "design-review/SKILL.md"
            "design-review/reference.md"
            "design-to-code/SKILL.md"
            "document-writer/SKILL.md"
            "document-writer/references/examples/README.md"
            "document-writer/references/examples/example-1-library.md"
            "document-writer/references/examples/example-2-cli.md"
            "document-writer/references/quality-rules.md"
            "document-writer/references/strategies.md"
            "expert-panel/SKILL.md"
            "expert-panel/references/review-panel.md"
            "frontend-api-guide/SKILL.md"
            "frontend-api-guide/reference.md"
            "implementation-report/SKILL.md"
            "interaction-design/SKILL.md"
            "memory-creator/SKILL.md"
            "migrate-to-codehub/SKILL.md"
            "negative-requirement/SKILL.md"
            "request-guard/SKILL.md"
            "requirement-doc-store/SKILL.md"
            "requirement-mining/SKILL.md"
            "requirement-mining/references/example.md"
            "scenario-rehearsal/SKILL.md"
            "scenario-rehearsal/reference.md"
            "task-dispatch/SKILL.md"
            "task-dispatch/reference.md"
            "test-planner/SKILL.md"
            "test-planner/references/examples/example-1-registration.md"
            "test-planner/references/test-strategies.md"
            "work-breakdown/SKILL.md"
        )
    elif [ "$SKILLS_DISCOVERED" = false ]; then
        # 缓存首次发现的文件列表，后续目标目录复用
        SKILLS_FILES=("${FILES[@]}")
        SKILLS_DISCOVERED=true
    fi

    echo "🧠 安装 AI Skills → ${DEST}"
    echo ""

    local file_count=0 skipped=0
    local skill_names_all=()   # 所有涉及的 skill 目录（去重）
    local skill_names_ok=()    # SKILL.md 下载成功的 skill 目录（去重）
    local _sn_fail=()          # 每个 skill 的失败文件数（与 skill_names_all 索引对齐）

    for f in "${FILES[@]}"; do
        # 提取 skill 名称用于过滤（取第一级目录名）
        local skill_name="${f%%/*}"

        # 记录 skill 目录（去重）并初始化失败计数
        local found=0 i=0
        for sn in "${skill_names_all[@]}"; do
            [ "$sn" = "$skill_name" ] && { found=1; break; }
            i=$((i + 1))
        done
        if [ "$found" -eq 0 ]; then
            skill_names_all+=("$skill_name")
            _sn_fail+=(0)
        fi

        if ! name_matches "$skill_name"; then
            continue
        fi

        local url="${RAW_BASE}/skills/${f}"
        local dest="${DEST}/${f}"
        if download "$url" "$dest"; then
            echo "  [OK] ${f}"
            file_count=$((file_count + 1))
            # 记录 SKILL.md 下载成功的 skill 目录（去重）
            if [ "${f##*/}" = "SKILL.md" ]; then
                local ok_found=0
                for sn in "${skill_names_ok[@]}"; do
                    [ "$sn" = "$skill_name" ] && { ok_found=1; break; }
                done
                [ "$ok_found" -eq 0 ] && skill_names_ok+=("$skill_name")
            fi
        else
            echo "  [FAIL] ${f}"
            # 找到 skill 在 skill_names_all 中的索引，增加失败计数
            local fi_idx=0
            for sn in "${skill_names_all[@]}"; do
                [ "$sn" = "$skill_name" ] && { _sn_fail[$fi_idx]=$((${_sn_fail[$fi_idx]} + 1)); break; }
                fi_idx=$((fi_idx + 1))
            done
        fi
    done

    # 统计跳过的 skill 数（目录级）
    for sn in "${skill_names_all[@]}"; do
        name_matches "$sn" || skipped=$((skipped + 1))
    done

    [ $skipped -gt 0 ] && echo "  跳过: ${skipped} 个未匹配的 skill"

    # 输出不完整 skill 的警告（存在下载失败文件的 skill）
    local _warned=0 _wi=0
    for sn in "${skill_names_all[@]}"; do
        if name_matches "$sn" && [ "${_sn_fail[$_wi]}" -gt 0 ]; then
            [ $_warned -eq 0 ] && echo "" && echo "⚠️ 以下 skill 存在下载失败的文件："
            echo "  - ${sn}: ${_sn_fail[$_wi]} 个文件失败"
            _warned=1
        fi
        _wi=$((_wi + 1))
    done

    echo ""
    echo "已安装: ${#skill_names_ok[@]}/${#skill_names_all[@]} 个 skill（共 ${file_count} 个文件）"
    if [ $file_count -gt 0 ]; then ANY_INSTALLED=1; fi
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

    # 动态发现：优先 gh（需已登录），降级为硬编码；使用缓存避免重复 API 调用
    local FILES=()
    if [ "$RULES_DISCOVERED" = true ]; then
        FILES=("${RULES_FILES[@]}")
    elif [ "$GH_AUTH_OK" = true ]; then
        echo "🔍 正在通过 GitHub API 发现规则文件列表..." >&2
        # 临时关闭 set -e 防止 gh api 失败导致脚本静默退出
        set +e
        local _rules_api_out
        _rules_api_out=$(gh api "repos/${GITHUB_REPO}/contents/rules" \
            --jq '.[] | select(.name | endswith(".md")) | .name' 2>/dev/null)
        local api_rc=$?
        set -e
        if [ $api_rc -ne 0 ]; then
            echo "   ⚠️ GitHub API 调用失败，将使用静态 rule 列表" >&2
        else
            while IFS= read -r name; do
                [ -z "$name" ] && continue
                FILES+=("$name")
            done <<< "$_rules_api_out"
            echo "   已发现 ${#FILES[@]} 个规则文件" >&2
        fi
    fi

    if [ ${#FILES[@]} -eq 0 ]; then
        echo "⚠️  gh 不可用，使用静态 rule 列表（可能不是最新）" >&2
FILES=(
    "gitnexus-mcp-rules.md"
    "agents-memory.md"
    "writing-pipeline.md"
    "solution-workflow.md"
)
    elif [ "$RULES_DISCOVERED" = false ]; then
        # 缓存首次发现的文件列表，后续目标目录复用
        RULES_FILES=("${FILES[@]}")
        RULES_DISCOVERED=true
    fi

    echo "📏 安装 AI Rules → ${DEST}"
    echo ""

    local count=0 total=0 skipped=0
    for f in "${FILES[@]}"; do
        # 提取规则名称用于过滤（去掉 .md 后缀）
        local rule_name="${f%.md}"
        if ! name_matches "$rule_name"; then
            skipped=$((skipped + 1))
            continue
        fi
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
    [ $skipped -gt 0 ] && echo "  跳过: ${skipped} 个未匹配的 rule"
    echo ""
    echo "已安装: ${count}/${total} 个规则文件"
    if [ $count -gt 0 ]; then ANY_INSTALLED=1; fi
}

# ============================================================
# 按模式执行（支持多目标目录）
# ============================================================
echo "🚀 skill-install.sh"
echo "   目标来源: ${SOURCE_DESC}"
echo "   目标数量: ${#TARGET_DIRS[@]}"
echo "   安装模式: ${MODES[*]}"
[ ${#NAME_LIST[@]} -gt 0 ] && echo "   名称过滤: $(IFS=', '; echo "${NAME_LIST[*]}")"
echo ""

ANY_INSTALLED=0

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
            skills)  install_skills ;;
            rules)   install_rules  ;;
        esac
        echo ""
    done
done

echo ""
if [ $ANY_INSTALLED -eq 0 ] && [ ${#NAME_LIST[@]} -gt 0 ]; then
    echo "⚠️ 未找到匹配的项，请检查名称是否正确"
    exit 1
fi
echo "✅ 完成"
