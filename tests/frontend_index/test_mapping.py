# -*- coding: utf-8 -*-
"""归属与映射的单元测试（本 skill 诚实性的核心）。

覆盖契约：深度即置信度（0/1/≥2）/ barrel 不扇出但按名字穿透 / 四类调用点
（direct、命名导入、命名空间导入、依赖注入）/ 外部 URL 剔除 / 多路由同文件去重 /
`--max-depth` 生效 / 无接口页面进 pending。
"""
from ._helpers import keys_of, page_by_route, rows_of

LAYERED = {
    "src/router/index.ts": """
        const P = () => import('../pages/p')
        export default [{ path: '/p', component: P }]
        """,
    # 页面自身直接调用（深度 0）→ 经命名导入的接口
    "src/pages/p.tsx": """
        import { listItems } from '../api/mod'
        import { Widget } from '../components/widget'

        export default function P() {
          listItems()
          return Widget()
        }
        """,
    "src/api/mod.ts": """
        export const listItems = request('GET', '/api/items')
        """,
    "src/api/request.ts": "export function request(m, u, d) { return [m, u, d] }\n",
    # 深度 1：页面直接依赖里发起
    "src/components/widget.tsx": """
        import { deep } from '../utils/deep'
        export const Widget = () => {
          fetch('/api/widget')
          return deep()
        }
        """,
    # 深度 2：依赖的依赖里发起
    "src/utils/deep.ts": "export const deep = () => fetch('/api/deep')\n",
}


def test_depth_semantics(make_project, scan_of):
    """深度 0/1/2 分别对应 🟢/🟡/🔵，且三者都出现在映射里（默认 maxDepth=2）。"""
    root = make_project(LAYERED)
    result = scan_of(root, include=["src/**"], routes=["src/router/**/*.ts"],
                     apiDirs=["src/api"])
    by_key = {}
    for r in rows_of(result, "src/pages/p.tsx"):
        by_key.setdefault(r["key"], r)
    assert by_key["/api/items"]["depth"] == 0
    assert by_key["/api/items"]["confidence"] == "🟢"
    assert by_key["/api/widget"]["depth"] == 1
    assert by_key["/api/widget"]["confidence"] == "🟡"
    assert by_key["/api/deep"]["depth"] == 2
    assert by_key["/api/deep"]["confidence"] == "🔵"


def test_max_depth_1_drops_indirect(make_project, scan_of):
    """`--max-depth 1` 时不应再出现 🔵 间接候选。"""
    root = make_project(LAYERED)
    result = scan_of(root, include=["src/**"], routes=["src/router/**/*.ts"],
                     apiDirs=["src/api"], maxDepth=1)
    depths = {r["depth"] for r in rows_of(result, "src/pages/p.tsx")}
    assert depths == {0, 1}, depths


def test_barrel_not_expanded_but_name_pierced(make_project, scan_of):
    """回归：barrel（`export * from` 集合）不参与归属遍历（否则页面"继承"整目录接口），
    但页面**点名导入**的符号仍要穿透 barrel 找到定义文件。"""
    root = make_project({
        "src/router/index.ts": """
            const P = () => import('../pages/p')
            export default [{ path: '/p', component: P }]
            """,
        "src/pages/p.tsx": """
            import { Widget } from '../components'
            export default function P() { return Widget() }
            """,
        "src/components/index.ts": """
            export * from './widget'
            export * from './other'
            export * from './third'
            """,
        "src/components/widget.tsx": "export const Widget = () => fetch('/api/widget')\n",
        "src/components/other.tsx": "export const Other = () => fetch('/api/other')\n",
        "src/components/third.tsx": "export const Third = () => fetch('/api/third')\n",
    })
    result = scan_of(root, include=["src/**"], routes=["src/router/**/*.ts"])
    keys = {k for _m, k in keys_of(result, "src/pages/p.tsx")}
    assert "/api/widget" in keys, "点名导入的符号必须穿透 barrel 命中"
    assert "/api/other" not in keys and "/api/third" not in keys, \
        "未导入的兄弟模块不应被 barrel 扇出进来"


def test_inject_variants_and_namespace(make_project, scan_of):
    """四类调用点：构造函数注入 / `inject()` 函数式注入（含 # 与 _ 前缀）/ 命名空间导入。"""
    root = make_project({
        "src/router/index.ts": """
            const P = () => import('../pages/p')
            export default [{ path: '/p', component: P }]
            """,
        "src/pages/p.ts": """
            import * as api from '../api/mod'
            import { Svc, Svc2 } from '../service/svc'
            import { inject } from '@angular/core'

            export class P {
              constructor(private svc: Svc) {}
              private readonly #svc2 = inject(Svc2)

              run() {
                this.svc.list()
                this.#svc2.detail()
                api.helper()
              }
            }
            """,
        "src/service/svc.ts": """
            import { inject } from '@angular/core'
            export class Svc {
              list() { return this.http.get('/api/svc/list') }
            }
            export class Svc2 {
              detail() { return this.http.get('/api/svc2/detail') }
            }
            """,
        "src/api/mod.ts": """
            export const helper = request('GET', '/api/helper')
            """,
        "src/api/request.ts": "export function request(m, u, d) { return [m, u, d] }\n",
    })
    result = scan_of(root, include=["src/**"], routes=["src/router/**/*.ts"],
                     apiDirs=["src/api"])
    vias = {r["via"] for r in rows_of(result, "src/pages/p.ts")}
    keys = {k for _m, k in keys_of(result, "src/pages/p.ts")}
    assert any(v.startswith("inject:svc.list") for v in vias), vias
    assert any(v.startswith("inject:") and "detail" in v for v in vias), vias
    assert any(v.startswith("ns:api.helper") for v in vias), vias
    assert "/api/svc/list" in keys and "/api/svc2/detail" in keys and "/api/helper" in keys


def test_external_url_excluded_from_mapping(make_project, scan_of):
    """外部绝对 URL（CDN / registry）不进业务映射表。"""
    root = make_project({
        "src/router/index.ts": """
            const P = () => import('../pages/p')
            export default [{ path: '/p', component: P }]
            """,
        "src/pages/p.ts": """
            export const P = () => {
              fetch('https://registry.npmjs.org/pkg')
              fetch('/api/local')
            }
            """,
    })
    result = scan_of(root, include=["src/**"], routes=["src/router/**/*.ts"])
    urls = {r["url"] for r in result.page_apis}
    assert "/api/local" in urls
    assert not [u for u in urls if "registry.npmjs.org" in u], "外部 URL 不应进入映射"


def test_multiple_routes_same_page_file_deduped(make_project, scan_of):
    """回归：同一页面文件被多条路由引用时，路由列表去重且不产生重复行。"""
    root = make_project({
        "src/router/index.ts": """
            const G = () => import('../pages/g')
            export default [
              { path: '/g', component: G },
              { path: '/g/new', component: G },
              { path: '/g/new', component: G },
            ]
            """,
        "src/pages/g.ts": "export const G = () => fetch('/api/g')\n",
    })
    result = scan_of(root, include=["src/**"], routes=["src/router/**/*.ts"])
    page = page_by_route(result, "/g")
    assert page is not None
    assert page["routes"] == ["/g", "/g/new"], page["routes"]     # 重复串已去重
    rows = rows_of(result, "src/pages/g.ts")
    assert len(rows) == 1, "同一页面文件的同一接口只应出一行"


def test_page_without_calls_goes_to_pending(make_project, scan_of):
    """无接口调用的页面要如实进 pending，而不是静默消失。"""
    root = make_project({
        "src/router/index.ts": """
            const L = () => import('../pages/layout')
            export default [{ path: '/layout', component: L }]
            """,
        "src/pages/layout.ts": "export const Layout = () => null\n",
    })
    result = scan_of(root, include=["src/**"], routes=["src/router/**/*.ts"])
    types = {p["type"] for p in result.pending}
    assert "页面无接口命中" in types
