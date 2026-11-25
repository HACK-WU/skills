#!/usr/bin/env python3
"""校验图集：配置完整性 + 三方对齐 + 图源存在 + （可选）导出文件可用性

用法：
    python3 check_atlas.py .                          # 校验 config + views + snippets
    python3 check_atlas.py . --html dist/atlas.html   # 额外校验导出单文件

三方对齐（唯一必须记住的约束）：
    nav[].page            →  pages[id]
    pages[id].code[].id   =  views/{id}.svg 里的 data-node-id
    pages[id].code[].file →  snippets[id][nodeId]

退出码：0 通过；1 有 error；2 体积超硬上限。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_io import load_atlas, page_ids

MAX_BYTES = 10 * 1024 * 1024
TARGET_BYTES = 3 * 1024 * 1024
EXTERNAL = re.compile(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', re.I)
NODE_ID = re.compile(r'data-node-id="([^"]+)"')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".", help="图集目录（含 site.json + nav/ 或 atlas.config.json）")
    ap.add_argument("--html", default=None, help="额外校验导出的单文件")
    args = ap.parse_args()
    root = args.root

    base, cfg, pages = load_atlas(root)

    errors, warns, oks = [], [], []
    root = base
    views_dir = cfg.get("views_dir") or "views"
    ids = page_ids(cfg)
    if not ids:
        errors.append("nav 里没有引用任何页面")

    deep = [0]

    def walk_nav(items, depth=0):
        """递归查 nav 结构本身：每个叶子必须有 page，分组必须有 children。"""
        for it in items or []:
            if not isinstance(it, dict):
                errors.append("nav 里有非对象节点（第 %d 层）" % depth)
                continue
            deep[0] = max(deep[0], depth + 1)
            kids = it.get("children")
            has_kids = isinstance(kids, list) and len(kids) > 0
            if has_kids:
                if it.get("page"):
                    errors.append(
                        "nav 节点 %s 同时有 page 和 children（二者互斥；"
                        "要让分组本身也是页面，把该页作为 children 的第一项）" % (it.get("id") or it.get("name") or "?"))
                walk_nav(kids, depth + 1)
            elif not it.get("page"):
                errors.append("nav 节点 %s 既没有 children 也没有 page（第 %d 层）"
                              % (it.get("id") or it.get("name") or "?", depth))

    walk_nav(cfg.get("nav") or [])
    if deep[0] > 4:
        warns.append("nav 最深 %d 层：侧栏每层缩进 12px，超过 4 层文字会挤到换行" % deep[0])

    snip_path = os.path.join(root, "snippets.json")
    snippets = cfg.get("snippets") or {}
    if not snippets:
        if os.path.isfile(snip_path):
            with open(snip_path, encoding="utf-8") as f:
                snippets = json.load(f)
        else:
            warns.append("没有片段（snippets.json / 配置内联）：所有节点将不可点")

    for pid in ids:
        page = pages.get(pid)
        if page is None:
            errors.append("%s：nav 引用了它，但 pages 里没有配置" % pid)
            continue

        if not (page.get("summary") or "").strip():
            warns.append("%s：缺 summary" % pid)
        if len(page.get("points") or []) < 3:
            errors.append("%s：解读不足 3 条" % pid)
        docs = page.get("docs") or []
        if not docs:
            warns.append("%s：没有 docs 条目" % pid)
        dup_docs = [d for d in docs if d in {c.get("file") for c in (page.get("code") or []) if c.get("file")}]
        if dup_docs:
            warns.append("%s：docs 里混了源码路径，与代码块重复（docs 应放文档）：%s"
                         % (pid, ", ".join(dup_docs)))

        svg_rel = page.get("svg") or os.path.join(views_dir, pid + ".svg")
        svg_path = svg_rel if os.path.isabs(svg_rel) else os.path.join(root, svg_rel)
        if not os.path.isfile(svg_path):
            errors.append("%s：缺图源 %s" % (pid, svg_rel))
            continue
        with open(svg_path, encoding="utf-8", errors="replace") as f:
            svg = f.read()
        node_ids = set(NODE_ID.findall(svg))
        if not node_ids:
            errors.append("%s：图内没有任何 data-node-id，节点无法挂代码" % pid)
        if page.get("interactive"):
            ip = page["interactive"] if os.path.isabs(page["interactive"]) else os.path.join(root, page["interactive"])
            if not os.path.isfile(ip):
                warns.append("%s：interactive 指向不存在的文件（%s）" % (pid, page["interactive"]))

        code = page.get("code") or []
        coded = [c.get("id") for c in code if c.get("file")]
        concept = [c.get("id") for c in code if c.get("concept")]
        snip_ids = set((snippets.get(pid) or {}).keys())

        for cid in coded:
            if cid not in node_ids:
                errors.append("%s/%s：代码条目在图里找不到同名节点（data-node-id 不匹配）" % (pid, cid))
            if cid not in snip_ids:
                errors.append("%s/%s：有代码位置但没有片段（重跑 collect_snippets.py）" % (pid, cid))
        for cid in concept:
            if cid in snip_ids:
                errors.append("%s/%s：标了 concept 却有片段（二者互斥）" % (pid, cid))
        for sid in snip_ids - set(coded):
            errors.append("%s/%s：孤儿片段（snippets 有、pages 无）" % (pid, sid))

        total_nodes = len(node_ids)
        covered = len(set(coded) & node_ids)
        if covered:
            oks.append("%s：%d/%d 节点可点" % (pid, covered, total_nodes))
        if total_nodes and covered / total_nodes < 0.5:
            warns.append("%s：可点覆盖率仅 %.0f%%（%d/%d），建议给主要节点补 code[]"
                         % (pid, covered / total_nodes * 100, covered, total_nodes))

    # 可选：校验导出单文件
    if args.html:
        if not os.path.isfile(args.html):
            errors.append("导出文件不存在：%s" % args.html)
        else:
            with open(args.html, encoding="utf-8", errors="replace") as f:
                html = f.read()
            size = os.path.getsize(args.html)
            if size > MAX_BYTES:
                errors.append("导出单文件 %.1f MB 超硬上限 10 MB" % (size / 1024 / 1024))
            elif size > TARGET_BYTES:
                warns.append("导出单文件 %.1f MB 超目标 3 MB" % (size / 1024 / 1024))
            else:
                oks.append("导出体积 %.2f MB" % (size / 1024 / 1024))
            ext = sorted({u for u in EXTERNAL.findall(html) if "www.w3.org" not in u})
            if ext:
                errors.append("导出文件有外链资源（离线不可用）：%s" % ", ".join(ext[:5]))
            else:
                oks.append("导出文件无外链资源")
            if "__ATLAS_FONTS__" in html:
                errors.append("导出文件字体占位符未替换")
            if not re.search(r'<script id="demo-config"', html):
                errors.append("导出文件缺少内置配置位（框架文件被改过？）")
            if re.search(r'"demo"\s*:\s*true', html):
                warns.append("导出文件带 demo:true 标记：顶栏会显示「示例」（导出时应移除）")

    for o in oks:
        print("  ✓ " + o)
    for w in warns:
        print("  ! " + w)
    for e in errors:
        print("  ✗ " + e, file=sys.stderr)

    over = args.html and os.path.isfile(args.html) and os.path.getsize(args.html) > MAX_BYTES
    if errors:
        print("\n校验失败：%d error / %d warning" % (len(errors), len(warns)), file=sys.stderr)
        return 2 if over else 1
    print("\n校验通过：0 error / %d warning" % len(warns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
