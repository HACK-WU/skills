#!/usr/bin/env python3
"""图源体检：SVG 是否「自包含到能独立渲染」——在装配/构建之前把黑块、空白图挡下来。

为什么必须查（框架的硬约束）：
    框架用 Shadow DOM 挂载图源（framework/index.html 的 attachShadow），SVG 自带的
    <style> 不外泄、壳层样式也进不去。所以图源必须自带样式；只写 class="c-backend"
    却不带对应规则时，浏览器按 SVG 默认 fill:black 渲染——节点退化成黑块。
    产物仍是合法 SVG，构建脚本不报错、体积正常、节点也能点，**只有人眼看得见**。
    同理：缺 viewBox 时框架剥掉 width/height 后无法缩放；缺 xmlns 时单独打开不渲染。

用法：
    python3 check_svg.py <图集目录>                 # 体检配置引用的全部图源
    python3 check_svg.py views/ *.svg               # 体检任意文件/目录
    python3 check_svg.py views/ --fix-style         # 从同批「主流样式块」补全缺失样式
    python3 check_svg.py views/ --json              # 机器可读

退出码：0 无阻断（可能有 warning）；1 有 error；2 输入错误。
"""
import argparse
import hashlib
import json
import os
import re
import sys

STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S | re.I)
CLASS_ATTR = re.compile(r"""\sclass\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
CLASS_RULE = re.compile(r"\.(-?[A-Za-z_][\w-]*)")
ATTR_CLASS_RULE = re.compile(r"""\[\s*class\s*[~|^$*]?=\s*["']([^"']+)["']""", re.I)
TAG = re.compile(r"""<(/?)([A-Za-z][\w:.-]*)((?:"[^"]*"|'[^']*'|[^>"'])*)(/?)>""", re.S)
ATTR = re.compile(r"""([A-Za-z_][\w:.-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>/]+))""")
VIEWBOX = re.compile(r"""\bviewBox\s*=\s*["']([^"']+)["']""", re.I)
XMLNS = re.compile(r"""\bxmlns\s*=\s*["']http://www\.w3\.org/2000/svg["']""", re.I)
EXTERNAL = re.compile(r"""(?:href|xlink:href|src)\s*=\s*["'](https?://[^"']+)["']""", re.I)
CSS_IMPORT = re.compile(r"@import\s+(?:url\()?\s*[\"']?\s*(?:https?:)?//", re.I)
NODE_ID = re.compile(r'data-node-id="([^"]+)"')

SHAPES = {"rect", "circle", "ellipse", "polygon", "polyline", "path"}
# 框架在 Shadow DOM 里自带的类（框架加边标签用），图源可以直接用，不算缺样式
SHELL_CLASSES = {"lk-tag", "lk-id", "lk-ev"}
NO_RENDER = {"defs", "marker", "clippath", "symbol", "pattern", "mask", "filter",
             "lineargradient", "radialgradient", "style", "title", "desc", "metadata"}

ERROR, WARN = "error", "warn"


def _attrs_of(raw):
    out = {}
    for a in ATTR.finditer(raw or ""):
        out[a.group(1).lower()] = a.group(2) or a.group(3) or a.group(4) or ""
    return out


def _style_fill(style):
    m = re.search(r"fill\s*:\s*([^;\"']+)", style or "", re.I)
    return m.group(1).strip() if m else ""


def _num(x, default=0.0):
    try:
        return float(str(x).replace("px", "").strip())
    except (TypeError, ValueError):
        return default


def _tags(text):
    """逐标签产出 (closing, tag, attrs_raw, self_closing)。

    自闭合判定不能只看最后的 `/>` 分组：属性段 `[^>"']*` 会把结尾的 `/` 一起吃进去，
    导致 `<rect ... />` 被当作开标签压栈、后面的 `</g>` 弹错层——继承链一乱，
    `shape-default-fill` 与 `blank-*` 都会误判。
    """
    for m in TAG.finditer(text):
        closing, tag, raw = m.group(1), (m.group(2) or "").lower(), m.group(3) or ""
        sc = bool(m.group(4)) or raw.rstrip().endswith("/")
        if sc:
            raw = raw.rstrip()[:-1]
        yield closing, tag, raw, sc


def _boxes(text):
    """粗估内容占用：rect 的框 + text 的锚点（用于判「大片空白」）。

    defs / marker 里的图形不渲染，必须排除；否则图例里的坐标会把 bbox 撑满，
    真正的"下半张空白"永远测不出来。
    """
    boxes, stack = [], []
    for closing, tag, raw, sc in _tags(text):
        if closing:
            if stack:
                stack.pop()
            continue
        a = _attrs_of(raw)
        hidden = (stack[-1] if stack else False) or tag in NO_RENDER
        if not hidden:
            if tag == "rect" and "width" in a and "height" in a:
                w, h = _num(a.get("width")), _num(a.get("height"))
                if w > 0 and h > 0:
                    boxes.append((_num(a.get("x")), _num(a.get("y")), w, h))
            elif tag in ("text", "circle", "ellipse"):
                boxes.append((_num(a.get("x")), _num(a.get("y")), 1, 1))
        if not sc:
            stack.append(hidden)
    return boxes


def inspect_svg(text, name="<svg>"):
    """返回 (issues, stats)。issues 条目：{level, code, msg, fix}。"""
    issues = []

    def add(level, code, msg, fix=""):
        issues.append({"level": level, "code": code, "msg": msg, "fix": fix})

    if not text or not re.search(r"<svg\b", text or "", re.I):
        add(ERROR, "not-svg", "内容里没有 <svg>，不是一个图源",
            "确认 figures[].svg 指向的确实是 SVG（不是 JSON / HTML）")
        return issues, {"name": name, "bytes": len((text or "").encode("utf-8"))}

    styles = STYLE_BLOCK.findall(text)
    style_text = "\n".join(styles)
    # 扫选择器前先抹掉 url(...)/字符串内容，否则 url(https://x/a.css) 里的 .css 会被当成 class
    selector_src = re.sub(r"url\([^)]*\)|[\"'][^\"']*[\"']", "", style_text)
    defined = set(CLASS_RULE.findall(selector_src))
    # 属性选择器写法 [class~="x"] 也算有规则——只认 .x 会把合法图源判成黑块
    defined |= set(ATTR_CLASS_RULE.findall(style_text))

    # 每个 class token 的元素是否都自带 fill/stroke（自带的话即使没规则也不会黑）
    used, token_selfsufficient = set(), {}
    for closing, tag, raw, _sc in _tags(text):
        if closing:
            continue
        a = _attrs_of(raw)
        cls = a.get("class") or ""
        if not cls.strip():
            continue
        has_paint = ("fill" in a) or ("stroke" in a) or \
                    bool(re.search(r"(?:fill|stroke)\s*:", a.get("style") or "", re.I))
        for tok in cls.split():
            used.add(tok)
            token_selfsufficient[tok] = token_selfsufficient.get(tok, True) and has_paint

    missing = sorted(used - defined - SHELL_CLASSES)
    hard = [t for t in missing if not token_selfsufficient.get(t, False)]
    soft = [t for t in missing if token_selfsufficient.get(t, False)]
    if hard:
        head = ", ".join(hard[:6]) + (" …" if len(hard) > 6 else "")
        add(ERROR, "class-undefined",
            "%d 个 class 没有对应样式规则（%s）——SVG 默认 fill:black，这些节点会渲染成黑块"
            % (len(hard), head),
            "图源必须自带 <style>（框架 Shadow DOM 挂载，壳层样式进不去）："
            "用 archify 重新 deliver 导出；或 check_svg.py <dir> --fix-style 从同批主流样式块补全")
    if soft:
        add(WARN, "class-unused-rule",
            "%d 个 class 没有对应规则（%s），但这些元素自带 fill/stroke，不会黑——样式不生效而已"
            % (len(soft), ", ".join(soft[:6])),
            "确认这些 class 是否本来该有规则（多半是样式块被裁掉了）")

    # 形状既无 fill 又无 class/style，祖先也没有 fill/class → 默认黑。
    # 祖先带 class 时其 fill 解析不到，按"未知"放过：宁可漏报也不制造噪音（黑块主判据是 class-undefined）。
    black, stack = [], []
    for closing, tag, raw, sc in _tags(text):
        if closing:
            if stack:
                stack.pop()
            continue
        a = _attrs_of(raw)
        parent = stack[-1] if stack else None
        hidden = (parent["hidden"] if parent else False) or tag in NO_RENDER
        own = ("fill" in a) or ("class" in a) or ("fill" in (a.get("style") or "").lower())
        inherited_fill = (parent["fill"] if parent else "") or _style_fill(a.get("style"))
        styled_parent = bool(parent["styled"]) if parent else False
        if tag in SHAPES and not hidden and not own and not inherited_fill and not styled_parent:
            black.append(tag)
        if not sc:
            stack.append({"fill": (a.get("fill") or _style_fill(a.get("style")) or ""),
                          "styled": styled_parent or ("class" in a),
                          "hidden": hidden})
    if black:
        add(WARN, "shape-default-fill",
            "%d 个形状元素没有 fill / class / style（%s）——按默认黑色填充，多半也是黑块"
            % (len(black), ", ".join(sorted(set(black)))),
            "补 fill 或 class；只描边的元素显式写 fill=\"none\"")

    vb = VIEWBOX.search(text)
    if not vb:
        add(ERROR, "no-viewbox",
            "缺 viewBox：框架会剥掉 width/height 让图跟着容器缩放，没有 viewBox 时比例丢失（可能被压扁/撑满）",
            "在 <svg> 上补 viewBox=\"0 0 宽 高\"")
    if not XMLNS.search(text):
        add(WARN, "no-xmlns",
            "缺 xmlns=\"http://www.w3.org/2000/svg\"：内联进 HTML 能显示，"
            "但单独作为 .svg 打开或导出 Markdown 图包时不渲染",
            "补 xmlns（export_markdown.py 会自动补，装配链路仍建议补齐）")

    ext = sorted({u for u in EXTERNAL.findall(text) if "www.w3.org" not in u})
    if ext:
        add(ERROR, "external-resource", "引用外链资源（离线不可用）：%s" % ", ".join(ext[:3]),
            "内联或用 base64；字体走 @font-face")
    if CSS_IMPORT.search(style_text):
        add(ERROR, "css-import", "<style> 里有 @import 外链样式：Shadow DOM 内加载不可靠且离线失败",
            "把规则内联进 <style>")
    if re.search(r"<script\b", text, re.I):
        add(WARN, "inline-script", "图源含 <script>：Shadow DOM 内会执行，离线图集不应依赖脚本",
            "改为纯静态图源")

    # ── 内容密度：空白图不是构建问题，但必须有可量化的描述 ──
    nodes = set(NODE_ID.findall(text))
    boxes = _boxes(text)
    stats = {
        "name": name,
        "bytes": len(text.encode("utf-8")),
        "nodes": len(nodes),
        "shapes": len(re.findall(r"<(?:rect|path|circle|ellipse|polygon|polyline)\b", text, re.I)),
        "texts": len(re.findall(r"<text\b", text, re.I)),
        "styles": len(styles),
        "style_sha": hashlib.sha1(style_text.encode("utf-8")).hexdigest()[:8] if style_text.strip() else "",
        "style_rules": len(defined),
        "viewBox": vb.group(1).strip() if vb else "",
        "fill_ratio": None,
        "blank_bottom": None,
    }
    if not nodes:
        add(WARN, "no-node-id",
            "图内没有任何 data-node-id：节点挂不上代码，读者点不开",
            "按约定给每个节点加 data-node-id（与 pages[].code[].id 同名）")
    elif len(nodes) <= 2:
        add(WARN, "sparse-graph",
            "图内只有 %d 个 data-node-id，内容偏少——先看图源 IR 是否只填了骨架，这不是构建问题"
            % len(nodes), "补全 IR 后重新出图；或把该页并进相邻视图")
    if vb and boxes:
        try:
            vx, vy, vw, vh = [_num(x) for x in re.split(r"[,\s]+", vb.group(1).strip())]
        except ValueError:
            vx = vy = 0.0
            vw = vh = 0.0
        if vw > 0 and vh > 0:
            x0 = min(b[0] for b in boxes)
            x1 = max(b[0] + b[2] for b in boxes)
            y0 = min(b[1] for b in boxes)
            y1 = max(b[1] + b[3] for b in boxes)
            stats["blank_bottom"] = round(max(0.0, (vy + vh - y1) / vh), 3)
            rects = [b for b in boxes if b[2] > 1 and b[3] > 1]
            if rects:
                covered = sum(b[2] * b[3] for b in rects)
                stats["fill_ratio"] = round(min(1.0, covered / (vw * vh)), 3)
            if len(boxes) >= 5:
                bottom = (vy + vh - y1) / vh
                right = (vx + vw - x1) / vw
                if bottom >= 0.45:
                    add(WARN, "blank-bottom",
                        "图幅下部约 %d%% 高度没有任何内容（viewBox 高 %.0f，内容到 %.0f）"
                        "——多为 IR 内容不足或画布画大了，不是构建问题"
                        % (bottom * 100, vh, y1 - vy), "补 IR 内容或收小 viewBox；有意留白可忽略")
                if right >= 0.45:
                    add(WARN, "blank-right",
                        "图幅右侧约 %d%% 宽度没有任何内容（viewBox 宽 %.0f，内容到 %.0f）"
                        % (right * 100, vw, x1 - vx), "收小 viewBox 或补内容")
    return issues, stats


# ── 批量 ──────────────────────────────────────────────


def svg_paths(targets):
    """把「目录 / 文件」展开成 (svg 绝对路径列表, base_dir)。目录优先按配置取，取不到再扫盘。"""
    paths, base = [], None
    for t in targets:
        p = os.path.abspath(t)
        if os.path.isdir(p):
            base = base or p
            got = []
            # 只有确实是图集目录才走配置解析；否则直接扫盘，避免 atlas_io 打无关报错
            if os.path.isfile(os.path.join(p, "site.json")) or \
                    os.path.isfile(os.path.join(p, "atlas.config.json")):
                try:
                    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                    from atlas_io import load_atlas, page_ids, figures_of
                    b, cfg, pages = load_atlas(p)
                    base = b
                    views_dir = cfg.get("views_dir") or "views"
                    for pid in page_ids(cfg):
                        for f in figures_of(pages.get(pid), pid, views_dir):
                            rel = f["svg"]
                            got.append(rel if os.path.isabs(rel) else os.path.join(b, rel))
                except SystemExit:
                    got = []
            if not got:
                for root, _d, files in os.walk(p):
                    got += [os.path.join(root, f) for f in sorted(files) if f.lower().endswith(".svg")]
            paths += got
        elif os.path.isfile(p):
            paths.append(p)
        else:
            print("找不到：%s" % t, file=sys.stderr)
            sys.exit(2)
    seen, uniq = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq, base


def run(paths, quiet_ok=False):
    """体检一批文件，返回 (results, errors, warns)。results: [(path, issues, stats)]"""
    results, nerr, nwarn = [], 0, 0
    for p in paths:
        name = os.path.basename(p)
        if not os.path.isfile(p):
            issues = [{"level": ERROR, "code": "missing", "msg": "文件不存在", "fix": "改 figures[].svg"}]
            stats = {"name": name}
        else:
            with open(p, encoding="utf-8", errors="replace") as f:
                text = f.read()
            issues, stats = inspect_svg(text, name)
        results.append((p, issues, stats))
        nerr += sum(1 for i in issues if i["level"] == ERROR)
        nwarn += sum(1 for i in issues if i["level"] == WARN)
    return results, nerr, nwarn


def report(results, quiet_ok=False):
    for path, issues, st in results:
        name = st.get("name") or os.path.basename(path)
        detail = []
        if st.get("nodes") is not None:
            detail.append("%d 节点" % st["nodes"])
        if st.get("styles"):
            detail.append("%d 个 style 块 / %d 条 class 规则（sha %s）"
                          % (st["styles"], st["style_rules"], st["style_sha"]))
        else:
            detail.append("无 <style>")
        if st.get("viewBox"):
            detail.append("viewBox %s" % st["viewBox"])
        if st.get("fill_ratio") is not None:
            detail.append("形状填充率 %.0f%%" % (st["fill_ratio"] * 100))
        if st.get("bytes"):
            detail.append("%.0f KB" % (st["bytes"] / 1024))
        bad = [i for i in issues if i["level"] == ERROR]
        mark = "✗" if bad else ("!" if issues else "✓")
        if issues or not quiet_ok:
            print("  %s %s　%s" % (mark, name, " · ".join(detail)))
        for it in issues:
            print("      %s [%s] %s" % ("✗" if it["level"] == ERROR else "!", it["code"], it["msg"]))
            if it.get("fix"):
                print("        → " + it["fix"])


# ── 样式补全（确定性修复：只做「整块缺失」这一种）────────────


def _style_of(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    blocks = STYLE_BLOCK.findall(text)
    body = "\n".join(blocks).strip()
    return text, body, set(CLASS_RULE.findall(body))


def fix_style(paths):
    """从同批「主流样式块」注入到缺样式或 class 无规则的图源。

    只处理两类可确定性修复的情况：① 完全没有 <style> ② 有 <style> 但整块就是主流块缺的那份。
    已有 <style> 但规则不全的，只报不修（改规则要懂图，交回人/archify）。
    """
    donors = {}      # sha -> {"body":..., "files":[...], "classes":set()}
    for p in paths:
        if not os.path.isfile(p):
            continue
        _text, body, classes = _style_of(p)
        if not body:
            continue
        sha = hashlib.sha1(body.encode("utf-8")).hexdigest()[:8]
        d = donors.setdefault(sha, {"body": body, "files": [], "classes": set(), "sha": sha})
        d["files"].append(os.path.basename(p))
        d["classes"] |= classes
    if not donors:
        print("没有可用作模板的样式块：同批文件里没有任何 <style>", file=sys.stderr)
        return 1
    ranked = sorted(donors.values(), key=lambda d: (-len(d["files"]), -len(d["classes"])))
    fixed, skipped = [], []
    for p in paths:
        if not os.path.isfile(p):
            continue
        text, body, own = _style_of(p)
        used = set()
        for m in CLASS_ATTR.finditer(text):
            used |= {t for t in (m.group(1) or m.group(2) or "").split() if t}
        missing = used - own
        if not missing:
            continue
        if body.strip():
            skipped.append((p, "已有 <style> 但缺 %d 条规则（%s）——不自动改，需重新导出"
                            % (len(missing), ", ".join(sorted(missing)[:4]))))
            continue
        donor = next((d for d in ranked if missing <= d["classes"]), None)
        if not donor:
            skipped.append((p, "%d 个 class 在同批样式块里都找不到定义（%s）——需重新出图"
                            % (len(missing), ", ".join(sorted(missing)[:4]))))
            continue
        m = re.search(r"<svg\b[^>]*>", text, re.I)
        if not m:
            skipped.append((p, "没有 <svg> 开标签"))
            continue
        injected = text[:m.end()] + "\n<style>\n" + donor["body"] + "\n</style>" + text[m.end():]
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(injected)
        os.replace(tmp, p)
        src = donor["files"][0] if donor["files"] else "?"
        fixed.append((p, "整块注入（含 %d 条 class 规则；样式块来自 %s，同批 %d 份一致，sha %s）"
                      % (len(donor["classes"]), src, len(donor["files"]), donor["sha"])))
    for p, msg in fixed:
        print("  ✓ 已补样式 %s：%s" % (os.path.basename(p), msg))
    sys.stdout.flush()
    for p, msg in skipped:
        print("  ! 未处理 %s：%s" % (os.path.basename(p), msg), file=sys.stderr)
    return 0 if fixed or not skipped else 1


def main():
    ap = argparse.ArgumentParser(description="图源体检：SVG 是否自包含（防黑块 / 空白图 / 不可缩放）")
    ap.add_argument("targets", nargs="+", help="图集目录、views 目录或若干 .svg")
    ap.add_argument("--fix-style", action="store_true",
                    help="从同批主流样式块补全缺失的 <style>（只处理整块缺失）")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    ap.add_argument("--quiet-ok", action="store_true", help="健康文件不打印（只列问题）")
    args = ap.parse_args()

    paths, _base = svg_paths(args.targets)
    if not paths:
        print("没有找到任何 SVG", file=sys.stderr)
        return 2

    if args.fix_style:
        fix_style(paths)

    results, nerr, nwarn = run(paths)
    if args.json:
        print(json.dumps([{"path": os.path.basename(p), "stats": st, "issues": iss}
                          for p, iss, st in results], ensure_ascii=False, indent=1))
    else:
        print("图源体检（%d 个文件）" % len(results))
        report(results, args.quiet_ok)
        print()
        sys.stdout.flush()
        if nerr:
            print("体检失败：%d error / %d warning（有 error 不要进入装配：产物能生成，但是黑块/残图）"
                  % (nerr, nwarn), file=sys.stderr)
        else:
            print("体检通过：0 error / %d warning" % nwarn)
    return 1 if nerr else 0


if __name__ == "__main__":
    sys.exit(main())
