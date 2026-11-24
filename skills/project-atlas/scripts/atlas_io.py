#!/usr/bin/env python3
"""图集输入的统一加载层：既支持单文件 config，也支持目录树。

两种形态对上层完全等价，都返回 (base, site, pages)：

  单文件：  atlas.config.json            { title, branch, nav[], pages{} }
  目录树：  site.json + nav/<分类>/_group.json + nav/<分类>/<页面>.json

目录约定：
  nav/01-架构总览/            ← 目录名仅用于排序，不进入 id
    _group.json               ← { id, name, q }                 三级分类
    overview.json             ← 文件名即页面 id
  nav/03-服务与测试/
    _group.json               ← { id, name, q, page: "stack" }  两级分类（分类即页面）
    stack.json
"""
import json
import os
import sys


def _die(msg):
    print("输入错误：" + msg, file=sys.stderr)
    sys.exit(2)


def load_atlas(path):
    """返回 (base_dir, site, pages)。path 可以是 config.json 或图集目录。"""
    path = os.path.abspath(path)

    if os.path.isfile(path):
        base = os.path.dirname(path)
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        if not isinstance(cfg.get("nav"), list):
            _die("%s 缺少 nav 数组" % path)
        return base, cfg, cfg.get("pages") or {}

    if not os.path.isdir(path):
        _die("找不到 %s" % path)

    base = path
    site_path = os.path.join(base, "site.json")
    if not os.path.isfile(site_path):
        _die("目录模式需要 site.json（放在 %s）" % base)
    with open(site_path, encoding="utf-8") as f:
        site = json.load(f)

    nav_root = os.path.join(base, "nav")
    if not os.path.isdir(nav_root):
        _die("目录模式需要 nav/ 目录（放在 %s）" % base)

    nav, pages = [], {}
    for dname in sorted(os.listdir(nav_root)):
        dpath = os.path.join(nav_root, dname)
        if not os.path.isdir(dpath) or dname.startswith("."):
            continue
        gpath = os.path.join(dpath, "_group.json")
        if not os.path.isfile(gpath):
            _die("分类目录缺 _group.json：%s" % dpath)
        with open(gpath, encoding="utf-8") as f:
            g = json.load(f)
        label = dname.split("-", 1)[-1]
        gid = g.get("id") or label
        item = {"id": gid, "name": g.get("name") or label, "q": g.get("q", "")}

        if g.get("page"):
            pid = g["page"]
            ppath = os.path.join(dpath, pid + ".json")
            if not os.path.isfile(ppath):
                _die("%s/_group.json 指向的 %s.json 不存在" % (dname, pid))
            with open(ppath, encoding="utf-8") as f:
                pages[pid] = json.load(f)
            item["page"] = pid
        else:
            found = []
            for fname in sorted(os.listdir(dpath)):
                if not fname.endswith(".json") or fname.startswith("_"):
                    continue
                pid = fname[:-5]
                with open(os.path.join(dpath, fname), encoding="utf-8") as f:
                    pages[pid] = json.load(f)
                found.append(pid)
            if not found:
                _die("分类目录下没有页面文件：%s" % dpath)
            # _group.json 的 order 可显式定序；缺省按文件名
            order = g.get("order")
            if order:
                missing = [x for x in order if x not in found]
                if missing:
                    _die("%s/_group.json 的 order 指向不存在的页面：%s" % (dname, ", ".join(missing)))
                extra = [x for x in found if x not in order]
                found = list(order) + extra
            item["children"] = [{"id": pid, "page": pid} for pid in found]
        nav.append(item)

    if not nav:
        _die("nav/ 下没有任何分类目录")
    site["nav"] = nav
    site["pages"] = pages
    return base, site, pages


def page_ids(site):
    """按 nav 顺序拍平出页面 id。"""
    out = []
    for g in site.get("nav", []):
        for k in (g.get("children") or [g]):
            pid = k.get("page") or k.get("id")
            if pid and pid not in out:
                out.append(pid)
    return out


def write_bundle(site, pages, out_path):
    """把目录树合成运行时用的单文件 config（浏览器无法列目录，必须有这一步）。

    先写临时文件再原子替换：写一半失败时不会留下半截 JSON 把运行时打挂。
    """
    payload = dict(site)
    payload["pages"] = pages
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, out_path)
    return out_path
