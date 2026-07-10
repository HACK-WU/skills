# httpflex-py 用法参考（供 API 测试直接套用）

> 本文件是 `api-testing` 技能的配套参考。AI 在生成测试客户端时应**照搬以下模板**，不要凭空猜测属性名或方法签名。所有内容基于 httpflex `0.1.1`（要求 Python ≥ 3.11）。

## 1. 安装

```bash
pip install "git+https://github.com/HACK-WU/httpflex.git"
# 带可选依赖：...#egg=httpflex[all]  /  [celery]  /  [redis]  /  [drf]
```
> 该库未发布到 PyPI，从 GitHub 安装第三方代码前必须获得用户显式批准。

## 2. 最小测试客户端

```python
from httpflex import BaseClient, JSONResponseParser

class UserAPIClient(BaseClient):
    base_url = "https://api.example.com"
    endpoint = "/users/{user_id}"      # 占位符用 {}
    method = "GET"                      # 默认 GET，自动 .upper()
    response_parser_class = JSONResponseParser

# 上下文管理器（自动关 Session）
with UserAPIClient() as client:
    result = client.request({"user_id": 123, "fields": "name,email"})
    print(result["data"])

# 或类方法直接调用（内部自动管理实例生命周期）
result = UserAPIClient.request({"user_id": 123})
```

## 3. REQUEST_DATA 映射规则

`request(data)` 的 `data` 是无保留键的普通字典，**全部字段作为业务参数发送**：

- `GET` / `DELETE` / `HEAD` / `OPTIONS`：字段进入 **URL 查询字符串**
- `POST` / `PUT` / `PATCH`：字段以 **JSON 请求体**发送
- `endpoint` 中的 `{占位符}` 从 `data` 取值替换，**已使用的键不再进入 query/body**

```python
class PostClient(BaseClient):
    base_url = "https://api.example.com"
    endpoint = "/users/{user_id}/posts/{post_id}"
    method = "GET"

result = PostClient.request({
    "user_id": 123,
    "post_id": 456,
    "include_comments": True,   # 剩余字段作为查询参数
})
# 实际请求: GET https://api.example.com/users/123/posts/456?include_comments=True
```

## 4. 统一响应结构与错误码

`request()` 始终返回归一化字典（**失败也返回结构，不抛异常**，除非钩子中断）：

```python
{
    "result": True,        # 请求是否成功（HTTP 2xx 且解析成功）
    "code": 200,           # HTTP 状态码；失败为负向错误码（见下）
    "message": "Success",  # 响应消息或错误描述
    "data": {...},         # 解析后的响应数据；失败时为 None
}
# CacheClient 额外携带 cache_key 字段
```

错误码常量（`httpflex.constants`）：

| code | 含义 |
|------|------|
| `-1` | 非 HTTP 错误（超时 / 网络） |
| `-2` | 未预期响应类型 |
| `-3` | 格式化失败 |

测试断言时先判 `result`，再读 `data`：

```python
if not result["result"]:
    print("请求失败:", result["code"], result["message"])
else:
    assert result["data"]["id"] == 123
```

## 5. Cookie 加载

httpflex **没有独立 cookie 属性**，统一通过请求头传入。客户端持有 `requests.Session`，设置后跨请求保持。

```python
# 方式 A：类级默认头（所有请求带此 Cookie）
class AuthedClient(BaseClient):
    base_url = "https://api.example.com"
    endpoint = "/me"
    default_headers = {"Cookie": "session=abc123; csrftoken=xyz"}

# 方式 B：实例级（更灵活，便于从变量注入）
client = SomeClient(headers={"Cookie": f"session={session_id}"})
```

> Cookie 头默认在日志中脱敏（`sensitive_headers` 含 `Cookie`），可放心使用。

## 6. 鉴权（Bearer / Token / 自定义头）

**推荐用 `requests.auth.AuthBase` 子类**（自动附加到每个请求）：

```python
from requests.auth import AuthBase

class BearerAuth(AuthBase):
    def __init__(self, token):
        self.token = token
    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self.token}"
        return request

client = SomeClient(authentication=BearerAuth("eyJ..."))
```

简化写法（仅静态头，直接用 `default_headers`）：

```python
class ApiKeyClient(BaseClient):
    base_url = "https://api.example.com"
    endpoint = "/data"
    default_headers = {"X-API-Key": "sk-xxxx"}
```

`authentication_class`（类属性）/ `authentication`（构造参数）接受 `AuthBase` 子类**或实例**；传类时框架自动实例化。

## 7. 超时与重试

```python
class ResilientClient(BaseClient):
    base_url = "https://api.example.com"
    endpoint = "/slow"
    default_timeout = 60          # 默认 30s
    enable_retry = True           # 默认 False
    max_retries = 3               # 默认 3
    retry_config = {              # 深合并默认配置
        "total": 3,
        "backoff_factor": 0.5,
        "status_forcelist": [429, 500, 502, 503, 504],
        # 默认 allowed_methods 含 POST；不可安全重试的接口移除 POST：
        "allowed_methods": ["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"],
        "raise_on_status": False,
    }
```

## 8. 批量并发测试

传入 `list[dict]` + `is_async=True`，结果**严格按输入顺序返回**；单项失败以结构化错误字典填充，不中断整体。

```python
with ListClient() as client:
    results = client.request(
        [{"id": 1}, {"id": 2}, {"id": 3}],
        is_async=True,          # 线程池并发，默认 max_workers=10
    )
# results[0] 对应 id=1
```

适合：参数化批量用例、轻量并发压测。线程池（默认）适合 IO 密集；跨进程用 `CeleryAsyncExecutor`（需 worker 侧 `register_celery_tasks`）。

## 9. 透明缓存（可选，验证缓存行为时用）

```python
from httpflex.cache import CacheClient, InMemoryCacheBackend

class CachedClient(CacheClient):
    base_url = "https://api.example.com"
    endpoint = "/posts"
    cache_backend_class = InMemoryCacheBackend
    default_cache_expire = 300   # 秒；0=永不过期

client = CachedClient()
client.request({"post_id": 1})   # 未命中 → 请求
client.request({"post_id": 1})   # 命中 → 直接返回
client.cacheless({"post_id": 1}) # 绕过读缓存，直接请求
client.refresh({"post_id": 1})   # 绕过读并强制写回
client.clear_cache()             # 清空（注意：无 delete_cache() 方法）
```

Redis 后端：`cache_backend_class = RedisCacheBackend`，`cache_backend_kwargs = {"host":..., "port":..., "db":..., "key_prefix": "app_"}`。用户隔离：`is_user_specific = True` 且构造传 `user_identifier="user_123"`。

## 10. 钩子（用于埋点 / 计时 / 注入）

```python
import time

client = SomeClient()

def add_trace(client, request_id, request_data):
    request_data["trace_id"] = request_id
    return request_data
client.register_hook("before_request", add_trace)

def log_time(client, request_id, response):   # response 是 requests.Response
    print(request_id, response.elapsed.total_seconds())
    return response
client.register_hook("after_request", log_time)

def on_err(client, request_id, error):
    print("failed", request_id, error)
client.register_hook("on_request_error", on_err)
```

> 计时也可在测试侧用 `time.perf_counter()` 包裹 `request()`，更直观。
> 钩子名仅限 `before_request` / `after_request` / `on_request_error`；`before_request` 钩子抛异常默认仅记录不中断，设 `raise_on_hook_error=True` 可中断。

## 11. 自定义响应解析 / 验证（可选）

- 响应解析器：实现 `BaseResponseParser.parse(client_instance, response)`
- 响应验证器：实现 `BaseResponseValidator.validate(client_instance, response, parsed_data)`，失败抛 `APIClientResponseValidationError`；现成实现 `StatusCodeValidator`
- 请求序列化器 / DRF：传 `request_serializer_class` 或 `DRFClient`（需 `[drf]`）

## 12. 异常体系（仅当显式启用钩子中断或手动 try 时）

| 异常 | 含义 |
|------|------|
| `APIClientError` | 基类 |
| `APIClientHTTPError` | 4xx/5xx（`.status_code`） |
| `APIClientNetworkError` | 网络错误 |
| `APIClientTimeoutError` | 超时 |
| `APIClientRequestValidationError` | 请求参数校验失败（`.errors`） |
| `APIClientResponseValidationError` | 响应校验失败 |

```python
from httpflex.exceptions import APIClientTimeoutError, APIClientHTTPError
try:
    r = client.request(data)
except APIClientTimeoutError:
    ...
```

## 13. 关键配置项速查（BaseClient）

| 类属性 | 默认 | 说明 |
|--------|------|------|
| `base_url` | `""` | **子类必填**，末尾 `/` 自动去 |
| `endpoint` | `""` | 支持 `{占位符}` |
| `method` | `"GET"` | 自动大写 |
| `default_timeout` | `30` | 秒 |
| `verify` | `True` | SSL 校验；`False` 仅开发 |
| `enable_retry` | `False` | 需 `max_retries>0` |
| `max_retries` | `3` | 重试次数 |
| `max_workers` | `10` | 异步线程数 |
| `default_headers` | `{}` | 默认请求头 |
| `authentication_class` | `None` | `AuthBase` 子类/实例 |
| `sensitive_headers` | `{Authorization, Cookie, X-API-Key, ...}` | 日志脱敏 |
| `response_parser_class` | `JSONResponseParser` | 响应解析器 |

构造参数同名可覆盖（如 `BaseClient(url=..., headers=..., timeout=..., authentication=...)`）。
