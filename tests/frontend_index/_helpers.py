# -*- coding: utf-8 -*-
"""frontend-index 测试的断言助手（纯函数，无需夹具）。

放独立模块而不是塞进 conftest：测试文件用 `from ._helpers import ...` 显式引入，
一眼能看出用了哪些助手（conftest 只放需要 pytest 生命周期管理的夹具）。
"""


def page_by_route(result, route):
    """取某路由对应的聚合页面条目（同一页面文件的多条路由已合并）。"""
    for page in getattr(result, "pages_agg", result.pages):
        if route in (page.get("routes") or []):
            return page
    return None


def rows_of(result, page_rel):
    """取某页面文件的所有映射行。"""
    return [r for r in result.page_apis if r["page_file"] == page_rel or r["page"] == page_rel]


def keys_of(result, page_rel):
    """某页面用到的接口 key 集合（method, key）。"""
    return {(r["method"], r["key"]) for r in rows_of(result, page_rel)}
