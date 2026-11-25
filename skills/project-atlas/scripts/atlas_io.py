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

    def scan(dpath, dname):
        """一个目录 = 一个分组节点；子目录递归，目录内 *.json = 该分组的页面。"""
        gpath = os.path.join(dpath, "_group.json")
        if not os.path.isfile(gpath):
            _die("分组目录缺 _group.json：%s" % dpath)
        with open(gpath, encoding="utf-8") as f:
            g = json.load(f)
        label = dname.split("-", 1)[-1] if "-" in dname else dname
        item = {"id": g.get("id") or label, "name": g.get("name") or label, "q": g.get("q", "")}

        own_pages = []
        if g.get("page"):
            own_pages.append(g["page"])
        for fname in sorted(os.listdir(dpath)):
            if fname.endswith(".json") and not fname.startswith("_"):
                pid = fname[:-5]
                if pid not in own_pages:
                    own_pages.append(pid)
        for pid in own_pages:
            ppath = os.path.join(dpath, pid + ".json")
            if not os.path.isfile(ppath):
                _die("%s/_group.json 指向的 %s.json 不存在" % (dname, pid))
            with open(ppath, encoding="utf-8") as f:
                pages[pid] = json.load(f)

        child_dirs = [d for d in sorted(os.listdir(dpath))
                      if os.path.isdir(os.path.join(dpath, d)) and not d.startswith(".")]

        # 只有「_group.json 显式写了 page」才压平成"分类即页面"；
        # 目录里放页面文件 = 分组 + 页面，不能因为只有一个页面就把层级吃掉
        if g.get("page") and not child_dirs and len(own_pages) == 1:
            item["page"] = own_pages[0]
            return item

        childs = [{"id": pid, "page": pid} for pid in own_pages]
        for sub in child_dirs:
            childs.append(scan(os.path.join(dpath, sub), sub))
        if not childs:
            _die("目录下既没有页面文件也没有子目录：%s" % dpath)
        order = g.get("order")
        if order:
            known = {c.get("page") or c.get("id") for c in childs}
            missing = [x for x in order if x not in known]
            if missing:
                _die("%s/_group.json 的 order 指向不存在的节点：%s" % (dname, ", ".join(missing)))
            childs.sort(key=lambda c: order.index(c.get("page") or c.get("id"))
                        if (c.get("page") or c.get("id")) in order else len(order))
        item["children"] = childs
        return item

    for dname in sorted(os.listdir(nav_root)):
        dpath = os.path.join(nav_root, dname)
        if not os.path.isdir(dpath) or dname.startswith("."):
            continue
        nav.append(scan(dpath, dname))

    if not nav:
        _die("nav/ 下没有任何分类目录")
    site["nav"] = nav
    site["pages"] = pages
    return base, site, pages


def page_ids(site):
    """按 nav 顺序递归拍平出页面 id（层级不限）。"""
    out = []

    def walk(items):
        for it in items or []:
            if not isinstance(it, dict):
                continue
            pid = it.get("page")
            if pid and pid not in out:
                out.append(pid)
            kids = it.get("children")
            if isinstance(kids, list) and kids:
                walk(kids)

    walk(site.get("nav") or [])
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
