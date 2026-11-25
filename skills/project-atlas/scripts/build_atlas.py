#!/usr/bin/env python3
"""导出单文件：atlas.config.json + views/*.svg + snippets.json → 一个可双击打开的 HTML

用法：
    python3 build_atlas.py atlas.config.json dist/atlas.html

它做的事（确定性工作，不交给 AI）：
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
from atlas_io import load_atlas, page_ids, write_bundle

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="图集目录（含 site.json + nav/）或单文件 atlas.config.json")
    ap.add_argument("out", help="输出 HTML 路径")
    ap.add_argument("--framework", default=None, help="框架文件，默认本 skill 的 framework/index.html")
    args = ap.parse_args()

    base, cfg, pages = load_atlas(args.config)
    here = os.path.dirname(os.path.abspath(__file__))
    fw_path = args.framework or os.path.join(here, "..", "framework", "index.html")

    with open(fw_path, encoding="utf-8") as f:
        html = f.read()

    report = []
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
            report.append("nav 引用了 %s，但 pages 里没有它的配置" % pid)
            continue
        svg_rel = page.get("svg") or os.path.join(views_dir, pid + ".svg")
        svg_path = svg_rel if os.path.isabs(svg_rel) else os.path.join(base, svg_rel)
        if not os.path.isfile(svg_path):
            report.append("%s 缺图源：%s" % (pid, svg_rel))
            continue
        with open(svg_path, encoding="utf-8", errors="replace") as f:
            svg = f.read()
        raw_bytes += len(svg.encode("utf-8"))
        svg = XML_DECL.sub("", svg)
        before = font_stat[0]
        svg = extract_fonts(svg)
        had_fonts = font_stat[0] > before
        if not SVG_ROOT.search(svg):
            report.append("%s 内容不是 SVG" % pid)
        block = '<template data-demo="1" data-view="%s"%s>%s</template>' % (
            pid, ' data-fonts="1"' if had_fonts else '', svg)
        if tpl_pattern(pid).search(html):
            html = tpl_pattern(pid).sub(lambda m: block, html, count=1)
        else:
            html = html.replace('<div id="view-sources" hidden></div>',
                                block + '\n<div id="view-sources" hidden></div>', 1)
        kept.append(pid)

    # 删掉框架自带、但本次配置没用到的示例图
    for pid in re.findall(r'<template data-demo="1" data-view="([^"]+)"', html):
        if pid not in kept:
            html = tpl_pattern(pid).sub('', html, count=1)

    # 3) 字体注入
    html = html.replace(FONTS_HOLE, "\n".join(fonts.values()), 1)
    if FONTS_HOLE in html:
        report.append("字体注入点缺失（框架文件被改过？）")

    leftover = [p for p in ("__ATLAS_FONTS__",) if p in html]
    if leftover:
        report.append("占位符残留：%s" % ", ".join(leftover))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)

    size = os.path.getsize(tmp)
    print("导出：%d 页 · 原始 SVG %.1f MB · 字体块 %d 个唯一（消除 %d 份重复）" % (
        len(kept), raw_bytes / 1024 / 1024, len(fonts), font_stat[1]))
    print("产物：%s（%.2f MB，目标 ≤3 MB / 上限 10 MB）" % (args.out, size / 1024 / 1024))
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
        print("提示：超过 3 MB 目标，考虑减页面", file=sys.stderr)
    return 0 if not report else 1


if __name__ == "__main__":
    sys.exit(main())
