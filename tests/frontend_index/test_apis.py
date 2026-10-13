# -*- coding: utf-8 -*-
"""接口定义提取与 URL 归一化的单元测试。

覆盖契约：request 工厂 / http 类方法（含嵌套泛型）/ 类方法归属（含带 `{ } ;` 的参数表）/
箭头常量 / 跨文件常量表达式（`A + '/x'`）/ 动态 URL 标记 / query 去除。
其中「带花括号的参数表」「类名前缀」「前缀常量不被吞」都是实测踩坑后的回归用例。
"""
API_PROJECT = {
    "src/api/mod.ts": """
        import { request } from './request'
        import { API_PREFIX } from './const'

        export const listItems = request('GET', 'rest/v2/items/')
        export const createItem = request('POST', `${API_PREFIX}/items`)
        """,
    "src/api/const.ts": "export const API_PREFIX = '/api'\n",
    "src/api/request.ts": "export function request(method, url, data) { return [method, url, data] }\n",
    "src/service/user.service.ts": """
        import { HttpClient } from '@angular/common/http'
        import { API_PREFIX } from '../api/const'

        export class UserService {
          constructor(private http: HttpClient) {}

          getAdminUsers(params?: { userId?: string; take?: number }) {
            return this.http.get<IPagination<IUser>>(`${API_PREFIX}/admin/users`, { params })
          }

          deleteUser(id: string) {
            return this.http.delete<void>(`${API_PREFIX}/admin/users/${id}`)
          }

          search(keyword: string) {
            return this.http.get(`${API_PREFIX}/search?q=${keyword}`)
          }
        }
        """,
    "src/pages/home.ts": "export const home = () => fetch('/api/public/ping')\n",
}


def test_request_factory_definitions_are_raw(make_project, scan_of):
    """接口定义侧只登记**原始写法**（url_raw 不去插值）——求值发生在映射阶段。"""
    root = make_project(API_PROJECT)
    result = scan_of(root, include=["src/api/**", "src/service/**", "src/pages/**"],
                     apiDirs=["src/api"])
    got = {(x["method"], x["symbol"]) for x in result.api_defs}
    assert ("GET", "listItems") in got
    assert ("POST", "createItem") in got
    by_symbol = {x["symbol"]: x for x in result.api_defs}
    assert by_symbol["listItems"]["url_raw"].strip("'\"") == "rest/v2/items/"
    assert by_symbol["createItem"]["url_raw"].strip("`") == "${API_PREFIX}/items", \
        "定义侧保留原样，便于回溯源码写法"


def test_template_prefix_resolved_in_mapping(make_project, scan_of):
    """映射侧：页面调用该接口时，`${API_PREFIX}` 必须被解析成真实前缀。"""
    root = make_project({
        "src/router/index.ts": """
            const P = () => import('../pages/p')
            export default [{ path: '/p', component: P }]
            """,
        "src/pages/p.ts": """
            import { createItem } from '../api/mod'
            export const P = () => createItem()
            """,
        "src/api/const.ts": "export const API_PREFIX = '/api'\n",
        "src/api/mod.ts": """
            import { API_PREFIX } from './const'
            export const createItem = request('POST', `${API_PREFIX}/items`)
            """,
        "src/api/request.ts": "export function request(m, u, d) { return [m, u, d] }\n",
    })
    result = scan_of(root, include=["src/**"], routes=["src/router/**/*.ts"],
                     apiDirs=["src/api"])
    keys = {(r["method"], r["key"]) for r in result.page_apis}
    assert ("POST", "/api/items") in keys, keys


def test_class_method_symbols_carry_class_prefix(make_project, scan_of):
    """回归：类名必须前缀到方法符号上（曾因正则缺 re.M 导致 `UserService.getX` 变成 `getX`）。"""
    root = make_project(API_PROJECT)
    result = scan_of(root, include=["src/service/**"], apiDirs=["src/service"])
    symbols = {x["symbol"] for x in result.api_defs}
    assert "UserService.getAdminUsers" in symbols
    assert "UserService.deleteUser" in symbols
    assert "getAdminUsers" not in symbols, "不应丢失类名前缀"


def test_braced_param_list_does_not_shift_attribution(make_project, scan_of):
    """回归：`getAdminUsers(params?: { userId?: string; take?: number })` 的参数表含 `{ } ;`。

    配平扫描失效时，该方法体内的调用会被算到**上一个方法**头上（产出错误 URL）。
    """
    root = make_project(API_PROJECT)
    result = scan_of(root, include=["src/service/**"], apiDirs=["src/service"])
    by_symbol = {x["symbol"]: x for x in result.api_defs}
    assert "/admin/users" in by_symbol["UserService.getAdminUsers"]["url_raw"]
    assert "/admin/users/${id}" in by_symbol["UserService.deleteUser"]["url_raw"]
    # 关键反例：两个方法各自的 URL 不能互相串（曾因参数表配平失效而串位）
    assert by_symbol["UserService.getAdminUsers"]["line"] != by_symbol["UserService.deleteUser"]["line"]
    assert "delete" not in by_symbol["UserService.getAdminUsers"]["url_raw"].lower()


def test_nested_generic_call_is_captured(make_project, scan_of):
    """回归：`http.get<IPagination<IUser>>(` 的嵌套尖括号不能导致漏识别。"""
    root = make_project(API_PROJECT)
    result = scan_of(root, include=["src/service/**"], apiDirs=["src/service"])
    got = {(x["method"], x["symbol"]) for x in result.api_defs}
    assert ("GET", "UserService.getAdminUsers") in got
    assert ("DELETE", "UserService.deleteUser") in got


def test_normalize_url_contract(sf):
    """归一化契约（reference.md §1.5）：query 去除、剩余参数段归一、前缀常量保留、外部 URL 判定。"""
    display, key, unresolved = sf.normalize_url("`${API_PREFIX}/search?q=${kw}`", {})
    assert key == "${API_PREFIX}/search", key                     # query 不进 key
    assert "API_PREFIX" in unresolved and "kw" in unresolved       # 未解析的插值如实登记
    assert display.startswith("${API_PREFIX}"), display            # 前缀常量保留带 $ 形态，不塌缩成 :param

    _d, key2, _u = sf.normalize_url("`/api/roles/${id}`", {})
    assert key2 == "/api/roles/:param", key2                       # 路径参数归一

    _d, key3, _u = sf.normalize_url("'/api/duty_rules/{pk}/'", {})
    assert key3 == "/api/duty_rules/:param", key3                  # 后缀占位符同样归一

    # 常量可解析时直接用值替换（前缀常量 + 已知常量表）
    display4, key4, _u = sf.normalize_url("`${API_PREFIX}/items`", {"API_PREFIX": "/api"})
    assert display4 == "/api/items" and key4 == "/api/items", (display4, key4)

    assert sf.is_external_url("'https://registry.npmjs.org/x'") is True
    assert sf.is_external_url("'/api/local'") is False


def test_prefix_constant_not_collapsed_by_param_rule(sf):
    """回归：`${前缀}` 曾被 `{pk} → :param` 规则二次吞掉，导致大量页面的 key 塌缩成同一个。"""
    for raw in ("`${this.apiUrl}/availability`", "`${API_PREFIX}/list`", "`${C_API_AUTH}/me`"):
        _d, key, _u = sf.normalize_url(raw, {})
        assert key.startswith("${"), "%s 的前缀常量被吞成 %s" % (raw, key)


def test_cross_file_const_expression(make_project, scan_of):
    """回归：`C_API_AUTH = API_PREFIX + '/auth'` 这类**表达式常量**要能沿 import 链求值。"""
    root = make_project({
        "src/router/index.ts": """
            const P = () => import('../pages/p')
            export default [{ path: '/p', component: P }]
            """,
        "src/pages/p.ts": """
            import { login } from '../api/auth'
            export const P = () => login()
            """,
        "src/api/const.ts": "export const API_PREFIX = '/api'\nexport const C_API_AUTH = API_PREFIX + '/auth'\n",
        "src/api/auth.ts": """
            import { C_API_AUTH } from './const'
            export const login = request('POST', `${C_API_AUTH}/login`)
            """,
        "src/api/request.ts": "export function request(m, u, d) { return [m, u, d] }\n",
    })
    result = scan_of(root, include=["src/**"], routes=["src/router/**/*.ts"], apiDirs=["src/api"])
    keys = {(r["method"], r["key"]) for r in result.page_apis}
    assert ("POST", "/api/auth/login") in keys, keys


def test_dynamic_url_keeps_expression_and_marks_unresolved(make_project, scan_of):
    """动态拼接不猜路径：保留原始表达式形态，并让 key 变成可聚合的模板。"""
    root = make_project({
        "src/api/dyn.ts": """
            export const byType = request('GET', `/api/${type}/list`)
            """,
        "src/api/request.ts": "export function request(m, u, d) { return [m, u, d] }\n",
    })
    result = scan_of(root, include=["src/api/**"], apiDirs=["src/api"])
    item = [x for x in result.api_defs if x["symbol"] == "byType"][0]
    assert "${type}" in item["url_raw"], "不可解析的插值必须原样保留"
