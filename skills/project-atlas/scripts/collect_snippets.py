#!/usr/bin/env python3
"""采集：atlas.config.json 的 pages[].code[] 里声明的代码位置 → snippets.json

用法：
    python3 collect_snippets.py atlas.config.json snippets.json --repo-root .

设计约束：
- 行号越界 / 文件缺失 / 区间非法 / 缺 why → 直接失败，不截断、不"尽力而为"
- concept: true 的节点跳过（无代码，前端标为不可点）
- 疑似密钥行脱敏，并在报告中列出
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_io import load_atlas, page_ids

SENSITIVE = re.compile(
    r"(?i)(api[_-]?key|secret|password|passwd|token|access[_-]?key)\s*[:=]\s*['\"][^'\"]{8,}"
)
# 关键符号：类名 / 函数名 / 接口名，用于"对应代码块"列表展示
SYMBOL = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|interface|type|const|let)\s+([A-Za-z_$][\w$]*)"
)


def extract_symbol(chunk):
    for line in chunk:
        m = SYMBOL.match(line)
        if m:
            return m.group(1)
    return ""


def git_short(root):
    try:
        out = subprocess.run(
            ["git", "-C", root, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="图集目录（含 site.json + nav/）或单文件 atlas.config.json")
    ap.add_argument("out")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--max-lines", type=int, default=80, help="单片段最大行数，超出判为区间过大")
    args = ap.parse_args()

    base, cfg, all_pages = load_atlas(args.config)
    commit = git_short(args.repo_root)
    snippets, errors, masked, concept = {}, [], [], []
    cache = {}

    for pid in page_ids(cfg):
        page = all_pages.get(pid)
        if page is None:
            errors.append("nav 引用了 %s，但 pages 里没有它的配置" % pid)
            continue

        for node in (page.get("code") or []):
            nid = node.get("id")
            if not nid:
                errors.append("%s: code 条目缺 id" % pid)
                continue
            if node.get("concept"):
                concept.append("%s/%s" % (pid, nid))
                continue
            rel = node.get("file")
            lines = node.get("lines") or []
            if not rel or len(lines) != 2:
                errors.append("%s/%s 缺 file 或 lines:[起,止]（无代码的节点请标 concept: true）" % (pid, nid))
                continue
            start, end = lines
            if not isinstance(start, int) or not isinstance(end, int) or end < start:
                errors.append("%s/%s 行区间非法：%r" % (pid, nid, lines))
                continue
            if end - start + 1 > args.max_lines:
                errors.append("%s/%s 区间过大（%d 行 > 上限 %d）" % (pid, nid, end - start + 1, args.max_lines))
                continue
            why = (node.get("why") or "").strip()
            if not why:
                errors.append("%s/%s 缺 why（为什么看这段代码，读者据此决定要不要点）" % (pid, nid))
                continue

            path = rel if os.path.isabs(rel) else os.path.join(args.repo_root, rel)
            if not os.path.isfile(path):
                errors.append("%s/%s 文件不存在：%s" % (pid, nid, rel))
                continue

            if path not in cache:
                with open(path, encoding="utf-8", errors="replace") as f:
                    cache[path] = f.read().split("\n")
            file_lines = cache[path]
            if start < 1 or end > len(file_lines):
                errors.append("%s/%s 行号越界：声明 %d-%d，文件 %s 共 %d 行" % (
                    pid, nid, start, end, rel, len(file_lines)))
                continue

            chunk = []
            for i, line in enumerate(file_lines[start - 1:end], start=start):
                if SENSITIVE.search(line):
                    masked.append("%s/%s:%d" % (pid, nid, i))
                    chunk.append(re.sub(r"(['\"]).*?\1", r"\1***\1", line, count=1))
                else:
                    chunk.append(line)

            snippets.setdefault(pid, {})[nid] = {
                "file": rel,
                "line": start,
                "endLine": end,
                "commit": commit,
                "why": why,
                "symbol": node.get("symbol") or extract_symbol(chunk),
                "snippet": "\n".join(chunk),
            }

    covered = sum(len(v) for v in snippets.values())
    total = covered + len(concept)
    print("片段采集：%d/%d 可点节点已挂代码（概念节点 %d 个不计入）" % (covered, total, len(concept)))
    if concept:
        print("概念节点（无代码，不可点）：%s" % ", ".join(concept))
    if masked:
        print("已脱敏行（含疑似密钥）：%s" % ", ".join(masked))
    if errors:
        print("\n校验失败 %d 项（未写出 %s）：" % (len(errors), args.out), file=sys.stderr)
        for e in errors:
            print("  ✗ " + e, file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(snippets, f, ensure_ascii=False, indent=1)
    print("已写出 %s（commit %s）" % (args.out, commit or "unknown"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
