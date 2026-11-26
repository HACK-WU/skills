#!/usr/bin/env python3
"""导出单文件：atlas.config.json + views/*.svg + snippets.json → 一个可双击打开的 HTML

用法：
    python3 build_atlas.py atlas.config.json dist/atlas.html

它做的事（确定性工作，不交给 AI）：
0. 两道前置门禁：输出路径不得覆盖框架壳；每张图源先过自包含体检（缺 style / 缺 viewBox
   / 外链 → 阻断），否则会产出"能构建、打开是黑块"的假成功产物
1. 把站点/页面/片段配置注入框架的内置配置位（导出后即使不联网、不起服务也渲染真实内容）
2. 把各页图源 SVG 内联进框架的内置图源位
3. 字体去重：各 SVG 内重复的 @font-face 提到壳层（@font-face 文档级注册，Shadow DOM 内可用）
4. 校验注入完整性后原子替换（失败不留半成品）

注意：日常开发不需要它——框架 + atlas.config.json + 起本地服务即可实时渲染。
本命令只用于「要发给别人 / 要双击就能看」的分发场景。
"""
import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_io import load_atlas, page_ids, write_bundle, figures_of, fig_key
from check_svg import inspect_svg

FONT_FACE = re.compile(r"@font-face\s*\{[^}]*\}", re.S)
XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>\s*", re.S)
SVG_ROOT = re.compile(r"<svg\b", re.S)
DEMO_CFG = re.compile(r'(<script id="demo-config" type="application/json">)[\s\S]*?(</script>)', re.S)
FONTS_HOLE = "/* __ATLAS_FONTS__ */"

MAX_BYTES = 10 * 1024 * 1024
TARGET_BYTES = 3 * 1024 * 1024


def safe_json(obj):
    return json.dumps(obj, ensure_ascii=False).replace("</script>", "<\\/script>")


def tpl_pattern(pid):
    return re.compile(r'<template data-demo="1" data-view="%s">[\s\S]*?</template>' % re.escape(pid))


def output_hazards(out, fw_path):
    """产物路径护栏：框架是唯一真源，被产物覆盖后示例态/交互/字体注入点全丢，且不可再生。

    实测事故：装配时把产物写到 .atlas/index.html（框架就放在那），69 KB 壳被覆盖。
    """
    o = os.path.realpath(out)
    bad = []
    if o == os.path.realpath(fw_path):
        bad.append("输出路径就是本次使用的框架文件（%s）——构建会就地覆盖它" % fw_path)
    skill_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    if o.startswith(skill_dir + os.sep):
        bad.append("输出路径落在 skill 目录内（%s）——产物不该混进 skill 与版本库" % skill_dir)
    if os.path.isfile(o):
        try:
            with open(o, encoding="utf-8", errors="replace") as f:
                head = f.read(512 * 1024)
        except OSError:
            head = ""
        if "__ATLAS_FONTS__" in head and 'id="demo-config"' in head:
            bad.append("目标位置已是一份框架壳（含 __ATLAS_FONTS__ 占位符与内置配置位）"
                       "——继续会覆盖唯一真源")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="图集目录（含 site.json + nav/）或单文件 atlas.config.json")
    ap.add_argument("out", help="输出 HTML 路径")
    ap.add_argument("--framework", default=None, help="框架文件，默认本 skill 的 framework/index.html")
    args = ap.parse_args()

    base, cfg, pages = load_atlas(args.config)
    here = os.path.dirname(os.path.abspath(__file__))
    fw_path = args.framework or os.path.join(here, "..", "framework", "index.html")

    hazards = output_hazards(args.out, fw_path)
    if hazards:
        print("\n导出中止：输出路径有风险（未写出任何文件）", file=sys.stderr)
        for h in hazards:
            print("  ✗ " + h, file=sys.stderr)
        print("  改用 dist/atlas.html 之类的独立目录；框架请保持原样（--framework 只指向要读的壳）",
              file=sys.stderr)
        return 1

    with open(fw_path, encoding="utf-8") as f:
        html = f.read()

    report = []
    fatal = []          # 阻断项：任何一条存在都不写出产物，避免"导出看起来成功"
    # 目录模式：顺便合成运行时用的单文件 config（浏览器无法列目录）
    if os.path.isdir(os.path.abspath(args.config)):
        bundle = os.path.join(base, "atlas.config.json")
        write_bundle(cfg, pages, bundle)
        print("运行时配置已更新：%s" % bundle)
    if not pages:
        report.append("配置里没有 pages：产物将只显示内置示例")
    views_dir = cfg.get("views_dir") or "views"

    # 片段：配置内联优先，否则读同目录 snippets.json
    snips = cfg.get("snippets") or {}
    if not snips:
        sp = os.path.join(base, "snippets.json")
        if os.path.isfile(sp):
            with open(sp, encoding="utf-8") as f:
                snips = json.load(f)
        else:
            report.append("没有片段：节点在导出文件里将不可点（先跑 collect_snippets.py 或内联 snippets）")

    # 1) 注入内置配置
    payload = dict(cfg)
    payload.pop("demo", None)          # 导出的是真实数据，不带示例标记
    payload["baked"] = True              # 标记已烘焙：运行时不再 fetch 外部配置
    payload["pages"] = pages
    payload["snippets"] = snips
    html = DEMO_CFG.sub(lambda m: m.group(1) + safe_json(payload) + m.group(2), html, count=1)

    # 2) 图源：替换框架自带示例图，多余的示例图删掉
    fonts, font_stat = {}, [0, 0]
    raw_bytes = 0
    kept = []
    style_stat, style_sha = [0], set()
    ids = page_ids(cfg)

    def extract_fonts(svg):
        def repl(m):
            block = m.group(0)
            key = hashlib.sha1(block.encode("utf-8")).hexdigest()
            font_stat[0] += 1
            if key in fonts:
                font_stat[1] += 1
            else:
                fonts[key] = block
            return ""
        return FONT_FACE.sub(repl, svg)

    for pid in ids:
        page = pages.get(pid)
        if page is None:
            fatal.append("nav 引用了 %s，但 pages 里没有它的配置" % pid)
            continue
        figs = figures_of(page, pid, views_dir)
        for i, f in enumerate(figs):
            key = fig_key(pid, f["id"], i)
            svg_rel = f["svg"]
            svg_path = svg_rel if os.path.isabs(svg_rel) else os.path.join(base, svg_rel)
            if not os.path.isfile(svg_path):
                fatal.append("%s/图 %d 缺图源：%s" % (pid, i + 1, svg_rel))
                continue
            with open(svg_path, encoding="utf-8", errors="replace") as fh:
                svg = fh.read()

            # 图源体检（构建前）：缺样式/缺 viewBox 的图能构建成功但打开是黑块或压扁，
            # 这种"看起来成功"的产物比直接失败更危险，一律阻断。
            svg_issues, svg_stats = inspect_svg(svg, svg_rel)
            for it in svg_issues:
                line = "%s/图 %d 图源体检：%s（%s）" % (pid, i + 1, it["msg"], svg_rel)
                if it["level"] == "error":
                    fatal.append(line + ("　→ " + it["fix"] if it.get("fix") else ""))
                else:
                    report.append(line)
            if svg_stats.get("styles"):
                style_stat[0] += 1
                style_sha.add(svg_stats["style_sha"])

            raw_bytes += len(svg.encode("utf-8"))
            svg = XML_DECL.sub("", svg)
            before = font_stat[0]
            svg = extract_fonts(svg)
            had_fonts = font_stat[0] > before
            if not SVG_ROOT.search(svg):
                fatal.append("%s/图 %d 内容不是 SVG" % (pid, i + 1))
            block = '<template data-demo="1" data-view="%s"%s>%s</template>' % (
                key, ' data-fonts="1"' if had_fonts else '', svg)
            if tpl_pattern(key).search(html):
                html = tpl_pattern(key).sub(lambda m: block, html, count=1)
            else:
                html = html.replace('<div id="view-sources" hidden></div>',
                                    block + '\n<div id="view-sources" hidden></div>', 1)
            kept.append(key)

    # 删掉框架自带、但本次配置没用到的示例图
    for key in re.findall(r'<template data-demo="1" data-view="([^"]+)"', html):
        if key not in kept:
            html = tpl_pattern(key).sub('', html, count=1)

    # 3) 字体注入
    html = html.replace(FONTS_HOLE, "\n".join(fonts.values()), 1)
    if FONTS_HOLE in html:
        report.append("字体注入点缺失（框架文件被改过？）")

    leftover = [p for p in ("__ATLAS_FONTS__",) if p in html]
    if leftover:
        report.append("占位符残留：%s" % ", ".join(leftover))

    # 有阻断项就不写产物：单文件是发给别人的，"失败但留下半成品"比直接失败更危险
    if fatal:
        print("\n导出中止：%d 项阻断问题（未写出产物）" % len(fatal), file=sys.stderr)
        for r in fatal:
            print("  ✗ " + r, file=sys.stderr)
        if os.path.exists(args.out):
            print("上一版产物保持不变：%s" % args.out, file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)

    size = os.path.getsize(tmp)
    print("导出：%d 页 / %d 张图 · 原始 SVG %.1f MB · 字体块 %d 个唯一（消除 %d 份重复）" % (
        len(ids), len(kept), raw_bytes / 1024 / 1024, len(fonts), font_stat[1]))
    print("产物：%s（%.2f MB，目标 ≤3 MB / 上限 10 MB）" % (args.out, size / 1024 / 1024))
    print("图源体检：%d/%d 张图自带样式（样式块 %d 种）" % (style_stat[0], len(kept), len(style_sha)))
    print("提示：这是分发用单文件；日常改配置不需要重新导出，起本地服务读 atlas.config.json 即可。")

    if report:
        print("\n需修正 %d 项：" % len(report), file=sys.stderr)
        for r in report:
            print("  ! " + r, file=sys.stderr)

    if size > MAX_BYTES:
        os.remove(tmp)
        print("超出硬上限，已清理临时文件；请减少页面或压缩图源", file=sys.stderr)
        return 2

    os.replace(tmp, args.out)
    if size > TARGET_BYTES:
        print("提示：超过 3 MB 目标（当前按页算，多图页要让位给总图数）", file=sys.stderr)
    return 0 if not report else 1


if __name__ == "__main__":
    sys.exit(main())
