#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_frontend.py — 前端「页面（路由）↔ HTTP 接口」静态映射提取器（零第三方依赖）

由 frontend-index skill 调用，也可单独使用。只读源码，不修改被扫描项目。

核心能力:
  1. 路由提取：配置式（`path:` + `component:` / `<Route>` / Angular `loadChildren`）与文件式（pages/、app/）
  2. 接口定义提取：`request('GET','url')` 工厂、`http/axios/fetch` 调用 → 符号 →（方法, URL）
  3. 调用点提取：直接 URL 调用、命名导入符号调用、命名空间调用、类注入实例方法调用
  4. 归属：页面 → 其 import 图（≤ max-depth）内调用点 → 接口；并输出反向「接口 → 页面」
  5. --check 新鲜度闸门：以 meta.json 记录的 commit 与当前 HEAD 比对
  6. --dump-config：输出探测到的约定（存为 .fe-index/config.json，重建时零猜测）

用法示例:
  python3 scan_frontend.py --root . --out temp/fe-map.md
  python3 scan_frontend.py --root . --include 'src/**' --routes 'src/app/**/*routing*.ts' \
      --api-dirs 'src/app/@core/services' --min-confidence high
  python3 scan_frontend.py --root . --dump-config
  python3 scan_frontend.py --root . --check --index .fe-index/my-app

退出码:
  0 成功（--check 模式：索引新鲜）
  2 未识别到路由或接口约定（无产出，需人工介入 / 走声明文件）
  3 环境或 IO 错误（路径不存在、git 不可用）
  4 提取结果为空（过滤后无条目）
  5 入参非法（未知参数、config 不是合法 JSON、slug 非法）
  6 --check：索引已过期（提交前进且触及扫描范围内的文件）
  7 --check：索引元信息缺失（meta.json 不存在或不可读）
"""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from datetime import datetime

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "out", "output", "coverage",
    ".next", ".nuxt", ".output", ".cache", ".turbo", ".parcel-cache",
    "__pycache__", ".venv", "venv", ".idea", ".vscode", ".pnpm-store",
    "bower_components", "jspm_packages", ".gitlab", ".husky",
}

SCAN_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue")

# 默认的"请求对象"尾名：这些对象上的 get/post/... 才视为 HTTP 调用
DEFAULT_REQUEST_OBJECTS = {
    "axios", "http", "httpclient", "$http", "$axios", "request", "req",
    "client", "instance", "ajax", "ky", "api", "httpservice", "service",
}

# 忽略的产物文件名模式
IGNORE_FILE_PATTERNS = ("*.min.js", "*.bundle.js", "*.map")

MAX_FILE_BYTES = 1_500_000


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def eprint(*args):
    print(*args, file=sys.stderr)


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def to_rel(path, root):
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        rel = path
    return rel.replace(os.sep, "/")


def strip_jsonc(text):
    """粗粒度去掉 JSONC 的注释（够用于 tsconfig）。"""
    out, i, n = [], 0, len(text)
    in_str = False
    quote = ""
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                in_str = False
            i += 1
            continue
        if ch in "\"'":
            in_str = True
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def load_jsonc(path):
    text = read_text(path)
    if not text:
        return None
    text = strip_jsonc(text)
    text = re.sub(r",\s*([}\]])", r"\1", text)  # 去尾逗号
    try:
        return json.loads(text)
    except ValueError:
        return None


def match_glob(rel, pattern):
    """glob 匹配，`**/` 按 gitignore 语义可匹配零层目录
    （否则 `src/app/**/*routing*.ts` 会漏掉顶层的 src/app/app-routing.module.ts）。"""
    if fnmatch.fnmatch(rel, pattern):
        return True
    if "**/" in pattern:
        return fnmatch.fnmatch(rel, pattern.replace("**/", ""))
    return False


def walk_files(root, includes, excludes):
    """遍历源码文件。includes/excludes 为相对路径的 fnmatch 模式。"""
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in filenames:
            if not name.endswith(SCAN_EXTS):
                continue
            if any(fnmatch.fnmatch(name, pat) for pat in IGNORE_FILE_PATTERNS):
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


def line_of(text, index):
    return text.count("\n", 0, index) + 1


# ---------------------------------------------------------------------------
# 别名与模块解析
# ---------------------------------------------------------------------------

def detect_tsconfig_aliases(root):
    """读 root 下（含 1 层子目录）的 tsconfig*.json，合并 compilerOptions.paths。
    monorepo 场景：向上最多 3 层，取父目录里的 tsconfig（如根 tsconfig.base.json）。"""
    aliases = {}
    candidates = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        depth = to_rel(dirpath, root).count("/")
        if dirpath != root and depth >= 2:
            dirnames[:] = []
        for name in filenames:
            if name.startswith("tsconfig") and name.endswith(".json"):
                candidates.append(os.path.join(dirpath, name))
    parent = os.path.dirname(root)
    for _ in range(3):
        if not parent or parent == os.path.dirname(parent):
            break
        try:
            for name in sorted(os.listdir(parent)):
                if name.startswith("tsconfig") and name.endswith(".json"):
                    candidates.append(os.path.join(parent, name))
        except OSError:
            pass
        parent = os.path.dirname(parent)
    for path in candidates:
        data = load_jsonc(path)
        if not isinstance(data, dict):
            continue
        opts = data.get("compilerOptions") or {}
        paths = opts.get("paths") or {}
        base_dir = os.path.dirname(path)
        if isinstance(opts.get("baseUrl"), str):
            base_dir = os.path.normpath(os.path.join(base_dir, opts["baseUrl"]))
        if not isinstance(paths, dict):
            continue
        for key, values in paths.items():
            if not isinstance(values, list) or not values:
                continue
            target = values[0]
            if not isinstance(target, str):
                continue
            alias = key[:-2] if key.endswith("/*") else key
            rel_target = target[:-2] if target.endswith("/*") else target
            resolved = os.path.normpath(os.path.join(base_dir, rel_target))
            if os.path.isdir(resolved) or os.path.exists(resolved):
                aliases.setdefault(alias, resolved)
    return aliases


def detect_webpack_aliases(root):
    """从 webpack 配置里尽力嗅探 '@alias': path.resolve(...,'src/xxx') 形式的别名。"""
    aliases = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if to_rel(dirpath, root).count("/") >= 2:
            dirnames[:] = []
        for name in filenames:
            if not re.match(r"webpack[\w.-]*\.(js|cjs|mjs|ts)$", name):
                continue
            text = read_text(os.path.join(dirpath, name))
            for m in re.finditer(
                r"""['"](@[\w/-]+|~@[\w/-]+)['"]\s*:\s*(?:path\.)?resolve\([^)]*?['"]([^'"]+)['"]""",
                text,
            ):
                alias = m.group(1).lstrip("~")
                target = os.path.normpath(os.path.join(root, m.group(2)))
                if os.path.isdir(target):
                    aliases.setdefault(alias, target)
    return aliases


def detect_workspace_packages(root):
    """扫 package.json（workspace 子包）建立 包名 → 目录 映射。"""
    packages = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        depth = to_rel(dirpath, root).count("/")
        if dirpath != root and depth >= 3:
            dirnames[:] = []
        if "package.json" not in filenames:
            continue
        if dirpath == root:
            continue
        data = load_jsonc(os.path.join(dirpath, "package.json")) or {}
        name = data.get("name")
        if isinstance(name, str) and name and not data.get("private") is None:
            packages.setdefault(name, dirpath)
    return packages


class Resolver:
    """import 路径 → 绝对文件路径 的解析器。"""

    PROBE_EXTS = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue",
                  "/index.ts", "/index.tsx", "/index.js", "/index.jsx", "/index.vue",
                  "/index.mjs")

    def __init__(self, root, aliases, packages):
        self.root = root
        self.aliases = dict(aliases or {})
        self.packages = dict(packages or {})
        self.cache = {}

    def resolve(self, src, from_file):
        """返回绝对路径或 None。"""
        if not src or src.startswith(("http:", "https:", "data:")):
            return None
        key = (src, from_file)
        if key in self.cache:
            return self.cache[key]
        result = self._resolve(src, from_file)
        self.cache[key] = result
        return result

    def _resolve(self, src, from_file):
        base = None
        if src.startswith("."):
            base = os.path.normpath(os.path.join(os.path.dirname(from_file), src))
        else:
            # 工作区包名（含子路径），如 monitor-api/modules/shield
            for name in sorted(self.packages, key=len, reverse=True):
                if src == name or src.startswith(name + "/"):
                    rest = src[len(name):].lstrip("/")
                    base = os.path.normpath(os.path.join(self.packages[name], rest))
                    break
            if base is None:
                for alias in sorted(self.aliases, key=len, reverse=True):
                    if src == alias or src.startswith(alias + "/"):
                        rest = src[len(alias):].lstrip("/")
                        base = os.path.normpath(os.path.join(self.aliases[alias], rest))
                        break
            if base is None:
                # 裸包名：解析到 root 下的同名目录（monorepo 常见）
                head = src.split("/")[0]
                guess = os.path.join(self.root, head)
                if os.path.isdir(guess):
                    base = os.path.normpath(os.path.join(self.root, src))
        if base is None:
            return None
        for probe in self.PROBE_EXTS:
            candidate = base + probe
            if os.path.isfile(candidate):
                return candidate
        return None


# ---------------------------------------------------------------------------
# import / export 解析
# ---------------------------------------------------------------------------

RE_IMPORT_FROM = re.compile(
    r"""^[ \t]*import\s+(?P<clause>[^'";]*?)\s*from\s*['"](?P<src>[^'"]+)['"]""", re.M)
RE_IMPORT_SIDE = re.compile(r"""^[ \t]*import\s*['"](?P<src>[^'"]+)['"]""", re.M)
RE_EXPORT_FROM = re.compile(
    r"""^[ \t]*export\s+(?P<clause>\{[^}]*\}|\*)\s*from\s*['"](?P<src>[^'"]+)['"]""", re.M)
RE_EXPORT_DECL = re.compile(
    r"""^[ \t]*export\s+(?:default\s+)?(?:async\s+)?(?:const|let|var|function|class)\s+(?P<name>[A-Za-z_$][\w$]*)""",
    re.M)


def parse_import_clause(clause):
    """解析 import 子句 → (default, [named], ns)。"""
    clause = clause.strip()
    default_name = None
    ns_name = None
    named = []
    if not clause:
        return default_name, named, ns_name
    ns_match = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", clause)
    if ns_match:
        ns_name = ns_match.group(1)
        clause = clause.replace(ns_match.group(0), "")
    brace = re.search(r"\{(.*)\}", clause, re.S)
    if brace:
        for item in brace.group(1).split(","):
            item = item.strip()
            if not item:
                continue
            if " as " in item:
                item = item.split(" as ")[-1].strip()
            if re.match(r"^[A-Za-z_$][\w$]*$", item):
                named.append(item)
        clause = clause.replace(brace.group(0), "")
    clause = clause.strip().strip(",").strip()
    if clause and re.match(r"^[A-Za-z_$][\w$]*$", clause):
        default_name = clause
    return default_name, named, ns_name


def parse_imports(text):
    """返回 [{types, names, default, ns, src, line}]（types 仅记 'import'/'export_from'）。"""
    records = []
    for m in RE_IMPORT_FROM.finditer(text):
        default, named, ns = parse_import_clause(m.group("clause"))
        if default is None and not named and ns is None:
            continue
        records.append({
            "kind": "import", "default": default, "named": named, "ns": ns,
            "src": m.group("src"), "line": line_of(text, m.start()),
        })
    for m in RE_IMPORT_SIDE.finditer(text):
        records.append({"kind": "side", "default": None, "named": [], "ns": None,
                        "src": m.group("src"), "line": line_of(text, m.start())})
    for m in RE_EXPORT_FROM.finditer(text):
        default, named, ns = parse_import_clause(m.group("clause"))
        records.append({"kind": "export_from", "default": None, "named": named, "ns": ns,
                        "src": m.group("src"), "line": line_of(text, m.start())})
    return records


def parse_exports(text):
    """返回 (declared_names:set, reexport_named:{name:src}, reexport_all:[src])。"""
    declared = set(RE_EXPORT_DECL.findall(text))
    reexport_named = {}
    reexport_all = []
    for m in RE_EXPORT_FROM.finditer(text):
        clause = m.group("clause").strip()
        src = m.group("src")
        if clause == "*":
            reexport_all.append(src)
            continue
        for item in clause.strip("{}").split(","):
            item = item.strip()
            if not item:
                continue
            parts = re.split(r"\s+as\s+", item)
            reexport_named[parts[-1].strip()] = (src, parts[0].strip())
    return declared, reexport_named, reexport_all


# ---------------------------------------------------------------------------
# URL 与调用提取
# ---------------------------------------------------------------------------

URL_LITERAL = r"""(?:`[^`]*`|'[^']*'|"[^"]*")"""
RE_FETCH_CALL = re.compile(r"""\bfetch\s*\(\s*(?P<url>""" + URL_LITERAL + r""")""")
RE_METHOD_CALL = re.compile(
    r"""(?P<obj>[A-Za-z_$][\w$.]*)\s*\.\s*(?P<m>get|post|put|delete|patch|head|options)"""
    r"""\s*(?:<[^()]{0,160}>)?\s*\(\s*(?P<url>""" + URL_LITERAL + r""")""")
RE_FACTORY_CALL = re.compile(
    r"""\b(?P<f>[A-Za-z_$][\w$]*)\s*\(\s*['"](?P<m>GET|POST|PUT|DELETE|PATCH|HEAD)['"]\s*,"""
    r"""\s*(?P<url>""" + URL_LITERAL + r""")""")
# 懒加载 import 说明：允许 webpack 魔法注释（import(/* webpackChunkName: 'X' */ '...')）
RE_LAZY_IMPORT_SPEC = r"""import\s*\(\s*(?:(?:/\*.*?\*/|//[^\n]*)\s*)*['"](?P<src>[^'"]+)['"]"""


def factory_calls(text):
    """request('GET', url) 形态的工厂调用（函数名需含 request，避免误收普通调用）。"""
    return [m for m in RE_FACTORY_CALL.finditer(text) if "request" in m.group("f").lower()]
RE_FACTORY_OBJ = re.compile(
    r"""\b(?P<f>[A-Za-z_$][\w$]*[Rr]equest)\s*\(\s*\{[^{}]{0,200}?url\s*:\s*(?P<url>""" + URL_LITERAL + r""")""",
    re.S)
RE_TEMPLATE_INTERP = re.compile(r"\$\{([^{}]*)\}")
RE_BRACE_PARAM_KEY = re.compile(r"(?<!\$)\{(\w+)\}")
RE_IDENT_EXPR = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$")

RE_CONST_ANY = re.compile(
    r"""^[ \t]*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*(?::[^=\n]+)?=\s*(?P<val>[^\n;]+?)\s*;?\s*$""",
    re.M)
RE_QUOTED_FULL = re.compile(r"""^(?P<q>[`'"])(?P<body>.*)(?P=q)$""", re.S)


def split_plus(expr):
    """按顶层 '+' 拆分表达式（忽略引号与括号内的加号）。"""
    parts, buf, depth_b, quote = [], [], 0, None
    i = 0
    while i < len(expr):
        ch = expr[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(expr):
                buf.append(expr[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "`'\"":
            quote = ch
            buf.append(ch)
        elif ch in "([{":
            depth_b += 1
            buf.append(ch)
        elif ch in ")]}":
            depth_b -= 1
            buf.append(ch)
        elif ch == "+" and depth_b == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts if len(parts) > 1 else [expr]


def eval_const_expr(expr, lookup, depth=0):
    """求值字符串常量表达式：字面量 / 模板串（可含 ${NAME}）/ 顶层 '+' 拼接。
    lookup(name) 返回被引用常量的值或 None。无法静态求值时返回 None（不猜）。"""
    if depth > 3:
        return None
    expr = expr.strip()
    m = RE_QUOTED_FULL.match(expr)
    if m:
        body = m.group("body")
        if "${" not in body:
            return body.replace("\\`", "`")
        failed = []

        def repl(mm):
            name = mm.group(1).strip()
            value = lookup(name) if RE_IDENT_EXPR.match(name) else None
            if value is None:
                failed.append(name)
                return ""
            return value

        out = RE_TEMPLATE_INTERP.sub(repl, body)
        return None if (failed or "${" in out) else out
    parts = split_plus(expr)
    if len(parts) <= 1:
        return None
    out = []
    for part in parts:
        part = part.strip()
        if not part:
            return None
        if part[0] in "`'\"":
            value = eval_const_expr(part, lookup, depth + 1)
        elif RE_IDENT_EXPR.match(part):
            value = lookup(part)
        else:
            value = None
        if value is None:
            return None
        out.append(value)
    return "".join(out)


def unquote(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] in "`'\"" and raw[-1] == raw[0]:
        return raw[1:-1], raw[0]
    return raw, ""


class ConstLookup(object):
    """dict 风格接口的常量查找器（normalize_url 用 `name in consts` / `consts[name]`）。"""

    def __init__(self, fn):
        self.fn = fn

    def __contains__(self, name):
        return self.fn(name) is not None

    def __getitem__(self, name):
        return self.fn(name)


RE_ABSOLUTE_URL = re.compile(r"""^\s*[`'"]?\s*(?:https?:)?//""")


def is_external_url(raw):
    """绝对 URL（外部服务/CDN/npm registry）不算业务后端接口，映射时单列。"""
    return bool(RE_ABSOLUTE_URL.match(raw))


def depth_confidence(depth):
    """深度 → 置信度：0 = 调用点在页面自身（🟢）；1 = 直接依赖（🟡）；≥2 = 间接候选（🔵）。"""
    if depth <= 0:
        return "🟢"
    if depth == 1:
        return "🟡"
    return "🔵"


def normalize_url(raw, consts):
    """→ (display, key, unresolved)  display 保留原样（可解析的 ${CONST} 已替换）；
    key 用于聚合同一接口；unresolved 为未解析的插值名列表。"""
    body, _quote = unquote(raw)
    unresolved = []

    def repl_display(m):
        expr = m.group(1).strip()
        value = consts[expr] if expr in consts else None
        if value is not None:
            return value
        unresolved.append(expr)
        if RE_IDENT_EXPR.match(expr):
            return "${%s}" % expr
        return "${?}"

    display = RE_TEMPLATE_INTERP.sub(repl_display, body)

    # key：首个 "/" 之前的插值视为前缀常量（保留名字区分，避免与实际路径参数混淆）；
    # 其余插值与 {pk} 之类占位符归一为 :param，使同一接口的不同参数名可聚合。
    first_slash = display.find("/")

    def repl_key(m):
        # 前缀常量用 ${NAME} 形态保留（带 $ 可避免被下面的 {pk}→:param 规则二次吞掉）
        if first_slash < 0 or m.start() < first_slash:
            expr = m.group(1).strip()
            return "${%s}" % (expr if RE_IDENT_EXPR.match(expr) else "?")
        return ":param"

    key = RE_TEMPLATE_INTERP.sub(repl_key, display)
    key = RE_BRACE_PARAM_KEY.sub(":param", key)
    key = key.split("?")[0]            # query 不进 key：同一接口的不同查询参数必须聚合成一条
    key = re.sub(r"/{2,}", "/", key).strip().rstrip("/")
    display = display.strip().rstrip("/")
    return display, key, unresolved


RE_DEF_START = re.compile(
    r"""^[ \t]*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:const|let|var|function)\s+"""
    r"""(?P<name>[A-Za-z_$][\w$]*)""")
RE_CLASS_START = re.compile(
    r"""^[ \t]*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)""",
    re.M)
KEYWORD_NAMES = {"if", "for", "while", "switch", "catch", "function", "return", "constructor",
                 "do", "else", "try", "finally", "case", "typeof", "await", "new", "in", "of",
                 "delete", "void", "super", "this", "yield"}

RE_METHOD_HEAD = re.compile(
    r"""(?m)^[ \t]{1,12}(?:public\s+|private\s+|protected\s+|static\s+|async\s+|readonly\s+|override\s+|get\s+|set\s+)*"""
    r"""(?P<name>[A-Za-z_$][\w$]*)\s*(?:<[^<>{}]{0,80}>)?\s*\(""")
RE_PROP_ARROW_HEAD = re.compile(
    r"""(?m)^[ \t]{1,12}(?:(?:public|private|protected|readonly|static|override)\s+)*"""
    r"""(?P<name>[A-Za-z_$][\w$]*)\s*(?::\s*[^=;\n]{0,100})?=\s*(?:async\s*)?\(""")


def balanced_scan(text, i):
    """text[i] == '(' 起，返回配对 ')' 的下标（跳过字符串/注释/嵌套）；失败返回 -1。"""
    depth = 0
    quote = None
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
        elif ch == "/" and text.startswith("//", i):
            j = text.find("\n", i)
            i = len(text) if j < 0 else j
            continue
        elif ch == "/" and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = len(text) if j < 0 else j + 2
            continue
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def skip_type_annotation(text, i):
    """跳过 `: Type` 片段（忽略泛型/对象类型嵌套），返回下一非空白位置。"""
    while i < len(text) and text[i] in " \t":
        i += 1
    if i < len(text) and text[i] == ":":
        i += 1
        depth = 0
        while i < len(text):
            ch = text[i]
            if ch in "({[<":
                depth += 1
            elif ch in ")}]>":
                if depth == 0:
                    break
                depth -= 1
            elif ch in ";=" and depth == 0:
                break
            i += 1
    while i < len(text) and text[i] in " \t":
        i += 1
    return i


def find_member_defs(text):
    """类体成员定义（方法 / 箭头函数属性）→ [(pos, name)]。

    参数表按括号配平扫描：支持多行、带 `{ }` `;` 的复杂参数（如
    `getAdminUsers(params?: { userId?: string; take?: number }) {`），
    避免这类声明漏识别导致其后的调用被算到上一个方法头上。
    """
    out = []
    for m in RE_METHOD_HEAD.finditer(text):
        name = m.group("name")
        if name in KEYWORD_NAMES:
            continue
        paren_start = m.end() - 1
        paren_end = balanced_scan(text, paren_start)
        if paren_end < 0:
            continue
        nxt = skip_type_annotation(text, paren_end + 1)
        if nxt < len(text) and text[nxt] == "{":
            out.append((m.start(), name))
    for m in RE_PROP_ARROW_HEAD.finditer(text):
        name = m.group("name")
        if name in KEYWORD_NAMES:
            continue
        paren_start = m.end() - 1
        paren_end = balanced_scan(text, paren_start)
        if paren_end < 0:
            continue
        nxt = skip_type_annotation(text, paren_end + 1)
        if text.startswith("=>", nxt):
            out.append((m.start(), name))
    return sorted(set(out))
RE_PROP_ARROW = re.compile(
    r"""^[ \t]{1,12}(?:(?:public|private|protected|readonly)\s+)*(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(""")
# 函数式注入（Angular 14+ / 部分 Vue）：`private readonly #svc = inject(SomeService)`
RE_INJECT_PROP = re.compile(
    r"""(?:^|[;{(,])\s*(?:(?:public|private|protected|readonly|static|declare|override)\s+)*"""
    r"""(?P<prop>#?[A-Za-z_$][\w$]*)\s*(?::\s*[A-Za-z_$][\w$<>\[\],\s|]*?)?\s*=\s*inject\s*(?:<[^>]*>)?\s*\(\s*(?P<cls>[A-Za-z_$][\w$]*)\s*\)""",
    re.M)   # 必须 re.M：换行后声明的 inject() 属性否则整行漏识别（实测 bug）


def extract_calls(text, request_objects):
    """从一段代码里提取请求调用 → [{call, method, url_raw, index, pos}]。"""
    hits = []
    for m in RE_FETCH_CALL.finditer(text):
        hits.append({"method": "GET", "url_raw": m.group("url"), "index": m.start(),
                     "obj": "fetch"})
    for m in RE_METHOD_CALL.finditer(text):
        obj = m.group("obj")
        tail = obj.split(".")[-1].lower().lstrip("$")
        if tail not in request_objects and ("$" + tail) not in request_objects:
            continue
        hits.append({"method": m.group("m").upper(), "url_raw": m.group("url"),
                     "index": m.start(), "obj": obj})
    for m in factory_calls(text):
        hits.append({"method": m.group("m").upper(), "url_raw": m.group("url"),
                     "index": m.start(), "obj": m.group("f")})
    for m in RE_FACTORY_OBJ.finditer(text):
        hits.append({"method": "", "url_raw": m.group("url"), "index": m.start(),
                     "obj": m.group("f")})
    seen = set()
    dedup = []
    for h in sorted(hits, key=lambda x: x["index"]):
        if h["index"] in seen:
            continue
        seen.add(h["index"])
        dedup.append(h)
    return dedup


RE_ARROW_OR_FUNC = re.compile(r"""(?:=>|\bfunction\b|\basync\s*\()""")
RE_DECL_CONST = re.compile(r"""^[ \t]*(?:export\s+)?(?:default\s+)?(?:const|let|var)\b""")


def extract_symbol_defs(text, request_objects, strict_const=False):
    """提取文件中「符号 → 请求调用」：const/function/method 归属。
    → {symbol: [call...]}  symbol 形如 'getAll' 或 'RoleService.getAll'。

    strict_const=True（接口层文件）：任何 const 声明都视为符号（`export const x = request(...)`）。
    strict_const=False（页面/组件文件）：只有函数式 const（箭头函数/function）才切换符号，
    方法体里的数据常量（`const data = JSON.stringify(...)`）不再抢占方法归属。
    """
    defs = {}
    current_class = None
    current_symbol = None
    class_defs = sorted((m.start(), m.group("name")) for m in RE_CLASS_START.finditer(text))
    member_defs = find_member_defs(text)
    ci = mi = 0
    lines = text.split("\n")
    offset = 0
    for raw in lines:
        stripped = raw.strip()
        line_start = offset
        line_end = line_start + len(raw)
        offset = line_end + 1
        if not stripped or stripped.startswith(("//", "*", "/*")):
            continue
        while ci < len(class_defs) and class_defs[ci][0] < line_start:
            ci += 1
        if ci < len(class_defs) and class_defs[ci][0] <= line_end:
            current_class = class_defs[ci][1]
            current_symbol = None
            ci += 1
            continue
        while mi < len(member_defs) and member_defs[mi][0] < line_start:
            mi += 1
        if mi < len(member_defs) and member_defs[mi][0] <= line_end:
            current_symbol = member_defs[mi][1]
            mi += 1
        d = RE_DEF_START.match(raw) or RE_PROP_ARROW.match(raw)
        if d:
            if strict_const or not RE_DECL_CONST.match(raw) or RE_ARROW_OR_FUNC.search(raw):
                current_symbol = d.group("name")
                if raw and not raw[0].isspace():
                    current_class = None
        if current_symbol is None and current_class is None:
            continue
        for call in extract_calls(raw, request_objects):
            symbol = current_symbol or ""
            if current_class and current_symbol:
                symbol = current_class + "." + current_symbol
            elif current_class and not current_symbol:
                symbol = current_class
            if not symbol:
                continue
            defs.setdefault(symbol, []).append(
                {"method": call["method"], "url_raw": call["url_raw"],
                 "line": line_of(text, line_start + call["index"])})
    return defs


def extract_lazy_imports(text):
    """const X = () => import('...') / lazy(() => import('...')) → {X: src}（容忍魔法注释）"""
    result = {}
    pattern = re.compile(
        r"""(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:lazy\s*\(\s*)?(?:async\s*)?\("""
        r"""[^)]*\)\s*=>\s*""" + RE_LAZY_IMPORT_SPEC, re.S)
    for m in pattern.finditer(text):
        result.setdefault(m.group(1), m.group("src"))
    return result


# ---------------------------------------------------------------------------
# 路由提取
# ---------------------------------------------------------------------------

RE_PATH_PROP = re.compile(r"""\bpath\s*:\s*(?P<q>['"`])(?P<val>[^'"`]*)(?P=q)""")
RE_PATH_ATTR = re.compile(r"""\bpath=(?P<q>['"])(?P<val>[^'"]*)(?P=q)""")
RE_COMPONENT_PROP = re.compile(r"""\bcomponent\s*:\s*(?P<val>[A-Za-z_$][\w$.]*)""")
RE_COMPONENTS_PROP = re.compile(r"""\bcomponents\s*:\s*\{(?P<body>[^}]*)\}""")
RE_INLINE_IMPORT = re.compile(RE_LAZY_IMPORT_SPEC, re.S)
RE_LOAD_CHILDREN = re.compile(
    r"""\bloadChildren\s*:\s*\([^)]*\)\s*=>\s*""" + RE_LAZY_IMPORT_SPEC, re.S)
RE_JSX_ROUTE = re.compile(r"""<Route\b(?P<attrs>[^>]{0,400})/?>""", re.S)
RE_ROUTE_NAME = re.compile(r"""\bname\s*:\s*['"`]([^'"`]+)['"`]""")


def extract_routes_from_file(path, text, resolver, root, lazy_map):
    """从单个路由文件提取条目 → [{route, name, component_src, line, composed}]"""
    entries = []
    matches = list(RE_PATH_PROP.finditer(text)) + list(RE_PATH_ATTR.finditer(text))
    if not matches:
        return entries
    matches.sort(key=lambda m: m.start())
    for idx, m in enumerate(matches):
        route = m.group("val")
        line_no = line_of(text, m.start())
        window_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        window = text[m.end():window_end][:1200]
        component_src = None
        inline = RE_INLINE_IMPORT.search(window)
        if inline:
            component_src = inline.group("src")
        else:
            comp = RE_COMPONENT_PROP.search(window)
            comps = RE_COMPONENTS_PROP.search(window)
            names = []
            if comp:
                names.append(comp.group("val").split(".")[-1])
            if comps:
                for item in comps.group("body").split(","):
                    item = item.strip()
                    if not item:
                        continue
                    val = item.split(":")[-1].strip()
                    if re.match(r"^[A-Za-z_$][\w$]*$", val):
                        names.append(val)
            for name in names:
                if name in lazy_map:
                    component_src = lazy_map[name]
                    break
                for imp in parse_imports(text):
                    if imp["kind"] == "import" and (
                            imp["default"] == name or name in imp["named"]):
                        component_src = imp["src"]
                        break
                if component_src:
                    break
        name_match = RE_ROUTE_NAME.search(window)
        child_match = RE_LOAD_CHILDREN.search(window)
        entries.append({
            "route": route,
            "name": name_match.group(1) if name_match else "",
            "component_src": component_src,
            "children_src": child_match.group("src") if child_match else None,
            "line": line_no,
            "file": path,
        })
    return entries


def detect_file_based_routes(files, root):
    """无配置路由时的文件式路由兜底（Next/Nuxt/uni-app 风格）。"""
    entries = []
    page_markers = ("/pages/", "/views/", "/app/")
    for path in files:
        rel = to_rel(path, root)
        if not any(marker in "/" + rel for marker in page_markers):
            continue
        base = os.path.basename(path)
        stem = re.sub(r"\.[^.]+$", "", base)
        if stem.startswith(("_", "components", "util", "utils")):
            continue
        if not any(seg in ("pages", "views", "app") for seg in rel.split("/")):
            continue
        idx = max([i for i, seg in enumerate(rel.split("/")) if seg in ("pages", "views", "app")] or [-1])
        if idx < 0:
            continue
        parts = rel.split("/")[idx + 1:]
        parts[-1] = stem
        if parts[-1] in ("index", "page", "_index"):
            parts = parts[:-1]
        if not parts:
            route = "/"
        else:
            route = "/" + "/".join(parts)
        entries.append({"route": route, "name": "", "component_src": None,
                        "component_file": path, "line": 0, "file": path})
    return entries


# ---------------------------------------------------------------------------
# 主扫描
# ---------------------------------------------------------------------------

class ScanResult(object):
    def __init__(self):
        self.pages = []          # 页面（路由）
        self.pages_agg = []      # 页面（按文件聚合多路由）
        self.api_defs = []       # 接口定义
        self.page_apis = []      # 页面 → 接口
        self.api_pages = []      # 接口 → 页面
        self.deps = []           # 页面 → 直接依赖
        self.pending = []        # 待确认
        self.stats = {}


def scan(root, opts):
    includes = opts.get("include") or []
    excludes = opts.get("exclude") or []
    request_objects = set(DEFAULT_REQUEST_OBJECTS)
    request_objects.update(opts.get("requestObjects") or [])
    max_depth = int(opts.get("maxDepth") or 2)
    route_globs = opts.get("routes") or []
    api_dirs = [os.path.normpath(os.path.join(root, d)).replace(os.sep, "/")
                for d in (opts.get("apiDirs") or [])]
    pages_dirs = [os.path.normpath(os.path.join(root, d)).replace(os.sep, "/")
                  for d in (opts.get("pagesDirs") or [])]

    aliases = {}
    aliases.update(detect_tsconfig_aliases(root))
    aliases.update(detect_webpack_aliases(root))
    for k, v in (opts.get("aliases") or {}).items():
        p = v if os.path.isabs(v) else os.path.normpath(os.path.join(root, v))
        aliases[k] = p
    packages = detect_workspace_packages(root)
    resolver = Resolver(root, aliases, packages)

    files = walk_files(root, includes, excludes)
    texts = {}
    for path in files:
        texts[path] = read_text(path)

    result = ScanResult()
    result.stats["files"] = len(files)
    result.stats["aliases"] = {k: to_rel(v, root) for k, v in aliases.items()}
    result.stats["packages"] = {k: to_rel(v, root) for k, v in packages.items()}

    # ---- 1. 路由 ----
    route_files = []
    for path in files:
        rel = to_rel(path, root)
        if route_globs:
            if not any(match_glob(rel, g) for g in route_globs):
                continue
        else:
            base = os.path.basename(path)
            if not (re.search(r"rout", base, re.I) or "/router" in "/" + rel
                    or "/routes" in "/" + rel):
                continue
            text = texts[path]
            if not re.search(r"""\bpath\s*[:=]""", text):
                continue
        route_files.append(path)

    route_entries = []
    for path in route_files:
        text = texts[path]
        lazy_map = extract_lazy_imports(text)
        for entry in extract_routes_from_file(path, text, resolver, root, lazy_map):
            if entry["component_src"]:
                resolved = resolver.resolve(entry["component_src"], path)
                entry["component_file"] = resolved
            route_entries.append(entry)
    if not route_entries:
        route_entries = detect_file_based_routes(files, root)
        if route_entries:
            result.stats["route_source"] = "file-based"
    else:
        result.stats["route_source"] = "config"
    result.stats["route_files"] = len(route_files)

    # Angular loadChildren：子路由文件的条目拼上父路由前缀（一层；更深的嵌套仍标相对路径待确认）
    child_parents = {}
    for entry in route_entries:
        src = entry.get("children_src")
        if not src:
            continue
        target = resolver.resolve(src, entry["file"])
        if not target:
            continue
        target_dir = os.path.dirname(target)
        for candidate in route_files:
            if os.path.dirname(candidate) == target_dir:
                child_parents.setdefault(candidate, []).append(entry["route"])
    if child_parents:
        composed_entries = []
        for entry in route_entries:
            parents = child_parents.get(entry["file"])
            if not parents:
                composed_entries.append(entry)
                continue
            for parent in parents:
                base = (parent or "").rstrip("/")
                sub = (entry["route"] or "").strip("/")
                new_route = (base + ("/" + sub if sub else "")) or "/"
                composed_entries.append(dict(entry, route=new_route, composed=True))
        route_entries = composed_entries

    # 页面集合（去重：同一页面文件可能被多个路由引用）
    pages = []
    seen_files = set()
    for entry in route_entries:
        comp = entry.get("component_file")
        route = entry["route"] or "/"
        if not route.startswith("/") and route not in ("", "/"):
            entry["relative"] = True
        pages.append({
            "route": route,
            "name": entry.get("name") or "",
            "file": comp,
            "rel": to_rel(comp, root) if comp else "",
            "line": entry.get("line") or 0,
            "source_file": to_rel(entry["file"], root),
            "relative": bool(entry.get("relative")),
        })
        if comp:
            seen_files.add(comp)
    result.pages = pages
    if not route_entries:
        result.pending.append({"type": "路由", "loc": "-", "content": "未提取到任何路由",
                               "reason": "配置式与文件式均未命中，需提供 --routes 或声明文件"})

    # ---- 2. 接口定义 ----
    api_files = set()
    for path in files:
        p = path.replace(os.sep, "/")
        if any(p.startswith(d + "/") or p == d for d in api_dirs):
            api_files.add(path)
    symbol_urls = {}   # (file, symbol) -> [{method,url_raw,line}]
    for path in files:
        text = texts[path]
        if not re.search(r"""\b(?:get|post|put|delete|patch|fetch|request)\s*(?:<[^()]{0,160}>)?\s*\(""", text):
            continue
        # 接口层文件判定：显式声明的 apiDirs，或自带 ≥2 个 request('METHOD', url) 工厂调用的模块
        api_like = path in api_files or len(factory_calls(text)) >= 2
        defs = extract_symbol_defs(text, request_objects, strict_const=api_like)
        if defs:
            symbol_urls[path] = defs

    # 接口层文件（决定深度归因）：① 显式 apiDirs；② 符号全部由类方法承载（Angular/Nest 风格
    # service，页面的 `this.#svc.method()` 视为页面自身在调接口）；③ 工厂模块（≥2 个 request 工厂）。
    # 组件/工具文件不算接口层 —— 它们内部的请求发生在依赖里，深度应按距离算。
    api_layer_files = set(api_files)
    for path, defs in symbol_urls.items():
        if path in api_layer_files:
            continue
        class_defs = [k for k in defs if "." in k]
        if class_defs and len(class_defs) == len(defs):
            api_layer_files.add(path)
        elif len(factory_calls(texts.get(path, ""))) >= 2:
            api_layer_files.add(path)

    for path, defs in symbol_urls.items():
        is_api_dir = path in api_files
        for symbol, calls in defs.items():
            for call in calls:
                result.api_defs.append({
                    "file": to_rel(path, root), "symbol": symbol,
                    "method": call["method"], "url_raw": call["url_raw"], "line": call["line"],
                    "in_api_dir": is_api_dir,
                })

    # ---- 3. 调用点 ----
    # (a) 导入符号的调用点： (file, symbol) -> [(line, obj)]
    import_symbols = {}   # file -> list of dicts from parse_imports
    for path, text in texts.items():
        import_symbols[path] = parse_imports(text)

    # 常量表达式表（用于 URL 归一化）：同文件 + 经 import / re-export 链追查
    const_exprs = {}
    for path, text in texts.items():
        table = {}
        for m in RE_CONST_ANY.finditer(text):
            table.setdefault(m.group("name"), m.group("val").strip())
        const_exprs[path] = table

    const_memo = {}

    def const_value(start_file, name, hops=4):
        """沿 import / re-export 链解析字符串常量（如 API_PREFIX）。"""
        key = (start_file, name)
        if key in const_memo:
            return const_memo[key]
        const_memo[key] = None  # 占位防环
        visited = set()
        queue = [(start_file, name, 0)]
        while queue:
            fpath, nm, depth = queue.pop(0)
            if not fpath or (fpath, nm) in visited or depth > hops:
                continue
            visited.add((fpath, nm))
            table = const_exprs.get(fpath) or {}
            if nm in table:
                value = eval_const_expr(table[nm], lambda n: const_value(fpath, n, hops))
                if value is not None:
                    const_memo[key] = value
                    return value
            text = texts.get(fpath, "")
            if not text:
                continue
            for imp in import_symbols.get(fpath, []):
                target = resolver.resolve(imp["src"], fpath)
                if not target:
                    continue
                names = set(imp["named"])
                if imp["default"]:
                    names.add(imp["default"])
                if nm in names:
                    queue.append((target, nm, depth + 1))
            _decl, reexport_named, reexport_all = parse_exports(text)
            if nm in reexport_named:
                src, orig = reexport_named[nm]
                target = resolver.resolve(src, fpath)
                if target:
                    queue.append((target, orig or nm, depth + 1))
            for src in reexport_all:
                target = resolver.resolve(src, fpath)
                if target:
                    queue.append((target, nm, depth + 1))
        return None

    def consts_for(path):
        return ConstLookup(lambda name: const_value(path, name))

    # 符号定义查找：沿 import / re-export 边做有界 BFS（跨文件 + 跨包 + barrel 中转）
    def defs_for_symbol(start_file, symbol, hops=4):
        """在 start_file 及其 import / re-export 链上找到 symbol 的接口定义。"""
        visited = set()
        queue = [(start_file, symbol, 0)]
        while queue:
            fpath, name, depth = queue.pop(0)
            if not fpath or (fpath, name) in visited or depth > hops:
                continue
            visited.add((fpath, name))
            defs = symbol_urls.get(fpath)
            if defs:
                if name in defs:
                    return [{"file": fpath, **dict(c)} for c in defs[name]]
                base, _dot, tail = name.rpartition(".")
                for key, calls in defs.items():
                    kbase, _kdot, ktail = key.rpartition(".")
                    if ktail != (tail or name):
                        continue
                    if base:
                        if kbase == base:
                            return [{"file": fpath, **dict(c)} for c in calls]
                    else:
                        # 无类名限定：仅当该文件只有一个类（或全为模块级符号）时接受，避免误配
                        classes = set(k.split(".")[0] for k in defs if "." in k)
                        if len(classes) <= 1:
                            return [{"file": fpath, **dict(c)} for c in calls]
            text = texts.get(fpath, "")
            if not text:
                continue
            base_name = name.split(".")[0]
            for imp in parse_imports(text):
                target = resolver.resolve(imp["src"], fpath)
                if not target:
                    continue
                names = set(imp["named"])
                if imp["default"]:
                    names.add(imp["default"])
                if base_name in names:
                    queue.append((target, name, depth + 1))
                elif imp["ns"] and base_name == imp["ns"] and "." in name:
                    queue.append((target, name.split(".", 1)[1], depth + 1))
            _decl, reexport_named, reexport_all = parse_exports(text)
            if name in reexport_named:
                src, orig = reexport_named[name]
                target = resolver.resolve(src, fpath)
                if target:
                    queue.append((target, orig or name, depth + 1))
            for src in reexport_all:
                target = resolver.resolve(src, fpath)
                if target:
                    queue.append((target, name, depth + 1))
        return []

    # (b) 逐文件找"符号调用点"
    symbol_uses = {}   # (file, symbol) -> [line]
    ns_uses = {}       # (file, ns) -> [(line, method)]
    direct_calls = {}  # file -> [call]
    class_ctor = {}    # file -> {prop: ClassName}
    for path, text in texts.items():
        if path in api_files and not pages_dirs:
            pass
        imports = import_symbols.get(path, [])
        for imp in imports:
            target = resolver.resolve(imp["src"], path)
            if imp["named"]:
                for name in imp["named"]:
                    for m in re.finditer(r"\b" + re.escape(name) + r"\s*\(", text):
                        symbol_uses.setdefault((path, name), []).append(line_of(text, m.start()))
            if imp["ns"]:
                for m in re.finditer(r"\b" + re.escape(imp["ns"]) + r"\s*\.\s*([A-Za-z_$][\w$]*)\s*\(", text):
                    ns_uses.setdefault((path, imp["ns"]), []).append(
                        (line_of(text, m.start()), m.group(1)))
        # 依赖注入：构造函数注入（private prop: Class）+ 函数式注入（prop = inject(Class)）
        for m in re.finditer(r"""(?:private|public|protected|readonly)\s+(#?[A-Za-z_$][\w$]*)\s*:\s*([A-Za-z_$][\w$<>]*)""", text):
            class_ctor.setdefault(path, {})[m.group(1).lstrip("#_")] = m.group(2).split("<")[0]
        for m in RE_INJECT_PROP.finditer(text):
            class_ctor.setdefault(path, {})[m.group("prop").lstrip("#_")] = m.group("cls")
        calls = extract_calls(text, request_objects)
        if calls:
            direct_calls[path] = calls

    # ---- 4. import 图与归属 ----
    exports_cache = {}
    for path, text in texts.items():
        exports_cache[path] = parse_exports(text)

    # barrel 文件（`export * from` / `export {...} from` 集合，如 index.ts 中转站）：
    # 遍历时绕开——否则页面会"继承"整个目录的全部接口（噪声爆炸）。
    # 符号解析（defs_for_symbol / const_value）仍会穿过 barrel，保证精确性。
    barrel_files = set()
    for path, text in texts.items():
        _decl, reexport_named, reexport_all = exports_cache[path]
        if path in api_files or direct_calls.get(path):
            continue
        if len(reexport_all) + len(reexport_named) >= 3:
            barrel_files.add(path)

    page_file_set = set(p["file"] for p in pages if p["file"])

    def resolve_name_in_module(module_file, name, hops=3):
        """在 module_file（含其 re-export 链）里找到「定义 name 的文件」。"""
        out = set()
        visited = set()
        queue = [(module_file, 0)]
        while queue:
            fpath, depth = queue.pop(0)
            if not fpath or fpath in visited or depth > hops:
                continue
            visited.add(fpath)
            declared, reexport_named, reexport_all = exports_cache.get(fpath) or parse_exports(
                texts.get(fpath, ""))
            if name in declared:
                out.add(fpath)
                continue
            if name in reexport_named:
                target = resolver.resolve(reexport_named[name][0], fpath)
                if target:
                    queue.append((target, depth + 1))
                continue
            for src in reexport_all:
                target = resolver.resolve(src, fpath)
                if target:
                    queue.append((target, depth + 1))
        return out

    graph = {}
    for path, imports in import_symbols.items():
        edges = []
        for imp in imports:
            target = resolver.resolve(imp["src"], path)
            if not target or target == path:
                continue
            names = set(imp["named"])
            if imp["default"]:
                names.add(imp["default"])
            if target in barrel_files:
                # barrel：按导入的符号名穿透到定义文件（而非扇出整个目录）
                if names:
                    for name in names:
                        edges.extend(resolve_name_in_module(target, name))
                continue
            edges.append(target)
        graph[path] = sorted(set(edges))

    symbol_uses_by_file = {}
    for (fpath, symbol), lines in symbol_uses.items():
        symbol_uses_by_file.setdefault(fpath, []).append((symbol, lines))
    ns_uses_by_file = {}
    for (fpath, ns), uses in ns_uses.items():
        ns_uses_by_file.setdefault(fpath, []).append((ns, uses))

    def call_sites_from_file(path):
        """一个文件里的所有请求调用 → [{method,url,key,display,unresolved,line,evidence,external}]

        注意：URL 归一化必须用 **URL 定义所在文件**（url_file）的常量表——调用点文件里
        通常没有 API_PREFIX 之类的导入（如页面注入服务、服务里写 URL）。
        """
        found = []

        def add(method, url_raw, line, via, url_file, def_file=None):
            display, key, unresolved = normalize_url(url_raw, consts_for(url_file))
            found.append({
                "method": method or "?", "display": display, "key": key,
                "unresolved": unresolved, "line": line,
                "evidence": "%s:%d" % (to_rel(path, root), line),
                "via": via, "external": is_external_url(url_raw),
                "def_file": def_file,
            })

        for call in direct_calls.get(path, []):
            add(call["method"], call["url_raw"], line_of(texts[path], call["index"]), "direct", path)
        for symbol, lines in symbol_uses_by_file.get(path, []):
            for d in defs_for_symbol(path, symbol):
                for ln in sorted(set(lines)):
                    add(d["method"], d["url_raw"], ln, "import:" + symbol,
                        d.get("file") or path, d.get("file"))
        for ns, uses in ns_uses_by_file.get(path, []):
            imp = next((i for i in import_symbols.get(path, []) if i["ns"] == ns), None)
            if not imp:
                continue
            target = resolver.resolve(imp["src"], path) or path
            for ln, method_name in uses:
                for d in defs_for_symbol(target, method_name):
                    add(d["method"], d["url_raw"], ln, "ns:%s.%s" % (ns, method_name),
                        d.get("file") or target, d.get("file"))
        # 类注入实例方法调用：this.prop.method(
        for prop, cls in class_ctor.get(path, {}).items():
            for m in re.finditer(
                    r"\bthis\.\s*[#_]?%s\s*\.\s*([A-Za-z_$][\w$]*)\s*\(" % re.escape(prop),
                    texts[path]):
                method_name = m.group(1)
                defs = defs_for_symbol(path, cls + "." + method_name) or \
                    defs_for_symbol(path, method_name)
                for d in defs:
                    add(d["method"], d["url_raw"], line_of(texts[path], m.start(1)),
                        "inject:%s.%s" % (prop, method_name), d.get("file") or path)
        return found

    # 归属遍历不进入：接口层文件（服务/API 模块，它们内部的 http 调用是"定义"）与 barrel。
    # 组件 / 工具文件仍然遍历 —— 它们内部的请求是真实的下游调用（深度按距离算）。
    def_carrier_files = set(api_layer_files)

    # BFS：页面 → 深度内文件
    def reachable(page_file, depth):
        out = [(page_file, 0)]
        seen = {page_file}
        frontier = [page_file]
        for d in range(1, depth + 1):
            nxt = []
            for f in frontier:
                for n in graph.get(f, []):
                    if n in seen or n in api_files or n in page_file_set or n in def_carrier_files:
                        continue
                    seen.add(n)
                    out.append((n, d))
                    nxt.append(n)
            frontier = nxt
        return out

    # 同一页面文件可能挂多条路由（/grafana、/grafana/new 同一组件）→ 按文件聚合，避免行数翻倍
    pages_by_file = []
    by_file_index = {}
    for page in pages:
        if not page["file"]:
            pages_by_file.append(dict(page, routes=[page["route"]]))
            continue
        item = by_file_index.get(page["file"])
        if item is None:
            item = dict(page, routes=[page["route"]])
            by_file_index[page["file"]] = item
            pages_by_file.append(item)
        else:
            # 同一路由串可能被多个路由文件/应用重复注册（微前端常见）→ 去重保留一次
            if page["route"] not in item["routes"]:
                item["routes"].append(page["route"])
            if not item["name"] and page["name"]:
                item["name"] = page["name"]
    result.stats["routes"] = len(pages)
    result.stats["pages"] = len(by_file_index)
    result.pages_agg = pages_by_file

    def routes_label(item):
        routes = item.get("routes") or [item.get("route") or "/"]
        if len(routes) <= 2:
            return "、".join(routes)
        return "、".join(routes[:2]) + " 等 %d 条" % len(routes)

    page_api_rows = []
    api_page_map = {}
    dep_rows = []
    external_seen = set()
    def distance_to(page_file, target, cap=8):
        """页面 → 目标文件的真实 import 距离。

        **接口层**（apiDirs / 全部由类方法承载的 service / 工厂模块）与 **barrel** 视为不透明：
        命中它们返回 None，语义是"页面自己发起了这个请求"（保持调用点所在文件的深度，
        如 Angular 的 `this.#svc.method()` 仍算 🟢）。
        组件 / 工具文件（内含请求但不是接口层）参与距离计算 —— 请求发生在那里，
        深度应为该文件到页面的距离（而不是页面自己）。
        """
        if target == page_file:
            return 0
        if target in api_layer_files or target in barrel_files:
            return None
        seen, frontier, dist = {page_file}, [page_file], 0
        while frontier and dist < cap:
            dist += 1
            nxt = []
            for f in frontier:
                for n in graph.get(f, []):
                    if n in seen or n in api_layer_files or n in barrel_files:
                        continue
                    if n == target:
                        return dist
                    seen.add(n)
                    nxt.append(n)
            frontier = nxt
        return None

    for page in pages_by_file:
        pfile = page["file"]
        if not pfile:
            continue
        rows = []
        deps = []
        depth_memo = {}
        for fpath, depth in reachable(pfile, max_depth):
            if fpath != pfile and fpath not in api_files and fpath not in page_file_set:
                deps.append({"file": to_rel(fpath, root), "depth": depth})
            for site in call_sites_from_file(fpath):
                if site.get("external"):
                    external_seen.add((site["display"], site["evidence"]))
                    continue
                site = dict(site)
                # 深度按「请求实际发生在哪个文件」算：符号导入的请求发生在定义文件里，
                # 定义文件不在图里（接口层/barrel 不参与遍历）时才归到调用点所在文件。
                def_file = site.pop("def_file", None)
                row_depth = depth
                if def_file and def_file != fpath:
                    if def_file not in depth_memo:
                        depth_memo[def_file] = distance_to(pfile, def_file)
                    found_depth = depth_memo[def_file]
                    if found_depth is not None:
                        row_depth = found_depth
                if row_depth > max_depth:
                    continue
                site["depth"] = row_depth
                rows.append(site)
        # 去重（同 key+method+evidence）
        uniq, seen = [], set()
        for r in rows:
            sig = (r["method"], r["key"], r["evidence"], r["via"])
            if sig in seen:
                continue
            seen.add(sig)
            uniq.append(r)
        for r in uniq:
            row = {
                "routes": page["routes"], "route": routes_label(page),
                "page": page["rel"], "page_file": page["rel"],
                "method": r["method"], "url": r["display"],
                "key": r["key"], "via": r["via"], "evidence": r["evidence"],
                "depth": r["depth"], "unresolved": r["unresolved"],
                "confidence": depth_confidence(r["depth"]),
            }
            page_api_rows.append(row)
            api_page_map.setdefault((r["method"], r["key"]), {
                "method": r["method"], "key": r["key"], "display": r["display"],
                "sites": [],
            })["sites"].append({
                "routes": page["routes"], "route": routes_label(page),
                "page": page["rel"], "evidence": r["evidence"], "depth": r["depth"],
            })
        if deps:
            dep_rows.append({"route": routes_label(page), "routes": page["routes"],
                             "page": page["rel"], "deps": deps})
        if not uniq:
            result.pending.append({
                "type": "页面无接口命中", "loc": page["rel"] or routes_label(page),
                "content": routes_label(page),
                "reason": "未在其 import 图内找到请求调用（可能动态/封装过深）"})

    for api in api_page_map.values():
        api["sites"].sort(key=lambda s: (s["depth"], s["route"]))
        api["direct_count"] = len([s for s in api["sites"] if s["depth"] <= 1])
        api["indirect_count"] = len(api["sites"]) - api["direct_count"]
    result.page_apis = page_api_rows
    result.api_pages = sorted(api_page_map.values(),
                              key=lambda x: (-x["direct_count"], -len(x["sites"]), x["key"]))
    result.deps = dep_rows

    # 待确认：未解析插值
    for row in page_api_rows:
        if row["unresolved"]:
            result.pending.append({
                "type": "URL 含未解析常量", "loc": row["evidence"],
                "content": "%s %s（未解析：%s）" % (row["method"], row["url"], ", ".join(row["unresolved"])),
                "reason": "常量不在可解析范围（跨包/运行时/env）"})

    # 外部绝对 URL：不是业务后端接口，单列备查（不进映射）
    for display, evidence in sorted(external_seen)[:50]:
        result.pending.append({
            "type": "外部 URL（已剔除）", "loc": evidence, "content": display[:120],
            "reason": "指向第三方/外部服务，非本应用后端接口"})
    if len(external_seen) > 50:
        result.pending.append({
            "type": "外部 URL（已剔除）", "loc": "-",
            "content": "共 %d 处" % len(external_seen), "reason": "同上（已截断显示）"})

    result.stats["pages"] = len([p for p in pages if p["file"]])
    result.stats["route_entries"] = len(pages)
    result.stats["api_defs"] = len(result.api_defs)
    result.stats["page_api_rows"] = len(page_api_rows)
    result.stats["unique_apis"] = len(result.api_pages)
    return result


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def render_md(result, opts, root):
    lines = []
    lines.append("# 前端「页面 ↔ 接口」扫描结果")
    lines.append("")
    lines.append("> 根目录：`%s`" % root)
    lines.append("> 生成时间：%s · 扫描器：scan_frontend.py v%s" % (datetime.now().strftime("%Y-%m-%d %H:%M"), VERSION))
    lines.append("> 文件 %(files)s · 路由条目 %(route_entries)s · 页面 %(pages)s · 接口定义 %(api_defs)s · 映射行 %(page_api_rows)s · 去重接口 %(unique_apis)s"
                 % result.stats)
    lines.append("")
    lines.append("## 1. 路由与页面")
    lines.append("")
    lines.append("| 路由 | 名称 | 页面文件 | 置信度 | 备注 |")
    lines.append("|------|------|----------|--------|------|")
    for p in getattr(result, "pages_agg", result.pages):
        routes = p.get("routes") or [p.get("route") or "/"]
        route_label = "、".join(routes[:3])
        if len(routes) > 3:
            route_label += " 等 %d 条" % len(routes)
        conf = "🟢" if p["file"] else "🟡"
        note = ""
        if p["relative"]:
            note = "相对路径（嵌套路由，父级待确认）"
        if not p["file"]:
            note = (note + "；" if note else "") + "组件未解析"
        if p["line"]:
            note = (note + "；" if note else "") + "路由定义 %s:%d" % (p["source_file"], p["line"])
        lines.append("| `%s` | %s | %s | %s | %s |" % (
            route_label, p["name"] or "-", "`%s`" % p["rel"] if p["rel"] else "-", conf, note or "-"))
    lines.append("")
    lines.append("## 2. 接口定义（符号 → 接口）")
    lines.append("")
    lines.append("| 文件 | 符号 | 方法 | URL | 行 |")
    lines.append("|------|------|------|-----|----|")
    for d in result.api_defs:
        lines.append("| `%s` | %s | %s | `%s` | %d |" % (
            d["file"], d["symbol"] or "-", d["method"] or "?", d["url_raw"].strip("`'\""), d["line"]))
    lines.append("")
    lines.append("## 3. 页面 → 接口")
    lines.append("")
    lines.append("| 路由 | 页面文件 | 方法 | URL | 来源 | 证据 | 深度 | 置信度 |")
    lines.append("|------|----------|------|-----|------|------|------|--------|")
    for r in result.page_apis:
        lines.append("| `%s` | `%s` | %s | `%s` | %s | %s | %d | %s |" % (
            r["route"], r["page_file"], r["method"], r["url"], r["via"], r["evidence"],
            r["depth"], r.get("confidence", "")))
    lines.append("")
    lines.append("## 4. 接口 → 页面（反向）")
    lines.append("")
    lines.append("> 「直接调用」= 调用点在页面自身或其直接依赖内（深度 ≤1）；「间接候选」= 经依赖链间接关联（深度 ≥2），仅供参考、需人工确认。")
    lines.append("")
    lines.append("| 方法 | URL | 直接调用页面 | 间接候选 | 调用点（直接） |")
    lines.append("|------|-----|--------------|----------|----------------|")
    for api in result.api_pages:
        direct = [s for s in api["sites"] if s["depth"] <= 1]
        sites = "；".join("`%s` %s" % (s["route"], s["evidence"]) for s in direct[:12])
        if len(direct) > 12:
            sites += "；…共 %d 处" % len(direct)
        indirect = api.get("indirect_count", 0)
        lines.append("| %s | `%s` | %d | %s | %s |" % (
            api["method"], api["key"], len(direct),
            indirect if indirect else "-", sites or "-"))
    lines.append("")
    lines.append("## 5. 页面 → 直接依赖（组件/模块，深度内）")
    lines.append("")
    lines.append("| 路由 | 页面文件 | 依赖（深度） |")
    lines.append("|------|----------|--------------|")
    for d in result.deps:
        deps = "、".join("`%s`(%d)" % (x["file"], x["depth"]) for x in d["deps"][:15])
        if len(d["deps"]) > 15:
            deps += " …共 %d 个" % len(d["deps"])
        lines.append("| `%s` | `%s` | %s |" % (d["route"], d["page"], deps))
    lines.append("")
    lines.append("## 6. 待确认 / 未解析")
    lines.append("")
    lines.append("| 类型 | 位置 | 内容 | 原因 |")
    lines.append("|------|------|------|------|")
    for p in result.pending[:200]:
        lines.append("| %s | %s | %s | %s |" % (p["type"], p["loc"], p["content"], p["reason"]))
    lines.append("")
    lines.append("## 7. 统计")
    lines.append("")
    for key, val in result.stats.items():
        if isinstance(val, dict):
            lines.append("- %s：%s" % (key, json.dumps(val, ensure_ascii=False)))
        else:
            lines.append("- %s：%s" % (key, val))
    lines.append("")
    return "\n".join(lines)


def render_tsv(result, opts, root):
    lines = []
    lines.append("#pages\troute\tname\tfile\trelative")
    for p in result.pages:
        lines.append("P\t%s\t%s\t%s\t%s" % (p["route"], p["name"], p["rel"], int(p["relative"])))
    lines.append("#defs\tfile\tsymbol\tmethod\turl\tline")
    for d in result.api_defs:
        lines.append("D\t%s\t%s\t%s\t%s\t%d" % (d["file"], d["symbol"], d["method"], d["url_raw"].strip("`'\""), d["line"]))
    lines.append("#page_api\troute\tpage\tmethod\turl\tvia\tevidence\tdepth")
    for r in result.page_apis:
        lines.append("A\t%s\t%s\t%s\t%s\t%s\t%s\t%d" % (
            r["route"], r["page_file"], r["method"], r["url"], r["via"], r["evidence"], r["depth"]))
    lines.append("#api_pages\tmethod\turl\tpages")
    for api in result.api_pages:
        pages_str = ";".join(s["route"] for s in api["sites"])
        lines.append("R\t%s\t%s\t%s" % (api["method"], api["key"], pages_str))
    return "\n".join(lines)


def render_json(result, opts, root):
    return json.dumps({
        "root": root, "generated": datetime.now().isoformat(timespec="seconds"),
        "scanner": "scan_frontend.py v" + VERSION,
        "stats": result.stats,
        "pages": result.pages,
        "pages_agg": getattr(result, "pages_agg", result.pages),
        "api_defs": result.api_defs,
        "page_apis": result.page_apis,
        "api_pages": [{k: v for k, v in api.items()} for api in result.api_pages],
        "deps": result.deps,
        "pending": result.pending[:500],
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 探测（--dump-config）与新鲜度（--check）
# ---------------------------------------------------------------------------

def detect_framework(root, files, texts):
    signals = []
    pkg_path = os.path.join(root, "package.json")
    deps = {}
    data = load_jsonc(pkg_path)
    if isinstance(data, dict):
        deps = {}
        for key in ("dependencies", "devDependencies"):
            if isinstance(data.get(key), dict):
                deps.update(data[key])
    name_set = set(deps)
    if "vue" in name_set:
        signals.append("package.json: vue")
    if "react" in name_set:
        signals.append("package.json: react")
    if "@angular/core" in name_set:
        signals.append("package.json: @angular/core")
    if "next" in name_set:
        signals.append("package.json: next")
    if "nuxt" in name_set:
        signals.append("package.json: nuxt")
    routes = []
    api_dirs = set()
    pages_dirs = set()
    for path in files:
        rel = to_rel(path, root)
        base = os.path.basename(path)
        if re.search(r"rout", base, re.I) and re.search(r"""\bpath\s*:""", texts.get(path, "")):
            routes.append(rel)
        segments = rel.split("/")
        for seg in segments[:-1]:
            low = seg.lower()
            if low in ("api", "apis", "services", "service"):
                api_dirs.add("/".join(segments[:segments.index(seg) + 1]))
        for i, seg in enumerate(segments[:-1]):
            if seg.lower() in ("pages", "views"):
                pages_dirs.add("/".join(segments[:i + 1]))
    framework = "unknown"
    if "next" in name_set:
        framework = "next"
    elif "nuxt" in name_set:
        framework = "nuxt"
    elif "@angular/core" in name_set:
        framework = "angular"
    elif "vue" in name_set:
        framework = "vue"
    elif "react" in name_set:
        framework = "react"
    return {
        "framework": framework,
        "signals": signals,
        "routes": sorted(set(routes))[:80],
        "pagesDirs": sorted(pages_dirs)[:20],
        "apiDirs": sorted(api_dirs)[:20],
        "aliases": {k: to_rel(v, root) for k, v in
                    list(detect_tsconfig_aliases(root).items()) +
                    list(detect_webpack_aliases(root).items())},
        "workspacePackages": {k: to_rel(v, root)
                              for k, v in detect_workspace_packages(root).items()},
    }


def run_check(root, index_dir):
    meta_path = os.path.join(index_dir, "meta.json")
    if not os.path.isfile(meta_path):
        eprint("✗ meta.json 不存在：%s" % meta_path)
        return 7
    meta = load_jsonc(meta_path) or {}
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
    try:
        diff = subprocess.run(["git", "-C", index_root, "diff", "--name-only",
                               "%s..%s" % (recorded, current), "--", meta.get("scope") or "."],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        eprint("✗ git diff 失败：%s" % exc)
        return 3
    if diff.returncode != 0:
        # 记录的 commit 不可达（换过仓库 / 历史被重写 / 记录被手改）→ 不能宣称"可用"
        eprint("✗ 无法比对：记录的 commit %s 在当前仓库不可达（%s）"
               % (recorded[:10], (diff.stderr or "").strip()[:120]))
        eprint("  处置：把 meta.json 的 commit 校正为当前 HEAD，或直接重建索引")
        return 3
    changed = [l for l in (diff.stdout or "").splitlines() if l.strip()]
    if not changed:
        print("✅ 索引可用：提交已前进（%s → %s），但扫描范围内无文件变化" % (recorded[:10], current[:10]))
        print("   （索引文件头应更新 commit 以消除后续误报）")
        return 0
    print("⚠️ 索引已过期：提交 %s → %s，范围内 %d 个文件有变化" % (recorded[:10], current[:10], len(changed)))
    for line in changed[:15]:
        print("   - %s" % line)
    if len(changed) > 15:
        print("   - …共 %d 个" % len(changed))
    print("   建议：重跑扫描脚本并重新标注（一条命令，见 SKILL.md 阶段 5）")
    return 6


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="scan_frontend.py",
        description="前端「页面（路由）↔ HTTP 接口」静态映射提取器（零依赖）")
    parser.add_argument("--root", required=True, help="扫描根目录（前端应用或仓库根）")
    parser.add_argument("--config", help="声明文件路径（默认 {root}/.fe-index/config.json）")
    parser.add_argument("--app", help="声明文件中有多个 apps 时选择哪个（slug）")
    parser.add_argument("--slug", help="应用标识（用于输出与 meta.json 匹配）")
    parser.add_argument("--include", action="append", default=[], help="只扫描匹配的相对路径 glob（可重复）")
    parser.add_argument("--exclude", action="append", default=[], help="排除匹配的相对路径 glob（可重复）")
    parser.add_argument("--routes", action="append", default=[], help="路由文件 glob（可重复，相对 root）")
    parser.add_argument("--pages-dir", action="append", default=[], help="页面目录（可重复，相对 root）")
    parser.add_argument("--api-dir", action="append", default=[], help="接口/请求层目录（可重复，相对 root）")
    parser.add_argument("--alias", action="append", default=[], help="路径别名 k=v（可重复）")
    parser.add_argument("--request-object", action="append", default=[], help="额外的请求对象名（如 myHttp）")
    parser.add_argument("--max-depth", type=int, default=2,
                        help="页面 import 图归属深度（默认 2：页面自身 0 + 直接依赖 1 + 间接候选 2）")
    parser.add_argument("--max", type=int, default=1000, help="映射行数上限（默认 1000，硬上限 5000）")
    parser.add_argument("--format", choices=("md", "tsv", "json"), default="md", help="输出格式")
    parser.add_argument("--out", help="输出文件（默认 stdout）")
    parser.add_argument("--dump-config", action="store_true", help="只输出探测到的约定（JSON）")
    parser.add_argument("--check", action="store_true", help="新鲜度检查模式：比对 meta.json 的 commit 与当前 HEAD")
    parser.add_argument("--index", help="索引目录（--check 用，如 .fe-index/my-app）")
    parser.add_argument("--verbose", action="store_true", help="输出探测细节到 stderr")
    parser.add_argument("--version", action="version", version="scan_frontend.py " + VERSION)
    return parser


def merge_config(args):
    cfg = {}
    config_path = args.config or os.path.join(args.root, ".fe-index", "config.json")
    if os.path.isfile(config_path):
        data = load_jsonc(config_path)
        if data is None:
            eprint("✗ 声明文件不是合法 JSON：%s" % config_path)
            sys.exit(5)
        apps = data.get("apps")
        if isinstance(apps, list) and apps:
            slug = args.app or args.slug
            chosen = None
            if slug:
                chosen = next((a for a in apps if a.get("slug") == slug), None)
                if chosen is None:
                    eprint("✗ 声明文件中没有 slug=%s 的应用" % slug)
                    sys.exit(5)
            else:
                chosen = apps[0]
                if len(apps) > 1:
                    eprint("⚠ 声明文件含 %d 个应用，未指定 --app，使用第一个：%s"
                           % (len(apps), chosen.get("slug")))
            cfg = dict(chosen)
            cfg_root = cfg.pop("root", None)
            if cfg_root:
                # 相对 root 的基准：声明文件在 `{root}/.fe-index/` 里时取其上一级，
                # 否则取声明文件所在目录（`--config` 指向别处时不再误算到文件系统根）
                base = os.path.dirname(config_path)
                if os.path.basename(base) == ".fe-index":
                    base = os.path.dirname(base)
                args.root = cfg_root if os.path.isabs(cfg_root) else os.path.normpath(
                    os.path.join(base, cfg_root))
        else:
            cfg = {k: v for k, v in data.items() if k != "apps"}
        if args.verbose:
            eprint("· 已加载声明文件：%s" % config_path)
    opts = dict(cfg)
    opts["include"] = list(cfg.get("include") or []) + list(args.include or [])
    opts["exclude"] = list(cfg.get("exclude") or []) + list(args.exclude or [])
    opts["routes"] = list(cfg.get("routes") or []) + list(args.routes or [])
    opts["pagesDirs"] = list(cfg.get("pagesDirs") or []) + list(args.pages_dir or [])
    opts["apiDirs"] = list(cfg.get("apiDirs") or []) + list(args.api_dir or [])
    opts["requestObjects"] = list(cfg.get("requestObjects") or []) + list(args.request_object or [])
    if args.max_depth != 2:
        opts["maxDepth"] = args.max_depth
    aliases = dict(cfg.get("aliases") or {})
    for item in args.alias or []:
        if "=" not in item:
            eprint("✗ --alias 需要 k=v 形式：%s" % item)
            sys.exit(5)
        key, val = item.split("=", 1)
        aliases[key] = val
    opts["aliases"] = aliases
    return opts


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    root = os.path.abspath(os.path.expanduser(args.root))
    if not os.path.isdir(root):
        eprint("✗ 根目录不存在：%s" % root)
        return 3
    if args.max > 5000:
        eprint("✗ --max 超过硬上限 5000")
        return 5
    if args.check:
        if not args.index:
            eprint("✗ --check 需要 --index <索引目录>")
            return 5
        return run_check(root, os.path.abspath(args.index))

    opts = merge_config(args)

    # 声明文件可能覆盖 app 的 root（monorepo 场景：config 在仓库根，应用在子目录）
    root = os.path.abspath(os.path.expanduser(args.root))
    if not os.path.isdir(root):
        eprint("✗ 根目录不存在（来自声明文件的 root？）：%s" % root)
        return 3

    if args.dump_config:
        files = walk_files(root, opts.get("include") or [], opts.get("exclude") or [])
        texts = {p: read_text(p) for p in files}
        detected = detect_framework(root, files, texts)
        detected["_note"] = ("把 suggested_config 存为 {root}/.fe-index/config.json，"
                            "并校正 routes / apiDirs / aliases（探测可能遗漏）后可让重建零猜测")
        print(json.dumps({"detected": detected,
                          "suggested_config": {"apps": [{
                              "slug": args.slug or os.path.basename(root) or "app",
                              "root": ".",
                              "include": opts.get("include") or ["src/**"],
                              "routes": detected["routes"][:40],
                              "pagesDirs": detected["pagesDirs"],
                              "apiDirs": detected["apiDirs"],
                              "aliases": detected["aliases"],
                          }]}}, ensure_ascii=False, indent=2))
        return 0

    result = scan(root, opts)

    if not result.pages and not result.api_defs:
        eprint("✗ 未识别到路由与接口约定（无产出）")
        eprint("  处置：用 --routes/--api-dir/--alias 显式指定，或先跑 --dump-config 生成声明文件")
        return 2
    if not result.page_apis:
        eprint("⚠ 提取结果为空：识别到 %d 个页面 / %d 个接口定义，但未建立映射"
               % (len(result.pages), len(result.api_defs)))

    # 截断（同步修正 stats，避免"统计数与产出数"不一致）
    limit = args.max
    truncated = []
    if len(result.page_apis) > limit:
        truncated.append("page_apis %d→%d" % (len(result.page_apis), limit))
        result.page_apis = result.page_apis[:limit]
    if len(result.api_pages) > limit:
        truncated.append("api_pages %d→%d" % (len(result.api_pages), limit))
        result.api_pages = result.api_pages[:limit]
    if truncated:
        result.stats["page_api_rows"] = len(result.page_apis)
        result.stats["unique_apis"] = len(result.api_pages)
        result.stats["truncated"] = "; ".join(truncated)
        result.pending.append({"type": "输出截断", "loc": "-", "content": ", ".join(truncated),
                               "reason": "超过 --max，重跑时提高上限或收窄 include"})

    if args.format == "md":
        out = render_md(result, opts, root)
    elif args.format == "tsv":
        out = render_tsv(result, opts, root)
    else:
        out = render_json(result, opts, root)

    if args.out:
        out_path = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(out)
        eprint("✅ 写入 %s（页面 %d · 映射 %d · 接口 %d）"
               % (out_path, result.stats.get("pages", 0), len(result.page_apis), len(result.api_pages)))
    else:
        print(out)

    if args.verbose:
        eprint("· 统计：%s" % json.dumps(result.stats, ensure_ascii=False))
    if not result.page_apis and not result.api_defs:
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
