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
        # 目录里只有运行时配置（单文件模式的产物）→ 按单文件读，免得必须先造一个 site.json
        bundle = os.path.join(base, "atlas.config.json")
        if os.path.isfile(bundle):
            with open(bundle, encoding="utf-8") as f:
                cfg = json.load(f)
            if not isinstance(cfg.get("nav"), list):
                _die("%s 缺少 nav 数组" % bundle)
            return base, cfg, cfg.get("pages") or {}
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


# ── 归一化层：一页多图 / 外部节点 ─────────────────────────────
# 框架（framework/index.html 的 figsOf / externalOf）与四个脚本必须同一口径，
# 否则会出现「浏览器能看、导出坏」。改约定只改这里。


def figures_of(page, pid, views_dir="views"):
    """把 pages[pid] 归一化成 figure 列表。

    figures 为数组时逐项取；缺省把旧的 svg/type/points 视为单图（向后兼容）。
    图源默认路径：第 1 张 views/<pid>.svg，其后 views/<pid>-<n>.svg。
    """
    page = page or {}
    figs = page.get("figures")
    if isinstance(figs, list) and figs:
        out = []
        for i, f in enumerate(figs):
            f = f or {}
            out.append({
                "id": f.get("id") or ("f%d" % (i + 1)),
                "name": f.get("name") or "",
                # 页级 type / interactive 作为兜底继承：单图改造成多图时不会静默丢掉
                "type": f.get("type") or page.get("type") or "",
                "q": f.get("q") or "",
                "svg": f.get("svg") or ("%s/%s-%d.svg" % (views_dir, pid, i + 1)),
                "points": f.get("points") or [],
                "interactive": f.get("interactive")
                               or ((page.get("interactive") or "") if i == 0 else ""),
            })
        return out
    return [{
        "id": "f1",
        "name": "",
        "type": page.get("type") or "",
        "q": "",
        "svg": page.get("svg") or ("%s/%s.svg" % (views_dir, pid)),
        "points": page.get("points") or [],
        "interactive": page.get("interactive") or "",
    }]


def fig_key(pid, fig_id, idx):
    """图源 template 的 key：第 1 张沿用 pid（兼容既有 tpl_pattern），其后 pid::figId。"""
    return pid if idx == 0 else ("%s::%s" % (pid, fig_id))


def resolve_code(page, site=None):
    """合并 code[] 与站点级 externals 字典，页面级字段优先。

    site.externals = { "<外部 id>": { owner, contract, returnsTo, returnForm } }
    页面里只写 { "id": "<外部 id>", "external": true } 即可引用，避免多页重复填写而漂移。
    """
    book = ((site or {}).get("externals") or {})
    out = []
    for c in ((page or {}).get("code") or []):
        if c.get("external") and c.get("id") in book:
            merged = dict(book[c["id"]])
            merged.update({k: v for k, v in c.items() if v not in (None, "")})
            merged["external"] = True
            out.append(merged)
        else:
            out.append(c)
    return out


def coded_of(page, site=None):
    """有源码的条目（外部节点天然没有 file，不在其中）。"""
    return [c for c in resolve_code(page, site) if c.get("file")]


def merge_id_links(links):
    """同一条标识符可能分多段流转（A→B→C→D），合成一行显示完整路径，避免同一个键列三遍。

    口径与 framework/index.html 的 mergeIdLinks 一致。
    """
    out, by = [], {}
    for l in links:
        if l["kind"] != "identifier":
            continue
        k = l["carries"] or "—"
        m = by.get(k)
        if m is None:
            m = {"key": k, "path": [l["from"], l["to"]], "branches": [],
                 "shape": l["shape"], "storedAt": l["storedAt"],
                 "cardinality": l["cardinality"], "note": l["note"]}
            by[k] = m
            out.append(m)
        else:
            if m["path"][-1] == l["from"]:
                m["path"].append(l["to"])
            else:
                m["branches"].append("%s → %s" % (l["from"], l["to"]))
            m["shape"] = m["shape"] or l["shape"]
            m["storedAt"] = m["storedAt"] or l["storedAt"]
            m["cardinality"] = m["cardinality"] or l["cardinality"]
            m["note"] = m["note"] or l["note"]
    return out


def link_path(m):
    s = " → ".join(m["path"])
    if m["branches"]:
        s += "；另：" + "、".join(m["branches"])
    return s


def links_of(page):
    """衔接关系：节点之间传的是什么、靠什么标识符对上。

    kind: identifier（标识符，后续操作靠它定位）/ event（事件、载荷）/ status（只回成功失败）/ none
    只有 identifier 是"衔接键"，其余不构成下次操作的入口。
    """
    out = []
    for l in ((page or {}).get("links") or []):
        if not isinstance(l, dict):
            continue
        out.append({
            "from": l.get("from") or "",
            "to": l.get("to") or "",
            "carries": l.get("carries") or "",
            "kind": l.get("kind") or "event",
            "shape": l.get("shape") or "",
            "storedAt": l.get("storedAt") or "",
            "cardinality": l.get("cardinality") or "",
            "note": l.get("note") or "",
        })
    return out


def externals_of(page, site=None):
    """外部服务条目：有归属与契约、没有源码。"""
    return [c for c in resolve_code(page, site) if c.get("external")]


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
