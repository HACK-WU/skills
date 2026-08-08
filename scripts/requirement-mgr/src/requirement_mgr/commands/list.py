# -*- coding: utf-8 -*-
"""req list: 列出需求，支持筛选、依赖展开、反向依赖查询、角色筛选。"""

import json
import re
import sys
from datetime import datetime

from requirement_mgr.core.config_loader import ConfigLoader
from requirement_mgr.core.meta_store import MetaStore
from requirement_mgr.core.requirement_utils import ARCHIVED_STATUS, find_req, find_rev_deps


DEFAULT_COLUMNS = ["id", "feature", "status", "role", "tags", "branch", "commits", "version", "created"]
ALL_COLUMNS = [
    "id", "feature", "status", "role", "tags", "branch", "version",
    "created", "updated", "parent_id", "depends_on", "docs", "commits",
]

ARCHIVE_STATUS = ARCHIVED_STATUS  # 兼容别名，常量收敛在 requirement_utils
ARCHIVE_PREFIX = "archive/"

# O-10：--from/--to 日期格式校验（YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS）
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$")


def _normalize_ts(ts: str) -> str:
    """将旧格式时间戳（YYYY-MM-DD）归一化为完整格式（YYYY-MM-DD HH:MM:SS），用于排序。

    新格式已为完整时间戳，直接返回。空字符串返回空。
    """
    if not ts:
        return ""
    if len(ts) <= 10:
        return ts + " 00:00:00"
    return ts


def _widen(s: str, width: int) -> str:
    """CJK 字符占 2 列宽的对齐辅助。"""
    w = sum(2 if ord(c) > 127 else 1 for c in s)
    return s + " " * max(0, width - w)


def _build_table(rows: list[dict], columns: list[str]) -> str:
    """构建 ASCII 表格字符串。"""
    headers = {
        "id": "ID",
        "feature": "功能名称",
        "status": "状态",
        "role": "角色",
        "tags": "标签",
        "branch": "分支",
        "version": "版本",
        "created": "创建日期",
        "updated": "更新日期",
        "parent_id": "父需求",
        "depends_on": "依赖",
        "docs": "关联文档",
        "commits": "关联提交",
    }
    header_row = [headers.get(c, c) for c in columns]

    # 计算列宽
    col_widths = [len(h) for h in header_row]
    for row in rows:
        for i, col in enumerate(columns):
            val = row.get(col)
            if isinstance(val, list):
                if val and isinstance(val[0], dict):
                    val = ", ".join(f"{d.get('path','?')}({d.get('type','?')})" for d in val)
                else:
                    val = ", ".join(str(v) for v in val)
            elif val is None:
                val = ""
            else:
                val = str(val)
            col_widths[i] = max(col_widths[i], sum(2 if ord(c) > 127 else 1 for c in val))

    def fmt_row(vals):
        return "│ " + " │ ".join(_widen(str(v), col_widths[i]) for i, v in enumerate(vals)) + " │"

    sep_top = "┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐"
    sep_mid = "├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤"
    sep_bot = "└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘"

    lines = [sep_top, fmt_row(header_row), sep_mid]
    for row in rows:
        vals = []
        for col in columns:
            val = row.get(col)
            if isinstance(val, list):
                if val and isinstance(val[0], dict):
                    val = ", ".join(f"{d.get('path','?')}({d.get('type','?')})" for d in val)
                else:
                    val = ", ".join(str(v) for v in val)
            elif val is None:
                val = ""
            else:
                val = str(val)
            vals.append(val)
        lines.append(fmt_row(vals))
    lines.append(sep_bot)
    return "\n".join(lines)


def _expand_deps(requirements: dict, dep_ids: list[str], depth: int, visited: set | None = None) -> list[dict]:
    """递归展开依赖，返回去重列表。"""
    if visited is None:
        visited = set()
    if depth <= 0:
        return []
    result = []
    for rid in dep_ids:
        if rid in visited:
            continue
        visited.add(rid)
        _, req = find_req(requirements, rid)
        if req:
            result.append(req)
            sub = _expand_deps(requirements, req.get("depends_on", []), depth - 1, visited)
            result.extend(sub)
    return result


def _format_detail(req: dict, requirements: dict, args) -> str:
    """格式化单个需求的完整信息。"""
    lines = []
    sep = "─" * 60
    lines.append(f"┌{sep}┐")
    lines.append(f"│ {'需求详情':^58} │")
    lines.append(f"├{'─' * 30}┬{'─' * 29}┤")

    role = req.get("role", "standalone")
    parent_id = req.get("parent_id")
    child_ids = req.get("child_ids", [])

    fields = [
        ("ID", req.get("id", "")),
        ("功能名称", req.get("feature", "")),
        ("状态", req.get("status", "")),
        ("角色", role),
        ("父需求", parent_id or "—"),
        ("子需求", ", ".join(child_ids) if child_ids else "—"),
        ("标签", ", ".join(req.get("tags", []))),
        ("分支", req.get("branch") or "—"),
        ("版本", str(req.get("version", ""))),
        ("创建日期", req.get("created", "")),
        ("更新日期", req.get("updated", "")),
    ]
    for label, value in fields:
        lines.append(f"│ {_widen(label, 12)} │ {_widen(value, 42)} │")

    lines.append(f"├{'─' * 30}┴{'─' * 29}┤")

    # 关联文档
    docs = req.get("docs", [])
    if docs:
        title = f"关联文档（{len(docs)} 项）："
        title_w = sum(2 if ord(c) > 127 else 1 for c in title)
        lines.append(f"│ {title}{' ' * max(0, 56 - title_w)} │")
        for d in docs:
            dt = d.get("type", "?")
            dp = d.get("path", "")
            lines.append(f"│   [{_widen(dt, 12)}] {_widen(dp[:40], 40)} │")

    # 关联提交（完整 hash 列表仅在详情视图展示，默认列只显示数量）
    commits = req.get("commits", [])
    if commits:
        title = f"关联提交（{len(commits)} 项）："
        title_w = sum(2 if ord(c) > 127 else 1 for c in title)
        lines.append(f"│ {title}{' ' * max(0, 56 - title_w)} │")
        for c in commits:
            lines.append(f"│   - {_widen(str(c)[:54], 54)} │")

    # 变更记录
    changelog = req.get("changelog", [])
    if changelog:
        lines.append(f"│ 变更记录（{len(changelog)} 项）：{' ' * 34} │")
        for entry in changelog[-5:]:
            lines.append(f"│   - {_widen(entry[:54], 54)} │")

    # 依赖
    if args.deps:
        dep_ids = req.get("depends_on", [])
        deps = _expand_deps(requirements, dep_ids, args.deps_depth)
        if deps:
            lines.append(f"├{'─' * 30}┬{'─' * 29}┤")
            lines.append(f"│ 依赖需求（{len(deps)} 项, depth={args.deps_depth}）：{' ' * 22} │")
            for d in deps:
                lines.append(f"│   {_widen(d['id'], 8)} {_widen(d['feature'][:22], 22)} [{_widen(d['status'], 8)}] {', '.join(d.get('tags', []))[:16]} │")

    # 反向依赖
    if args.rev_deps:
        rev = find_rev_deps(requirements, req.get("id", ""))
        if rev:
            lines.append(f"├{'─' * 30}┬{'─' * 29}┤")
            lines.append(f"│ 反向依赖（{len(rev)} 项）：{' ' * 37} │")
            for r in rev:
                lines.append(f"│   {_widen(r['id'], 8)} {_widen(r['feature'][:22], 22)} [{_widen(r['status'], 8)}] │")

    lines.append(f"└{'─' * 30}┴{'─' * 29}┘")
    return "\n".join(lines)


def cmd_list(args):
    """执行 req list 命令。"""
    # 加载数据
    try:
        cl = ConfigLoader()
        storage_root = cl.read()
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 筛选值校验：无效值直接报错，避免静默返回空结果被误读为"无匹配"。
    # 白名单为空的配置项表示"不限制"，此时跳过校验。
    if args.status:
        valid_statuses = list(cl.get_requirement_statuses())
        # 兼容未含系统保留状态的旧自定义 config（list --status 已归档 是正当查询）
        if ARCHIVED_STATUS not in valid_statuses:
            valid_statuses.append(ARCHIVED_STATUS)
        if args.status not in valid_statuses:
            print(f"错误: 无效状态 '{args.status}'，有效值: {', '.join(valid_statuses)}", file=sys.stderr)
            sys.exit(1)
    if args.role:
        valid_roles = cl.get_requirement_roles()
        if args.role not in valid_roles:
            print(f"错误: 无效角色 '{args.role}'，有效值: {', '.join(valid_roles)}", file=sys.stderr)
            sys.exit(1)
    if args.category:
        feature_categories = cl.get_feature_categories()
        if feature_categories and args.category not in feature_categories:
            print(f"错误: 无效分类 '{args.category}'，有效值: {', '.join(feature_categories)}", file=sys.stderr)
            sys.exit(1)
    if args.tag:
        requirement_tags = cl.get_requirement_tags()
        if requirement_tags:
            invalid = [t for t in args.tag if t not in requirement_tags]
            if invalid:
                print(f"错误: 无效标签 {invalid}，有效值: {', '.join(requirement_tags)}", file=sys.stderr)
                sys.exit(1)
    # --limit 校验：负值非法
    if args.limit is not None and args.limit < 0:
        print(f"错误: --limit 不能为负值（{args.limit}），0 表示全部", file=sys.stderr)
        sys.exit(1)
    # O-10：--columns 无效列名报错（避免静默输出空列）
    if args.columns:
        cols = [c.strip() for c in args.columns.split(",") if c.strip()]
        if not cols:
            print(f"错误: --columns 不能为空，有效列: {', '.join(ALL_COLUMNS)}", file=sys.stderr)
            sys.exit(1)
        invalid_cols = [c for c in cols if c not in ALL_COLUMNS]
        if invalid_cols:
            print(f"错误: 无效列名 {invalid_cols}，有效列: {', '.join(ALL_COLUMNS)}", file=sys.stderr)
            sys.exit(1)
    # O-10：--from/--to 日期格式校验（正则验格式 + strptime 验日历合法性）+ 区间合法性
    for _flag, _val in (("--from", args.date_from), ("--to", args.date_to)):
        if not _val:
            continue
        if not _DATE_RE.match(_val):
            print(f"错误: {_flag} 日期格式非法 '{_val}'，应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS", file=sys.stderr)
            sys.exit(1)
        _fmt = "%Y-%m-%d %H:%M:%S" if len(_val) > 10 else "%Y-%m-%d"
        try:
            datetime.strptime(_val, _fmt)
        except ValueError:
            print(f"错误: {_flag} 日期非法 '{_val}'，不是有效的日历日期/时间", file=sys.stderr)
            sys.exit(1)
    if args.date_from and args.date_to:
        from_norm = _normalize_ts(args.date_from)
        to_norm = _normalize_ts(args.date_to)
        if len(args.date_to) <= 10:
            to_norm = args.date_to + " 23:59:59"
        if from_norm > to_norm:
            print(f"错误: --from '{args.date_from}' 晚于 --to '{args.date_to}'，区间为空", file=sys.stderr)
            sys.exit(1)

    ms = MetaStore(storage_root)
    data = ms.load()
    requirements = data["requirements"]

    # 筛选
    results = []
    for dir_name, req in requirements.items():
        # --id 模式不受归档过滤影响，始终可查到
        if args.id and req.get("id") != args.id:
            continue
        # 默认隐藏已归档需求（除非 --include-archived 或显式 --status 或 --id 查询）
        if not args.include_archived and not args.status and not args.id:
            if req.get("status") == ARCHIVE_STATUS:
                continue
        # --status
        if args.status and req.get("status") != args.status:
            continue
        # --tag (AND)
        if args.tag:
            req_tags = req.get("tags", [])
            if not all(t in req_tags for t in args.tag):
                continue
        # --role
        if args.role:
            req_role = req.get("role", "standalone")
            if req_role != args.role:
                continue
        # --parent-id
        if args.parent_id:
            req_parent = req.get("parent_id")
            if req_parent != args.parent_id:
                continue
        # --category（已归档需求键名带 archive/ 前缀，先去掉前缀再匹配分类）
        if args.category:
            key = dir_name
            if key.startswith(ARCHIVE_PREFIX):
                key = key[len(ARCHIVE_PREFIX):]
            parts = key.split("/")
            if len(parts) < 2:
                continue
            if parts[0] != args.category:
                continue
        # --from / --to（归一化处理旧格式时间戳）
        updated = _normalize_ts(req.get("updated", ""))
        if args.date_from and updated < _normalize_ts(args.date_from):
            continue
        if args.date_to:
            # date_to 使用当天末尾时间进行比较
            date_to = _normalize_ts(args.date_to)
            if len(args.date_to) <= 10:  # 旧格式日期
                date_to = args.date_to + " 23:59:59"
            if updated > date_to:
                continue
        # --search
        if args.search and args.search.lower() not in req.get("feature", "").lower():
            continue
        results.append(req)

    # --id 详情模式
    if args.id and results:
        req = results[0]
        if args.json_output:
            output = dict(req)
            if args.deps:
                output["_deps"] = _expand_deps(requirements, req.get("depends_on", []), args.deps_depth)
            if args.rev_deps:
                output["_rev_deps"] = find_rev_deps(requirements, req.get("id", ""))
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(_format_detail(req, requirements, args))
        return

    # 按 created 降序（归一化处理旧格式时间戳）
    results.sort(key=lambda r: _normalize_ts(r.get("created", "")), reverse=True)

    if not results:
        print("（无匹配需求）")
        return

    # --limit 截断（0 表示全部）；对表格与 --json 一致生效，行为可预测
    total = len(results)
    limit = args.limit if args.limit is not None else 0
    truncated = limit > 0 and total > limit
    if truncated:
        display_results = results[:limit]
    else:
        display_results = results

    if args.json_output:
        print(json.dumps(display_results, ensure_ascii=False, indent=2))
    else:
        columns_str = args.columns or ",".join(DEFAULT_COLUMNS)
        columns = [c.strip() for c in columns_str.split(",") if c.strip()]
        # 复制一份再格式化
        display_rows = []
        for r in display_results:
            row = dict(r)
            if "tags" in row and isinstance(row["tags"], list):
                row["tags"] = ", ".join(row["tags"])
            # 兼容旧数据：无 role 字段时默认 standalone
            if "role" not in row:
                row["role"] = "standalone"
            # 旧数据无 branch 字段展示 —
            row["branch"] = row.get("branch") or "—"
            # commits 默认列仅展示数量，完整 hash 列表在 --id 详情查看
            row["commits"] = str(len(row.get("commits", []) or []))
            display_rows.append(row)
        print(_build_table(display_rows, columns))
        if truncated:
            print(f"共 {total} 个需求，显示最近 {limit} 个（--limit 0 查看全部）")
        else:
            print(f"共 {total} 个需求")
