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

一页多图：第 1 张图 images/<pid>.svg，其后 images/<pid>-<figId>.svg，
每张图在 md 里各成一节（图名 + 图片 + 这张图的解读）；代码表整页合并去重。

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
from atlas_io import (load_atlas, page_ids, figures_of, resolve_code,
                      links_of, merge_id_links, link_path)
from check_svg import inspect_svg

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


# 文件名：路径分隔符 / Windows 保留字符 / 中英文冒号 / 控制字符一律换成连字符
BAD_NAME = re.compile(r'[/\\:*?"<>|\r\n\t：]')
MAX_NAME = 60          # 字符数上限（中文按 1 字算，远低于 255 字节的文件系统限制）


def safe_name(title, pid, used):
    """页面标题 → 可用的文件名（不含 .md）：清非法字符 → 去重 → 截断。

    used 按分类目录维护（不同目录允许同名），比较时忽略大小写（macOS/Windows 默认不敏感）。
    """
    n = BAD_NAME.sub("-", (title or "").strip())
    n = re.sub(r"-{2,}", "-", n).strip("- .")
    if not n:
        n = pid
    if len(n) > MAX_NAME:
        n = n[:MAX_NAME].rstrip("- .") + "…"
    base, i = n, 2
    while n.lower() in used:
        n = "%s-%d" % (base, i)
        i += 1
    used.add(n.lower())
    return n


# 代码块语言：按扩展名推断，认不出就不标（fence 留空）
LANG = {
    "ts": "ts", "tsx": "tsx", "js": "js", "jsx": "jsx", "mjs": "js", "cjs": "js",
    "py": "python", "go": "go", "rs": "rust", "java": "java", "kt": "kotlin",
    "c": "c", "h": "c", "cpp": "cpp", "cc": "cpp", "hpp": "cpp", "cs": "csharp",
    "rb": "ruby", "php": "php", "swift": "swift", "scala": "scala",
    "sh": "bash", "bash": "bash", "zsh": "bash", "ps1": "powershell",
    "sql": "sql", "json": "json", "yaml": "yaml", "yml": "yaml", "toml": "toml",
    "ini": "ini", "md": "markdown", "html": "html", "css": "css",
    "vue": "vue", "svelte": "svelte", "proto": "protobuf", "tf": "hcl",
}


def lang_of(path):
    p = (path or "").rsplit("/", 1)[-1]
    return LANG.get(p.rsplit(".", 1)[-1].lower(), "") if "." in p else ""


def page_md(pid, page, snippets, site, img_names=None, no_code=False):
    """img_names: {figId: 文件名}，由 main 决定哪几张图成功导出；None = 不导出图。"""
    figs = figures_of(page, pid, site.get("views_dir") or "views")
    many = len(figs) > 1

    out = ["# " + (page.get("title") or pid), ""]
    meta = []
    if page.get("type"):
        meta.append(page["type"])
    elif not many and figs[0].get("type"):
        meta.append(figs[0]["type"])
    if many:
        meta.append("%d 张图" % len(figs))
    if site.get("generated_at"):
        meta.append("生成于 " + site["generated_at"])
    if site.get("branch") and site.get("baseline"):
        meta.append("基线 %s@%s" % (site["branch"], site["baseline"]))
    if meta:
        out += ["> " + " · ".join(meta), ""]
    if page.get("summary"):
        out += [page["summary"], ""]

    for i, f in enumerate(figs):
        if many:
            out += ["## 图 %d · %s" % (i + 1, f.get("name") or f.get("id") or ""), ""]
        if f.get("q"):
            out += ["> 这张图回答：" + f["q"], ""]
        name = (img_names or {}).get(f["id"])
        if name:
            out += ["![%s](./images/%s)" % (f.get("name") or (page.get("title") or pid), name), ""]
        if f.get("points"):
            out += ["### 怎么读这张图" if many else "## 怎么读这张图", ""]
            for p in f["points"]:
                out.append("- **%s**：%s" % (p[0], p[1] if len(p) > 1 else ""))
            out.append("")

    code = resolve_code(page, site)

    codes = [c for c in code if c.get("file")]
    if codes:
        out += ["## 对应代码", ""]
        if not no_code:
            out += ["> 生成时的代码快照，不代表仓库当前 HEAD。", ""]
        for c in codes:
            sn = (snippets.get(pid) or {}).get(c.get("id")) or {}
            sym = c.get("symbol") or sn.get("symbol") or ""
            lines = c.get("lines") or []
            loc = "%s:%s-%s" % (c["file"], lines[0] if lines else "-", lines[1] if lines else "-")
            head = "### `%s`" % loc
            if c.get("id"):
                head += " · " + str(c["id"])
            if sym:
                head += " · " + sym
            out += [head, ""]
            if c.get("why"):
                out += [str(c["why"]), ""]
            snip = "" if no_code else (sn.get("snippet") or "").strip("\n")
            if snip:
                out += ["```" + lang_of(c["file"]), snip, "```", ""]
            elif not no_code:
                out += ["*（未采集到代码快照：先跑 `collect_snippets.py`）*", ""]

    exts = [c for c in code if c.get("external")]
    if exts:
        out += ["## 外部依赖", "",
                "> 只到契约粒度：外部服务的内部实现不展开，它有自己的知识地图。", "",
                "| 外部服务 | 归属 | 契约 | 回程 |", "| --- | --- | --- | --- |"]
        for c in exts:
            if c.get("oneWay"):
                ret = "单向（不要求回程）"
            else:
                ret = "→ %s" % (c.get("returnsTo") or "-")
                if c.get("returnForm"):
                    ret += "（%s）" % c["returnForm"]
            out.append("| %s | %s | %s | %s |" % (
                cell(c.get("id")), cell(c.get("owner") or "-"),
                cell(c.get("contract") or "-"), cell(ret)))
        out.append("")

    links = links_of(page)
    if links:
        id_links = merge_id_links(links)
        flow_links = [l for l in links if l["kind"] not in ("identifier", "status", "none")]
        quiet = [l for l in links if l["kind"] in ("status", "none")]
        out += ["## 衔接关系", ""]
        if id_links:
            out += ["**标识符（后续操作靠它定位）**", "",
                    "| 衔接键 | 流转路径 | 形态 | 持久化 | 说明 |",
                    "| --- | --- | --- | --- | --- |"]
            for m in id_links:
                key = m["key"] + (("（%s）" % m["cardinality"]) if m["cardinality"] else "")
                out.append("| %s | %s | %s | %s | %s |" % (
                    cell(key), cell(link_path(m)),
                    cell(m["shape"] or "-"), cell(m["storedAt"] or "⚠ 未说明"),
                    cell(m["note"] or "-")))
            out.append("")
        if flow_links:
            out += ["**传递内容（不构成标识符）**", "",
                    "| 内容 | 产出 → 消费 | 说明 |", "| --- | --- | --- |"]
            for l in flow_links:
                out.append("| %s | %s → %s | %s |" % (
                    cell(l["carries"] or "-"), cell(l["from"]), cell(l["to"]),
                    cell(l["note"] or "-")))
            out.append("")
        if quiet:
            out.append("> 另有 %d 条状态型返回（成功 / 失败）不构成衔接键：%s"
                       % (len(quiet), "、".join(l["from"] + " → " + l["to"] for l in quiet)))
            out.append("")

    docs = page.get("docs") or []
    if docs:
        out += ["## 参考文档", ""]
        out += ["- " + d for d in docs]
        out.append("")
    return "\n".join(out)


def readme_md(gs, site, name_map):
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
                                          page.get("title") or pid, g["dir"],
                                          name_map.get(pid) or pid))
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="图集目录（含 site.json + nav/）或 atlas.config.json")
    ap.add_argument("out", help="输出目录，或以 .zip 结尾的压缩包路径")
    ap.add_argument("--no-images", action="store_true", help="不导出图源（md 里也不写图片引用）")
    ap.add_argument("--clean", action="store_true", help="输出目录模式：先清空目标目录，避免上一版遗留")
    ap.add_argument("--no-code", action="store_true", help="不导出代码块正文（只留路径与说明）")
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

    # 文件名用页面标题（读者认得出），按分类目录去重；图片仍用 pid（内部资源，重名风险高）
    name_map = {}
    for g in gs:
        used = set()
        for pid in g["pages"]:
            page = pages.get(pid) or {}
            name_map[pid] = safe_name(page.get("title"), pid, used)

    files = [("README.md", readme_md(gs, site, name_map).encode("utf-8"))]
    missing, bad_svg = [], []
    for g in gs:
        for pid in g["pages"]:
            page = pages.get(pid) or {}
            img_names = {}
            if not args.no_images:
                figs = figures_of(page, pid, views_dir)
                for i, f in enumerate(figs):
                    rel = f["svg"]
                    path = rel if os.path.isabs(rel) else os.path.join(base, rel)
                    fname = ("%s.svg" % pid) if i == 0 else ("%s-%s.svg" % (pid, f["id"]))
                    if os.path.isfile(path):
                        with open(path, encoding="utf-8", errors="replace") as fh:
                            raw = fh.read()
                        # 图源体检：md 图包原样带走 SVG，黑块/缺样式会一起进入文档库。
                        # 本段只在导出图时执行（--no-images 已在更外层跳过），故不需要额外豁免
                        svg_issues, _st = inspect_svg(raw, rel)
                        for it in svg_issues:
                            line = "%s/图 %d 图源体检：%s（%s）" % (pid, i + 1, it["msg"], rel)
                            if it["level"] == "error":
                                bad_svg.append(line + ("　→ " + it["fix"] if it.get("fix") else ""))
                            else:
                                print("  ! " + line, file=sys.stderr)
                        svg = norm_svg(raw)
                        if svg:
                            files.append(("%s/images/%s" % (g["dir"], fname), svg.encode("utf-8")))
                            img_names[f["id"]] = fname
                    else:
                        missing.append("%s/图 %d → %s" % (pid, i + 1, rel))
            files.append(("%s/%s.md" % (g["dir"], name_map.get(pid) or pid),
                          page_md(pid, page, snippets, site, img_names,
                                  args.no_code).encode("utf-8")))

    # 图源体检失败就中止：文档库里出现黑块图，读者会以为"这系统就是黑的"
    if bad_svg:
        print("\n导出中止：%d 处图源体检未通过（未写出产物）" % len(bad_svg), file=sys.stderr)
        for m in bad_svg:
            print("  ✗ " + m, file=sys.stderr)
        print("先修图源（python3 check_svg.py <图集目录>），再重跑导出", file=sys.stderr)
        return 1

    # 缺图源就中止：md 里图片断链的交付物比不出更糟（确实要无图版请显式加 --no-images）
    if missing and not args.no_images:
        print("\n导出中止：%d 处缺图源（未写出产物）" % len(missing), file=sys.stderr)
        for m in missing:
            print("  ✗ " + m, file=sys.stderr)
        print("确实要出无图版请加 --no-images", file=sys.stderr)
        return 1

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
    if args.no_images:
        print("提示：--no-images，md 里不含图片引用")
    return 0


PAGES_CACHE = {}

if __name__ == "__main__":
    sys.exit(main())
