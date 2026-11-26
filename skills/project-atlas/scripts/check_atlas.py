#!/usr/bin/env python3
"""校验图集：配置完整性 + 三方对齐 + 图源存在 + （可选）导出文件可用性

用法：
    python3 check_atlas.py .                          # 校验 config + views + snippets
    python3 check_atlas.py . --html dist/atlas.html   # 额外校验导出单文件

三方对齐（唯一必须记住的约束）：
    nav[].page            →  pages[id]
    pages[id].code[].id   =  本页任一 figures[].svg 里的 data-node-id（至少一张图里有）
    pages[id].code[].file →  snippets[id][nodeId]

一页多图与外部节点的额外约束：
    figures[].id 唯一 / 每图 ≥3 条解读 / 每图图源存在
    external 节点必须有 owner + contract，且 returnsTo 落回本页内部节点（或显式 oneWay）
    可点率分母只算内部节点（外部天然没有源码）

退出码：0 通过；1 有 error；2 体积超硬上限。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_io import (load_atlas, page_ids, figures_of, resolve_code, links_of)
from check_svg import inspect_svg

MAX_BYTES = 10 * 1024 * 1024
TARGET_BYTES = 3 * 1024 * 1024
EXTERNAL = re.compile(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', re.I)
NODE_ID = re.compile(r'data-node-id="([^"]+)"')
DATA_LINK = re.compile(r'data-link="([^"]+)"')


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

    linted_svg = {}   # svg 绝对路径 → 是否通过（同一图源被多页引用时只体检一次）

    for pid in ids:
        page = pages.get(pid)
        if page is None:
            errors.append("%s：nav 引用了它，但 pages 里没有配置" % pid)
            continue

        if not (page.get("summary") or "").strip():
            warns.append("%s：缺 summary" % pid)

        code = resolve_code(page, cfg)
        coded = [c.get("id") for c in code if c.get("file")]
        concept = [c.get("id") for c in code if c.get("concept")]
        exts = [c for c in code if c.get("external")]

        docs = page.get("docs") or []
        if not docs:
            warns.append("%s：没有 docs 条目" % pid)
        dup_docs = [d for d in docs if d in set(coded)]
        if dup_docs:
            warns.append("%s：docs 里混了源码路径，与代码块重复（docs 应放文档）：%s"
                         % (pid, ", ".join(dup_docs)))

        # ── figures 级：id 唯一 / 解读条数 / 图源存在 / 节点收集 ──
        figs = figures_of(page, pid, views_dir)
        seen_fig, fig_nodes, fig_links = set(), {}, set()
        for i, f in enumerate(figs):
            fid = f["id"]
            if fid in seen_fig:
                errors.append("%s：figures[].id 重复（%s）——跨图关联与图源 key 都靠它区分，必须唯一"
                              % (pid, fid))
            seen_fig.add(fid)
            if len(f["points"]) < 3:
                errors.append("%s/图 %d：解读不足 3 条（每张图都要能说清怎么读）" % (pid, i + 1))

            svg_rel = f["svg"]
            svg_path = svg_rel if os.path.isabs(svg_rel) else os.path.join(root, svg_rel)
            if not os.path.isfile(svg_path):
                errors.append("%s/图 %d：缺图源 %s" % (pid, i + 1, svg_rel))
                continue
            with open(svg_path, encoding="utf-8", errors="replace") as fh:
                svg = fh.read()

            # 图源自包含体检：缺样式 = 黑块，缺 viewBox = 不能缩放（Shadow DOM 挂载，壳层样式进不去）。
            # 同一图源被多页引用时只体检一次，否则同一个缺陷会在报告里重复 N 遍
            if svg_path not in linted_svg:
                svg_issues, _stats = inspect_svg(svg, svg_rel)
                clean_fig = True
                for it in svg_issues:
                    msg = "%s/图 %d：%s（%s）" % (pid, i + 1, it["msg"], svg_rel)
                    if it["level"] == "error":
                        clean_fig = False
                        errors.append(msg + ("　→ " + it["fix"] if it.get("fix") else ""))
                    else:
                        warns.append(msg)
                linted_svg[svg_path] = clean_fig

            node_ids = set(NODE_ID.findall(svg))
            if not node_ids:
                errors.append("%s/图 %d：图内没有任何 data-node-id，节点无法挂代码" % (pid, i + 1))
            fig_nodes[fid] = node_ids
            for dl in DATA_LINK.findall(svg):
                pair = [x.strip() for x in dl.split("->", 1)]
                if len(pair) == 2:
                    fig_links.add(tuple(pair))

            if f.get("interactive"):
                ip = f["interactive"] if os.path.isabs(f["interactive"]) else os.path.join(root, f["interactive"])
                if not os.path.isfile(ip):
                    warns.append("%s/图 %d：interactive 指向不存在的文件（%s）" % (pid, i + 1, f["interactive"]))

        all_nodes = set()
        for ns in fig_nodes.values():
            all_nodes |= ns

        # 多图相关性：两张图一个共享节点都没有，多半该拆成两页（同屏对照是说给读者省一次跳转，
        # 不是给不相关的图省一页）
        if len(fig_nodes) > 1:
            sets = list(fig_nodes.values())
            if not any(sets[i] & sets[j] for i in range(len(sets)) for j in range(i + 1, len(sets))):
                warns.append("%s：%d 张图之间没有任何共享节点——若无需同屏对照，建议拆成多页"
                              % (pid, len(sets)))

        # ── 三方对齐：code[] 是页级，按"至少出现在一张图里"判定 ──
        snip_ids = set((snippets.get(pid) or {}).keys())
        for cid in coded:
            if cid not in all_nodes:
                errors.append("%s/%s：代码条目在本页任何一张图里都找不到同名节点（data-node-id 不匹配）"
                              % (pid, cid))
            if cid not in snip_ids:
                errors.append("%s/%s：有代码位置但没有片段（重跑 collect_snippets.py）" % (pid, cid))
        for cid in concept:
            if cid in snip_ids:
                errors.append("%s/%s：标了 concept 却有片段（二者互斥）" % (pid, cid))
        ext_set = set(c["id"] for c in exts)
        for cid in ext_set:
            if cid in snip_ids:
                errors.append("%s/%s：标了 external 却有片段（外部服务没有本仓源码，二者互斥）"
                              % (pid, cid))
            if cid not in all_nodes:
                warns.append("%s/%s：外部节点没画在任何一张图里（只在依赖清单中出现，读者在图上看不到它）"
                              % (pid, cid))
        for sid in snip_ids - set(coded):
            errors.append("%s/%s：孤儿片段（snippets 有、pages 无）" % (pid, sid))

        # 图上有节点但没配 code：warning（多半是新加节点忘了配）
        unlabeled = sorted(all_nodes - set(coded) - set(concept) - ext_set)
        if unlabeled:
            warns.append("%s：图上有 %d 个节点没配 code（显示为概念节点）：%s"
                          % (pid, len(unlabeled), ", ".join(unlabeled[:6])))

        # ── 外部节点：契约必填 + 回程必须落回内部 ──
        internal_ids = set(coded) | set(concept)
        for c in exts:
            cid = c["id"]
            miss = [k for k in ("owner", "contract") if not (c.get(k) or "").strip()]
            if miss:
                errors.append("%s/%s：外部节点缺 %s（外部服务没有源码可校验，契约字段是唯一准入门槛）"
                              % (pid, cid, " / ".join(miss)))
            if c.get("oneWay"):
                continue
            to = (c.get("returnsTo") or "").strip()
            if not to:
                errors.append("%s/%s：外部节点缺 returnsTo——给出回程落点，或显式标 oneWay: true（单向链路）"
                              % (pid, cid))
            elif to in ext_set:
                errors.append("%s/%s：returnsTo 指向另一个外部节点（%s）——回程必须落回本项目内部"
                              % (pid, cid, to))
            elif to not in internal_ids:
                errors.append("%s/%s：returnsTo 指向的 %s 在本页 code[] 里不存在或没有源码"
                              % (pid, cid, to))

        # ── 衔接关系：两头必须存在；identifier 必须有名字、建议说明存哪 ──
        links = links_of(page)
        ids_all = set(c.get("id") for c in code if c.get("id"))
        # 持久化按"键"判断：同一条 data_id 可能有多段流转，只要任意一段写了 storedAt 就够
        stored_keys = set(l["carries"] for l in links
                          if l["kind"] == "identifier" and l["storedAt"].strip())
        warned_keys = set()
        for l in links:
            f, t = l["from"], l["to"]
            if not f or not t:
                errors.append("%s：links 条目缺 from / to（衔接关系要说清两头是谁）" % pid)
                continue
            for side, nid in (("from", f), ("to", t)):
                if nid not in ids_all:
                    errors.append("%s：links 的 %s=%s 不在本页 code[] 里（衔接关系指向了不存在的节点）"
                                  % (pid, side, nid))
            if l["kind"] == "identifier":
                if not l["carries"].strip():
                    errors.append("%s：%s→%s 标了 identifier 却缺 carries（标识符必须有名字）"
                                  % (pid, f, t))
                elif l["carries"] not in stored_keys and l["carries"] not in warned_keys:
                    warned_keys.add(l["carries"])
                    warns.append("%s：标识符 %s 整条流转都没写 storedAt"
                                  "（没说明存在哪，重启后可能对不上）" % (pid, l["carries"]))
        if links:
            oks.append("%s：%d 条衔接关系（其中 %d 条标识符）"
                       % (pid, len(links), len([l for l in links if l["kind"] == "identifier"])))

        # 图源 data-link ↔ links 双向一致（status/none 本就不上图，不参与比对）
        if links and fig_nodes:
            labeled = set((l["from"], l["to"]) for l in links
                          if l["kind"] not in ("status", "none"))
            for pair in sorted(fig_links - labeled):
                warns.append("%s：图源标了 data-link=\"%s->%s\"，但 links[] 里没有这条衔接关系"
                             "（标签不会出现）" % (pid, pair[0], pair[1]))
            if len(fig_nodes) == len(figs):
                for l in links:
                    if l["kind"] == "identifier" and (l["from"], l["to"]) not in fig_links:
                        warns.append("%s：identifier 边 %s→%s 在图源里没有 data-link，"
                                     "图上标不出 %s" % (pid, l["from"], l["to"], l["carries"]))

        # ── 覆盖率：分母只算内部节点 ──
        internal_nodes = all_nodes - ext_set
        covered = internal_nodes & set(coded)
        if internal_nodes:
            oks.append("%s：%d/%d 内部节点可点（%d 张图）"
                       % (pid, len(covered), len(internal_nodes), len(figs)))
            if len(covered) / len(internal_nodes) < 0.5:
                warns.append("%s：内部节点可点率仅 %.0f%%（%d/%d），建议给主要节点补 code[]"
                             % (pid, len(covered) / len(internal_nodes) * 100,
                                len(covered), len(internal_nodes)))
        if exts:
            oks.append("%s：%d 个外部依赖（只到契约粒度）" % (pid, len(exts)))

    if linted_svg:
        oks.append("图源体检：%d/%d 张图样式自包含（style 在 SVG 内、有 viewBox、无外链）"
                   % (sum(1 for ok in linted_svg.values() if ok), len(linted_svg)))

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
