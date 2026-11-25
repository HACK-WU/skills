#!/usr/bin/env python3
"""导出 Markdown 目录包（命令版，与页面上的「导出 ↓」输出一致）

用法：
    python3 export_markdown.py <图集目录> dist-md/          # 输出目录
    python3 export_markdown.py <图集目录> atlas-md.zip      # 直接出 zip（路径以 .zip 结尾即判定）
    python3 export_markdown.py <图集目录> dist-md/ --no-images   # 不带图

产物结构（与侧栏大纲一一对应）：
    README.md                          标题 / 导语 / 基线 / 目录树
    01-架构总览/overview.md
    01-架构总览/images/overview.svg     图源原样导出（含内联字体，可单独打开）

与页面内导出的关系：两处实现同一份 md 模板，改动时需同步
（framework/index.html 的 pageMarkdown/readmeMarkdown ↔ 本脚本）。
"""
import argparse
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_io import load_atlas, page_ids

SVG_START = re.compile(r"<svg\b[^>]*>", re.S)
XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>\s*", re.S)


def safe_dir(name, idx):
    return "%02d-%s" % (idx + 1, re.sub(r'[/\\:*?"<>|]', "-", str(name)))


def groups(site):
    """递归出叶子分组：dir 是完整相对路径，path 是从根到叶的分组名。"""
    out = []

    def walk(items, parent_dir, parent_path):
        for i, it in enumerate(items or []):
            if not isinstance(it, dict):
                continue
            label = it.get("name") or it.get("id") or ("item%d" % (i + 1))
            d = (parent_dir + "/" if parent_dir else "") + safe_dir(label, i)
            kids = it.get("children")
            if isinstance(kids, list) and kids:
                walk(kids, d, parent_path + [label])
            else:
                pid = it.get("page") or it.get("id")
                if not pid:
                    continue
                # 叶子并入父目录；顶层页面才自建目录
                out.append({"dir": parent_dir or d, "name": label, "q": it.get("q") or "",
                            "pages": [pid], "path": parent_path + [label]})

    walk(site.get("nav") or [], "", [])
    return out


def norm_svg(text):
    """补 XML 声明与 xmlns —— 内联进 HTML 时不需要，独立文件必须有。"""
    s = XML_DECL.sub("", text).strip()
    if not s:
        return None
    m = SVG_START.search(s)
    if not m:
        return None
    tag = m.group(0)
    if not re.search(r'xmlns\s*=\s*["\']http://www\.w3\.org/2000/svg["\']', tag):
        s = s.replace(tag, tag[:-1] + ' xmlns="http://www.w3.org/2000/svg">', 1)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + s


def cell(t):
    return re.sub(r"\s*\n\s*", " ", str(t if t is not None else "")).replace("|", "\\|")


def page_md(pid, page, snippets, site, has_image=True):
    out = ["# " + (page.get("title") or pid), ""]
    meta = []
    if page.get("type"):
        meta.append(page["type"])
    if site.get("generated_at"):
        meta.append("生成于 " + site["generated_at"])
    if site.get("branch") and site.get("baseline"):
        meta.append("基线 %s@%s" % (site["branch"], site["baseline"]))
    if meta:
        out += ["> " + " · ".join(meta), ""]
    if page.get("summary"):
        out += [page["summary"], ""]
    if has_image:
        out += ["![%s](./images/%s.svg)" % (page.get("title") or pid, pid), ""]

    points = page.get("points") or []
    if points:
        out += ["## 怎么读这张图", ""]
        for p in points:
            out.append("- **%s**：%s" % (p[0], p[1] if len(p) > 1 else ""))
        out.append("")

    codes = [c for c in (page.get("code") or []) if c.get("file")]
    if codes:
        out += ["## 对应代码", "", "| 节点 | 位置 | 符号 | 说明 |", "| --- | --- | --- | --- |"]
        for c in codes:
            sn = (snippets.get(pid) or {}).get(c.get("id")) or {}
            sym = c.get("symbol") or sn.get("symbol") or ""
            lines = c.get("lines") or []
            loc = "`%s:%s-%s`" % (c["file"], lines[0] if lines else "-", lines[1] if lines else "-")
            out.append("| %s | %s | %s | %s |" % (cell(c.get("id")), loc, cell(sym or "-"), cell(c.get("why") or "")))
        out.append("")

    docs = page.get("docs") or []
    if docs:
        out += ["## 参考文档", ""]
        out += ["- " + d for d in docs]
        out.append("")
    return "\n".join(out)


def readme_md(gs, site):
    out = ["# " + (site.get("title") or "项目知识地图"), ""]
    if site.get("subtitle"):
        out += [site["subtitle"], ""]
    if site.get("intro"):
        out += [site["intro"], ""]
    if site.get("notice"):
        out += ["> " + site["notice"], ""]
    meta = []
    if site.get("branch") and site.get("baseline"):
        meta.append("基线 %s@%s" % (site["branch"], site["baseline"]))
    if site.get("generated_at"):
        meta.append("生成于 " + site["generated_at"])
    meta.append("%d 页" % sum(len(g["pages"]) for g in gs))
    out += [" · ".join(meta), "", "## 目录", ""]
    for g in gs:
        pid = g["pages"][0]
        page = PAGES_CACHE.get(pid) or {}
        trail = " / ".join(g.get("path") or [g["name"]])
        out.append("- %s[%s](%s/%s.md)" % (trail + " → " if trail else "",
                                           page.get("title") or pid, g["dir"], pid))
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="图集目录（含 site.json + nav/）或 atlas.config.json")
    ap.add_argument("out", help="输出目录，或以 .zip 结尾的压缩包路径")
    ap.add_argument("--no-images", action="store_true", help="不导出图源（md 里也不写图片引用）")
    ap.add_argument("--clean", action="store_true", help="输出目录模式：先清空目标目录，避免上一版遗留")
    args = ap.parse_args()

    base, site, pages = load_atlas(args.src)
    global PAGES_CACHE
    PAGES_CACHE = pages
    snip_path = os.path.join(base, "snippets.json")
    snippets = site.get("snippets") or {}
    if not snippets and os.path.isfile(snip_path):
        with open(snip_path, encoding="utf-8") as f:
            snippets = json.load(f)

    gs = groups(site)
    if not gs:
        print("nav 为空，没有可导出的页面", file=sys.stderr)
        return 2

    views_dir = site.get("views_dir") or "views"
    files = [("README.md", readme_md(gs, site).encode("utf-8"))]
    missing = []
    for g in gs:
        for pid in g["pages"]:
            page = pages.get(pid) or {}
            has_image = False
            if not args.no_images:
                rel = page.get("svg") or os.path.join(views_dir, pid + ".svg")
                path = rel if os.path.isabs(rel) else os.path.join(base, rel)
                if os.path.isfile(path):
                    with open(path, encoding="utf-8", errors="replace") as f:
                        svg = norm_svg(f.read())
                    if svg:
                        files.append(("%s/images/%s.svg" % (g["dir"], pid), svg.encode("utf-8")))
                        has_image = True
                else:
                    missing.append("%s → %s" % (pid, rel))
            files.append(("%s/%s.md" % (g["dir"], pid),
                          page_md(pid, page, snippets, site, has_image).encode("utf-8")))

    want_zip = args.out.lower().endswith(".zip")
    if want_zip:
        root = os.path.basename(args.out)[:-4]
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
            for rel, data in files:
                z.writestr("%s/%s" % (root, rel), data)
        size = os.path.getsize(args.out)
    else:
        if args.clean and os.path.isdir(args.out):
            import shutil
            for name in os.listdir(args.out):
                t = os.path.join(args.out, name)
                shutil.rmtree(t) if os.path.isdir(t) else os.remove(t)
            print("已清空输出目录：%s" % args.out)
        for rel, data in files:
            dst = os.path.join(args.out, rel)
            os.makedirs(os.path.dirname(dst) or args.out, exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
        size = sum(os.path.getsize(os.path.join(args.out, r)) for r, _ in files)
        produced = {r for r, _ in files}
        stale = []
        for root_dir, _dirs, fs in os.walk(args.out):
            for f in fs:
                rel = os.path.relpath(os.path.join(root_dir, f), args.out)
                if rel not in produced:
                    stale.append(rel)
        if stale:
            print("  ! 输出目录有本次未产出的文件（上一版遗留，加 --clean 可清空）：", file=sys.stderr)
            for x in stale[:5]:
                print("    " + x, file=sys.stderr)

    pages_n = sum(len(g["pages"]) for g in gs)
    imgs_n = len([f for f in files if f[0].endswith(".svg")])
    print("导出：%d 页 · %d 个 md · %d 张图 · %.0f KB" % (pages_n, pages_n + 1, imgs_n, size / 1024))
    print("产物：%s%s" % (args.out, "（zip）" if want_zip else "（目录）"))
    if missing:
        print("\n以下页面缺图源，已跳过（md 里的图片会指向不存在的文件）：", file=sys.stderr)
        for m in missing:
            print("  ! " + m, file=sys.stderr)
        return 1
    return 0


PAGES_CACHE = {}

if __name__ == "__main__":
    sys.exit(main())
