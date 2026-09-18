#!/usr/bin/env bash
# ============================================================
# Skills 安装器 — 基于 npx skills 管理本仓库的 AI Skills
#
# 管理目录: ~/.hackwu-skills/
#   ├── skills/              # npx 安装的 skill（openclaw 映射 = cwd/skills/）
#   ├── skills-lock.json     # npx 生成的跟踪文件（update/remove/list 依据）
#   └── targets.list         # 目标目录记录: <目标目录>[\t<仓库1> <仓库2> ...]
#                            #   仓库列 = 该目标的来源意图（install 写入/合并），
#                            #   update/prune 据此圈定范围；老记录（无仓库列）
#                            #   首次使用时按目标现有 skill 反查来源并写回
#
# 同步范围: 管理源是多仓库共享池（--repo 只往池里追加），同步到目标时按
#           "本次操作的仓库"圈定范围，不会把其他仓库的 skill 带到目标。
#           （install 未指定 --repo 时 = 默认仓库 HACK-WU/skills；
#             update 未指定 --repo/-n 时 = 各目标自己的来源记录）
#
# 用法:
#   bash skill-install.sh install -t /path/to/target     # 安装（默认）
#   bash skill-install.sh update [-t ...] [-n names] [--repo ...]  # 更新并同步
#   bash skill-install.sh remove <names>                  # 删除 + 同步
#   bash skill-install.sh prune [-t ...] [-y]             # 清理目标中不属于其来源的 skill
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

# 可选技能目录：存放依赖第三方 skill/模块的技能（--optional 的别名目标）
OPTIONAL_REPO_URL="https://github.com/HACK-WU/skills/tree/master/skills-optional"

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
PRUNE_APPLY=0

show_help() {
    cat << EOF
Skills 安装器 — 基于 npx skills 管理 AI Skills

用法:
  bash skill-install.sh <操作> [选项]
  操作:
    install   安装 skill 到目标目录（默认操作，可省略）
    update    更新管理源中已安装的 skill 并同步到目标目录
    remove    从管理源删除指定 skill 并同步删除所有目标
    prune     清理目标中"安装器装过但不属于该目标来源"的 skill（默认预演，-y 执行）
    list      列出管理源中已安装的 skill（含来源仓库）
    --help    显示此帮助

选项:
  -t <path>            目标目录（可多次使用，与 --file 互斥；update/prune 时限定处理的目标目录）
  -n <names>           指定 skill（逗号分隔，如 -n code-review,design-craft）
  --repo <owner/repo>  指定仓库（可多次使用；install/update 指定安装源，prune 指定期望来源，list 按来源过滤）
  --optional           别名，等价于 --repo $OPTIONAL_REPO_URL
                       （可选技能目录：依赖第三方 skill/模块的技能）
  --file <path>        从配置文件读取目标目录（与 -t 互斥）
  -y, --yes            prune 时真正执行删除（不加则只预演列出）
  -h, --help           显示此帮助

同步范围:
  管理源是多仓库共享池，同步到目标时按"本次操作的仓库"圈定范围：
  指定 --repo 时只同步这些仓库的 skill（可再叠加 -n 收窄名称）；
  install 未指定 --repo 时 = 默认仓库 HACK-WU/skills；
  update 未指定 --repo / -n 时 = 各目标自己的来源记录
  （记录在 $MANAGE_DIR/targets.list 每行的仓库列；老记录首次使用时按
   目标现有 skill 反查来源并写回；判定不出则跳过，不做全量复制）。

默认配置文件（不指定 -t / --file 时读取）:
  $DEFAULT_TARGETS_FILE

管理目录:
  $MANAGE_DIR
  （npx skills 的安装/跟踪工作目录，update/remove/prune/list 基于此持续管理）

示例:
  bash skill-install.sh -t ~/projects/app
  bash skill-install.sh install -n code-review,design-craft -t ~/projects/app
  bash skill-install.sh install --optional -t ~/projects/app    # 只装可选技能
  bash skill-install.sh install --repo HACK-WU/skills --optional -t ~/app  # 主技能+可选技能
  bash skill-install.sh update -t ~/projects/app
  bash skill-install.sh update -n code-review --repo HACK-WU/skills
  bash skill-install.sh remove code-review
  bash skill-install.sh prune                      # 预演：列出各目标中外来的 skill
  bash skill-install.sh prune -t ~/app -y          # 执行清理指定目标
  bash skill-install.sh prune -t ~/app --repo HACK-WU/skills -y
                                                   # 以 --repo 为期望来源清理，并纠正该目标记录
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
        --optional)
            # 别名，等价于 --repo "$OPTIONAL_REPO_URL"
            REPOS+=("$OPTIONAL_REPO_URL")
            REPOS_SPECIFIED=1
            ;;
        --file)
            shift
            [ $# -eq 0 ] && error "--file 需要参数"
            CONFIG_FILE="$1"
            ;;
        --file=*) CONFIG_FILE="${arg#*=}" ;;
        -y|--yes) PRUNE_APPLY=1 ;;
        install|update|remove|prune|list)
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

# 目标目录 → 实际落盘目录（目标名以 skills 结尾时直接用，否则拼 /skills）
target_dest() {
    local t="$1" leaf="${t%/}"
    leaf="${leaf##*/}"
    if [ "$leaf" = "skills" ]; then
        printf '%s' "$t"
    else
        printf '%s/skills' "$t"
    fi
}

# ============================================================
# 目标记录（targets.list）
# 格式: <目标目录>[\t<仓库1> <仓库2> ...]
#   仓库列 = "这个目标要装哪些仓库"的意图记录（install 写入 / 合并），
#   也是 update / prune 圈定同步范围的依据 —— 管理源是多仓库共享池，
#   不按目标记来源就只能全量复制（会把其他仓库的 skill 带进目标）。
#   老记录（无 \t）视为来源未知：首次使用时按目标现有 skill 反查 lock
#   来源并写回（见 resolve_target_repos），判定不出则跳过同步。
# ============================================================
# 仓库列表并集（保持原顺序；仓库标识不含空格）
merge_repo_list() {
    local out="" w
    for w in $1 $2; do
        case " $out " in
            *" $w "*) ;;
            *) out="$out $w" ;;
        esac
    done
    printf '%s' "${out# }"
}

# 写入/更新某目标的仓库列：mode = merge（合并，记录意图）| set（覆盖，纠正记录）
# merge 且仓库无变化时不重写文件（少动状态文件，收敛并发写窗口）
_write_target_record() {
    local t="$1" mode="$2" add="$3"
    [ -f "$TARGETS_FILE" ] || touch "$TARGETS_FILE"

    # 已是目标值则直接返回（merge 模式下 add ⊆ 现有 也算已是）
    local cur
    cur="$(target_repos_from_file "$t")"
    if [ "$mode" = "set" ] && [ "$cur" = "$add" ]; then
        return 0
    fi
    if [ "$mode" = "merge" ] && [ "$(merge_repo_list "$cur" "$add")" = "$cur" ] && [ -n "$cur" ]; then
        return 0
    fi

    local tmp="${TARGETS_FILE}.tmp.$$"
    local found=0 p rest newv
    : > "$tmp"
    while IFS=$'\t' read -r p rest; do
        [ -z "$p" ] && continue
        if [ "$p" = "$t" ]; then
            found=1
            if [ "$mode" = "set" ]; then
                newv="$add"
            else
                newv="$(merge_repo_list "$rest" "$add")"
            fi
            if [ -n "$newv" ]; then
                printf '%s\t%s\n' "$p" "$newv" >> "$tmp"
            else
                printf '%s\n' "$p" >> "$tmp"
            fi
        elif [ -n "$rest" ]; then
            printf '%s\t%s\n' "$p" "$rest" >> "$tmp"
        else
            printf '%s\n' "$p" >> "$tmp"
        fi
    done < "$TARGETS_FILE"
    if [ "$found" = "0" ]; then
        if [ -n "$add" ]; then
            printf '%s\t%s\n' "$t" "$add" >> "$tmp"
        else
            printf '%s\n' "$t" >> "$tmp"
        fi
    fi
    mv "$tmp" "$TARGETS_FILE"
}

# 记录/合并目标及其仓库来源（去重，bash 3.2 兼容）
record_target() {
    local t="$1"
    shift
    _write_target_record "$t" merge "$*"
}

# 覆盖写入目标的仓库来源（prune --repo 纠正记录用）
set_target_repos() {
    local t="$1"
    shift
    _write_target_record "$t" set "$*"
}

# 输出所有已记录目标路径（每行一个，去掉仓库列）
get_recorded_targets() {
    [ ! -f "$TARGETS_FILE" ] && return 0
    local line p
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        p="${line%%$'\t'*}"
        [ -n "$p" ] && echo "$p"
    done < "$TARGETS_FILE"
}

# 读某目标记录中的仓库列表
target_repos_from_file() {
    [ -f "$TARGETS_FILE" ] || return 0
    local want="$1" p rest
    while IFS=$'\t' read -r p rest; do
        if [ "$p" = "$want" ]; then
            printf '%s' "$rest"
            return 0
        fi
    done < "$TARGETS_FILE"
}

# lock 中所有 skill 的 "name<TAB>source" 清单（供来源反查 / prune 分类）
lock_name_sources() {
    [ ! -f "$LOCK_FILE" ] && return 0
    LOCK_FILE="$LOCK_FILE" node -e '
const fs=require("fs");
let d;
try{ d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,"utf8")); }catch(e){ process.exit(0); }
for(const name of Object.keys(d.skills||{}).sort()){
  console.log(name+"\t"+((d.skills[name]||{}).source||"unknown"));
}
'
}

# 反查：目标里已有哪些 skill → 它们在 lock 中的来源仓库（并集）
infer_target_repos() {
    local dest="$1"
    [ -d "$dest" ] || return 0
    local names map
    names="$(ls -1 "$dest" 2>/dev/null | tr '\n' ' ')"
    [ -n "$names" ] || return 0
    map="$(lock_name_sources)"
    [ -n "$map" ] || return 0
    local name n s out=""
    for name in $names; do
        [ -d "$dest/$name" ] || continue
        while IFS=$'\t' read -r n s; do
            if [ "$n" = "$name" ] && [ -n "$s" ]; then
                out="$(merge_repo_list "$out" "$s")"
                break
            fi
        done <<< "$map"
    done
    printf '%s' "$out"
}

# 解析目标的来源仓库：记录优先；老记录/无记录则反查并写回（自愈）
resolve_target_repos() {
    local t="$1" repos
    repos="$(target_repos_from_file "$t")"
    if [ -n "$repos" ]; then
        printf '%s' "$repos"
        return 0
    fi
    repos="$(infer_target_repos "$(target_dest "$t")")"
    if [ -n "$repos" ]; then
        record_target "$t" $repos
        warn "目标记录缺少来源仓库，已按目标现有 skill 反查并写回: $t → $repos"
    fi
    printf '%s' "$repos"
}

# ============================================================
# 同步范围（scope）：只同步来源匹配本次操作仓库的 skill
# ============================================================
# 管理源 ~/.hackwu-skills/skills/ 是多仓库共享池（--repo 只是往里追加），
# 所以同步前必须按来源仓库圈定范围，否则会把池里其他仓库的 skill 一并复制到目标。
SYNC_SCOPE_ACTIVE=0
SYNC_NAMES=""

# 计算范围内的 skill 名（每行一个）
# 依据 lock 的 source（来源仓库）与 skillPath（仓库内路径）过滤；参数 = 允许的仓库列表
compute_sync_names() {
    [ ! -f "$LOCK_FILE" ] && return 0
    LOCK_FILE="$LOCK_FILE" REPO_SPECS="$*" NAME_WANTED="${NAME_FILTER//,/ }" node -e '
const fs=require("fs");
let d;
try{ d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,"utf8")); }catch(e){ process.exit(0); }
const skills=d.skills||{};
// 归一化仓库标识：抹平协议前缀/git@/scp 形式/.git/尾斜杠差异，并拆出 tree 子路径
function norm(s){
  let v=String(s||"").trim();
  if(!v) return null;
  v=v.replace(/^[a-z][a-z0-9+.-]*:\/\//i,"").replace(/^git@/i,"");
  v=v.replace(/^([^/]+):(?!\/)/,"$1/");
  v=v.replace(/\/-\/tree\//,"/tree/");
  let sub="";
  const m=v.match(/\/tree\/([^/]+)(?:\/(.*))?$/);
  if(m){ sub=m[2]||""; v=v.slice(0,m.index); }
  v=v.replace(/\.git$/i,"").replace(/\/+$/,"");
  return {repo:v.toLowerCase(),sub:sub.replace(/^\/+|\/+$/g,"").toLowerCase()};
}
function sameRepo(a,b){ return a===b||a.endsWith("/"+b)||b.endsWith("/"+a); }
// 整仓库安装（未指定子路径）时 npx 只收录这些容器下的 skill，
// 如 skills-optional/ 下的 skill 不会被 "npx skills add owner/repo" 收录
const CONTAINERS=["skills","plugins"];
function inPlainLayout(p){
  const seg=p.split("/");
  if(seg.length<=2) return true;
  if(CONTAINERS.indexOf(seg[0])>=0) return true;
  return seg[0].charAt(0)==="."&&seg[1]==="skills";
}
const specs=String(process.env.REPO_SPECS||"").split(/\s+/).filter(Boolean).map(norm).filter(Boolean);
const wanted=(process.env.NAME_WANTED||"").split(/\s+/).filter(Boolean);
const wantSet=wanted.length?new Set(wanted):null;
const out=new Set();
for(const x of specs){
  const cand=[];
  for(const name of Object.keys(skills)){
    if(wantSet&&!wantSet.has(name)) continue;
    const e=skills[name]||{};
    const src=norm(e.source);
    if(!src||!sameRepo(src.repo,x.repo)) continue;
    const sp=String(e.skillPath||"").toLowerCase();
    if(x.sub){ if(sp.indexOf(x.sub+"/")===0) cand.push({name:name,plain:true}); }
    else cand.push({name:name,plain:inPlainLayout(sp)});
  }
  // 指定子路径的仓库：命中即为范围；整仓库：优先排除同仓库其他子目录的 skill，
  // 若据此筛空（第三方仓库的目录布局不在常见容器内）则退回该仓库全部命中，避免漏同步
  const pruned=cand.filter(function(c){ return c.plain; });
  for(const c of (pruned.length?pruned:cand)) out.add(c.name);
}
const names=[...out].sort();
process.stdout.write(names.length?names.join("\n")+"\n":"");
'
}

# 圈定同步范围（参数 = 本次操作的仓库列表；未指定 --repo 时传默认仓库）
set_sync_scope() {
    # 兜底 || true：解析失败时退化为空范围（下方会警告并跳过同步），而不是让整个脚本中断
    SYNC_NAMES="$(compute_sync_names "$@" | tr "\n" " " || true)"
    SYNC_NAMES="${SYNC_NAMES% }"
    SYNC_SCOPE_ACTIVE=1
}

# 范围内 skill 数量
scope_count() {
    local n=0 name
    for name in $SYNC_NAMES; do
        n=$((n + 1))
    done
    echo "$n"
}

# ============================================================
# 同步：管理源 → 目标（增量同步，管理源是更新来源）
# 只覆盖更新同名文件，不删除目标中管理源没有的文件（保护本地手动修改）
# ============================================================
sync_to_target() {
    local target="$1"
    local dest
    dest="$(target_dest "$target")"

    mkdir -p "$dest"

    if [ ! -d "$MANAGE_SKILLS_DIR" ] || [ -z "$(ls -A "$MANAGE_SKILLS_DIR" 2>/dev/null)" ]; then
        # 管理源为空，跳过同步（不删除目标中已有文件）
        return 0
    fi

    # 优先 rsync（增量同步：覆盖更新，不删除多余文件）
    local has_rsync=0
    if command -v rsync &>/dev/null; then
        has_rsync=1
    fi

    if [ "$SYNC_SCOPE_ACTIVE" = "1" ]; then
        # 只同步范围内（本次操作仓库）的 skill：管理源是多仓库共享池，
        # 全量复制会把池里其他仓库的 skill 一并带到目标
        local name
        for name in $SYNC_NAMES; do
            [ -d "$MANAGE_SKILLS_DIR/$name" ] || continue
            if [ "$has_rsync" = "1" ]; then
                rsync -a "$MANAGE_SKILLS_DIR/$name/" "$dest/$name/"
            else
                mkdir -p "$dest/$name"
                cp -r "$MANAGE_SKILLS_DIR/$name/"* "$dest/$name/" 2>/dev/null || true
            fi
        done
        return 0
    fi

    if [ "$has_rsync" = "1" ]; then
        rsync -a "$MANAGE_SKILLS_DIR/" "$dest/"
    else
        # 降级 cp：直接覆盖复制（不先清空目标）
        cp -r "$MANAGE_SKILLS_DIR/"* "$dest/" 2>/dev/null || true
    fi
}

# 按目标自己的来源记录圈定同步范围；返回 1 = 判定不出（调用方应跳过而非全量兜底）
scope_for_target() {
    local t="$1" repos
    repos="$(resolve_target_repos "$t")"
    [ -n "$repos" ] || return 1
    set_sync_scope $repos
    [ -n "$SYNC_NAMES" ] || return 1
    return 0
}

# 同步所有已记录目标
# 参数 "1" = 调用方已用 set_sync_scope 设定显式范围（--repo / -n），对所有目标适用；
# 否则按各目标自己的来源记录圈定范围（无记录则反查；判定不出则跳过，不做全量兜底）
sync_all_recorded() {
    local fixed="${1:-0}"
    local count=0 total=0
    while IFS= read -r t; do
        [ -z "$t" ] && continue
        total=$((total + 1))
        if [ ! -d "$t" ]; then
            warn "目标目录不存在，跳过: $t"
            continue
        fi
        if [ "$fixed" = "1" ]; then
            if [ -z "$SYNC_NAMES" ]; then
                warn "同步范围为 0，跳过: $t"
                continue
            fi
        elif ! scope_for_target "$t"; then
            warn "无法判定目标的来源仓库，跳过同步（避免把管理源全量复制）: $t"
            warn "  可用 'install --repo <repo> -t $t' 重建记录"
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
    # 圈定同步范围：只同步本次安装源（REPOS）的 skill
    set_sync_scope "${REPOS[@]}"
    if [ -z "$SYNC_NAMES" ]; then
        warn "同步范围为 0：管理源中没有匹配安装源（${REPOS[*]}）的 skill，已跳过同步"
        warn "  管理源是多仓库共享池，全量同步会把其他仓库的 skill 复制到目标；可用 'list --repo <repo>' 检查"
    else
        info "同步到目标目录（范围: $(scope_count) 个 skill · 来源 ${REPOS[*]}）..."
        for t in "${TARGETS[@]}"; do
            mkdir -p "$t"
            sync_to_target "$t"
            # 记录/合并该目标的来源仓库（供 update / prune 圈定范围）
            record_target "$t" "${REPOS[@]}"
            echo "  [SYNC] $t"
        done

        echo ""
        info "已安装并同步到 ${#TARGETS[@]} 个目标"
    fi
    info "管理命令: update（更新）/ remove <names>（删除）/ prune（清理）/ list（查看）"
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

    # 同步范围：
    #   显式指定 --repo / -n 时 = 该范围（对本次涉及的目标统一生效）
    #   否则 = 各目标自己的来源记录（无记录则反查自愈；判定不出则跳过，不做全量兜底）
    local explicit_scope=0
    if [ "$REPOS_SPECIFIED" = "1" ] || [ -n "$NAME_FILTER" ]; then
        explicit_scope=1
        set_sync_scope "${repos[@]}"
    fi

    echo ""
    info "同步到目标目录..."
    if [ ${#TARGETS[@]} -gt 0 ]; then
        # -t 指定了目标，只同步这些
        for t in "${TARGETS[@]}"; do
            mkdir -p "$t"
            if [ "$explicit_scope" = "0" ] && ! scope_for_target "$t"; then
                warn "无法判定目标的来源仓库，跳过同步（避免把管理源全量复制）: $t"
                warn "  可用 'install --repo <repo> -t $t' 重建记录"
                continue
            fi
            if [ -z "$SYNC_NAMES" ]; then
                warn "同步范围为 0：管理源中没有匹配（${repos[*]}${NAME_FILTER:+ · -n $NAME_FILTER}）的 skill，跳过: $t"
                continue
            fi
            sync_to_target "$t"
            record_target "$t"
            echo "  [SYNC] $t"
        done
    else
        # 未指定 -t，同步所有已记录目标（显式范围统一适用，否则按各目标记录）
        sync_all_recorded "$explicit_scope"
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

    # 兜底：npx skills remove 在 lock 与内部集合漂移时可能静默失败（退出码仍为 0），
    # 需主动校验并清理 lock 中残留条目 + 管理源目录，避免 list 仍显示、update 复活。
    # node 退出码：0=有残留条目，1=lock 中已无该条目（视为干净）
    local stale=""
    for name in $names; do
        if LOCK_FILE="$LOCK_FILE" NAME="$name" node -e '
const fs=require("fs");
const d=JSON.parse(fs.readFileSync(process.env.LOCK_FILE,"utf8"));
process.exit(d.skills && d.skills[process.env.NAME] ? 0 : 1);
'; then
            stale="$stale $name"
        fi
    done
    if [ -n "$stale" ]; then
        warn "npx 未删除 lock 条目（状态漂移），手动兜底清理:$stale"
        LOCK_FILE="$LOCK_FILE" STALE_NAMES="${stale# }" node -e '
const fs=require("fs");
const f=process.env.LOCK_FILE;
const d=JSON.parse(fs.readFileSync(f,"utf8"));
for(const n of process.env.STALE_NAMES.split(" ")){ delete d.skills[n]; }
fs.writeFileSync(f, JSON.stringify(d, null, 2) + "\n");
'
        for name in $stale; do
            rm -rf "${MANAGE_SKILLS_DIR:?}/$name" 2>/dev/null || true
        done
    fi

    echo ""
    info "同步删除到所有已记录目标..."
    # 因 sync_to_target 为增量同步（不删多余文件），此处显式删除目标中对应的 skill 目录
    while IFS= read -r t; do
        [ -z "$t" ] && continue
        [ ! -d "$t" ] && continue
        local dest
        dest="$(target_dest "$t")"
        for name in $names; do
            rm -rf "${dest:?}/$name" 2>/dev/null || true
        done
    done < <(get_recorded_targets)
    # 此处不再全量重同步：管理源是多仓库共享池，全量同步会把池里其他仓库的
    # skill 复制进这些目标（删除已在上面的循环中逐目标完成）
    echo ""
    info "删除完成"
}

# ============================================================
# 清理：删除目标中"安装器管理过、但不属于该目标来源范围"的 skill
# ============================================================
# 用于修复历史污染（早期版本按全量复制，目标里混进了其他仓库的 skill）。
# 只处理 lock 中登记过的 skill（＝安装器管理过的），手工新增目录一律保留；
# 默认预演只列出，加 -y 才真正删除；判定不出来源则拒绝执行（避免误删）。
do_prune() {
    ensure_manage_dir
    [ ! -f "$LOCK_FILE" ] && error "管理源为空，无判定依据。请先 install。"

    local targets=()
    resolve_targets
    if [ ${#TARGETS[@]} -gt 0 ]; then
        targets=("${TARGETS[@]}")
    else
        while IFS= read -r t; do
            [ -n "$t" ] && targets+=("$t")
        done < <(get_recorded_targets)
    fi
    [ ${#targets[@]} -eq 0 ] && error "未指定目标（-t <path>），且无已记录目标"

    echo "🧹 skill-install.sh prune"
    echo "   管理目录: $MANAGE_DIR"
    echo "   目标数量: ${#targets[@]}"
    echo "   模式: $([ "$PRUNE_APPLY" = "1" ] && echo "执行删除" || echo "预演（仅列出，加 -y 执行）")"
    echo ""

    # 期望来源：显式 --repo 时以它为准（可纠正老记录/被污染记录里的来源），
    # 否则按该目标自己的记录（无记录则反查自愈）
    local explicit=0
    if [ "$REPOS_SPECIFIED" = "1" ]; then
        explicit=1
    fi

    local map
    map="$(lock_name_sources)"

    local t dest repos name n s src kept
    local total_removed=0 total_targets=0
    for t in "${targets[@]}"; do
        dest="$(target_dest "$t")"
        if [ ! -d "$dest" ]; then
            warn "目标目录不存在，跳过: $t"
            continue
        fi
        if [ "$explicit" = "1" ]; then
            repos="${REPOS[*]}"
            set_sync_scope "${REPOS[@]}"
            if [ -z "$SYNC_NAMES" ]; then
                warn "指定的仓库（$repos）在管理源中没有匹配的 skill，跳过: $t"
                continue
            fi
        else
            repos="$(resolve_target_repos "$t")"
            if [ -z "$repos" ]; then
                warn "无法判定目标的来源仓库，跳过（避免误删）: $t"
                warn "  可用 'prune -t <目标> --repo <期望仓库>' 指定期望来源后再清理"
                continue
            fi
            set_sync_scope $repos
        fi
        total_targets=$((total_targets + 1))
        local removed=0
        echo "  $dest（保留来源: $repos）"
        for name in $(ls -1 "$dest" 2>/dev/null); do
            [ -d "$dest/$name" ] || continue
            # 只清理 lock 中登记过的 skill（安装器管理过的），手工目录一律保留
            src=""
            while IFS=$'\t' read -r n s; do
                if [ "$n" = "$name" ]; then
                    src="$s"
                    break
                fi
            done <<< "$map"
            [ -n "$src" ] || continue
            # 属于该目标来源范围 → 保留
            case " $SYNC_NAMES " in
                *" $name "*) continue ;;
            esac
            if [ "$PRUNE_APPLY" = "1" ]; then
                rm -rf "${dest:?}/$name" 2>/dev/null || true
                echo "    [DEL]  $name  （来源: $src）"
            else
                echo "    [待删] $name  （来源: $src）"
            fi
            removed=$((removed + 1))
        done
        [ "$removed" = "0" ] && echo "    （无外来 skill）"
        total_removed=$((total_removed + removed))
        # 显式指定期望来源时同步纠正记录（预演阶段只提示，-y 才写）
        if [ "$explicit" = "1" ]; then
            if [ "$PRUNE_APPLY" = "1" ]; then
                set_target_repos "$t" "${REPOS[@]}"
                echo "    [记录] 该目标来源已更新为: $repos"
            else
                echo "    [记录] 加 -y 时会把该目标来源更新为: $repos"
            fi
        fi
    done

    echo ""
    if [ "$PRUNE_APPLY" = "1" ]; then
        info "已从 $total_targets 个目标清理 $total_removed 个不属于其来源范围的 skill"
    else
        info "预演：$total_targets 个目标共 $total_removed 个外来 skill 待清理（确认后加 -y 执行）"
        if [ "$total_removed" = "0" ] && [ "$explicit" = "0" ]; then
            info "提示：若目标里混有历史污染、但反查把它算成了'目标自己的来源'，"
            info "  可用 'prune -t <目标> --repo <期望仓库> -y' 显式指定期望来源后再清理"
        fi
    fi
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
    prune)   do_prune ;;
    list)    do_list ;;
    *)       error "未知操作: $ACTION" ;;
esac

echo ""
echo "✅ 完成"