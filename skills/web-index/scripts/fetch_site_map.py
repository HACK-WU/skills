#!/usr/bin/env python3
"""从站点的一手地图提取候选链接，供 web-index 技能生成本地网页索引。

优先链：llms.txt > sitemap.xml（含 sitemapindex 递归，最深 2 层）> --sitemap 指定地址
只用 Python 3 标准库，零依赖；单次请求、串行拉取，不做并发重试。

退出码：
  0  成功（输出候选链接）
  2  无地图可用 —— 交给 AI 从页面导航人工提取
  3  网络失败 / 超时 / 非预期响应 / 站点明确拒绝（403、429、robots 全站禁止）—— 可换入口页重试一次，被拒则停
  4  有地图但过滤后为空 —— 多半是 --scope 前缀写错，请放宽后重试
  5  入参非法（缺 scheme/host、--max 超硬上限）—— 修正参数后重跑，重试无意义

用法：
  python3 fetch_site_map.py https://example.com/docs --scope /docs --exclude /blog --max 300
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 仅类型检查期可见；运行时不依赖 dict[...]（保持 Python 3.8 兼容）
    Item = dict[str, str]  # 一条候选链接：url / title / desc / section / source

USER_AGENT = "web-index/1.0 (+local site map fetch; single request, no crawling)"
HARD_MAX = 1000
MAX_SITEMAP_DEPTH = 2
MAX_CHILD_SITEMAPS = 20

LINK_RE = re.compile(r"^\s*[-*]\s+\[([^\]]+)\]\(([^)\s]+)\)\s*(?:[:：]\s*(.*))?$")
HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")


class FetchError(Exception):
    """网络层失败，统一由主流程转成退出码 3。"""


def fetch(url: str, timeout: int) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            raise FetchError(f"{exc.code} {url} —— 站点拒绝，不再重试（也不会伪造 UA 绕过）")
        raise FetchError(f"HTTP {exc.code} {url}")
    except (urllib.error.URLError, OSError) as exc:
        raise FetchError(f"请求失败 {url}：{exc}")


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def abs_url(base: str, link: str) -> str:
    joined = urllib.parse.urljoin(base, link.strip())
    parts = urllib.parse.urlsplit(joined)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


# ---------- 地图来源 ----------

def parse_llms(url: str, timeout: int) -> list[Item]:
    body = fetch(url, timeout)
    items: list[Item] = []
    section = ""
    for line in body.splitlines():
        header = HEADER_RE.match(line)
        if header:
            section = header.group(2).strip()
            continue
        link = LINK_RE.match(line)
        if link:
            items.append(
                {
                    "url": abs_url(url, link.group(2)),
                    "title": link.group(1).strip(),
                    "desc": (link.group(3) or "").strip(),
                    "section": section,
                    "source": "llms.txt",
                }
            )
    return items


def try_llms_txt(base: str, start_path: str, timeout: int, verbose: bool,
                 forced_sub: str = "") -> list[Item]:
    """抓根 llms.txt；若是分层索引（Section indexes），自动跟到命中的那张子索引。

    有些站点（实测 langchain docs）的根 llms.txt 只列出各子分区的 llms.txt 指针，
    直接采根会得到一堆 `.../llms.txt` 废条目，必须再下一层才是真正的页面清单。
    """
    root_url = base + "/llms.txt"
    try:
        items = parse_llms(root_url, timeout)
    except FetchError as exc:
        log(verbose, f"llms.txt 未命中：{exc}")
        return []
    log(verbose, f"llms.txt 命中 {len(items)} 条（{root_url}）")

    children = [it for it in items if it["url"].endswith("/llms.txt")]
    if not children:
        return items

    if forced_sub:
        target = base + forced_sub if forced_sub.startswith("/") else f"{base}/{forced_sub}"
        if not target.endswith("/llms.txt"):
            target = target.rstrip("/") + "/llms.txt"
    else:
        target, best = "", ""
        for child in children:
            cpath = urllib.parse.urlsplit(child["url"]).path[: -len("/llms.txt")]
            if start_path.startswith(cpath) and len(cpath) > len(best):
                target, best = child["url"], cpath

    if not target:
        log(verbose, "根索引是分层索引但起点不在任何分区内，根内容无页面可用 → 交下一级数据源")
        return []

    log(verbose, f"检测到分层索引，跟随子索引 {target}")
    try:
        sub_items = parse_llms(target, timeout)
    except FetchError as exc:
        log(verbose, f"子索引取用失败：{exc}，退回根索引")
        return items
    log(verbose, f"子索引命中 {len(sub_items)} 条（{target}）")
    return sub_items


def parse_sitemap(url: str, timeout: int, depth: int, verbose: bool) -> list[Item]:
    body = fetch(url, timeout)
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise FetchError(f"地图解析失败 {url}：{exc}")

    tag = strip_ns(root.tag)
    items: list[Item] = []

    if tag == "sitemapindex":
        if depth >= MAX_SITEMAP_DEPTH:
            log(verbose, "子地图递归已达上限，停止展开")
            return items
        locs: list[str] = []
        for child in list(root)[:MAX_CHILD_SITEMAPS]:
            for node in child:
                if strip_ns(node.tag) == "loc" and node.text:
                    locs.append(node.text.strip())
        if len(list(root)) > MAX_CHILD_SITEMAPS:
            log(verbose, f"子地图超过 {MAX_CHILD_SITEMAPS} 个，只取前 {MAX_CHILD_SITEMAPS} 个")
        for loc in locs:
            items.extend(parse_sitemap(loc, timeout, depth + 1, verbose))
        return items

    if tag != "urlset":
        raise FetchError(f"未知地图格式 {url}（根元素 <{tag}>）")

    for entry in root:
        if strip_ns(entry.tag) != "url":
            continue
        loc_text = ""
        for node in entry:
            if strip_ns(node.tag) == "loc" and node.text:
                loc_text = node.text.strip()
                break
        if not loc_text:
            continue
        parts = urllib.parse.urlsplit(loc_text)
        items.append(
            {
                "url": urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")),
                "title": "",
                "desc": "",
                "section": "",  # 由 section_from_path 在过滤后统一计算
                "source": "sitemap",
            }
        )
    log(verbose, f"sitemap 命中 {len(items)} 条（{url}）")
    return items


def section_from_path(path: str, scopes: list[str]) -> str:
    """分区建议：取 --scope 前缀**之后**的第一个路径段。

    sitemap 来源的站点常把全部页面放在同一个一级目录下（如 /docs/...），
    若直接取绝对路径首段会得到恒定的同一个值，导致分区失效、几百条挤进一个分区。
    """
    for scope in scopes:
        if path.startswith(scope):
            return pick_section([p for p in path[len(scope):].split("/") if p])
    return pick_section([p for p in path.split("/") if p])


def pick_section(segments: list[str]) -> str:
    """在去掉 scope 后的剩余路径段里挑分区。

    - 首段是目录 → 用它
    - 首段是叶子页（带扩展名）→ 用它所在的**父目录**；若它直接贴在 scope 下（无父目录），返回空串，
      表示"这个结构没有天然分区"，交给 AI 按页面名前缀人工归并——与其编 300 个每页一分区的假分区，不如诚实留空
    """
    if not segments:
        return ""
    first = segments[0]
    if "." in first:
        return segments[-2] if len(segments) >= 2 else ""
    return first


# ---------- robots ----------

def disallowed_paths(base: str, timeout: int, verbose: bool) -> list[str]:
    try:
        body = fetch(base + "/robots.txt", timeout)
    except FetchError as exc:
        log(verbose, f"robots.txt 不可读（视为允许）：{exc}")
        return []
    rules: list[str] = []
    applies = False
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            applies = agent == "*"
        elif applies and lower.startswith("disallow:"):
            value = line.split(":", 1)[1].strip()
            if value:
                rules.append(value)
    log(verbose, f"robots.txt 读到 {len(rules)} 条 Disallow")
    return rules


# ---------- 过滤与输出 ----------

def filter_items(items: list[Item], scopes: list[str], excludes: list[str],
                 disallow: list[str]) -> list[Item]:
    kept: list[Item] = []
    seen = set()
    for item in items:
        path = urllib.parse.urlsplit(item["url"]).path
        if scopes and not any(path.startswith(s) for s in scopes):
            continue
        if any(x in item["url"] for x in excludes):
            continue
        if any(path.startswith(r) for r in disallow):
            continue
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        kept.append(item)
    return kept


def render_md(items: list[Item]) -> str:
    lines = ["| # | URL | 来源 | 分区建议 | 标题 / 描述 |", "|---|-----|------|----------|-------------|"]
    for idx, item in enumerate(items, 1):
        note = " — ".join(p for p in [item["title"], item["desc"]] if p) or ""
        lines.append(f"| {idx} | {item['url']} | {item['source']} | {item['section']} | {note} |")
    return "\n".join(lines) + "\n"


def render_tsv(items: list[Item]) -> str:
    lines = ["url\tsource\tsection\tnote"]
    for item in items:
        note = " — ".join(p for p in [item["title"], item["desc"]] if p)
        lines.append(f"{item['url']}\t{item['source']}\t{item['section']}\t{note}")
    return "\n".join(lines) + "\n"


def log(verbose: bool, message: str) -> None:
    if verbose:
        print(f"[web-index] {message}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="提取站点一手地图中的候选链接")
    parser.add_argument("url", help="站点任意页面 URL（脚本自动取 scheme + host）")
    parser.add_argument("--scope", action="append", default=[], help="只保留路径以该前缀开头的条目，可重复")
    parser.add_argument("--exclude", action="append", default=[], help="丢弃含该子串的 URL，可重复")
    parser.add_argument("--max", type=int, default=300, help=f"条数上限（硬上限 {HARD_MAX}）")
    parser.add_argument("--sitemap", help="手工指定地图地址，跳过自动探测")
    parser.add_argument("--llms", default="",
                        help="手工指定要跟随的 llms.txt 子索引路径（如 /oss/python），"
                             "根索引是分层索引且自动匹配错误时使用")
    parser.add_argument("--out", help="输出文件，缺省打印到 stdout")
    parser.add_argument("--format", choices=["md", "tsv"], default="md")
    parser.add_argument("--timeout", type=int, default=15, help="单请求超时秒数，默认 15")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.max > HARD_MAX:
        print(f"[web-index] --max 超过硬上限 {HARD_MAX}，请收窄 scope 而不是抬高上限", file=sys.stderr)
        return 5

    parts = urllib.parse.urlsplit(args.url)
    if not parts.scheme or not parts.netloc:
        print("[web-index] 起始 URL 需包含 scheme 与 host，如 https://example.com/docs", file=sys.stderr)
        return 5
    base = f"{parts.scheme}://{parts.netloc}"

    try:
        items: list[Item] = []
        if args.sitemap:
            items = parse_sitemap(args.sitemap, args.timeout, 1, args.verbose)
            if not items:
                print(
                    "[web-index] 指定的 --sitemap 地址没有解析到任何条目（退出码 5）："
                    "多半是地址给错，请核对后重跑",
                    file=sys.stderr,
                )
                return 5
        else:
            items = try_llms_txt(base, parts.path, args.timeout, args.verbose, args.llms)
            if not items:
                try:
                    items = parse_sitemap(base + "/sitemap.xml", args.timeout, 1, args.verbose)
                except FetchError as exc:
                    log(args.verbose, f"sitemap.xml 未命中：{exc}")
        if not items:
            print(
                "[web-index] 未找到 llms.txt / sitemap.xml（退出码 2）："
                "请换用页面导航人工提取，或用 --sitemap 指定地址",
                file=sys.stderr,
            )
            return 2

        disallow = disallowed_paths(base, args.timeout, args.verbose)
        if "/" in disallow:
            print(
                "[web-index] robots.txt 禁止抓取该站全部路径（Disallow: /）—— 已停止，不绕过（退出码 3）",
                file=sys.stderr,
            )
            return 3
        items = filter_items(items, args.scope, args.exclude, disallow)
        for item in items:
            if item["source"] != "llms.txt":
                # llms.txt 自带站点维护的一级标题，信任它；sitemap 只能靠路径推断
                item["section"] = section_from_path(
                    urllib.parse.urlsplit(item["url"]).path, args.scope
                )
    except FetchError as exc:
        print(f"[web-index] {exc}", file=sys.stderr)
        return 3

    if not items:
        print("[web-index] 过滤后为空（退出码 4）：多半是 --scope 前缀写错，去掉或用更短前缀重试", file=sys.stderr)
        return 4

    truncated = False
    if len(items) > args.max:
        items = items[: args.max]
        truncated = True

    text = render_md(items) if args.format == "md" else render_tsv(items)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError as exc:
            print(
                f"[web-index] 写入 {args.out} 失败（退出码 5）：{exc}\n"
                f"[web-index] 提示：--out 的父目录需已存在（本仓库约定放 temp/，不存在先创建）",
                file=sys.stderr,
            )
            return 5
        print(f"[web-index] {len(items)} 条写入 {args.out}")
    else:
        print(text, end="")

    if truncated:
        print(f"[web-index] 已达 --max {args.max}，结果被截断：建议收窄 scope", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
