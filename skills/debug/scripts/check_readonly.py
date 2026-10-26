#!/usr/bin/env python3
"""静态只读检查器：检查线上排查片段是否包含已知写操作/副作用/凭证。

设计边界：
- 只做静态分析，绝不执行被检查代码。
- 不能证明“绝对无写”；动态拼接、第三方库内部写、框架启动副作用仍可能绕过。
- 发现不确定项时给 WARN，要求人工确认；已知写操作给 BLOCK。

退出码：0 通过 / 1 发现阻断项（--strict 下 WARN 也算） / 2 输入或解析失败。
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shlex
import sys
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

EXIT_OK = 0
EXIT_BLOCK = 1
EXIT_ERROR = 2

ORM_WRITE_METHODS = {
    "save",
    "bulk_create",
    "bulk_update",
    "get_or_create",
    "update_or_create",
}
CACHE_WRITE_METHODS = {
    "set",
    "set_many",
    "delete",
    "delete_many",
    "clear",
    "incr",
    "decr",
    "touch",
    "add",
    "remove",
    "setdefault",
    "get_or_set",
}
HTTP_WRITE_METHODS = {"post", "put", "patch", "delete"}
SQLA_WRITE_METHODS = {
    "add",
    "add_all",
    "merge",
    "flush",
    "commit",
    "bulk_save_objects",
    "bulk_insert_mappings",
    "bulk_update_mappings",
}
EXPORT_WRITE_METHODS = {
    "to_csv",
    "to_excel",
    "to_json",
    "to_parquet",
    "to_sql",
    "to_pickle",
    "to_xml",
    "to_html",
    "savefig",
}
REDIS_WRITE_METHODS = {
    "set",
    "setex",
    "psetex",
    "setnx",
    "mset",
    "msetnx",
    "getset",
    "getdel",
    "getex",
    "del",
    "unlink",
    "hset",
    "hmset",
    "hdel",
    "hincrby",
    "hincrbyfloat",
    "lpush",
    "rpush",
    "lpushx",
    "rpushx",
    "linsert",
    "lset",
    "lrem",
    "ltrim",
    "rpoplpush",
    "lmove",
    "sadd",
    "srem",
    "spop",
    "smove",
    "zadd",
    "zrem",
    "zincrby",
    "zpopmin",
    "zpopmax",
    "incr",
    "decr",
    "incrby",
    "decrby",
    "incrbyfloat",
    "lpop",
    "rpop",
    "setrange",
    "expire",
    "expireat",
    "pexpire",
    "pexpireat",
    "persist",
    "rename",
    "renamenx",
    "flushall",
    "flushdb",
    "swapdb",
    "eval",
    "evalsha",
    "eval_ro",
    "evalsha_ro",
    "fcall",
    "fcall_ro",
    "publish",
    "spublish",
    "pfadd",
    "geoadd",
    "xadd",
    "xdel",
    "xtrim",
    "execute_command",
}
UNIVERSAL_WRITE_ATTRS = (
    ORM_WRITE_METHODS
    | CACHE_WRITE_METHODS
    | HTTP_WRITE_METHODS
    | SQLA_WRITE_METHODS
    | EXPORT_WRITE_METHODS
    | REDIS_WRITE_METHODS
    | {
        "update",
        "delete",
        "create",
        "set",
        "get_or_set",
        "add",
        "remove",
        "clear",
        "commit",
        "flush",
        "write",
        "writelines",
        "write_text",
        "write_bytes",
        "mkdir",
        "unlink",
        "chmod",
        "touch",
        "send",
        "publish",
        "enqueue",
        "setdefault",
        "apply_async",
        "delay",
        "request",
    }
)
BARE_WRITE_NAMES = UNIVERSAL_WRITE_ATTRS - {"set"}
INTROSPECTION_ATTRS = {"__dict__", "__getattribute__"}
OS_WRITE_METHODS = {
    "system",
    "popen",
    "remove",
    "unlink",
    "rename",
    "replace",
    "mkdir",
    "makedirs",
    "rmdir",
    "removedirs",
    "chmod",
    "chown",
    "truncate",
    "putenv",
    "unsetenv",
    "setdefault",
    "pop",
    "update",
}
SHUTIL_WRITE_PREFIX = "shutil."
SHUTIL_WRITE_METHODS = {
    "copy",
    "copy2",
    "copyfile",
    "copytree",
    "move",
    "rmtree",
    "make_archive",
    "unpack_archive",
}
SUBPROCESS_WRITE_METHODS = {
    "run",
    "call",
    "check_call",
    "check_output",
    "Popen",
    "getoutput",
    "getstatusoutput",
}
PATH_WRITE_METHODS = {
    "write_text",
    "write_bytes",
    "touch",
    "mkdir",
    "unlink",
    "rename",
    "chmod",
}
DYNAMIC_CALLS = {
    "eval",
    "exec",
    "compile",
    "getattr",
    "setattr",
    "delattr",
    "__import__",
    "vars",
    "globals",
    "locals",
    "methodcaller",
    "attrgetter",
}
REDIS_WRITE_COMMANDS = {
    "SET",
    "SETEX",
    "PSETEX",
    "SETNX",
    "MSET",
    "MSETNX",
    "GETSET",
    "GETDEL",
    "GETEX",
    "DEL",
    "UNLINK",
    "HSET",
    "HMSET",
    "HDEL",
    "HINCRBY",
    "HINCRBYFLOAT",
    "LPUSH",
    "RPUSH",
    "LPUSHX",
    "RPUSHX",
    "LINSERT",
    "LSET",
    "LREM",
    "LTRIM",
    "RPOPLPUSH",
    "LMOVE",
    "SADD",
    "SREM",
    "SPOP",
    "SMOVE",
    "ZADD",
    "ZREM",
    "ZINCRBY",
    "ZPOPMIN",
    "ZPOPMAX",
    "INCR",
    "DECR",
    "INCRBY",
    "DECRBY",
    "INCRBYFLOAT",
    "APPEND",
    "SETRANGE",
    "EXPIRE",
    "EXPIREAT",
    "PEXPIRE",
    "PEXPIREAT",
    "PERSIST",
    "RENAME",
    "RENAMENX",
    "MOVE",
    "COPY",
    "FLUSHALL",
    "FLUSHDB",
    "SWAPDB",
    "EVAL",
    "EVALSHA",
    "EVAL_RO",
    "EVALSHA_RO",
    "FCALL",
    "FCALL_RO",
    "PUBLISH",
    "SPUBLISH",
    "PFADD",
    "GEOADD",
    "XADD",
    "XDEL",
    "XTRIM",
    "MULTI",
    "EXEC",
    "DISCARD",
    "WATCH",
    "UNWATCH",
    "SCRIPT",
    "FUNCTION",
    "ACL",
    "AUTH",
}
REDIS_WARN_COMMANDS = {"KEYS", "MONITOR", "SUBSCRIBE", "PSUBSCRIBE", "SSUBSCRIBE"}
REDIS_READ_COMMANDS = {
    "GET",
    "MGET",
    "HGET",
    "HMGET",
    "HGETALL",
    "HKEYS",
    "HVALS",
    "HLEN",
    "HEXISTS",
    "LRANGE",
    "LLEN",
    "LINDEX",
    "SMEMBERS",
    "SCARD",
    "SISMEMBER",
    "ZRANGE",
    "ZREVRANGE",
    "ZRANGEBYSCORE",
    "ZSCORE",
    "ZCARD",
    "ZCOUNT",
    "SCAN",
    "SSCAN",
    "HSCAN",
    "ZSCAN",
    "TTL",
    "PTTL",
    "EXISTS",
    "TYPE",
    "INFO",
    "DBSIZE",
    "STRLEN",
    "GETRANGE",
    "BITCOUNT",
    "BITPOS",
    "PFCOUNT",
    "GEOSEARCH",
    "GEOPOS",
    "GEODIST",
    "XRANGE",
    "XREVRANGE",
    "XLEN",
    "XREAD",
    "COMMAND",
    "HELLO",
    "PING",
    "ECHO",
    "SELECT",
}
SQL_ALLOWED_FIRST = {"SELECT", "WITH", "EXPLAIN", "SHOW", "DESC", "DESCRIBE"}
SQL_BANNED = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "REPLACE",
    "TRUNCATE",
    "ALTER",
    "DROP",
    "CREATE",
    "GRANT",
    "REVOKE",
    "CALL",
    "DO",
    "SET",
    "USE",
    "LOCK",
    "UNLOCK",
    "MERGE",
    "UPSERT",
    "COPY",
    "VACUUM",
    "REINDEX",
    "CLUSTER",
    "ANALYZE",
    "NEXTVAL",
    "SETVAL",
}
SQL_WRITE_FUNCTIONS = {"NEXTVAL", "SETVAL", "PG_ADVISORY_LOCK", "PG_ADVISORY_UNLOCK"}
SQL_WARN_FUNCTIONS = {"PG_SLEEP"}
MUTATION_URL_WORDS = (
    "delete",
    "remove",
    "update",
    "create",
    "pay",
    "cancel",
    "refund",
    "approve",
    "submit",
    "send",
    "upload",
    "reset",
    "close",
)

PLACEHOLDER_RE = re.compile(
    r"(?i)(<[^>]+>|\$\{?\w+\}?|YOUR[_A-Z0-9-]*|REDACTED|CHANGEME|EXAMPLE|PLACEHOLDER|xxx+|\*{3,})"
)
CREDENTIAL_PATTERNS: Sequence[Tuple[re.Pattern[str], str]] = (
    (
        re.compile(
            r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?key|token)['\"]?\s*[:=]\s*['\"][^'\"]{3,}['\"]"
        ),
        "credential-literal",
    ),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/\-]{10,}=*"), "bearer-token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws-key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private-key"),
    (
        re.compile(
            r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|rediss|amqp(?:s)?)://[^:\s/]*:[^@\s]+@"
        ),
        "db-url-with-password",
    ),
    (
        re.compile(
            r"(?i)\bAuthorization['\"]?\s*[:=]\s*['\"]?Bearer\s+[A-Za-z0-9._~+/\-]{10,}"
        ),
        "auth-header",
    ),
    (
        re.compile(r"(?i)\bAuthorization['\"]?\s*[:=]\s*['\"]?Basic\s+[A-Za-z0-9+/=]{8,}"),
        "basic-auth",
    ),
    (
        re.compile(r"(?i)\bX-Api-Key['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9\-_]{8,}"),
        "api-key-header",
    ),
    (
        re.compile(r"(?i)\bCookie['\"]?\s*[:=]\s*['\"]?[^'\"\n]*(?:session|token|auth)[^'\"\n]*"),
        "cookie-header",
    ),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "github-token"),
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"), "api-key"),
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
        "jwt",
    ),
    (
        re.compile(r"(?i)[?&](?:password|passwd|pwd|token|secret|api_key)=([^&\s'\"]{3,})"),
        "credential-query",
    ),
    (
        re.compile(
            r"(?i)(?:^|\s)--(?:password|passwd|token|secret|api[-_]?key)(?:=|\s+)([^\s'\"]{3,})"
        ),
        "credential-cli",
    ),
)


class InputError(Exception):
    """输入无法读取或无法解析。"""


@dataclass
class Finding:
    severity: str
    rule: str
    line: int
    message: str
    snippet: str = ""


def last_attr(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        base = dotted_name(node.func)
        return f"{base}()" if base else "()"
    if isinstance(node, ast.Subscript):
        base = dotted_name(node.value)
        return f"{base}[]" if base else "[]"
    return ""


def call_arg(node: ast.Call, index: int = 0, keyword: Optional[str] = None) -> Optional[ast.AST]:
    if index < len(node.args):
        return node.args[index]
    if keyword:
        for kw in node.keywords:
            if kw.arg == keyword:
                return kw.value
    return None


def looks_like_sql(text: str) -> bool:
    return bool(
        re.match(
            r"(?is)^\s*("
            r"SELECT\b.*\bFROM\b"
            r"|WITH\b.*\bSELECT\b"
            r"|EXPLAIN\b.*\bSELECT\b"
            r"|INSERT\s+INTO\b"
            r"|UPDATE\b.*\bSET\b"
            r"|DELETE\s+FROM\b"
            r"|CREATE\s+(TABLE|INDEX|VIEW|DATABASE)\b"
            r"|ALTER\s+TABLE\b"
            r"|DROP\s+(TABLE|INDEX|VIEW|DATABASE)\b"
            r"|TRUNCATE\s+TABLE\b"
            r"|GRANT\b"
            r"|REVOKE\b"
            r")",
            text,
        )
    )


def strip_sql(sql: str) -> str:
    """移除 SQL 注释与字符串字面量，保留换行以便定位行号。"""
    out: List[str] = []
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if ch == "-" and nxt == "-":
            j = sql.find("\n", i)
            if j == -1:
                break
            out.append("\n")
            i = j + 1
            continue
        if ch == "/" and nxt == "*":
            j = sql.find("*/", i + 2)
            if j == -1:
                break
            out.append("\n" * sql[i : j + 2].count("\n"))
            i = j + 2
            continue
        if ch == "'":
            j = i + 1
            while j < n:
                if sql[j] == "\\":
                    j += 2
                    continue
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append("\n" * sql[i:j].count("\n"))
            i = j
            continue
        if ch in {'"', "`"}:
            quote = ch
            j = i + 1
            while j < n:
                if sql[j] == quote:
                    if j + 1 < n and sql[j + 1] == quote:
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append("\n" * sql[i:j].count("\n"))
            i = j
            continue
        if ch == "$":
            match = re.match(r"\$[A-Za-z_]*\$", sql[i:])
            if match:
                tag = match.group(0)
                end = sql.find(tag, i + len(tag))
                if end != -1:
                    j = end + len(tag)
                    out.append("\n" * sql[i:j].count("\n"))
                    i = j
                    continue
        out.append(ch)
        i += 1
    return "".join(out)


def split_sql_statements(stripped: str) -> List[str]:
    return [part.strip() for part in stripped.split(";") if part.strip()]


def line_at(text: str, position: int, base_line: int = 1) -> int:
    return base_line + text.count("\n", 0, position)


def detect_language(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise InputError("输入为空")

    python_hint = bool(
        re.search(
            r"(?m)^\s*(?:import|from)\s+\w|^\s*def\s+\w|\.objects\.|print\(|requests\.|httpx\.|\bModel\b",
            text,
        )
    )
    if python_hint:
        try:
            ast.parse(text)
            return "python"
        except SyntaxError:
            try:
                ast.parse(textwrap.dedent(text))
                return "python"
            except SyntaxError:
                pass

    if re.search(r"(?m)^\s*(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/|https?://)\S*|^\s*(?:curl|wget)\b", text):
        return "http"

    sql_probe = strip_sql(text)
    if re.search(
        r"(?im)^\s*(SELECT|WITH|EXPLAIN|SHOW|DESCRIBE|DESC|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|BEGIN|START\s+TRANSACTION)\b",
        sql_probe,
    ):
        return "sql"

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        first = line.split()[0].upper()
        if first == "REDIS-CLI" or first in REDIS_READ_COMMANDS or first in REDIS_WRITE_COMMANDS:
            return "redis"
        break

    try:
        ast.parse(text)
        return "python"
    except SyntaxError:
        pass

    raise InputError("无法自动识别语言，请用 --lang 指定 python/sql/redis/http")


class ReadOnlyChecker:
    def __init__(self, text: str, lang: str = "auto", strict: bool = False) -> None:
        self.text = text
        self.lang = lang
        self.strict = strict
        self.findings: List[Finding] = []
        self._seen = set()
        self.local_functions = set()
        self.write_aliases = set()
        self.special_aliases = {}

    def redact_secrets(self, text: str) -> str:
        redacted = text
        for pattern, _ in CREDENTIAL_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted

    def add(self, severity: str, rule: str, line: int, message: str, snippet: str = "") -> None:
        key = (severity, rule, line, message)
        if key in self._seen:
            return
        self._seen.add(key)
        if not snippet:
            snippet = self.line_snippet(line)
        snippet = self.redact_secrets(snippet)
        self.findings.append(Finding(severity, rule, line, message, snippet))

    def line_snippet(self, line: int) -> str:
        lines = self.text.splitlines()
        if 1 <= line <= len(lines):
            return lines[line - 1].strip()[:120]
        return ""

    def check(self) -> List[Finding]:
        if self.lang == "auto":
            self.lang = detect_language(self.text)
        if self.lang == "python":
            self.check_python()
        elif self.lang == "sql":
            self.scan_sql(self.text, base_line=1, context="SQL")
        elif self.lang == "redis":
            self.check_redis()
        elif self.lang == "http":
            self.check_http()
        elif self.lang == "text":
            pass
        else:
            raise InputError(f"不支持的语言：{self.lang}")
        self.check_credentials()
        self.findings.sort(key=lambda f: (f.line, {"block": 0, "warn": 1, "info": 2}[f.severity]))
        return self.findings

    # ---------- Python ----------

    def check_python(self) -> None:
        try:
            tree = ast.parse(self.text)
        except SyntaxError:
            try:
                tree = ast.parse(textwrap.dedent(self.text))
            except SyntaxError as exc:
                raise InputError(f"无法解析为 Python：{exc}") from exc

        self.local_functions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.write_aliases = set()
        self.special_aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    local = alias.asname or alias.name
                    if alias.name in BARE_WRITE_NAMES:
                        self.write_aliases.add(local)
                    elif alias.name in {"urlopen", "Request"}:
                        self.special_aliases[local] = alias.name

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                self.check_python_call(node)
            elif isinstance(node, (ast.Assign, ast.AugAssign)):
                self.check_env_write(node)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if looks_like_sql(node.value):
                    self.scan_sql(node.value, base_line=getattr(node, "lineno", 1), context="embedded SQL")

        parent_map = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parent_map[child] = parent
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            attr = node.attr
            parent = parent_map.get(node)
            is_call_func = isinstance(parent, ast.Call) and parent.func is node
            is_intermediate = isinstance(parent, ast.Attribute)
            contextual_write = self.is_contextual_write_attr(node)
            if attr in INTROSPECTION_ATTRS:
                self.add(
                    "block",
                    "dynamic-attribute",
                    node.lineno,
                    f"禁止通过 .{attr} 动态取属性；无法确认不会取到写方法",
                )
            elif (attr in UNIVERSAL_WRITE_ATTRS or contextual_write) and not is_call_func and not is_intermediate:
                self.add(
                    "block",
                    "write-attribute",
                    node.lineno,
                    f"引用了写方法 .{attr}；禁止作为值传递/别名，请直接使用只读查询",
                )

    def check_python_call(self, node: ast.Call) -> None:
        func = node.func
        attr = last_attr(func)
        call_attr = self.special_aliases.get(attr, attr) if isinstance(func, ast.Name) else attr
        full = dotted_name(func)
        lower = full.lower()
        line = node.lineno

        if attr in DYNAMIC_CALLS or attr == "import_module" or lower.startswith("importlib."):
            self.add(
                "block",
                "dynamic-dispatch",
                line,
                f"动态调用 {full or attr}() 可能隐藏写操作，禁止用于线上只读取证",
            )
            return

        if isinstance(func, ast.Name):
            if (
                attr in BARE_WRITE_NAMES or attr in self.write_aliases
            ) and attr not in self.local_functions:
                self.add(
                    "block",
                    "bare-write-call",
                    line,
                    f"直接调用写方法名 {attr}()；无法确认只读，请改用明确的只读方法",
                )
                return
        elif attr in UNIVERSAL_WRITE_ATTRS:
            self.add(
                "block",
                "write-method",
                line,
                f"{full or attr}() 是写/副作用方法，线上只读片段禁止使用",
            )
            return

        if attr == "select_for_update":
            self.add("block", "query-lock", line, "select_for_update() 会锁行，线上只读查询禁止使用")
            return

        if (
            lower.startswith(("pickle.", "marshal.", "dill.", "shelve.", "joblib.", "torch."))
            and attr in {"load", "loads", "open"}
        ) or (lower.startswith("yaml.") and attr == "load") or (
            lower.startswith("pandas.") and attr == "read_pickle"
        ):
            self.add(
                "block",
                "unsafe-deserialization",
                line,
                "不安全反序列化可能执行任意代码/写数据；请改用只读解析或人工确认",
            )
            return

        if attr == "raw":
            sql_arg = call_arg(node, 0, "raw_query")
            if isinstance(sql_arg, ast.Constant) and isinstance(sql_arg.value, str):
                self.scan_sql(sql_arg.value, base_line=line, context=".raw()")
            else:
                self.add(
                    "block",
                    "unknown-sql",
                    line,
                    "无法静态确认 .raw() 的 SQL 是否只读；请改为字符串字面量或人工确认",
                )
            return

        if attr == "extra":
            self.add("warn", "orm-extra", line, "extra() 可拼接 SQL，需人工确认只读")
            return

        if attr in {"execute", "executemany"}:
            if attr == "executemany":
                self.add("block", "sql-executemany", line, "executemany() 通常是写操作，禁止使用")
                return
            sql_arg = call_arg(node, 0)
            if isinstance(sql_arg, ast.Constant) and isinstance(sql_arg.value, str):
                self.scan_sql(sql_arg.value, base_line=line, context="cursor.execute()")
            else:
                self.add(
                    "block",
                    "unknown-sql",
                    line,
                    "无法静态确认 cursor.execute() 的 SQL 是否只读；请改为字符串字面量或人工确认",
                )
            return

        if attr == "open":
            mode = call_arg(node, 1, "mode")
            if mode is None:
                return
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
                if any(ch in mode.value for ch in "wax+"):
                    self.add("block", "file-write", line, f"open(..., '{mode.value}') 会写文件")
            else:
                self.add("warn", "open-mode", line, "open() 的 mode 无法静态确定，请确认是只读")

        if attr in PATH_WRITE_METHODS:
            if self.looks_like_path(full):
                self.add("block", "file-write", line, f"{full} 会写文件/目录")
            else:
                self.add("warn", "path-write", line, f"{full} 可能是文件写入，请人工确认")

        if attr == "replace" and self.looks_like_path(full):
            self.add("block", "file-write", line, f"{full} 会覆盖文件")

        if lower.startswith(SHUTIL_WRITE_PREFIX) or lower.startswith("os.") and attr in OS_WRITE_METHODS:
            self.add("block", "os-write", line, f"{full} 会修改进程/文件/环境")
        if lower.startswith("subprocess.") or attr in {"system", "popen"}:
            self.add("block", "subprocess", line, f"{full} 会启动外部进程")

        if attr == "apply" and ("task" in lower or "celery" in lower):
            self.add("block", "task-enqueue", line, f"{full} 会同步执行异步任务")
            return

        if call_attr == "urlopen":
            data_arg = call_arg(node, 1)
            data_kw = any(kw.arg == "data" for kw in node.keywords)
            method_node = next((kw.value for kw in node.keywords if kw.arg == "method"), None)
            method = ""
            if isinstance(method_node, ast.Constant) and isinstance(method_node.value, str):
                method = method_node.value.upper()
            if data_arg is not None or data_kw or (method and method not in {"GET", "HEAD", "OPTIONS"}):
                self.add("block", "http-write", line, "urlopen(url, data=/method=) 可能发起写请求")
            return

        if call_attr == "Request":
            data_arg = call_arg(node, 1)
            data_kw = any(kw.arg == "data" for kw in node.keywords)
            method_node = call_arg(node, 3, "method")
            method = ""
            if isinstance(method_node, ast.Constant) and isinstance(method_node.value, str):
                method = method_node.value.upper()
            if data_arg is not None or data_kw or (method and method not in {"GET", "HEAD", "OPTIONS"}):
                self.add("block", "http-write", line, "Request(data=/method=) 可能发起写请求")
            return

    def looks_like_path(self, full: str) -> bool:
        return any(token in full for token in ("Path(", "pathlib.", ".resolve()", "file_path"))

    def is_contextual_write_attr(self, node: ast.Attribute) -> bool:
        base = dotted_name(node.value).lower()
        attr = node.attr
        if base == "os" or base.startswith("os."):
            return attr in OS_WRITE_METHODS
        if base == "shutil" or base.startswith("shutil."):
            return attr in SHUTIL_WRITE_METHODS
        if base == "subprocess" or base.startswith("subprocess."):
            return attr in SUBPROCESS_WRITE_METHODS
        if base == "urllib" or base.startswith("urllib."):
            return attr in {"urlopen", "Request"}
        if "path" in base:
            return attr in PATH_WRITE_METHODS or attr == "replace"
        return False

    def check_env_write(self, node: ast.AST) -> None:
        targets: Iterable[ast.AST]
        if isinstance(node, ast.Assign):
            targets = node.targets
        else:
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Subscript) and dotted_name(target.value) == "os.environ":
                self.add("block", "env-write", getattr(node, "lineno", 1), "禁止修改 os.environ")

    # ---------- SQL ----------

    def scan_sql(self, sql: str, base_line: int = 1, context: str = "SQL") -> None:
        stripped = strip_sql(sql)
        statements = split_sql_statements(stripped)
        if not statements:
            self.add("warn", "sql-empty", base_line, f"{context} 为空，无法判定")
            return

        middle = statements
        if len(statements) == 3:
            first = statements[0].upper()
            last = statements[2].upper()
            if (
                first.startswith("BEGIN READ ONLY")
                or first.startswith("START TRANSACTION READ ONLY")
            ) and last == "ROLLBACK":
                middle = [statements[1]]
        elif len(statements) > 1:
            self.add(
                "block",
                "sql-multi-statement",
                base_line,
                f"{context} 含多条语句；除只读事务包装外禁止线上执行",
            )
            return

        for stmt in middle:
            upper = stmt.upper()
            first_match = re.match(r"\s*([A-Z]+)", upper)
            first = first_match.group(1) if first_match else ""
            if first not in SQL_ALLOWED_FIRST:
                self.add(
                    "block",
                    "sql-non-select",
                    base_line,
                    f"{context} 首关键字为 {first or '未知'}，只允许 SELECT/WITH/EXPLAIN/SHOW/DESC",
                )
                continue

            if first == "EXPLAIN" and re.search(r"\bANALYZE\b", upper):
                self.add("block", "sql-explain-analyze", base_line, "EXPLAIN ANALYZE 会实际执行查询，禁止使用")

            scan_upper = re.sub(r"\bFOR\s+(UPDATE|SHARE)\b", " ", upper)
            scan_upper = re.sub(r"\bLOCK\s+IN\s+SHARE\s+MODE\b", " ", scan_upper)

            for keyword in sorted(SQL_BANNED):
                if keyword == "ANALYZE" and first == "EXPLAIN":
                    continue
                if re.search(rf"\b{keyword}\b", scan_upper):
                    self.add(
                        "block",
                        "sql-banned-keyword",
                        base_line,
                        f"{context} 含写/高危关键字 {keyword}",
                    )
                    break

            if re.search(r"\bFOR\s+(UPDATE|SHARE)\b", upper) or re.search(
                r"\bLOCK\s+IN\s+SHARE\s+MODE\b", upper
            ):
                self.add("block", "sql-lock", base_line, "查询带锁（FOR UPDATE/SHARE），禁止使用")

            if re.search(r"\bINTO\s+(OUTFILE|DUMPFILE)\b", scan_upper):
                self.add("block", "sql-file-write", base_line, "SELECT ... INTO OUTFILE/DUMPFILE 会写文件")

            if re.search(r"\bCOPY\b", scan_upper):
                self.add("block", "sql-copy", base_line, "COPY 会读写文件，禁止使用")

            for func in SQL_WRITE_FUNCTIONS:
                if re.search(rf"\b{func}\s*\(", scan_upper):
                    self.add("block", "sql-write-function", base_line, f"{func}() 会产生写入/锁副作用")

            for func in SQL_WARN_FUNCTIONS:
                if re.search(rf"\b{func}\s*\(", scan_upper):
                    self.add("warn", "sql-slow-function", base_line, f"{func}() 可能阻塞/拖慢线上")

            if first == "SELECT" and " INTO " in f" {scan_upper} ":
                self.add("block", "sql-select-into", base_line, "SELECT ... INTO 会写表/变量")

            if re.search(r"\bSELECT\s+\*", scan_upper):
                self.add("warn", "sql-select-star", base_line, "SELECT * 会拉取多余字段，建议明确字段")

            if first in {"SELECT", "WITH"} and not re.search(
                r"\b(WHERE|LIMIT|GROUP\s+BY|HAVING)\b", scan_upper
            ):
                self.add(
                    "warn",
                    "sql-no-limit",
                    base_line,
                    "查询未发现 WHERE/LIMIT/GROUP BY，可能全表扫描；请加时间窗或 LIMIT",
                )

    # ---------- Redis ----------

    def check_redis(self) -> None:
        for line_no, raw in enumerate(self.text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                tokens = shlex.split(line, posix=True)
            except ValueError:
                tokens = line.split()
            if not tokens:
                continue
            if tokens[0].lower() == "redis-cli":
                tokens = self.strip_redis_cli_options(tokens[1:], line_no)
                if not tokens:
                    continue
            command = tokens[0].upper()
            arg = tokens[1].upper() if len(tokens) > 1 else ""

            if command in {"AUTH"}:
                self.add("block", "redis-auth", line_no, "不要在片段中包含 AUTH/凭证")
                continue
            if command == "CONFIG":
                if arg == "HELP":
                    continue
                if arg == "GET":
                    self.add("warn", "redis-config-read", line_no, "CONFIG GET 可能返回敏感配置，请确认字段")
                    continue
                self.add("block", "redis-config-write", line_no, f"CONFIG {arg or ''} 可能修改实例配置")
                continue
            if command == "CLIENT":
                if arg in {"LIST", "INFO", "GETNAME", "ID"}:
                    continue
                self.add("block", "redis-client-write", line_no, f"CLIENT {arg or ''} 可能影响连接")
                continue
            if command in REDIS_WARN_COMMANDS:
                self.add("warn", "redis-heavy", line_no, f"{command} 可能阻塞或长时间占用连接")
                continue
            if command in REDIS_WRITE_COMMANDS:
                self.add("block", "redis-write", line_no, f"{command} 是 Redis 写/管理命令")
                continue
            if command in REDIS_READ_COMMANDS:
                continue
            self.add("warn", "redis-unknown", line_no, f"未识别的 Redis 命令 {command}，请人工确认")

    def strip_redis_cli_options(self, tokens: List[str], line_no: int) -> List[str]:
        value_opts = {
            "-h",
            "--host",
            "-p",
            "--port",
            "-n",
            "--db",
            "-s",
            "--sock",
            "-u",
            "--uri",
            "--user",
            "--pass",
            "--tls-ca-cert",
            "--tls-cert",
            "--tls-key",
        }
        result: List[str] = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            lower = token.lower()
            if lower in {"-a", "--pass"}:
                self.add("block", "redis-credential", line_no, "redis-cli -a/--pass 会把密码写入命令历史")
                i += 2
                continue
            if token.startswith("-a") and len(token) > 2:
                self.add("block", "redis-credential", line_no, "redis-cli -a 会把密码写入命令历史")
                i += 1
                continue
            if lower.startswith("--pass="):
                self.add("block", "redis-credential", line_no, "redis-cli --pass 会把密码写入命令历史")
                i += 1
                continue
            if lower == "--user" or lower.startswith("--user="):
                self.add("block", "redis-credential", line_no, "redis-cli --user 属于认证信息，请移除")
                i += 2 if lower == "--user" else 1
                continue
            if lower in {"-u", "--uri"}:
                if i + 1 < len(tokens) and "://" in tokens[i + 1] and "@" in tokens[i + 1]:
                    self.add("block", "redis-credential", line_no, "redis-cli URI 含凭证")
                i += 2
                continue
            if token.startswith("-u") and len(token) > 2:
                if "://" in token and "@" in token:
                    self.add("block", "redis-credential", line_no, "redis-cli URI 含凭证")
                i += 1
                continue
            if lower.startswith("--uri="):
                if "://" in token and "@" in token:
                    self.add("block", "redis-credential", line_no, "redis-cli URI 含凭证")
                i += 1
                continue
            if lower == "--pipe":
                self.add("block", "redis-pipe", line_no, "redis-cli --pipe 可批量执行写命令")
                i += 1
                continue
            if lower == "--eval" or lower.startswith("--eval="):
                self.add("block", "redis-eval", line_no, "redis-cli --eval 会执行 Lua 脚本")
                i += 2 if lower == "--eval" else 1
                continue
            if lower in {"--ldb", "--ldb-sync-mode"}:
                self.add("block", "redis-debug", line_no, f"redis-cli {lower} 会进入脚本调试")
                i += 1
                continue
            if lower == "--rdb":
                self.add("warn", "redis-rdb", line_no, "redis-cli --rdb 会拉取数据并写本地文件")
                i += 2
                continue
            if lower in value_opts:
                i += 2
                continue
            if token.startswith("-"):
                i += 1
                continue
            result.append(token)
            i += 1
        return result

    # ---------- HTTP ----------

    def check_http(self) -> None:
        for line_no, raw in enumerate(self.text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("curl"):
                self.check_curl(line, line_no)
                continue
            if line.lower().startswith("wget"):
                self.check_wget(line, line_no)
                continue
            match = re.match(r"(?i)^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\S+)", line)
            if match:
                method = match.group(1).upper()
                url = match.group(2)
                if method not in {"GET", "HEAD", "OPTIONS"}:
                    self.add("block", "http-write", line_no, f"{method} 是写请求，禁止使用")
                elif self.has_mutation_word(url):
                    self.add("warn", "http-mutation-url", line_no, f"GET {url} 的路径含副作用词，请确认")
                continue
            self.add("warn", "http-unknown", line_no, "未识别的 HTTP 片段，请人工确认")

    def check_curl(self, line: str, line_no: int) -> None:
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            tokens = line.split()
        method: Optional[str] = None
        has_data = False
        writes_file = False
        url = ""
        data_opts = {
            "--data",
            "--data-raw",
            "--data-binary",
            "--data-urlencode",
            "-f",
            "--form",
        }
        header_opts = {"-h", "--header", "-b", "--cookie", "-a", "--user-agent", "-e", "--referer"}
        i = 1
        while i < len(tokens):
            token = tokens[i]
            lower = token.lower()
            if token == "-D" or lower == "--dump-header":
                writes_file = True
                i += 2
                continue
            if token == "-d":
                has_data = True
                i += 2
                continue
            if lower == "--json":
                has_data = True
                i += 2
                continue
            if lower.startswith("--json="):
                has_data = True
                i += 1
                continue
            if lower in {"--trace", "--trace-ascii", "--stderr"}:
                writes_file = True
                i += 2
                continue
            if lower == "--oauth2-bearer":
                self.add("block", "http-credential", line_no, "curl --oauth2-bearer 会内联 token")
                i += 2
                continue
            if lower.startswith("--oauth2-bearer="):
                self.add("block", "http-credential", line_no, "curl --oauth2-bearer 会内联 token")
                i += 1
                continue
            if lower in {"-x", "--request"} and i + 1 < len(tokens):
                method = tokens[i + 1].upper()
                i += 2
                continue
            if token == "-K" or lower == "--config":
                self.add("block", "http-config", line_no, "curl -K/--config 可隐藏任意写请求选项")
                i += 2
                continue
            if lower.startswith("--config="):
                self.add("block", "http-config", line_no, "curl --config 可隐藏任意写请求选项")
                i += 1
                continue
            if token.startswith("-X") and len(token) > 2:
                method = token[2:].upper()
                i += 1
                continue
            if lower.startswith("--request="):
                method = token.split("=", 1)[1].upper()
                i += 1
                continue
            if token.startswith("-d") and len(token) > 2:
                has_data = True
                i += 1
                continue
            if token.startswith("-T") and len(token) > 2:
                self.add("block", "http-upload", line_no, "curl -T 会上传文件")
                i += 1
                continue
            if token.startswith("-o") and len(token) > 2:
                writes_file = True
                i += 1
                continue
            if token.startswith("-u") and len(token) > 2:
                self.add("block", "http-credential", line_no, "curl -u 会内联账号密码")
                i += 1
                continue
            if token.startswith("-H") and len(token) > 2:
                i += 1
                continue
            if token.startswith("-A") and len(token) > 2:
                i += 1
                continue
            if token.startswith("-b") and len(token) > 2:
                i += 1
                continue
            if lower.startswith("--data") or lower.startswith("--form"):
                has_data = True
                i += 1
                continue
            if lower.startswith("--upload-file="):
                self.add("block", "http-upload", line_no, "curl --upload-file 会上传文件")
                i += 1
                continue
            if lower.startswith("--output="):
                writes_file = True
                i += 1
                continue
            if lower.startswith("--cookie-jar="):
                writes_file = True
                i += 1
                continue
            if lower.startswith("--user="):
                self.add("block", "http-credential", line_no, "curl --user 会内联账号密码")
                i += 1
                continue
            if lower.startswith("--header=") or lower.startswith("--cookie="):
                i += 1
                continue
            if lower.startswith("--user-agent=") or lower.startswith("--referer="):
                i += 1
                continue
            if lower in data_opts:
                has_data = True
                i += 2
                continue
            if lower in {"-t", "--upload-file"}:
                self.add("block", "http-upload", line_no, "curl -T 会上传文件")
                i += 2
                continue
            if lower in {"-o", "--output"}:
                writes_file = True
                i += 2
                continue
            if lower in {"-O", "--remote-name"}:
                writes_file = True
                i += 1
                continue
            if lower in {"-c", "--cookie-jar"}:
                writes_file = True
                i += 2
                continue
            if lower in {"-i", "--head"}:
                method = method or "HEAD"
                i += 1
                continue
            if lower in {"-g", "--get"}:
                method = method or "GET"
                i += 1
                continue
            if lower in {"-u", "--user"}:
                self.add("block", "http-credential", line_no, "curl -u 会内联账号密码")
                i += 2
                continue
            if lower in header_opts:
                i += 2
                continue
            if token.startswith("-"):
                i += 1
                continue
            if not url:
                url = token
            i += 1

        if writes_file:
            self.add("block", "http-file-write", line_no, "curl 的 -o/-O/-c 会写本地文件")
        if method is None:
            method = "POST" if has_data else "GET"
        if method not in {"GET", "HEAD", "OPTIONS"}:
            self.add("block", "http-write", line_no, f"curl 使用 {method} 写请求，禁止线上执行")
        elif self.has_mutation_word(url):
            self.add("warn", "http-mutation-url", line_no, f"GET {url} 的路径含副作用词，请确认")

    def check_wget(self, line: str, line_no: int) -> None:
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            tokens = line.split()
        for token in tokens[1:]:
            lower = token.lower()
            if lower in {"--post-data", "--post-file", "--body-data", "--body-file"} or lower.startswith(
                ("--post-data=", "--post-file=", "--body-data=", "--body-file=")
            ):
                self.add("block", "http-write", line_no, "wget --post-*/--body-* 会发起写请求")
                return
            if lower.startswith("--method="):
                method = token.split("=", 1)[1].upper()
                if method not in {"GET", "HEAD", "OPTIONS"}:
                    self.add("block", "http-write", line_no, f"wget --method={method} 是写请求")
                    return
            if token in {"-O", "--output-document"} or lower.startswith("--output-document="):
                self.add("block", "http-file-write", line_no, "wget -O/--output-document 会写本地文件")
                return

    def has_mutation_word(self, url: str) -> bool:
        lower = url.lower()
        return any(word in lower for word in MUTATION_URL_WORDS)

    # ---------- Credentials ----------

    def check_credentials(self) -> None:
        for pattern, rule in CREDENTIAL_PATTERNS:
            for match in pattern.finditer(self.text):
                matched = match.group(0)
                if PLACEHOLDER_RE.search(matched):
                    continue
                line = line_at(self.text, match.start())
                self.add("block", rule, line, "片段疑似包含凭证/密钥；请改用环境变量并轮换已泄露凭证")

    # ---------- Output ----------


def read_input(path: str) -> str:
    if path in {"-", ""}:
        return sys.stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"无法读取文件 {path}: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="静态检查线上只读排查片段：阻断已知写操作、凭证与高风险副作用。"
    )
    parser.add_argument("path", nargs="?", default="-", help="文件路径；- 表示 stdin")
    parser.add_argument(
        "--lang",
        choices=["auto", "python", "sql", "redis", "http", "text"],
        default="auto",
        help="片段语言；text 只做敏感信息扫描",
    )
    parser.add_argument("--strict", action="store_true", help="把 WARN 也视为失败")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        text = read_input(args.path)
        checker = ReadOnlyChecker(text, args.lang, args.strict)
        findings = checker.check()
    except (InputError, ValueError) as exc:
        if args.as_json:
            print(
                json.dumps(
                    {"ok": False, "error": str(exc), "language": args.lang},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    has_block = any(f.severity == "block" for f in findings)
    has_warn = any(f.severity == "warn" for f in findings)
    ok = not has_block and not (args.strict and has_warn)
    summary = {
        "block": sum(1 for f in findings if f.severity == "block"),
        "warn": sum(1 for f in findings if f.severity == "warn"),
        "info": sum(1 for f in findings if f.severity == "info"),
    }

    if args.as_json:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "language": checker.lang,
                    "strict": args.strict,
                    "summary": summary,
                    "findings": [asdict(f) for f in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for finding in findings:
            label = finding.severity.upper()
            print(f"{label:<5} L{finding.line:<4} {finding.rule}: {finding.message}")
            if finding.snippet:
                print(f"      {finding.snippet}")
        if findings:
            print(f"\nSummary: {summary['block']} block, {summary['warn']} warn")
        else:
            print("PASS: 未发现已知写操作/凭证（静态检查，不保证绝对无副作用）")
        if not ok and not has_block and args.strict:
            print("STRICT: WARN 被视为失败")

    return EXIT_OK if ok else EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(main())
