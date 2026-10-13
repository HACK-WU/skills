#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backend-index 扫描器 v2（**模块级**）：从后端源码提取「模块 ↔ 目录 ↔ 入口 ↔ 依赖 ↔ 数据表」。

v2 相对 v1（接口级）的变更 —— 依据见 SKILL.md「为什么是模块级」：
  - 索引对象：**模块**（不是接口）。接口只作模块属性（挂载前缀 + 接口数 + controller 文件），
    逐接口契约交给 expert-team（Step 8.3 写 ki `tags=api`）与 `implementation/05-接口.md`，不重复建设
  - 删除：方法级实现链（CQRS 跨文件续链 / 方法体配平 / 深度截断 / handler 归属）——噪声与维护成本大头
  - 保留强化：@Module 解析、typed repository → 表、全局与模块前缀、专家资产探测（.module-experts）
  - 新增：模块依赖图（含「被依赖」反查）、非 HTTP 入口（MQ/CQRS/定时任务）、--emit-tree 一键落盘

**分工纪律**：脚本只做穷举机械活（模块全集 / 前缀合成 / 依赖反查 / 表反查 / 一键重建），
任何语义判断（模块中文职责、专家关联确认、分组）留给 AI——见 SKILL.md 阶段 3。

设计口径与 scan_frontend.py 同源（双模式 / 新鲜度闸门 / 退出码族 / `[待确认]` 不猜），实现独立。

用法：
    python3 scan_backend.py --root <仓库根> [选项]
    python3 scan_backend.py --root <根> --dump-config              # 探测框架与约定
    python3 scan_backend.py --root <根> --emit-tree .fe-index/xxx  # 一条命令落盘整棵树
    python3 scan_backend.py --root <根> --check --index .fe-index/xxx

框架：NestJS（@Module/@Controller/@Get + TypeORM/Mongoose forFeature + CQRS/MQ）
      Django（apps.py/models.Model + urls.py include('app.urls') + DRF）
                       —— 混合仓库用 --framework 指定。
"""
import argparse

import fnmatch
import json
import os
import re
import subprocess
import sys
from datetime import date

VERSION = "2.0.0"
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "out", "output", "coverage",
             ".venv", "venv", "__pycache__", ".next", ".nuxt", "vendor", ".mypy_cache",
             ".pytest_cache", "migrations"}
TS_EXTS = (".ts", ".tsx", ".js", ".mjs", ".cjs")
PY_EXTS = (".py",)
MAX_FILE_BYTES = 2 * 1024 * 1024
PAIRS = {"(": ")", "{": "}", "[": "]"}
MAX_PENDING = 200


def eprint(*args):
    print(*args, file=sys.stderr)


def to_rel(path, root):
    rel = os.path.relpath(path, root)
    return rel.replace(os.sep, "/")


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(MAX_FILE_BYTES)
    except OSError:
        return ""


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def match_glob(rel, pattern):
    """`**/` 按 gitignore 语义可匹配零层目录（与 frontend 脚本同口径）。"""
    if fnmatch.fnmatch(rel, pattern):
        return True
    if "**/" in pattern:
        return fnmatch.fnmatch(rel, pattern.replace("**/", ""))
    return False


def walk_files(root, includes, excludes, exts):
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in filenames:
            if not name.endswith(exts):
                continue
            if name.endswith(".spec.ts") or name.endswith(".test.ts") or name.startswith("test_"):
                continue
            full = os.path.join(dirpath, name)
            rel = to_rel(full, root)
            if includes and not any(match_glob(rel, pat) for pat in includes):
                continue
            if excludes and any(match_glob(rel, pat) for pat in excludes):
                continue
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            result.append(full)
    return result


def kebab(name):
    """ChatModule → chat（slug：稳定、可读、与前端 slug 同风格）。"""
    name = re.sub(r"(?:Module|Config)$", "", name or "")
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name)
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s or "module"


def snake(name):
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name or "")
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()


# ---------------------------------------------------------------------------
# 通用：配平扫描 / 注释剥离
# ---------------------------------------------------------------------------
def pair_scan(text, i):
    """text[i] ∈ ([{ 时返回配对闭合符号下标（跳过字符串/注释/嵌套），失败 -1。"""
    if i >= len(text) or text[i] not in PAIRS:
        return -1
    open_ch, close_ch = text[i], PAIRS[text[i]]
    depth, quote = 0, None
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "`'\"":
            quote = ch
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = len(text) if j < 0 else j
            continue
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = len(text) if j < 0 else j + 2
            continue
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def balanced_scan(text, i):
    return pair_scan(text, i)


def strip_comments(text):
    """剥离注释（尊重字符串，避免把 'https://x' 当行注释截断）。"""
    out = []
    i, n, quote = 0, len(text), None
    while i < n:
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == "\\":
                out.append(text[i + 1:i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "`'\"":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# 通用正则
# ---------------------------------------------------------------------------
RE_CLASS = re.compile(
    r"""(?m)^[ \t]*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)"""
    r"""(?:\s*<[^>{}]*>)?(?:\s+extends\s+(?P<base>[A-Za-z_$][\w$]*)"""
    r"""(?:\s*<[^>{}]*>)?)?""")

# --- NestJS ---
RE_MODULE_DEC = re.compile(r"""@Module\s*\(\s*\{""")
RE_CTRL = re.compile(r"""@Controller\(\s*(?:['"`](?P<path>[^'"`]*)['"`])?\s*\)""")
RE_ROUTE = re.compile(
    r"""@(?P<verb>Get|Post|Put|Patch|Delete|Head|Options|All)\(\s*(?:['"`](?P<path>[^'"`]*)['"`])?\s*\)""")
RE_GUARD = re.compile(r"""@UseGuards\(\s*(?P<guards>[^)]*)\)""")
RE_ENTITY = re.compile(r"""@Entity\(\s*(?:['"`](?P<table>[^'"`]+)['"`])?\s*\)""")
RE_INJECT_REPO = re.compile(r"""@InjectRepository\(\s*(?P<entity>[A-Z][\w$]*)\s*\)""")
RE_INJECT_MODEL = re.compile(r"""@InjectModel\(\s*(?P<entity>[A-Z][\w$]*)\s*(?:,|\))""")
# `\b` 必需：否则 parseGithubRepository(url) / localizeRepository(x) 会误配出实体 url / x（实测假阳性）
RE_GET_REPO = re.compile(r"""\b(?:getRepository|Repository)\s*\(\s*(?P<entity>[A-Z][\w$]*)\s*\)""")
RE_REPO_TYPE = re.compile(r"""\bRepository\s*<\s*(?P<entity>[A-Z][\w$]*)\s*>""")
RE_INTERFACE = re.compile(r"""(?m)^[ \t]*(?:export\s+)?interface\s+(?P<name>[A-Za-z_$][\w$]*)""")
RE_FEATURE = re.compile(r"""([A-Za-z_$][\w$]*)\.forFeature\s*\(""")
RE_FORWARD_REF = re.compile(r"""forwardRef\s*\(\s*\(\s*\)\s*=>\s*([A-Za-z_$][\w$]*)""")
RE_TOKEN = re.compile(r"""\b([A-Z][\w$]*)\b""")
RE_PROCESSOR = re.compile(r"""@Processor\(\s*(?:['"`](?P<name>[^'"`]+)['"`])?""")
RE_HANDLER = re.compile(r"""@(?:Command|Query|Events)Handler\(\s*(?P<cls>[A-Za-z_$][\w$]*)""")
# 事件/命令发送：bus.execute(new X) / publish(new X) / send(new X) / dispatch(new X)
RE_BUS_SEND = re.compile(
    r"""\.\s*(?:execute|send|publish|dispatch)\s*\(\s*new\s+(?P<cls>[A-Za-z_$][\w$]*)""")
RE_INJECT_QUEUE = re.compile(r"""@InjectQueue\(\s*['"`](?P<name>[^'"`]+)['"`]""")
RE_CRON = re.compile(r"""@(?:Cron|Interval|Timeout)\s*\(""")
RE_SET_PREFIX = re.compile(r"""setGlobalPrefix\(\s*(?P<arg>[^,)]+)""")

# --- Django ---
RE_DJ_PATH = re.compile(r"""\b(?:re_)?path\(\s*[rf]?['"](?P<path>[^'"]*)['"]\s*,\s*(?P<target>[^,\n]+)""")
RE_DJ_INCLUDE = re.compile(r"""include\(\s*[rf]?['"](?P<mod>[^'"]+)['"]""")
RE_DJ_REGISTER = re.compile(r"""router\.register\(\s*r?['"](?P<prefix>[^'"]+)['"]\s*,\s*(?P<view>\w+)""")
RE_DJ_CLASS = re.compile(r"""(?m)^class\s+(?P<name>\w+)\s*\((?P<bases>[^)]*)\)\s*:""")
RE_DJ_DBTABLE = re.compile(r"""db_table\s*=\s*['"](?P<table>[\w.]+)['"]""")
RE_DJ_VIEW_DEC = re.compile(r"""@api_view\(\s*\[(?P<methods>[^\]]*)\]""")
RE_DJ_ACTION = re.compile(r"""@action\(""")
RE_DJ_APP_CONFIG = re.compile(r"""(?m)^class\s+(?P<name>\w+)\(\s*AppConfig\s*\)""")
RE_TOP_LEVEL = re.compile(r"(?m)^(?=\S)")   # 类体边界（缩进回到顶层的下一行）
RE_DJ_IMPORT = re.compile(r"""(?m)^\s*from\s+(?P<mod>[\w.]+)\s+import\s+(?P<names>\([^)]*\)|[^\n]+)""")
RE_DJ_GET_MODEL = re.compile(
    r"""get_model\(\s*['"](?P<app>[\w.]+)['"]\s*,\s*['"](?P<model>\w+)['"]""")
RE_DJ_SIGNAL = re.compile(r"""@receiver\(""")
RE_DJ_TASK = re.compile(r"""@(?:shared_task|app\.task|periodic_task)""")

FRONTEND_MARKERS = ("@angular/core", "from 'react'", 'from "react"', "from 'vue'",
                    'from "vue"', "vue-router", "@vue/", "from 'svelte'", "from 'sveltekit'")

# 框架/基础库模块：imports 里很常见，**不是**项目模块——不报「模块未解析」，只进 libs
FRAMEWORK_MODULES = {
    "TypeOrmModule", "MongooseModule", "SequelizeModule", "PrismaModule", "CqrsModule",
    "ConfigModule", "NestConfigModule", "JwtModule", "PassportModule", "CacheModule",
    "ScheduleModule", "BullModule", "HttpModule", "ServeStaticModule", "MulterModule",
    "RouterModule", "DiscoveryModule", "EventEmitterModule", "ThrottlerModule",
    "TerminusModule", "GraphQLModule", "MicroservicesModule", "WebsocketModule",
    "LoggerModule", "I18nModule", "TelegrafModule", "QueueModule", "RedisModule",
    "ElasticsearchModule", "OpenTelemetryModule", "MetricsModule", "CliModule",
}
RE_LIB_MODULE = re.compile(
    r"""^(?:TypeOrm|Mongoose|Sequelize|Prisma|Bull|Queue|Redis|Kafka|RabbitMQ|Grpc|"""
    r"""Elasticsearch|OpenSearch|GraphQL|Apollo|I18n|Swagger|OpenTelemetry|Passport|Jwt)""")

# 泛型类型参数常被 `Repository<T>` 一类写法误当实体名——不当实体处理
GENERIC_ENTITY_NAMES = {"T", "K", "V", "R", "E", "ID", "TEntity", "TResult", "TData",
                        "TModel", "TKey", "TValue", "TRecord", "Entity"}


def looks_frontend(text):
    """monorepo 里前后端同仓：NestJS 模式下必须排除 Angular/React/Vue 文件（同名类污染，实测 bug）。"""
    return any(marker in text for marker in FRONTEND_MARKERS)


def _names(raw):
    """拆 `AuthGuard, RolesGuard` 一类的守卫串为名字列表。"""
    out = []
    for part in re.split(r"[,\s]+", raw or ""):
        part = part.strip().strip("()")
        if not part or part in ("new", "true", "false"):
            continue
        if "(" in part:
            part = part.split("(")[0]
        out.append(part)
    return out


def resolve_global_prefix(files, texts):
    """解析全局路由前缀：支持字面量与「同文件 const 变量」两种写法。"""
    for path in files:
        text = texts.get(path, "")
        if not text or "setGlobalPrefix" not in text:
            continue
        m = RE_SET_PREFIX.search(text)
        if not m:
            continue
        arg = (m.group("arg") or "").strip()
        lit = re.match(r"""['"`](?P<p>[^'"`]*)['"`]""", arg)
        if lit:
            return lit.group("p")
        mv = re.search(r"""(?:const|let|var)\s+%s\s*=\s*['"`](?P<p>[^'"`]+)['"`]"""
                       % re.escape(arg), text)
        if mv:
            return mv.group("p")
        nearby = text[max(0, m.start() - 800):m.start()]
        cands = re.findall(r"""['"`](/[\w/-]+)['"`]""", nearby)
        if cands:
            return cands[-1]
    return ""


# ---------------------------------------------------------------------------
# NestJS：@Module 解析
# ---------------------------------------------------------------------------
def parse_module_options(raw):
    """从 `@Module({...})` 体内提取 imports/controllers/providers/exports 的数组原文。"""
    out = {}
    for key in ("imports", "controllers", "providers", "exports"):
        m = re.search(r"""(?:^|[\s,{])%s\s*:\s*\[""" % key, raw)
        if not m:
            continue
        start = raw.find("[", m.start())
        end = pair_scan(raw, start)
        out[key] = raw[start + 1:end if end > 0 else len(raw)]
    return out


def options_tokens(raw, skip_schema=True):
    """从选项数组文本提取 PascalCase 标识符（类/模块/token），返回 (tokens, entities)。

    覆盖 `[A, forwardRef(() => B), X.forFeature([E1, E2]), {name: E.name, schema: ESchema}]`。
    小写开头的对象键（provide/name/schema/useClass）天然被 PascalCase 过滤掉。
    """
    clean = strip_comments(raw or "")
    tokens, entities, feature_raws = [], [], []
    for m in RE_FORWARD_REF.finditer(clean):
        tokens.append(m.group(1))
    for m in RE_FEATURE.finditer(clean):
        tokens.append(m.group(1))
        lp = clean.find("(", m.end() - 1)
        rp = pair_scan(clean, lp)
        inner = clean[lp + 1:rp if rp > 0 else len(clean)]
        feature_raws.append(inner)
        for t in RE_TOKEN.finditer(inner):
            name = t.group(1)
            if skip_schema and name.endswith("Schema"):
                continue
            entities.append(name)
    rest = RE_FORWARD_REF.sub(" ", clean)
    rest = re.sub(r"""[A-Za-z_$][\w$]*\.forFeature\s*\([^)]*\)""", " ", rest)
    for m in RE_TOKEN.finditer(rest):
        tokens.append(m.group(1))
    seen, ordered = set(), []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    seen_e, ordered_e = set(), []
    for t in entities:
        if t not in seen_e:
            seen_e.add(t)
            ordered_e.append(t)
    return ordered, ordered_e, feature_raws


def parse_nest_module_file(text):
    """返回文件内的 @Module 定义：class / options 原文 / 行号。"""
    m = RE_MODULE_DEC.search(text)
    if not m:
        return None
    brace = text.find("{", m.start())
    end = pair_scan(text, brace)
    if end < 0:
        return None
    nxt = RE_CLASS.search(text, end)
    cls = nxt.group("name") if (nxt and nxt.start() - end < 400) else ""
    if not cls:
        first = RE_CLASS.search(text)
        cls = first.group("name") if first else ""
    return {"class": cls, "options": parse_module_options(text[brace + 1:end]),
            "line": line_of(text, m.start())}


# ---------------------------------------------------------------------------
# 符号表（类 → 文件 / 实体 → 表）
# ---------------------------------------------------------------------------
class Symbols(object):
    """类名 → 文件、实体 → 表 的全局索引。

    monorepo 同名类常见（前后端同名 service），因此一个类名可对应多个文件：解析时优先取
    与来源同源（前两段路径相同）的候选，取不到退回第一个候选并标注 `[同名类]`，绝不静默取错。
    """

    def __init__(self, root=None):
        self.root = root or ""
        self.class_files = {}
        self.entity_table = {}
        self.interfaces = set()

    def add(self, path, text):
        for m in RE_CLASS.finditer(text):
            name = m.group("name")
            self.class_files.setdefault(name, [])
            if path not in self.class_files[name]:
                self.class_files[name].append(path)
        for m in RE_INTERFACE.finditer(text):
            self.interfaces.add(m.group("name"))
        for m in RE_ENTITY.finditer(text):
            # 窗口 1500：@Entity 与 class 之间可能夹着 @Index/@ApiProperty 等装饰器
            # （实测 model-access-request.entity.ts 相隔 13 行 > 旧阈值 400 → 漏检）
            nxt = RE_CLASS.search(text, m.end())
            if not (nxt and nxt.start() - m.end() < 1500):
                continue
            cls = nxt.group("name")
            if cls in self.entity_table:
                continue
            self.entity_table[cls] = {
                "table": m.group("table") or snake(cls),
                "declared": bool(m.group("table")),
                "file": path,
            }

    def _homing(self, path):
        rel = to_rel(path, self.root) if self.root else path
        return "/".join(rel.split("/")[:2])

    def resolve_class(self, name, from_file=""):
        """按名字找类的定义文件；同名多候选时优先同源。返回 (file, ambiguous)。"""
        cands = self.class_files.get(name)
        if not cands:
            return None, False
        if len(cands) == 1:
            return cands[0], False
        src = self._homing(from_file)
        same = [c for c in cands if self._homing(c) == src]
        if same:
            return same[0], False
        return cands[0], True


class Result(object):
    def __init__(self):
        self.modules = []      # 模块卡
        self.tables = []       # 表 → 模块（反向）
        self.experts = []      # 专家资产探测结果
        self.stats = {}
        self.pending = []
        self._pending_seen = set()
        self._pending_truncated = False
        self._default_named = []   # 未显式声明表名的实体（聚合后进待确认）

    def note_pending(self, ptype, loc, content, reason, dedupe_extra=""):
        key = (ptype, loc, dedupe_extra)
        if key in self._pending_seen:
            return
        if len(self.pending) >= MAX_PENDING:
            # 不静默丢弃：截断本身要留痕（否则"待确认 N 条"会被误读成全部）
            if not self._pending_truncated:
                self._pending_truncated = True
                self.pending.append({
                    "type": "待确认已截断", "loc": "-",
                    "content": "超过上限 %d 条" % MAX_PENDING,
                    "reason": "收窄 --include 或分应用建库后重跑，可减少待确认项"})
            return
        self._pending_seen.add(key)
        self.pending.append({"type": ptype, "loc": loc, "content": content, "reason": reason})


# ---------------------------------------------------------------------------
# 归属：目录最长前缀 + 声明文件
# ---------------------------------------------------------------------------
def assign_ownership(files, module_dirs):
    """按「最长模块目录前缀」给文件定归属（嵌套模块各拿自己的文件，不互相吞并）。"""
    dirs = sorted(set(module_dirs), key=lambda d: -len(d))
    owners = {}
    for path in files:
        for d in dirs:
            if path.startswith(d + os.sep):
                owners.setdefault(d, []).append(path)
                break
    return owners


def scan_nestjs(root, files, texts, opts, result):
    symbols = Symbols(root)
    for path in files:
        if path.endswith(TS_EXTS):
            symbols.add(path, texts.get(path, ""))

    # 常量数组索引：`controllers: [...Controllers]` / `imports: [...Modules]` 的展开来源
    # （实测：packages/auth/src/social-auth.module.ts 的 controllers: [...Controllers]，
    #   Controllers 定义在同包 internal.ts 的 `export const Controllers = [...]`）
    const_arrays = {}
    for path in files:
        if not path.endswith(TS_EXTS):
            continue
        text = texts.get(path, "")
        if "const" not in text:
            continue
        for m in re.finditer(
                r"""(?m)^[ \t]*(?:export\s+)?const\s+(?P<name>[A-Za-z_$][\w$]*)"""
                r"""\s*(?::[^=\n]+)?=\s*\[""", text):
            start = text.find("[", m.end() - 1)
            end = pair_scan(text, start)
            if end < 0:
                continue
            const_arrays.setdefault(m.group("name"), []).append((path, text[start + 1:end]))

    # 已声明的常量名（用于区分「定义不在扫描范围」与「定义不是简单数组」）
    const_declared = set()
    for path in files:
        if path.endswith(TS_EXTS):
            const_declared.update(re.findall(
                r"""(?m)^[ \t]*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*[:=]""",
                texts.get(path, "")))

    def expand_array(raw, from_file, depth=0):
        """展开选项数组（含 `...X` 常量数组展开）→ (tokens, entities)。展开不到就如实标注。"""
        tokens, entities, _raws = options_tokens(raw)
        spreads = set(re.findall(r"""\.\.\.\s*([A-Za-z_$][\w$]*)""", strip_comments(raw)))
        out_tokens = [t for t in tokens if t not in spreads]
        out_entities = [e for e in entities if e not in spreads]
        for name in spreads:
            cands = const_arrays.get(name) or []
            if not cands:
                if depth == 0:
                    reason = ("`...%s` 的定义不是简单数组（条件表达式/函数返回等），未展开" % name
                              if name in const_declared else
                              "`...%s` 的定义不在扫描范围（跨包/外部依赖？），未展开" % name)
                    result.note_pending("展开未解析", name, to_rel(from_file, root), reason,
                                        dedupe_extra=to_rel(from_file, root))
                continue
            # 展开优先级：同目录 → **本模块目录树内唯一命中** → 同包唯一命中；否则不猜。
            # 实测：每个模块各有一个 `commands/handlers/index.ts` 里的同名 `CommandHandlers`
            # 数组（25 个同名候选），盲选第一个会把别模块的 handler 算进本模块。
            base_dir = os.path.dirname(from_file)
            same_dir = [c for c in cands if os.path.dirname(c[0]) == base_dir]
            tree = [c for c in cands if c[0].startswith(base_dir + os.sep)]
            pkg = [c for c in cands if symbols._homing(c[0]) == symbols._homing(from_file)]
            pick = None
            if same_dir:
                idx = [c for c in same_dir if os.path.basename(c[0]).startswith("index.")]
                pick = (idx or same_dir)[0]
            elif len(tree) == 1:
                pick = tree[0]
            elif len(pkg) == 1:
                pick = pkg[0]
            if pick is None:
                if depth == 0:
                    result.note_pending(
                        "展开未解析", name, to_rel(from_file, root),
                        "`...%s` 有 %d 个同名定义（各模块各有一个），无法确定归属，不猜未展开"
                        % (name, len(cands)), dedupe_extra=to_rel(from_file, root))
                continue
            if depth < 3:
                sub_t, sub_e = expand_array(pick[1], pick[0], depth + 1)
                out_tokens += [t for t in sub_t if t not in out_tokens]
                out_entities += [e for e in sub_e if e not in out_entities]
        return out_tokens, out_entities

    module_defs = []
    for path in files:
        if not path.endswith(TS_EXTS):
            continue
        text = texts.get(path, "")
        if "@Module" not in text:
            continue
        parsed = parse_nest_module_file(text)
        if parsed and parsed["class"]:
            module_defs.append((path, parsed))

    if not module_defs:
        result.note_pending("未找到模块", "-", "",
                            "没有解析到 @Module 声明（检查 --include 是否覆盖后端源码）")
        return

    owners = assign_ownership(files, [os.path.dirname(p) for p, _ in module_defs])
    name_counts = {}
    for _p, parsed in module_defs:
        name_counts[parsed["class"]] = name_counts.get(parsed["class"], 0) + 1
    used_slugs = set()

    # 事件/命令边索引（不经 imports 的跨模块耦合）：
    #   CQRS：@CommandHandler(X) 的承载模块目录 ← X 被哪个模块 execute/publish
    #   MQ  ：@Processor('q') 的消费模块目录 ← 'q' 被哪个模块 @InjectQueue
    # 这类耦合在 imports 里看不见，但"改一个 Command/队列消息"照样影响对方模块。
    handler_dir = {}
    queue_dir = {}
    for path, parsed in module_defs:
        d = os.path.dirname(path)
        for f in owners.get(d, []):
            text = texts.get(f, "")
            if not text:
                continue
            for m in RE_HANDLER.finditer(text):
                handler_dir.setdefault(m.group("cls"), d)
            for m in RE_PROCESSOR.finditer(text):
                if m.group("name"):
                    queue_dir.setdefault(m.group("name"), d)

    def is_module_class(name):
        for f in symbols.class_files.get(name) or []:
            base = os.path.basename(f)
            if base.endswith(".module.ts") or base.endswith(".module.js"):
                return True
        return False

    for path, parsed in module_defs:
        cls = parsed["class"]
        dirpath = os.path.dirname(path)
        slug = kebab(cls)
        if name_counts[cls] > 1:      # 同名模块（monorepo 各包一个）→ 加父目录区分
            slug = "%s--%s" % (slug, kebab(os.path.basename(os.path.dirname(dirpath)) or "root"))
        base_slug, n = slug, 2
        while slug in used_slugs:
            slug, n = "%s-%d" % (base_slug, n), n + 1
        used_slugs.add(slug)

        opts_raw = parsed["options"]
        import_names, feature_entities = expand_array(opts_raw.get("imports", ""), path)
        ctrl_names, _ctrl_e = expand_array(opts_raw.get("controllers", ""), path)
        prov_names, _prov_e = expand_array(opts_raw.get("providers", ""), path)
        export_names, _exp_e = expand_array(opts_raw.get("exports", ""), path)
        feature_entities = [e for e in feature_entities
                            if e not in GENERIC_ENTITY_NAMES and len(e) > 2]
        # forFeature([...Entities]) 形态：把数组容器名替换为其成员，再做泛型过滤
        expanded_entities = []
        for e in feature_entities:
            if e in const_arrays:
                sub_tokens, _e2 = expand_array(const_arrays[e][0][1], const_arrays[e][0][0])
                for t in sub_tokens:
                    if t not in expanded_entities:
                        expanded_entities.append(t)
                continue
            if e not in expanded_entities:
                expanded_entities.append(e)
        feature_entities = [e for e in expanded_entities
                            if e not in GENERIC_ENTITY_NAMES and len(e) > 2]

        owned = list(owners.get(dirpath, []))
        declared = []
        for name in ctrl_names + prov_names:
            f, amb = symbols.resolve_class(name, path)
            if not f:
                continue
            if amb:
                # 同名类且无同源候选 → **不猜**：一旦猜错，会把别的包的文件算进本模块
                # （实测：误把 auth.trial.handler.ts 算进 AIModule → 54 个模块"发送"同一个 Command）
                result.note_pending("同名类未归属", name, to_rel(path, root),
                                    "providers/controllers 声明的类在全仓有多个同名定义且无同源候选，"
                                    "不猜归属（该文件未计入本模块）")
                continue
            if f not in owned and f not in declared:
                declared.append(f)
        scope_files = owned + declared

        # --- 控制器：挂载前缀 + 接口数（模块属性，不逐接口建表）---
        controllers, seen_ctrl = [], set()

        def add_controller(f, cname=""):
            if not f or f in seen_ctrl:
                return
            text = texts.get(f, "")
            cm = RE_CTRL.search(text)
            if not cm:
                return
            seen_ctrl.add(f)
            route_hits = list(RE_ROUTE.finditer(text))
            hints = []
            for rm in route_hits:
                seg = (rm.group("path") or "").strip("/")
                head = seg.split("/")[0] if seg else ""
                if head and head not in hints:
                    hints.append(head)
            controllers.append({
                "file": to_rel(f, root), "class": cname,
                "prefix": cm.group("path") or "",
                "routes": len(route_hits),
                "path_hints": hints[:5],
                "line": line_of(text, cm.start()),
            })

        for name in ctrl_names:
            f, amb = symbols.resolve_class(name, path)
            if not f:
                result.note_pending("控制器未解析", name, to_rel(path, root),
                                    "controllers 声明的类未在扫描范围内找到（共享包/动态模块？）")
                continue
            if amb:
                # 同上：同名类歧义不猜（跳过已由上一步留痕，这里不重复记）
                continue
            add_controller(f, name)
        for f in scope_files:
            if "@Controller" in texts.get(f, ""):
                add_controller(f)
        total_routes = sum(c["routes"] for c in controllers)

        # --- 数据表：forFeature 声明 + 归属文件里的仓储用法 ---
        table_uses = {}

        def note_entity(entity, via, ev_file=None, ev_line=0):
            if entity in GENERIC_ENTITY_NAMES or len(entity) <= 2:
                return          # 泛型参数（Repository<T>）不是实体
            info = symbols.entity_table.get(entity)
            if info is None:
                where = to_rel(ev_file, root) if ev_file else to_rel(path, root)
                if entity in symbols.interfaces:
                    # 实测：`@InjectRepository(IEmail)` —— 用接口 token 注入自定义 provider，不是 TypeORM 实体
                    result.note_pending("非实体 token（接口）", entity,
                                        "%s（来自 %s）" % (where, via),
                                        "注入 token 是接口/类型而非实体 → 无表可映射（自定义 provider）")
                else:
                    result.note_pending("表名未解析", entity, "%s（来自 %s）" % (where, via),
                                        "实体未找到 @Entity 声明（跨包实体/动态注册？），不猜表名")
                return
            key = info["table"]
            item = table_uses.setdefault(key, {
                "table": key, "declared": info["declared"], "entities": [],
                "uses": 0, "via": via, "evidence": ""})
            item["uses"] += 1
            if entity not in item["entities"]:
                item["entities"].append(entity)
            if not item["evidence"] and ev_file:
                item["evidence"] = "%s:%d" % (to_rel(ev_file, root), ev_line)
            if not info["declared"] and key not in result._default_named:
                result._default_named.append(key)

        for entity in feature_entities:
            note_entity(entity, "@Module imports forFeature")
        for f in scope_files:
            text = texts.get(f, "")
            if not text:
                continue
            for m in RE_INJECT_REPO.finditer(text):
                note_entity(m.group("entity"), "@InjectRepository", f, line_of(text, m.start()))
            for m in RE_INJECT_MODEL.finditer(text):
                note_entity(m.group("entity"), "@InjectModel", f, line_of(text, m.start()))
            for m in RE_GET_REPO.finditer(text):
                note_entity(m.group("entity"), "getRepository", f, line_of(text, m.start()))
            for m in RE_REPO_TYPE.finditer(text):
                if m.group("entity") != "any":
                    note_entity(m.group("entity"), "Repository<T>", f, line_of(text, m.start()))

        # --- 依赖：imports 命中其他模块（反向「被依赖」在最后统一回填）---
        deps, libs = [], []
        for name in import_names:
            if name == cls:
                continue
            if is_module_class(name):
                deps.append(name)
                continue
            if name.endswith("Module"):
                if name in FRAMEWORK_MODULES or RE_LIB_MODULE.match(name):
                    if name not in libs:
                        libs.append(name)      # 框架/基础库模块：只记依赖，不报未解析
                    continue
                result.note_pending("模块未解析", name, to_rel(path, root),
                                    "imports 里的模块类未在扫描范围内找到（共享包/动态模块？）")
            if name not in libs:
                libs.append(name)

        # --- 非 HTTP 入口 / 守卫（按 scope_files：含被本模块组合进来的外部文件）---
        mq, cqrs, tasks, guards = [], [], 0, []
        for f in scope_files:
            text = texts.get(f, "")
            if not text:
                continue
            for m in RE_PROCESSOR.finditer(text):
                mq.append(m.group("name") or "(匿名队列)")
            for m in RE_HANDLER.finditer(text):
                cqrs.append(m.group("cls"))
            tasks += len(RE_CRON.findall(text))
            for m in RE_GUARD.finditer(text):
                for g in _names(m.group("guards")):
                    if g not in guards:
                        guards.append(g)
        # --- 事件/命令边：只取**模块自有文件**（每条边都能用 `grep 模块目录` 复验）。
        # 被组合进来的外部文件里的发送归其 home 模块，否则会出现"54 个模块都发送同一个命令"式虚报。
        cqrs_targets, mq_targets = {}, {}
        for f in owned:
            text = texts.get(f, "")
            if not text:
                continue
            for m in RE_BUS_SEND.finditer(text):
                tgt = handler_dir.get(m.group("cls"))
                if tgt and tgt != dirpath:
                    cqrs_targets.setdefault(tgt, set()).add(m.group("cls"))
            for m in RE_INJECT_QUEUE.finditer(text):
                tgt = queue_dir.get(m.group("name"))
                if tgt and tgt != dirpath:
                    mq_targets.setdefault(tgt, set()).add(m.group("name"))
        line_count = sum(texts.get(f, "").count("\n") + 1 for f in scope_files)

        result.modules.append({
            "name": cls, "slug": slug, "kind": "nestjs",
            "dir": to_rel(dirpath, root) or ".",
            "class_file": to_rel(path, root), "line": parsed["line"],
            "files": len(scope_files), "owned_files": len(owned), "lines": line_count,
            "controllers": controllers,
            "prefixes": sorted({c["prefix"] for c in controllers if c["prefix"]}),
            "routes": total_routes,
            "deps": sorted(set(deps)), "dependents": [],
            "libs": libs[:12], "exports": export_names,
            "tables": sorted(table_uses.values(), key=lambda x: -x["uses"]),
            "guards": guards[:8],
            "entries": {"mq": mq, "cqrs": cqrs, "tasks": tasks},
            "event_edges": [], "event_edges_in": [],
            "_dirpath": dirpath, "_cqrs_targets": cqrs_targets, "_mq_targets": mq_targets,
            "experts": [],
            "file_list": [to_rel(f, root) for f in scope_files],
            "confidence": "🟢",
        })

    resolve_event_edges(result)

    build_dependents(result)
    build_tables_reverse(result)
    for table in result._default_named[:20]:
        result.note_pending("默认命名表名（待确认）", table, "",
                            "实体未显式声明 @Entity('表名')，按类名推断（TypeORM 默认命名）——建议核对")
    result.stats["default_named_tables"] = len(result._default_named)


def build_dependents(result):
    by_name = {m["name"]: m for m in result.modules}
    for m in result.modules:
        m["dependents"] = []
    for m in result.modules:
        for dep in m["deps"]:
            target = by_name.get(dep)
            if target and m["name"] not in target["dependents"]:
                target["dependents"].append(m["name"])
    for m in result.modules:
        m["dependents"] = sorted(m["dependents"])


def resolve_event_edges(result):
    """把事件/命令边的目标（模块目录）解析为模块名，并算反向（谁给我发命令/消息）。

    这类耦合不走 `imports`（CQRS 总线 / MQ 队列按类型与队列名解耦），
    但"改一个 Command 或消费的消息结构"照样影响对方模块——必须入图。
    """
    dir_to_name = {}
    for m in result.modules:
        d = m.pop("_dirpath", None)
        if d:
            dir_to_name[d] = m["name"]
    reverse = {}
    for m in result.modules:
        edges = []
        for tgt_dir, names in (m.pop("_cqrs_targets", None) or {}).items():
            tname = dir_to_name.get(tgt_dir)
            if tname and tname != m["name"]:
                edges.append({"kind": "cqrs", "target": tname,
                              "names": sorted(names)[:6], "count": len(names)})
        for tgt_dir, names in (m.pop("_mq_targets", None) or {}).items():
            tname = dir_to_name.get(tgt_dir)
            if tname and tname != m["name"]:
                edges.append({"kind": "mq", "target": tname,
                              "names": sorted(names)[:6], "count": len(names)})
        m["event_edges"] = sorted(edges, key=lambda x: (x["kind"], x["target"]))
        for e in m["event_edges"]:
            reverse.setdefault(e["target"], {}).setdefault(m["name"], set()).update(e["names"])
    for m in result.modules:
        m.setdefault("event_edges", [])
        m["event_edges_in"] = [
            {"source": src, "names": sorted(names)[:6], "count": len(names)}
            for src, names in sorted((reverse.get(m["name"]) or {}).items())]
    result.stats["event_edges"] = sum(len(m["event_edges"]) for m in result.modules)


def build_tables_reverse(result):
    table_map = {}
    for m in result.modules:
        for t in m["tables"]:
            row = table_map.setdefault(t["table"], {"table": t["table"], "modules": []})
            row["modules"].append({"slug": m["slug"], "name": m["name"], "uses": t["uses"],
                                   "declared": t["declared"], "via": t["via"]})
    out = []
    for table, row in sorted(table_map.items()):
        row["modules"].sort(key=lambda x: -x["uses"])
        row["module_count"] = len(row["modules"])
        row["uses"] = sum(x["uses"] for x in row["modules"])
        row["declared"] = all(x["declared"] for x in row["modules"])
        out.append(row)
    out.sort(key=lambda x: (-x["module_count"], -x["uses"], x["table"]))
    result.tables = out


# ---------------------------------------------------------------------------
# Django：模块 = app
# ---------------------------------------------------------------------------
def scan_django(root, files, texts, opts, result):
    py_files = [p for p in files if p.endswith(PY_EXTS)]
    apps = {}
    for path in py_files:
        base, dirpath = os.path.basename(path), os.path.dirname(path)
        if base == "apps.py":
            entry = apps.setdefault(dirpath, {"dir": dirpath, "config": ""})
            m = RE_DJ_APP_CONFIG.search(texts.get(path, ""))
            if m:
                entry["config"] = m.group("name")
    # 无 apps.py 的老项目兜底：models.py + (views.py|urls.py) 且目录名不是 models/
    # （只认 models.py 会把 packages/xxx/models/ 这种子包误判成 app——实测 bk-monitor 误判 9 个）
    for path in py_files:
        if os.path.basename(path) != "models.py":
            continue
        dirpath = os.path.dirname(path)
        if dirpath in apps or os.path.basename(dirpath) == "models":
            continue
        if not os.path.isfile(os.path.join(dirpath, "__init__.py")):
            continue
        if (os.path.isfile(os.path.join(dirpath, "views.py"))
                or os.path.isfile(os.path.join(dirpath, "urls.py"))):
            apps.setdefault(dirpath, {"dir": dirpath, "config": ""})

    if not apps:
        result.note_pending("未找到模块", "-", "",
                            "没有识别到 Django app（apps.py / models.py + __init__.py）")
        return

    app_names = {os.path.basename(d) for d in apps}
    owners = assign_ownership(files, list(apps))
    used_slugs = set()

    # --- 第一遍：各 app 的模型定义 + 全局模型索引（模型类名 → 定义 app / 表名 / 是否显式）---
    app_models = {}
    model_index = {}
    for dirpath in apps:
        name0 = os.path.basename(dirpath)
        models, seen = [], set()
        for f in owners.get(dirpath, []):
            if not (os.path.basename(f) == "models.py"
                    or (os.sep + "models" + os.sep) in f):
                continue
            text = texts.get(f, "")
            for m in RE_DJ_CLASS.finditer(text):
                bases = m.group("bases")
                # 基类判定放宽：`models.Model` / `BaseModel` / `XxxModel` 都算（大小写不敏感），
                # 或类体内显式写了 db_table（自定义基类常见）——实测 bk-monitor 严格 \bModel\b
                # 只能识别约一半模型
                maybe_model = bool(re.search(r"model", bases, re.I))
                if not maybe_model and "db_table" not in text[m.start():m.start() + 4000]:
                    continue
                # 在【真实类体】内找 db_table / abstract（Django 的 Meta 常在字段之后，
                # 固定窗口会把显式声明漏判成默认命名）
                nxt_top = RE_TOP_LEVEL.search(text, m.end())
                body = text[m.start():nxt_top.start() if nxt_top else len(text)]
                if re.search(r"abstract\s*=\s*True", body):
                    continue
                dt = RE_DJ_DBTABLE.search(body)
                table = dt.group("table") if dt else "%s_%s" % (name0, m.group("name").lower())
                if table in seen:
                    continue
                seen.add(table)
                if not dt and table not in result._default_named:
                    result._default_named.append(table)
                models.append({"table": table, "entities": [m.group("name")], "uses": 1,
                               "declared": bool(dt), "via": "models.Model（定义）",
                               "evidence": "%s:%d" % (to_rel(f, root), line_of(text, m.start())),
                               "own": True})
                model_index.setdefault(m.group("name"), (dirpath, table, bool(dt)))
        app_models[dirpath] = models

    def model_usage(dirpath, owned, tables):
        """跨 app 使用：import 其他 app 的模型 / apps.get_model → 该表也算本模块的关联面。"""
        own_tables = {t["table"] for t in tables}
        out = []
        for f in owned:
            text = texts.get(f, "")
            if not text or "model" not in text.lower():
                continue
            hits = []
            for m in RE_DJ_IMPORT.finditer(text):
                for nm in _names(m.group("names")):
                    hit = model_index.get(nm)
                    if hit and hit[0] != dirpath:
                        hits.append((nm, hit, m.start()))
            for m in RE_DJ_GET_MODEL.finditer(text):
                hit = model_index.get(m.group("model"))
                if hit and hit[0] != dirpath:
                    hits.append((m.group("model"), hit, m.start()))
            for nm, hit, pos in hits:
                if hit[1] in own_tables:
                    continue
                item = None
                for t in out:
                    if t["table"] == hit[1]:
                        item = t
                        break
                if item is None:
                    item = {"table": hit[1], "entities": [], "uses": 0,
                            "declared": hit[2], "own": False,
                            "via": "import（%s）" % os.path.basename(hit[0]), "evidence": ""}
                    out.append(item)
                item["uses"] += 1
                if nm not in item["entities"]:
                    item["entities"].append(nm)
                if not item["evidence"]:
                    item["evidence"] = "%s:%d" % (to_rel(f, root), line_of(text, pos))
        return out

    for dirpath, meta in sorted(apps.items()):
        name = os.path.basename(dirpath)
        slug = kebab(name)
        base_slug, n = slug, 2
        while slug in used_slugs:
            slug, n = "%s-%d" % (base_slug, n), n + 1
        used_slugs.add(slug)
        owned = owners.get(dirpath, [])

        # --- 表：本 app 定义的（第一遍已提取）+ 跨 app 使用的 ---
        tables = [dict(t) for t in app_models.get(dirpath, [])]
        tables += model_usage(dirpath, owned, tables)

        # --- 挂载前缀：urls*.py 里 include('...{app}.urls') + 本 app 的 router.register ---
        prefixes, registers = [], []
        for path in py_files:
            if not os.path.basename(path).startswith("urls"):
                continue
            for m in RE_DJ_PATH.finditer(texts.get(path, "")):
                inc = RE_DJ_INCLUDE.search(m.group("target"))
                if not inc:
                    continue
                parts = inc.group("mod").split(".")
                if "urls" in parts and name in parts[:-1]:
                    # re_path(r'^uptime_check/') → 去掉正则锚点 ^ / $
                    prefixes.append(m.group("path").strip("^$").strip("/"))
        for f in owned:
            if os.path.basename(f).startswith("urls"):
                for m in RE_DJ_REGISTER.finditer(texts.get(f, "")):
                    registers.append(m.group("prefix"))

        # --- 视图入口（约）：api_view + @action + ViewSet 类 + router 注册 ---
        views = len(registers)
        for f in owned:
            base = os.path.basename(f)
            if "view" not in base and (os.sep + "views" + os.sep) not in f:
                continue
            text = texts.get(f, "")
            views += len(RE_DJ_VIEW_DEC.findall(text)) + len(RE_DJ_ACTION.findall(text))
            for m in RE_DJ_CLASS.finditer(text):
                if "View" in m.group("bases"):
                    views += 1

        # --- 依赖：跨 app import ---
        deps = []
        for f in owned:
            for m in re.finditer(r"""(?m)^\s*(?:from|import)\s+([\w.]+)""", texts.get(f, "")):
                head = m.group(1).split(".")[0]
                if head in app_names and head != name and head not in deps:
                    deps.append(head)

        # --- 非 HTTP 入口 / 守卫 ---
        tasks = signals = 0
        guards = []
        for f in owned:
            text = texts.get(f, "")
            tasks += len(RE_DJ_TASK.findall(text))
            signals += len(RE_DJ_SIGNAL.findall(text))
            for m in re.finditer(r"""permission_classes\s*=\s*\[(?P<cls>[^\]]*)\]""", text):
                for g in _names(m.group("cls")):
                    if g not in guards:
                        guards.append(g)

        line_count = sum(texts.get(f, "").count("\n") + 1 for f in owned)
        models_file = os.path.join(dirpath, "models.py")
        entry_file = models_file if os.path.isfile(models_file) else (owned[0] if owned else "")
        result.modules.append({
            "name": meta.get("config") or name, "slug": slug, "kind": "django",
            "dir": to_rel(dirpath, root) or ".",
            "class_file": to_rel(entry_file, root) if entry_file else "", "line": 1,
            "files": len(owned), "owned_files": len(owned), "lines": line_count,
            "controllers": [],
            "prefixes": sorted({p for p in prefixes if p}),
            "routes": views,
            "deps": sorted(deps), "dependents": [],
            "libs": [], "exports": [],
            "tables": sorted(tables, key=lambda x: x["table"]),
            "guards": guards[:8],
            "entries": {"mq": [], "cqrs": [], "tasks": tasks, "signals": signals},
            "event_edges": [], "event_edges_in": [],
            "experts": [],
            "file_list": [to_rel(f, root) for f in owned][:60],
            "confidence": "🟢" if meta.get("config") else "🟡",
        })

    build_dependents(result)
    build_tables_reverse(result)
    if result._default_named:
        # Django 默认命名是**框架规范**（{app_label}_{模型名小写}）——聚合一条，不逐表刷屏
        result.note_pending(
            "默认命名表名（框架规范）", "%d 张" % len(result._default_named),
            "、".join(result._default_named[:8])
            + (" 等" if len(result._default_named) > 8 else ""),
            "未显式 db_table → 按 Django 默认命名推断；项目若自定义命名策略需核对")
    result.stats["default_named_tables"] = len(result._default_named)


# ---------------------------------------------------------------------------
# 专家资产探测（.module-experts/）
# ---------------------------------------------------------------------------
def detect_experts(root, extra_dirs):
    bases = [os.path.join(root, ".module-experts"), os.path.join(root, "module-experts")]
    bases += [os.path.abspath(os.path.expanduser(d)) for d in (extra_dirs or [])]
    out, seen = [], set()
    for base in bases:
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            p = os.path.join(base, name)
            if not os.path.isdir(p) or name in seen:
                continue
            seen.add(name)
            out.append({"name": name,
                        "path": to_rel(p, root) if p.startswith(root) else p, "dir": p})
    return out


def match_experts(experts, result, root):
    """模块 ↔ 专家资产关联：在专家资产文本里找模块名/slug 的出现（有证据才连，不猜测）。"""
    for e in experts:
        hay = []
        for cand in ("agent.md", "INDEX.md"):
            fp = os.path.join(e["dir"], cand)
            if os.path.isfile(fp):
                hay.append(read_text(fp))
        try:
            for fname in sorted(os.listdir(e["dir"]))[:8]:
                if fname.endswith(".md") and fname.startswith("C"):
                    hay.append(read_text(os.path.join(e["dir"], fname)))
        except OSError:
            pass
        hay_text = "\n".join(hay)
        e["modules"] = []
        for m in result.modules:
            needles = {m["name"], m["name"].replace("Module", ""), m["slug"],
                       os.path.basename(m["dir"].rstrip("/"))}
            for needle in needles:
                if not needle or len(needle) < 3:
                    continue
                if re.search(r"(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])" % re.escape(needle),
                             hay_text, re.I):
                    e["modules"].append({"slug": m["slug"], "name": m["name"], "hit": needle})
                    m["experts"].append({"name": e["name"], "path": e["path"], "hit": needle})
                    break
    result.experts = experts
    result.stats["experts"] = len(experts)
    result.stats["modules_with_experts"] = sum(1 for m in result.modules if m["experts"])


# ---------------------------------------------------------------------------
# 框架探测 / 新鲜度
# ---------------------------------------------------------------------------
def detect_framework(root, files, texts):
    detected = {"framework": None, "global_prefix": "", "src_dirs": [], "signals": {}}
    nest = 0
    for path in files:
        if os.path.basename(path) == "package.json":
            raw = read_text(path)
            data = json.loads(raw) if raw.strip().startswith("{") else {}
            deps = {}
            for key in ("dependencies", "devDependencies"):
                deps.update(data.get(key) or {})
            if "@nestjs/core" in deps:
                nest += 1
    dj = 1 if any(os.path.basename(p) == "manage.py" for p in files) else 0
    if not dj:
        dj = sum(1 for p in files
                 if p.endswith(PY_EXTS)
                 and re.search(r"""(?m)^\s*(?:from|import)\s+django""", texts.get(p, "")))
        dj = 1 if dj else 0
    module_decls = sum(1 for p in files
                       if p.endswith(TS_EXTS) and "@Module" in texts.get(p, ""))
    detected["signals"] = {"nestjs_projects": nest, "django_signals": dj,
                           "module_decls": module_decls}
    detected["framework"] = "nestjs" if (nest or module_decls) else ("django" if dj else None)
    detected["global_prefix"] = resolve_global_prefix(files, texts)
    for name in ("src", "apps", "packages", "libs", "services", "server"):
        if os.path.isdir(os.path.join(root, name)):
            detected["src_dirs"].append(name)
    detected["ts_files"] = sum(1 for p in files if p.endswith(TS_EXTS))
    detected["py_files"] = sum(1 for p in files if p.endswith(PY_EXTS))
    return detected


def _scope_pathspecs(scope):
    """meta.json 的 scope → git pathspec 列表。

    必须**一个 glob 一个参数**：把 `"packages/**, apps/**"` 当单个 pathspec 传给 git 会匹配不到
    任何文件 → 变化被漏判 → `--check` 错报"索引可用"（实测静默假阴性，最坏的一类失效）。
    """
    if not scope:
        return ["."]
    if isinstance(scope, (list, tuple)):
        items = [str(x).strip() for x in scope]
    else:
        items = [s.strip() for s in str(scope).split(",")]
    items = [s for s in items if s]
    return items or ["."]


def run_check(root, index_dir):
    meta_path = os.path.join(index_dir, "meta.json")
    if not os.path.isfile(meta_path):
        eprint("✗ meta.json 不存在：%s" % meta_path)
        return 7
    meta = json.loads(read_text(meta_path) or "{}")
    recorded = meta.get("commit")
    index_root = meta.get("root") or root
    if not recorded:
        eprint("✗ meta.json 缺少 commit 字段")
        return 7
    try:
        head = subprocess.run(["git", "-C", index_root, "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        eprint("✗ git 不可用：%s" % exc)
        return 3
    if head.returncode != 0:
        eprint("✗ 不是 git 仓库或 git 失败：%s" % (head.stderr or "").strip())
        return 3
    current = head.stdout.strip()
    if current == recorded:
        print("✅ 索引新鲜：commit 未变化（%s）" % current[:10])
        return 0
    diff = subprocess.run(["git", "-C", index_root, "diff", "--name-only",
                           "%s..%s" % (recorded, current), "--"]
                          + _scope_pathspecs(meta.get("scope")),
                          capture_output=True, text=True, timeout=30)
    if diff.returncode != 0:
        # 记录的 commit 不可达（换过仓库 / 历史被重写 / 记录被手改）→ 不能宣称"可用"
        eprint("✗ 无法比对：记录的 commit %s 在当前仓库不可达（%s）"
               % (recorded[:10], (diff.stderr or "").strip()[:120]))
        eprint("  处置：把 meta.json 的 commit 校正为当前 HEAD，或直接重建索引")
        return 3
    changed = [l for l in (diff.stdout or "").splitlines() if l.strip()]
    if not changed:
        print("✅ 索引可用：提交已前进（%s → %s），但扫描范围内无文件变化"
              % (recorded[:10], current[:10]))
        return 0
    print("⚠️ 索引已过期：提交 %s → %s，范围内 %d 个文件有变化"
          % (recorded[:10], current[:10], len(changed)))
    for name in changed[:20]:
        eprint("   - %s" % name)
    eprint("   建议：重跑扫描脚本（--emit-tree 覆盖落盘）")
    return 6


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------
def _prefix_label(m, global_prefix):
    if not m["prefixes"]:
        # `@Controller()` 无前缀是常见写法（实测 xpert 多数模块）——用方法路径首段展示真实路由面
        hints = []
        for c in m["controllers"]:
            for h in c.get("path_hints") or []:
                if h not in hints:
                    hints.append(h)
        if not hints:
            return "-"
        base = ("`/%s` + " % (global_prefix or "").strip("/")) if global_prefix else ""
        label = "%s方法路径 %s" % (base, "、".join("`%s`" % h for h in hints[:3]))
        if len(hints) > 3:
            label += " 等 %d 个" % len(hints)
        return label
    parts = []
    for p in m["prefixes"][:3]:
        full = "/" + "/".join(x for x in [(global_prefix or "").strip("/"), p.strip("/")] if x)
        parts.append("`%s`" % full)
    label = "、".join(parts)
    if len(m["prefixes"]) > 3:
        label += " 等 %d 个" % len(m["prefixes"])
    return label


def _entry_label(entries, events=0):
    bits = []
    if entries.get("mq"):
        bits.append("MQ %d" % len(entries["mq"]))
    if entries.get("cqrs"):
        bits.append("CQRS %d" % len(entries["cqrs"]))
    if entries.get("tasks"):
        bits.append("任务 %d" % entries["tasks"])
    if entries.get("signals"):
        bits.append("信号 %d" % entries["signals"])
    if events:
        bits.append("事件边 %d" % events)
    return " · ".join(bits) or "-"


def _short_list(names, limit=3):
    if not names:
        return "-"
    label = "、".join(names[:limit])
    if len(names) > limit:
        label += " 等 %d" % len(names)
    return label


def render_index_md(result, root, opts, meta):
    gp = result.stats.get("global_prefix") or ""
    gp_label = ("`/%s`" % gp.strip("/")) if gp else "（未探测到）"
    lines = ["# %s 后端模块索引" % (meta.get("slug") or "backend"), "",
             "> 根目录：`%s` · 框架：**%s** · 全局前缀：%s" % (root, result.stats.get("framework") or "?", gp_label),
             "> 生成：%s · commit：`%s` · 范围：`%s` · 扫描器：scan_backend.py v%s" % (
                 meta.get("generated") or "", (meta.get("commit") or "?")[:10],
                 ", ".join(_scope_pathspecs(meta.get("scope"))), VERSION),
             "> 新鲜度校验：`python3 scan_backend.py --root %s --check --index <本目录>`" % root, ""]
    lines.append("**这个索引回答什么**：改某个模块要连带看谁（依赖/被依赖）、改某张表要通知哪些模块、"
                 "某模块的数据面与非 HTTP 入口、模块的代码在哪。**接口级契约**见 `.module-experts/` "
                 "专家资产与 ki 接口信息（`tags=api`）——本索引不重复建设。")
    lines.append("")

    lines.append("## 1. 模块地图（%d）" % len(result.modules))
    lines.append("")
    lines.append("| 模块 | 目录 | 挂载前缀 | 接口 | 表 | 依赖 | 被依赖 | 非 HTTP 入口 | 专家资产 |")
    lines.append("|------|------|----------|------|----|------|--------|--------------|----------|")
    for m in sorted(result.modules, key=lambda x: (-x["routes"], x["slug"])):
        exp = "、".join(e["name"] for e in m["experts"]) if m["experts"] else "-"
        lines.append("| [%s](modules/%s.md) `%s` | `%s` | %s | %d | %d | %s | %s | %s | %s |" % (
            m["name"], m["slug"], m["slug"], m["dir"], _prefix_label(m, gp), m["routes"],
            len(m["tables"]), _short_list(m["deps"]), _short_list(m["dependents"]),
            _entry_label(m["entries"], len(m.get("event_edges") or [])), exp))
    lines.append("")

    edges = [(m["slug"], m["deps"]) for m in result.modules if m["deps"]]
    edge_count = sum(len(d) for _s, d in edges)
    lines.append("## 2. 模块依赖图（%d 条边）" % edge_count)
    lines.append("")
    slug_by_name = {m["name"]: m["slug"] for m in result.modules}
    if edge_count and edge_count <= 120:
        lines.append("```mermaid")
        lines.append("graph LR")
        for src, deps in edges:
            for dep in deps:
                tgt = slug_by_name.get(dep)
                if tgt:
                    lines.append("  %s --> %s" % (src.replace("-", "_"), tgt.replace("-", "_")))
        lines.append("```")
    elif edge_count:
        lines.append("（边数 %d > 120，图过密，按模块列出）" % edge_count)
        lines.append("")
        for m in result.modules:
            if m["deps"]:
                lines.append("- `%s` → %s" % (m["slug"], "、".join("`%s`" % d for d in m["deps"])))
    else:
        lines.append("（无模块间依赖声明）")
    lines.append("")

    lines.append("## 3. 表 → 模块（反向，%d 张表）" % len(result.tables))
    lines.append("")
    if result.tables:
        lines.append("| 表 | 模块数 | 模块（引用次数） |")
        lines.append("|----|--------|------------------|")
        for t in result.tables[:60]:
            mark = "" if t["declared"] else " ⚠︎默认命名"
            lines.append("| `%s`%s | %d | %s |" % (
                t["table"], mark, t["module_count"],
                "、".join("`%s`（%d）" % (x["slug"], x["uses"]) for x in t["modules"][:5])
                + (" 等 %d 个模块" % len(t["modules"]) if len(t["modules"]) > 5 else "")))
        if len(result.tables) > 60:
            lines.append("")
            lines.append("（共 %d 张，完整见 `tables.md`）" % len(result.tables))
    else:
        lines.append("（未提取到表）")
    lines.append("")

    lines.append("## 4. 专家资产（%d 个）" % len(result.experts))
    lines.append("")
    if result.experts:
        lines.append("| 专家 | 路径 | 关联模块 |")
        lines.append("|------|------|----------|")
        for e in result.experts:
            mods = "、".join("`%s`" % x["slug"] for x in e["modules"]) if e["modules"] else "**未关联**"
            lines.append("| %s | `%s` | %s |" % (e["name"], e["path"], mods))
        lines.append("")
        lines.append("> 关联按专家资产文本里出现的模块名/slug 机械判定；「未关联」不代表无关"
                     "（专家名可能用中文业务名，与代码标识无字面重叠）。")
    else:
        lines.append("（未发现专家资产——接口级契约可先靠 ki 接口信息或现场 grep）")
    lines.append("")

    lines.append("## 5. 待确认（%d）" % len(result.pending))
    lines.append("")
    if result.pending:
        lines.append("| 类型 | 位置 | 内容 | 原因 |")
        lines.append("|------|------|------|------|")
        for p in result.pending[:50]:
            lines.append("| %s | `%s` | %s | %s |" % (
                p["type"], p["loc"], (p["content"] or "-")[:60], p["reason"]))
        if len(result.pending) > 50:
            lines.append("")
            lines.append("（共 %d 条，其余见 JSON 输出）" % len(result.pending))
    else:
        lines.append("（无）")
    return "\n".join(lines) + "\n"


def render_module_md(m, root, global_prefix):
    lines = ["# %s（`%s`）" % (m["name"], m["slug"]), "",
             "- **位置**：`%s/` · 归属文件 **%d** 个 · 约 **%d** 行" % (
                 m["dir"], m["files"], m["lines"]),
             "- **定义**：`%s:%d`（%s）" % (m["class_file"], m["line"], m["kind"]),
             "- **挂载前缀**：%s · 视图/接口入口 **%d** 个" % (_prefix_label(m, global_prefix), m["routes"]),
             "- **置信度**：%s（模块边界来自 %s 声明）" % (
                 m["confidence"], "@Module" if m["kind"] == "nestjs" else "apps.py/models.py"),
             ""]
    if m["controllers"]:
        lines.append("## 控制器（模块对外面）")
        lines.append("")
        lines.append("| 文件 | 前缀 | 接口数 | 位置 |")
        lines.append("|------|------|--------|------|")
        for c in m["controllers"]:
            lines.append("| `%s`%s | `%s` | %d | `:%d` |" % (
                c["file"], "（%s）" % c["class"] if c["class"] else "",
                c["prefix"] or "-", c["routes"], c["line"]))
        lines.append("")
    lines.append("## 依赖关系")
    lines.append("")
    lines.append("- **依赖**（改它要连带看）：%s" % (
        "、".join("`%s`" % d for d in m["deps"]) if m["deps"] else "无（顶层模块或被依赖方未在扫描范围）"))
    lines.append("- **被依赖**（动它会影响）：%s" % (
        "、".join("`%s`" % d for d in m["dependents"]) if m["dependents"] else "无"))
    if m["libs"]:
        lines.append("- **依赖的库/框架模块**：%s" % "、".join("`%s`" % x for x in m["libs"]))
    lines.append("")
    events_out = m.get("event_edges") or []
    events_in = m.get("event_edges_in") or []
    if events_out or events_in:
        lines.append("## 事件/命令耦合（不经 imports，%d 出 / %d 入）" % (
            len(events_out), len(events_in)))
        lines.append("")
        if events_out:
            lines.append("**我发出**（改这些命令/事件要连带看目标模块）：")
            lines.append("")
            for e in events_out:
                kind = "CQRS" if e["kind"] == "cqrs" else "MQ 队列"
                more = (" 等 %d 个" % e["count"]) if e["count"] > len(e["names"]) else ""
                lines.append("- → `%s`（%s：%s%s）" % (
                    e["target"], kind, "、".join("`%s`" % n for n in e["names"]), more))
            lines.append("")
        if events_in:
            lines.append("**我接收**（这些模块发来的命令/消息由我处理，改它们要连带看我）：")
            lines.append("")
            for e in events_in:
                more = (" 等 %d 个" % e["count"]) if e["count"] > len(e["names"]) else ""
                lines.append("- ← `%s`（%s%s）" % (
                    e["source"], "、".join("`%s`" % n for n in e["names"]), more))
            lines.append("")
    lines.append("## 数据表（%d）" % len(m["tables"]))
    lines.append("")
    if m["tables"]:
        lines.append("| 表 | 实体 | 引用次数 | 来源 | 证据 |")
        lines.append("|----|------|----------|------|------|")
        for t in m["tables"]:
            mark = "" if t["declared"] else " ⚠︎默认命名"
            lines.append("| `%s`%s | %s | %d | %s | `%s` |" % (
                t["table"], mark, "、".join(t["entities"]), t["uses"], t["via"],
                t["evidence"] or "-"))
    else:
        lines.append("（未引用数据表——纯计算/转发型模块）")
    lines.append("")
    entries = m["entries"]
    if any(entries.get(k) for k in ("mq", "cqrs", "tasks", "signals")):
        lines.append("## 非 HTTP 入口")
        lines.append("")
        if entries.get("mq"):
            lines.append("- **MQ 消费者**（%d）：%s" % (
                len(entries["mq"]), _short_list(["`%s`" % x for x in entries["mq"]], 6)))
        if entries.get("cqrs"):
            lines.append("- **CQRS Handler**（%d）：%s" % (
                len(entries["cqrs"]), _short_list(["`%s`" % x for x in entries["cqrs"]], 6)))
        if entries.get("tasks"):
            lines.append("- **定时任务**：%d 处" % entries["tasks"])
        if entries.get("signals"):
            lines.append("- **信号接收**：%d 处" % entries["signals"])
        lines.append("")
    if m["guards"]:
        lines.append("## 守卫/权限\n")
        lines.append("、".join("`%s`" % g for g in m["guards"]))
        lines.append("")
    if m["experts"]:
        lines.append("## 专家资产（深挖读这些）")
        lines.append("")
        for e in m["experts"]:
            lines.append("- `%s`（命中标识 `%s`）" % (e["path"], e["hit"]))
        lines.append("")
    lines.append("## 归属文件（%d）" % m["files"])
    lines.append("")
    shown = m["file_list"][:40]      # 卡片限流 40 条；JSON 里保留完整清单
    for f in shown:
        lines.append("- `%s`" % f)
    if len(m["file_list"]) > len(shown):
        lines.append("- ……其余 %d 个见 JSON 输出（完整清单）" % (len(m["file_list"]) - len(shown)))
    return "\n".join(lines) + "\n"


def render_tables_md(result):
    lines = ["# 表 → 模块（反向索引）", "",
             "> 用途：改/删某张表前，先看哪些模块引用了它（穷举反查，机械提取）。",
             "> 接口级影响面（精确到某个 handler）见各模块的 `.module-experts/` 资产或现场 grep。", ""]
    if not result.tables:
        lines.append("（未提取到表）")
        return "\n".join(lines) + "\n"
    lines.append("| 表 | 模块数 | 模块（引用次数 · 来源） |")
    lines.append("|----|--------|--------------------------|")
    for t in result.tables:
        mark = "" if t["declared"] else " ⚠︎默认命名"
        lines.append("| `%s`%s | %d | %s |" % (
            t["table"], mark, t["module_count"],
            "、".join("`%s`（%d · %s）" % (x["slug"], x["uses"], x["via"]) for x in t["modules"])))
    return "\n".join(lines) + "\n"


def render_json(result, root, opts, meta):
    return json.dumps({
        "root": root, "generated": meta.get("generated"),
        "scanner": "scan_backend.py v%s" % VERSION,
        "stats": result.stats,
        "modules": result.modules,
        "tables": result.tables,
        "experts": result.experts,
        "pending": result.pending,
    }, ensure_ascii=False, indent=2)


def render_md(result, root, opts, meta):
    """单文件 md（stdout/--out 用）：索引 + 全部模块卡 + 表反查。"""
    gp = result.stats.get("global_prefix") or ""
    out = render_index_md(result, root, opts, meta)
    out += "\n---\n\n# 模块卡\n\n"
    for m in sorted(result.modules, key=lambda x: x["slug"]):
        out += render_module_md(m, root, gp) + "\n"
    out += "\n---\n\n" + render_tables_md(result)
    return out


def render_tsv(result, root):
    lines = ["#kind\tslug\tname\tdir\tprefixes\troutes\ttables\tdeps\tdependents\tentries\texperts"]
    for m in result.modules:
        entries = "/".join("%s:%d" % (k, len(v) if isinstance(v, list) else v)
                           for k, v in m["entries"].items() if v)
        lines.append("M\t%s\t%s\t%s\t%s\t%d\t%d\t%s\t%s\t%s\t%s" % (
            m["slug"], m["name"], m["dir"], ",".join(m["prefixes"]), m["routes"],
            len(m["tables"]), ",".join(m["deps"]), ",".join(m["dependents"]), entries,
            ",".join(e["name"] for e in m["experts"])))
    for t in result.tables:
        lines.append("T\t%s\t\t\t\t\t%d\t%s\t\t\t" % (
            t["table"], t["module_count"], ",".join(x["slug"] for x in t["modules"])))
    return "\n".join(lines) + "\n"


def emit_tree(result, root, out_dir, opts, meta):
    os.makedirs(os.path.join(out_dir, "modules"), exist_ok=True)
    gp = result.stats.get("global_prefix") or ""
    with open(os.path.join(out_dir, "index.md"), "w", encoding="utf-8") as fh:
        fh.write(render_index_md(result, root, opts, meta))
    for m in result.modules:
        with open(os.path.join(out_dir, "modules", "%s.md" % m["slug"]), "w",
                  encoding="utf-8") as fh:
            fh.write(render_module_md(m, root, gp))
    with open(os.path.join(out_dir, "tables.md"), "w", encoding="utf-8") as fh:
        fh.write(render_tables_md(result))
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)


def load_jsonc(path):
    """读声明文件（容忍 // 与 /* */ 注释——人手改的 JSON 常带注释）。"""
    text = read_text(path) or ""
    text = re.sub(r"(?m)^\s*//[^\n]*$", "", text)
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    try:
        return json.loads(text)
    except ValueError:
        return None


def project_root(root):
    """**项目根**：`.fe-index/` 的唯一落点。

    判定顺序：`git rev-parse --show-toplevel` → 逐级向上找 `.git` → 兜底 `root` 本身。
    monorepo 里 `--root` 常给**应用子目录**，但索引属于整个项目——落点必须确定，不能随
    `--root` 或 cwd 漂移（实测踩过：`--emit-tree` 相对 cwd 解析，换个目录跑就写到别处）。
    """
    try:
        r = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            return os.path.abspath(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    base = os.path.abspath(root)
    while True:
        if os.path.isdir(os.path.join(base, ".git")):
            return base
        parent = os.path.dirname(base)
        if parent == base:
            return os.path.abspath(root)
        base = parent


def find_config(root, explicit, levels=3):
    """声明文件定位：显式路径 > **项目根**的 `.fe-index/config.json` > `{root}` 下的 > 向上 ≤3 层（兼容旧布局）。"""
    if explicit:
        return explicit
    proj = project_root(root)
    for base in (proj, os.path.abspath(root)):
        cand = os.path.join(base, ".fe-index", "config.json")
        if os.path.isfile(cand):
            return cand
    base = os.path.abspath(root)
    for _ in range(levels):
        parent = os.path.dirname(base)
        if parent == base:
            break
        base = parent
        cand = os.path.join(base, ".fe-index", "config.json")
        if os.path.isfile(cand):
            return cand
    return None


FRONTEND_KEYS = ("routes", "pagesDirs", "apiDirs", "aliases", "requestObjects", "maxDepth")
BACKEND_KEYS = ("framework", "expertsDir")


def app_kind(app):
    """判定声明条目的归属：显式 `kind` 优先；老声明（无 kind）按特征键推断，推不出返回 ""。"""
    kind = app.get("kind")
    if kind:
        return kind
    if any(k in app for k in FRONTEND_KEYS):
        return "frontend"
    if any(k in app for k in BACKEND_KEYS):
        return "backend"
    return ""


def merge_config(args, root):
    """读声明文件补全参数；CLI 显式传入优先。

    与 `frontend-index` **共用同一个 config.json**：只认 `kind=backend` 的条目。
    **失效模式纪律**（实测踩过）：把自己/别人的**上层**声明"当成本项目的声明"会拦下原本正常的
    扫描，因此——
      - 显式 `--config`：声明不可用即报错（用户明确指向它）
      - 默认路径 `{root}/.fe-index/config.json`：不可用即报错（本项目自己的声明）
      - **向上找到的上层声明**：只在无歧义可用时采用；否则打印一行说明后**忽略**，按 CLI 继续
    返回 (root, cfg)；cfg 为 None 表示"显式/默认声明不可用"（调用方 return 5）。
    """
    explicit = bool(args.config)
    config_path = find_config(root, args.config)
    if not config_path or not os.path.isfile(config_path):
        return root, {}
    # 规范落点是【项目根】的 .fe-index/：位于项目根（或 --root）下 = 本项目声明（不可用即报错）；
    # 只有项目根之外的更上层才算"别人的"，才允许忽略
    canonical = {os.path.abspath(os.path.join(project_root(root), ".fe-index", "config.json")),
                 os.path.abspath(os.path.join(root, ".fe-index", "config.json"))}
    via_upward = not explicit and os.path.abspath(config_path) not in canonical
    if via_upward:
        eprint("· 发现项目根之外的声明文件：%s" % config_path)

    def ignore(msg):
        if explicit or not via_upward:
            eprint("✗ %s：%s" % (msg, config_path))
            return None
        eprint("· %s，已忽略该上层声明，按命令行参数继续" % msg)
        return {}

    data = load_jsonc(config_path)
    if data is None:
        return root, ignore("声明文件不是合法 JSON")
    apps = [a for a in (data.get("apps") or []) if isinstance(a, dict)]
    if not apps:
        return root, ignore("声明文件里没有 apps[]")
    backend_apps = [a for a in apps if app_kind(a) == "backend"]
    if not backend_apps:
        # 兼容无特征键的老声明（既不像前端也不像后端）
        backend_apps = [a for a in apps if app_kind(a) == ""]
    if not backend_apps:
        # 只有其他类型的条目（例如只有前端声明）→ 这份声明**不是给本端的**：
        # 说明一行后忽略，绝不拦路（实测：bk-monitor 的前端声明曾拦下后端扫描）
        eprint("· 声明文件里没有后端应用（%s），忽略它按命令行参数继续" % config_path)
        return root, {}

    slug = args.app or args.slug
    chosen = None
    if slug:
        chosen = next((a for a in backend_apps if a.get("slug") == slug), None)
        if chosen is None:
            return root, ignore("声明文件里没有 slug=%s 的后端应用" % slug)
    else:
        if len(backend_apps) > 1:
            if via_upward:
                return root, ignore("上层声明含 %d 个后端应用且未指定 --app/--slug" % len(backend_apps))
            eprint("⚠ 声明文件含 %d 个后端应用，未指定 --app/--slug，使用第一个：%s"
                   % (len(backend_apps), backend_apps[0].get("slug")))
        chosen = backend_apps[0]
    cfg = dict(chosen)
    cfg_root = cfg.pop("root", None)
    new_root = root
    if cfg_root:
        base = os.path.dirname(os.path.abspath(config_path))
        if os.path.basename(base) == ".fe-index":
            base = os.path.dirname(base)
        new_root = os.path.normpath(os.path.join(base, cfg_root))
    experts = cfg.get("expertsDir") or cfg.get("experts") or []
    if isinstance(experts, str):
        experts = [experts]
    return new_root, {"include": cfg.get("include") or [], "exclude": cfg.get("exclude") or [],
                      "framework": cfg.get("framework") or "auto",
                      "slug": cfg.get("slug"), "experts": experts}


def git_head(root):
    try:
        r = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


# ---------------------------------------------------------------------------
# 扫描主流程
# ---------------------------------------------------------------------------
def scan(root, opts):
    result = Result()
    framework = (opts.get("framework") or "auto").lower()
    includes = opts.get("include") or []
    excludes = opts.get("exclude") or []
    all_files = walk_files(root, includes, excludes, TS_EXTS + PY_EXTS)
    texts = {p: read_text(p) for p in all_files}
    detected = detect_framework(root, all_files, texts)
    if framework == "auto":
        framework = detected["framework"]
    if not framework:
        result.stats["framework"] = None
        return result, detected
    if framework == "nestjs":
        # 前后端同仓时必须剔除前端文件（同名类会污染类 → 文件解析，实测 bug）
        kept = [p for p in all_files if not (p.endswith(TS_EXTS) and looks_frontend(texts[p]))]
        if len(kept) != len(all_files):
            result.stats["frontend_files_skipped"] = len(all_files) - len(kept)
        all_files = kept
    result.stats["framework"] = framework
    result.stats["files"] = len(all_files)
    result.stats["global_prefix"] = detected.get("global_prefix") or ""
    result.stats["src_dirs"] = detected.get("src_dirs") or []
    if framework == "nestjs":
        scan_nestjs(root, all_files, texts, opts, result)
    else:
        scan_django(root, all_files, texts, opts, result)
    result.stats["modules"] = len(result.modules)
    result.stats["controllers"] = sum(len(m["controllers"]) for m in result.modules)
    result.stats["routes"] = sum(m["routes"] for m in result.modules)
    result.stats["tables"] = len(result.tables)
    result.stats["deps_edges"] = sum(len(m["deps"]) for m in result.modules)
    result.stats.setdefault("event_edges", 0)
    experts = detect_experts(root, opts.get("experts") or [])
    if experts:
        match_experts(experts, result, root)
    else:
        result.experts = []
        result.stats["experts"] = 0
    return result, detected


def build_meta(args, root, result):
    slug = args.slug or os.path.basename(os.path.abspath(root).rstrip(os.sep)) or "backend"
    return {
        "slug": slug,
        "kind": "backend",
        "root": root,
        # 数组形式：每个 glob 一条 pathspec（字符串拼接会让 --check 静默漏判，见 _scope_pathspecs）
        "scope": list(args.include) if args.include else ["."],
        "framework": result.stats.get("framework"),
        "commit": git_head(root),
        "generated": date.today().isoformat(),
        "stats": result.stats,
        "scanner": "scan_backend.py v%s" % VERSION,
        "check_cmd": "python3 scan_backend.py --root %s --check --index %s"
                     % (root, os.path.join(project_root(root), ".fe-index", slug)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="backend-index 扫描器 v%s（模块级）" % VERSION)
    parser.add_argument("--root", required=True, help="仓库根目录")
    parser.add_argument("--config", help="声明文件路径（默认 {root}/.fe-index/config.json，存在则自动读取）")
    parser.add_argument("--app", help="声明文件含多个后端应用时选哪个（slug）")
    parser.add_argument("--framework", default="auto", choices=["auto", "nestjs", "django"])
    parser.add_argument("--include", action="append", default=[], help="只扫匹配路径（可重复）")
    parser.add_argument("--exclude", action="append", default=[], help="排除匹配路径（可重复）")
    parser.add_argument("--experts-dir", action="append", default=[],
                        help="额外专家资产目录（可重复，默认探测 {root}/.module-experts/）")
    parser.add_argument("--max", type=int, default=500, help="模块数上限（默认 500，硬上限 5000）")
    parser.add_argument("--format", default="md", choices=["md", "tsv", "json"])
    parser.add_argument("--out", help="输出到文件")
    parser.add_argument("--emit-tree", nargs="?", const="", metavar="DIR",
                        help="落盘整棵树（index.md + modules/ + tables.md + meta.json）；"
                             "不带值 = {项目根}/.fe-index/{slug}（相对路径一律以项目根为基准，不看 cwd）")
    parser.add_argument("--slug", help="应用标识（默认取根目录名）")
    parser.add_argument("--dump-config", action="store_true", help="只探测框架与约定")
    parser.add_argument("--check", action="store_true", help="新鲜度检查（需 --index）")
    parser.add_argument("--index", help="索引目录（--check 用）")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version="scan_backend.py v%s" % VERSION)
    args = parser.parse_args(argv)

    root = os.path.abspath(os.path.expanduser(args.root))
    if not os.path.isdir(root):
        eprint("✗ 根目录不存在：%s" % root)
        return 3
    if args.max > 5000:
        eprint("✗ --max 超过硬上限 5000")
        return 5
    # 声明文件（可选）：存在则补全参数，CLI 显式传入优先——重建时零猜测
    root, cfg = merge_config(args, root)
    if cfg is None:
        return 5
    if cfg:
        if not os.path.isdir(root):
            eprint("✗ 声明文件里的 root 不存在：%s" % root)
            return 3
        if not args.include:
            args.include = cfg["include"]
        if not args.exclude:
            args.exclude = cfg["exclude"]
        if args.framework == "auto":
            args.framework = cfg["framework"]
        if not args.slug:
            args.slug = cfg["slug"]
        if not args.experts_dir:
            args.experts_dir = cfg["experts"]
        if args.framework not in ("auto", "nestjs", "django"):
            eprint("✗ 声明文件里的 framework 非法：%s（可选 auto/nestjs/django）" % args.framework)
            return 5
        if args.verbose:
            eprint("· 已应用声明文件：root=%s include=%s framework=%s"
                   % (root, args.include or "全仓", args.framework))
    if args.check:
        if not args.index:
            eprint("✗ --check 需要 --index <索引目录>")
            return 5
        idx = args.index
        if not os.path.isabs(idx):
            # 相对 --index 以【项目根】为基准（`{项目根}/.fe-index/{slug}` 是规范落点）——
            # 与 --emit-tree 同口径，避免从不同 cwd 跑时找不到索引
            idx = os.path.join(project_root(root), idx)
        return run_check(root, idx)

    if args.dump_config:
        files = walk_files(root, args.include, args.exclude, TS_EXTS + PY_EXTS)
        texts = {p: read_text(p) for p in files}
        detected = detect_framework(root, files, texts)
        detected["_note"] = ("把 suggested_config 存为 {root}/.fe-index/config.json 并校正"
                             "（尤其 include / framework）")
        print(json.dumps({"detected": detected, "suggested_config": {"apps": [{
            "kind": "backend", "slug": args.slug or os.path.basename(root) or "backend",
            "root": ".", "framework": detected["framework"],
            "include": args.include or ["%s/**" % d for d in (detected["src_dirs"] or ["src"])],
        }]}}, ensure_ascii=False, indent=2))
        return 0

    opts = {"framework": args.framework, "include": args.include, "exclude": args.exclude,
            "experts": args.experts_dir}
    result, detected = scan(root, opts)
    signals = detected.get("signals") or {}
    if signals.get("django_signals") and (signals.get("nestjs_projects")
                                         or signals.get("module_decls")):
        # 同仓多框架：本次只扫了一个框架，另一侧模块未收录——必须显式告警，不能静默只扫一半
        eprint("⚠ 检测到 NestJS 与 Django 信号并存，本次只扫了 **%s**；"
               "另一侧模块未收录（需要时分别建两个 slug）" % (result.stats.get("framework") or "?"))
    if result.stats.get("framework") is None:
        eprint("✗ 未识别到后端框架（NestJS @Module / Django app 均未命中）")
        eprint("  处置：用 --framework 显式指定，或 --include 收窄范围后重试")
        return 2
    if not result.modules:
        eprint("⚠ 提取结果为空：识别到框架 %s，但未解析出模块" % result.stats.get("framework"))
        for p in result.pending[:5]:
            eprint("   - %s：%s" % (p["type"], p["reason"]))
        return 4
    limit = args.max
    if len(result.modules) > limit:
        result.stats["truncated"] = "modules %d→%d" % (len(result.modules), limit)
        result.modules = result.modules[:limit]
        result.note_pending("输出截断", "-", result.stats["truncated"], "超过 --max，重跑时提高上限")
        # 截断后必须重算/清理跨引用：否则依赖、被依赖、表反查、事件边里会残留指向不存在模块的项
        kept = {m["name"] for m in result.modules}
        for m in result.modules:
            m["deps"] = [d for d in m["deps"] if d in kept]
            m["event_edges"] = [e for e in m.get("event_edges", []) if e["target"] in kept]
            m["event_edges_in"] = [e for e in m.get("event_edges_in", []) if e["source"] in kept]
        build_dependents(result)
        build_tables_reverse(result)
        result.stats["tables"] = len(result.tables)
        result.stats["deps_edges"] = sum(len(m["deps"]) for m in result.modules)
        result.stats["event_edges"] = sum(len(m.get("event_edges", [])) for m in result.modules)

    meta = build_meta(args, root, result)
    if args.emit_tree is not None:
        # `.fe-index/` 一律落在【项目根】：不带值 → {项目根}/.fe-index/{slug}；
        # 相对路径也以项目根为基准（原先相对 cwd，换个目录跑就写到别处——实测陷阱）
        raw = (args.emit_tree or "").strip()
        if not raw:
            out_dir = os.path.join(project_root(root), ".fe-index", meta["slug"])
        elif os.path.isabs(raw):
            out_dir = raw
        else:
            out_dir = os.path.join(project_root(root), raw)
        emit_tree(result, root, out_dir, opts, meta)
        print("✅ 落盘 %s（模块 %d · 表 %d · 依赖边 %d · 专家资产 %d · 待确认 %d）" % (
            out_dir, len(result.modules), len(result.tables), result.stats["deps_edges"],
            result.stats.get("experts", 0), len(result.pending)))
        if args.verbose:
            eprint("· 统计：%s" % json.dumps(result.stats, ensure_ascii=False))
        return 0

    if args.format == "json":
        out = render_json(result, root, opts, meta)
    elif args.format == "tsv":
        out = render_tsv(result, root)
    else:
        out = render_md(result, root, opts, meta)
    if args.out:
        out_path = os.path.abspath(args.out)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(out)
        print("✅ 写入 %s（模块 %d · 表 %d · 依赖边 %d · 待确认 %d）" % (
            out_path, len(result.modules), len(result.tables),
            result.stats["deps_edges"], len(result.pending)))
    else:
        print(out)
    if args.verbose:
        eprint("· 统计：%s" % json.dumps(result.stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
