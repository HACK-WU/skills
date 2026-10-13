# -*- coding: utf-8 -*-
"""路由（页面）提取的单元测试。

覆盖契约：配置式路由 / components 多组件 / 懒加载魔法注释 / loadChildren 一层路径组合 /
文件式路由兜底 / glob 的 `**/` 零层语义 —— 后两项是实测踩过坑后加的回归用例。
"""
from ._helpers import page_by_route

VUE_BASIC = {
    "src/router/index.ts": """
        const Dashboard = () => import('../pages/dashboard/dashboard.vue')
        const Users = () => import('../pages/users/users.vue')

        export default [
          { path: '/dashboard', name: 'dashboard', component: Dashboard },
          { path: '/users', name: 'users', component: Users },
        ]
        """,
    "src/pages/dashboard/dashboard.vue": "<template><div/></template>\n",
    "src/pages/users/users.vue": "<template><div/></template>\n",
}


def test_config_routes_basic(make_project, scan_of):
    root = make_project(VUE_BASIC)
    result = scan_of(root, routes=["src/router/**/*.ts"])
    assert result.stats["route_source"] == "config"
    assert {p["route"] for p in result.pages} == {"/dashboard", "/users"}
    dashboard = page_by_route(result, "/dashboard")
    assert dashboard["rel"] == "src/pages/dashboard/dashboard.vue"
    assert dashboard["file"]                                      # 组件已解析到真实文件


def test_components_prop_multiple(make_project, scan_of):
    """Vue 的 `components: { a: X, b: Y }` 应取默认/首个组件，不丢路由。"""
    root = make_project({
        "src/router/index.ts": """
            const Detail = () => import('../pages/detail/detail.vue')
            export default [
              { path: '/detail/:id', components: { default: Detail } },
            ]
            """,
        "src/pages/detail/detail.vue": "<template><div/></template>\n",
    })
    result = scan_of(root, routes=["src/router/**/*.ts"])
    page = page_by_route(result, "/detail/:id")
    assert page is not None and page["file"], "components 形态的路由必须解析出组件文件"


def test_magic_comment_lazy_import(make_project, scan_of):
    """回归：`import(/* webpackChunkName: 'X' */ '...')` 曾导致页面解析全灭。"""
    root = make_project({
        "src/router/index.ts": """
            const AlarmShield = () => import(/* webpackChunkName: 'AlarmShield' */ '../pages/alarm-shield/alarm-shield')
            export default [{ path: '/trace/alarm-shield', components: { noCache: AlarmShield } }]
            """,
        "src/pages/alarm-shield/alarm-shield.tsx": "export default function P() { return null }\n",
    })
    result = scan_of(root, routes=["src/router/**/*.ts"])
    page = page_by_route(result, "/trace/alarm-shield")
    assert page is not None and page["file"], "魔法注释不应阻断懒加载组件解析"


def test_glob_double_star_matches_top_level(make_project, scan_of):
    """回归：`src/app/**/*routing*.ts` 必须也能匹配顶层的 `src/app/app-routing.module.ts`。

    曾因 fnmatch 把 `**/` 当"至少一层目录"，导致顶层路由文件整体丢失。
    """
    root = make_project({
        "src/app/app-routing.module.ts": """
            const Home = () => import('./home/home.component')
            export const routes = [{ path: '/home', component: Home }]
            """,
        "src/app/home/home.component.ts": "export class HomeComponent {}\n",
    })
    result = scan_of(root, routes=["src/app/**/*routing*.ts"])
    assert result.stats["route_files"] == 1
    assert page_by_route(result, "/home") is not None


def test_load_children_composes_one_level(make_project, scan_of):
    """Angular `loadChildren`：子路由条目应拼上父路径（一层）。"""
    root = make_project({
        "src/app/app-routing.module.ts": """
            export const routes = [
              { path: 'auth', loadChildren: () => import('./auth/auth.module').then(m => m.AuthModule) },
            ]
            """,
        "src/app/auth/auth.module.ts": "export class AuthModule {}\n",
        "src/app/auth/auth-routing.module.ts": """
            const Login = () => import('./login/login.component')
            export const routes = [{ path: 'login', component: Login }]
            """,
        "src/app/auth/login/login.component.ts": "export class LoginComponent {}\n",
    })
    result = scan_of(root, routes=["src/app/**/*routing*.ts"])
    assert page_by_route(result, "auth/login") is not None, "子路由应被拼成 auth/login"
    assert page_by_route(result, "login") is None, "拼接后不应再保留裸相对路径条目"


def test_file_based_routes_fallback(make_project, scan_of):
    """无配置式路由时按文件式兜底（Next/Nuxt/uni-app 风格）。

    约定：`pages/index.vue` → `/`；`pages/user/list.vue` → `/user/list`；
    `pages/index/index.vue` → `/index`（目录式，不去尾）。
    """
    root = make_project({
        "src/pages/index.vue": "<template><div/></template>\n",
        "src/pages/user/list.vue": "<template><div/></template>\n",
        "src/pages/index/index.vue": "<template><div/></template>\n",
    })
    result = scan_of(root, include=["src/pages/**"])
    assert result.stats["route_source"] == "file-based"
    routes = {p["route"] for p in result.pages}
    assert routes == {"/", "/user/list", "/index"}, routes


def test_unresolved_route_marked_pending(make_project, scan_of):
    """组件解析不到时不留空行：页面文件为 None，但路由仍被登记。"""
    root = make_project({
        "src/router/index.ts": """
            export default [{ path: '/ghost', component: () => import('../pages/ghost/ghost.vue') }]
            """,
    })
    result = scan_of(root, routes=["src/router/**/*.ts"])
    page = page_by_route(result, "/ghost")
    assert page is not None
    assert page["file"] is None
