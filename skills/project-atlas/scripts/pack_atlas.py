#!/usr/bin/env python3
"""一条命令完成分发打包：build → check → 收拢 interactive 依赖 → 清单（可选 zip）

用法：
    python3 pack_atlas.py <图集目录或 config.json> dist/
    python3 pack_atlas.py <图集目录> dist/ --zip
    python3 pack_atlas.py <图集目录> dist/ --name 项目知识地图

产出（dist/ 下）：
    atlas.html            自包含产物（唯一必须分发的文件）
    views/*.html          仅当某页配了 interactive 时随附，保持相对路径
    MANIFEST.txt          拷贝清单（文件、大小、sha256 前 12 位）
    atlas.zip             加了 --zip 时额外生成

任何一步失败即终止，不产出"半个包"。
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from atlas_io import load_atlas, page_ids, figures_of


def run(script, *args):
    cmd = [sys.executable, os.path.join(HERE, script)] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.stderr.strip():
        print(r.stderr.strip(), file=sys.stderr)
    return r.returncode


def sha12(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="图集目录（含 site.json + nav/）或 atlas.config.json")
    ap.add_argument("out", nargs="?", default="dist", help="分发目录，默认 dist/")
    ap.add_argument("--name", default="atlas", help="产物文件名（默认 atlas，.html 自动加）")
    ap.add_argument("--zip", action="store_true", help="额外打一个 zip")
    ap.add_argument("--with-source", action="store_true",
                    help="同时带上配置与图源（便于对方后续维护，分发本身不需要）")
    ap.add_argument("--clean", action="store_true",
                    help="打包前清空输出目录（避免上一版遗留的废弃文件混进清单）")
    args = ap.parse_args()

    base, site, pages = load_atlas(args.src)
    dist = os.path.abspath(args.out)
    os.makedirs(dist, exist_ok=True)
    if args.clean and os.path.isdir(dist):
        for name in os.listdir(dist):
            target = os.path.join(dist, name)
            shutil.rmtree(target) if os.path.isdir(target) else os.remove(target)
        print("已清空输出目录：%s" % dist)
    html = os.path.join(dist, args.name + ".html")

    print("① 构建")
    if run("build_atlas.py", args.src, html) != 0:
        print("\n构建失败，终止打包", file=sys.stderr)
        return 1

    print("\n② 校验")
    if run("check_atlas.py", args.src, "--html", html) != 0:
        print("\n校验未通过，终止打包（产物留在 %s 供排查）" % html, file=sys.stderr)
        return 1

    print("\n③ 收拢 interactive 依赖")
    extras, missing = [], []
    views_dir = site.get("views_dir") or "views"
    for pid in page_ids(site):
        page = pages.get(pid) or {}
        # 页级与 figure 级都要收：一页多图时每张图可以各自带交互版
        rels = [page.get("interactive")] + [f.get("interactive") for f in figures_of(page, pid, views_dir)]
        for rel in [r for r in rels if r]:
            src = rel if os.path.isabs(rel) else os.path.join(base, rel)
            if not os.path.isfile(src):
                missing.append("%s → %s" % (pid, rel))
                continue
            dst = os.path.join(dist, rel)
            os.makedirs(os.path.dirname(dst) or dist, exist_ok=True)
            shutil.copy2(src, dst)
            if rel not in extras:
                extras.append(rel)
    if extras:
        for e in extras:
            print("  + " + e)
    else:
        print("  （没有 interactive 依赖，产物只有一个文件）")
    if missing:
        print("  ! 以下 interactive 指向的文件不存在，已跳过：", file=sys.stderr)
        for m in missing:
            print("    " + m, file=sys.stderr)

    print("\n④ 附带源文件")
    if args.with_source:
        for rel in ("site.json", "atlas.config.json", "snippets.json"):
            src = os.path.join(base, rel)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(dist, rel))
                extras.append(rel)
                print("  + " + rel)
        nav_src = os.path.join(base, "nav")
        if os.path.isdir(nav_src):
            shutil.copytree(nav_src, os.path.join(dist, "nav"), dirs_exist_ok=True)
            extras.append("nav/")
            print("  + nav/")
        # 图源也必须带：否则对方拿到的是"改不了也重建不了"的半套源文件
        views_rel = site.get("views_dir") or "views"
        views_src = os.path.join(base, views_rel)
        if os.path.isdir(views_src):
            shutil.copytree(views_src, os.path.join(dist, views_rel), dirs_exist_ok=True)
            extras.append(views_rel + "/")
            print("  + %s/" % views_rel)
    else:
        print("  （跳过；需要对方后续维护时加 --with-source）")

    # 清单只统计"本次产出"，不把 dist 里上一版遗留的文件算进来；
    # extras 里可能有目录（nav/、views/），递归展开成具体文件
    produced = [html]
    for e in extras:
        p = os.path.join(dist, e.rstrip("/"))
        if os.path.isdir(p):
            for root, _dirs, fs in os.walk(p):
                for f in sorted(fs):
                    produced.append(os.path.join(root, f))
        elif os.path.isfile(p):
            produced.append(p)
    rows = [(os.path.relpath(p, dist), os.path.getsize(p), sha12(p)) for p in produced]
    rows.sort()
    total = sum(r[1] for r in rows)
    lines = ["分发清单（pack_atlas.py 生成）", ""]
    lines.append("分支 %s @ %s　生成于 %s" % (
        site.get("branch", "unknown"), site.get("baseline", "unknown"), site.get("generated_at", "")))
    lines.append("")
    for rel, size, h in rows:
        lines.append("  %-40s %8.1f KB  %s" % (rel, size / 1024, h))
    lines.append("")
    lines.append("  合计 %.2f MB / %d 个文件" % (total / 1024 / 1024, len(rows)))
    lines.append("")
    lines.append("拷贝方式：把 dist/ 下所有文件按原相对路径放到目标系统；")
    lines.append("只带 %s.html 也能独立打开（配置/图源/字体/片段都已内联）。" % args.name)
    manifest = "\n".join(lines) + "\n"
    with open(os.path.join(dist, "MANIFEST.txt"), "w", encoding="utf-8") as f:
        f.write(manifest)
    mine = {r[0] for r in rows} | {"MANIFEST.txt"}
    actual = set()
    for root, _dirs, files in os.walk(dist):
        for f in files:
            actual.add(os.path.relpath(os.path.join(root, f), dist))
    stale = sorted(actual - mine)
    if stale:
        print("  ! 输出目录有本次未产出的文件（上一版遗留，加 --clean 可清空）：", file=sys.stderr)
        for x in stale[:5]:
            print("    " + x, file=sys.stderr)
    print("\n" + manifest)

    if args.zip:
        zpath = os.path.join(dist, args.name + ".zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for p in produced + [os.path.join(dist, "MANIFEST.txt")]:
                if os.path.exists(p):
                    z.write(p, os.path.relpath(p, dist))
        print("打包：%s（%.2f MB）" % (zpath, os.path.getsize(zpath) / 1024 / 1024))

    print("\n完成：%s" % dist)
    if not extras:
        print("提示：产物只有 %s.html 一个文件，直接拷走即可。" % args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
