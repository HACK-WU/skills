# API 测试端到端示例

> 配套 `api-testing` 技能。演示"自然语言描述 → 端点清单 → 测试客户端 → 用例 → 断言 → 报告"的完整闭环。所有代码可直接运行（需先安装 httpflex 且 base_url 可达）。

## 场景：用户服务 API

用户描述：
> 有个用户服务，base_url 是 `https://api.example.com`，需要 Bearer Token 鉴权。
> - `GET /users/{user_id}`：返回 `{id, name, email}`，正常 200。
> - `POST /users`：body 传 `{name, email}`，创建成功 201，缺 name 返回 400。
> - 不带 token 调任何接口应返回 401。

## 步骤 1：解析为端点清单

| name | method | endpoint | path_params | params | auth | expected |
|------|--------|----------|-------------|--------|------|----------|
| 获取用户 | GET | /users/{user_id} | [user_id] | — | bearer | result=True, code=200, data 含 id/name/email |
| 创建用户 | POST | /users | — | name(str,必填), email(str) | bearer | 成功 result=True, code=201 |
| 创建用户-缺参 | POST | /users | — | email 但缺 name | bearer | result=False, code=400 |
| 无鉴权访问 | GET | /users/{user_id} | [user_id] | — | none | result=False, code=401 |

## 步骤 2：测试客户端（含 Bearer 鉴权）

```python
from httpflex import BaseClient, JSONResponseParser
from requests.auth import AuthBase

class BearerAuth(AuthBase):
    def __init__(self, token):
        self.token = token
    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self.token}"
        return request

TOKEN = "eyJ_example_token"

class GetUserClient(BaseClient):
    base_url = "https://api.example.com"
    endpoint = "/users/{user_id}"
    method = "GET"
    response_parser_class = JSONResponseParser
    authentication_class = BearerAuth

class CreateUserClient(BaseClient):
    base_url = "https://api.example.com"
    endpoint = "/users"
    method = "POST"
    response_parser_class = JSONResponseParser
    authentication_class = BearerAuth
```

## 步骤 3+4：用例与业务断言

```python
cases = []

# 用例 1：正常路径
r = GetUserClient.request({"user_id": 123}, authentication=BearerAuth(TOKEN))
cases.append({
    "name": "获取用户-正常",
    "pass": r["result"] and r["code"] == 200
            and set(["id", "name", "email"]).issubset(r["data"] or {}),
    "code": r["code"], "detail": r,
})

# 用例 2：创建成功
r = CreateUserClient.request({"name": "Alice", "email": "a@x.com"},
                             authentication=BearerAuth(TOKEN))
cases.append({
    "name": "创建用户-成功",
    "pass": r["result"] and r["code"] == 201,
    "code": r["code"], "detail": r,
})

# 用例 3：缺必填参数
r = CreateUserClient.request({"email": "a@x.com"},
                             authentication=BearerAuth(TOKEN))
cases.append({
    "name": "创建用户-缺 name",
    "pass": (not r["result"]) and r["code"] == 400,
    "code": r["code"], "detail": r,
})

# 用例 4：无鉴权 → 期望 401
r = GetUserClient.request({"user_id": 123})   # 不带 authentication
cases.append({
    "name": "无鉴权访问",
    "pass": (not r["result"]) and r["code"] == 401,
    "code": r["code"], "detail": r,
})

passed = sum(1 for c in cases if c["pass"])
print(f"通过 {passed}/{len(cases)}")
for c in cases:
    print(("✅" if c["pass"] else "❌"), c["name"], c["code"])
```

## 步骤 5：产出报告

```
# API 测试报告

## 概览
- 通过：4 / 4
- base_url：https://api.example.com
- 鉴权方式：bearer

## 明细
| 端点 | 用例 | 结果 | code | 说明 |
|------|------|------|------|------|
| GET /users/{id} | 正常路径 | ✅ PASS | 200 | data 含 id/name/email |
| POST /users | 创建成功 | ✅ PASS | 201 | — |
| POST /users | 缺 name | ✅ PASS | 400 | 正确拒绝 |
| GET /users/{id} | 无鉴权 | ✅ PASS | 401 | 正确拦截 |

## 建议
- 鉴权与参数校验均符合预期，无阻塞问题。
```

## 变体：Cookie 鉴权 + 批量并发

```python
class CookieClient(BaseClient):
    base_url = "https://api.example.com"
    endpoint = "/users/{user_id}"
    default_headers = {"Cookie": "session=abc123"}   # 见 reference.md §5

# 批量并发（顺序保持）
with CookieClient() as client:
    results = client.request(
        [{"user_id": i} for i in (1, 2, 3)],
        is_async=True,
    )
assert all(r["result"] for r in results)
```

## 变体：缓存行为验证

```python
from httpflex.cache import CacheClient

class CachedUserClient(CacheClient):
    base_url = "https://api.example.com"
    endpoint = "/users/{user_id}"
    default_cache_expire = 300

c = CachedUserClient(authentication=BearerAuth(TOKEN))
r1 = c.request({"user_id": 1})          # 未命中
r2 = c.request({"user_id": 1})          # 命中
assert r1["data"] == r2["data"]
c.clear_cache()
```
