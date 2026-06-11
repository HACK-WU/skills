#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S-02: 列出需求，支持筛选、依赖展开、反向依赖查询。"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / ".requirements" / "scripts"))

# Windows GBK 编码修复
sys.stdout.reconfigure(encoding="utf-8")

from config_loader import ConfigLoader
from meta_store import MetaStore
from requirement_utils import find_req, find_rev_deps

DEFAULT_COLUMNS = ["id", "feature", "status", "tags", "version", "updated"]
ALL_COLUMNS = [
    "id", "feature", "status", "tags", "version",
    "created", "updated", "depends_on",
]


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
        "tags": "标签",
        "version": "版本",
        "created": "创建日期",
        "updated": "更新日期",
        "depends_on": "依赖",
    }
    header_row = [headers.get(c, c) for c in columns]

    # 计算列宽
    col_widths = [len(h) for h in header_row]
    for row in rows:
        for i, col in enumerate(columns):
            val = row.get(col)
            if isinstance(val, list):
                val = ", ".join(val)
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
                val = ", ".join(val)
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

    fields = [
        ("ID", req.get("id", "")),
        ("功能名称", req.get("feature", "")),
        ("状态", req.get("status", "")),
        ("标签", ", ".join(req.get("tags", []))),
        ("版本", str(req.get("version", ""))),
        ("创建日期", req.get("created", "")),
        ("更新日期", req.get("updated", "")),
    ]
    for label, value in fields:
        lines.append(f"│ {_widen(label, 12)} │ {_widen(value, 42)} │")

    lines.append(f"├{'─' * 30}┴{'─' * 29}┤")

    # 变更记录
    changelog = req.get("changelog", [])
    if changelog:
        lines.append(f"│ 变更记录（{len(changelog)} 项）：{' ' * 34} │")
        for entry in changelog[-5:]:  # 最近 5 条
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


def main():
    parser = argparse.ArgumentParser(description="列出需求")
    parser.add_argument("--id", help="精确匹配需求 ID")
    parser.add_argument("--status", help="按状态筛选")
    parser.add_argument("--tag", action="append", help="按标签筛选（可重复，AND 关系）")
    parser.add_argument("--from", dest="date_from", help="更新日期起 (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="更新日期止 (YYYY-MM-DD)")
    parser.add_argument("--search", help="模糊搜索功能名称")
    parser.add_argument("--deps", action="store_true", help="展开依赖需求")
    parser.add_argument("--rev-deps", action="store_true", help="反向依赖查询")
    parser.add_argument("--deps-depth", type=int, default=1, help="依赖展开深度（默认 1）")
    parser.add_argument("--json", dest="json_output", action="store_true", help="JSON 格式输出")
    parser.add_argument("--columns", default=",".join(DEFAULT_COLUMNS),
                        help="自定义显示列（逗号分隔）")
    parser.add_argument("--no-color", action="store_true", help="禁用颜色")
    args = parser.parse_args()

    # 加载数据
    try:
        cl = ConfigLoader()
        storage_root = cl.read()
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    ms = MetaStore(storage_root)
    data = ms.load()
    requirements = data["requirements"]

    # 筛选
    results = []
    for dir_name, req in requirements.items():
        # --id
        if args.id and req.get("id") != args.id:
            continue
        # --status
        if args.status and req.get("status") != args.status:
            continue
        # --tag (AND)
        if args.tag:
            req_tags = req.get("tags", [])
            if not all(t in req_tags for t in args.tag):
                continue
        # --from / --to
        updated = req.get("updated", "")
        if args.date_from and updated < args.date_from:
            continue
        if args.date_to and updated > args.date_to:
            continue
        # --search
        if args.search and args.search.lower() not in req.get("feature", "").lower():
            continue
        results.append(req)

    # --id 详情模式
    if args.id and results:
        req = results[0]
        if args.json_output:
            if args.deps:
                req = dict(req)
                req["_deps"] = _expand_deps(requirements, req.get("depends_on", []), args.deps_depth)
            if args.rev_deps:
                req = dict(req)
                req["_rev_deps"] = find_rev_deps(requirements, req.get("id", ""))
            print(json.dumps(req, ensure_ascii=False, indent=2))
        else:
            print(_format_detail(req, requirements, args))
        return

    # 按 updated 降序
    results.sort(key=lambda r: r.get("updated", ""), reverse=True)

    if not results:
        print("（无匹配需求）")
        return

    if args.json_output:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        columns = [c.strip() for c in args.columns.split(",") if c.strip()]
        # 复制一份再格式化，避免修改原始 requirements 数据
        display_rows = []
        for r in results:
            row = dict(r)
            if "tags" in row and isinstance(row["tags"], list):
                row["tags"] = ", ".join(row["tags"])
            display_rows.append(row)
        print(_build_table(display_rows, columns))
        print(f"共 {len(results)} 个需求")


if __name__ == "__main__":
    main()
