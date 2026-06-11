# 示例 1：库/SDK — HTTP 请求库

假设项目为 `easy-fetch`，一个轻量级 HTTP 请求库，12 个公开 API，15 个配置项。

---

## Before（典型 AI 默认输出）

````markdown
# easy-fetch

A simple HTTP client for Node.js.

## Installation

```bash
npm install easy-fetch
```

## Usage

```js
const { EasyFetch } = require('easy-fetch')
const client = new EasyFetch()
const data = await client.get('https://api.example.com/users')
```

## API

### get(url, options?)
Send a GET request.

### post(url, body, options?)
Send a POST request.

### put(url, body, options?)
Send a PUT request.

### delete(url, options?)
Send a DELETE request.

### configure(options)
Configure the client. Supports all options.

## Contributing

See CONTRIBUTING.md for details.

## License

MIT
````

**问题诊断**：
- 概述只有一句话，不知道它解决什么问题、和其他库的区别
- 安装没有前置条件和验证方法
- API 只有函数签名，无参数说明、无返回值说明、无示例输出
- `configure` 的 "Supports all options" 是典型模糊表述
- 没有示例输出，读者不知道调用后能得到什么
- 没有子文档导航

---

## After（本 skill 策略输出）

### README.md

````markdown
# easy-fetch

一个轻量级、零依赖的 HTTP 请求库，支持请求拦截、响应变换、自动重试。

## 概述

`easy-fetch` 是一个 Node.js HTTP 客户端。

**解决的问题**：
- 原生的 `fetch` API 缺少重试、超时、拦截器等常用功能
- 现有的 HTTP 客户端库（如 axios、got）体积较大，部分已停止维护

**与其他方案的区别**：
- 与 axios 相比：更轻量（< 5KB），API 设计更简洁
- 与 got 相比：支持浏览器和 Node.js 双端，相同的 API
- 与原生 fetch 相比：增加了重试、超时、拦截器、自动 JSON 解析

## 安装

### 前置条件
- Node.js >= 16.0.0
- 或在现代浏览器中直接使用

### 安装命令
```bash
npm install easy-fetch
# 或
yarn add easy-fetch
# 或
pnpm add easy-fetch
```

### 验证安装
```bash
node -e "require('easy-fetch')" && echo "✓ 安装成功"
```

## 快速开始

```js
import { EasyFetch } from 'easy-fetch'

const client = new EasyFetch({ baseURL: 'https://api.example.com' })

const data = await client.get('/users')
// → { data: [{ id: 1, name: "Alice" }, { id: 2, name: "Bob" }], total: 2 }

const newUser = await client.post('/users', { name: "Charlie" })
// → { id: 3, name: "Charlie", createdAt: "2025-06-11T08:00:00Z" }
```

30 秒内，你已完成了第一个请求。

## 核心 API 速览

### `client.get(url, options?)`
```js
const users = await client.get('/users', { params: { page: 1 } })
// → { data: [...], total: 42, page: 1 }
```
详见 [API 参考](./api-reference.md)

### `client.post(url, body, options?)`
```js
const result = await client.post('/users', { name: "Diana" })
// → { id: 4, name: "Diana" }
```
详见 [API 参考](./api-reference.md)

### `client.configure(options)`
```js
client.configure({ timeout: 5000, retries: 3 })
// 之后所有请求均以 5 秒超时、最多 3 次重试执行
```
详见 [配置指南](./configuration.md)

### 拦截器
```js
client.beforeRequest(req => {
  console.log(`→ ${req.method} ${req.url}`)
})
// → → GET https://api.example.com/users
```
详见 [高级用法](./advanced-usage.md)

## 文档导航

| 文档 | 内容 |
|------|------|
| [API 参考](./api-reference.md) | 12 个 API 的完整参数、返回值、示例和注意事项 |
| [配置指南](./configuration.md) | 15 个配置项的详解，含多场景配置示例 |
| [高级用法](./advanced-usage.md) | 拦截器、中间件、自定义适配器 |

## License

MIT
````

### api-reference.md（节选）

````markdown
# API 参考

## 概述

`easy-fetch` 对外暴露的完整 API 列表。每个 API 包含完整的参数说明、返回值、示例和注意事项。

## 构造函数

### `new EasyFetch(options?)`

创建 HTTP 客户端实例。

**参数**：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| options | object | 否 | 全局配置项，详见 [配置指南](./configuration.md) |

**返回值**：`EasyFetch` 实例

**示例**：
```js
const client = new EasyFetch({ baseURL: 'https://api.example.com', timeout: 5000 })
// 创建一个指向 api.example.com 的客户端，请求超过 5 秒自动超时
```

---

## 请求方法

### `client.get(url, options?)`

发送 GET 请求。

**参数**：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| url | string | 是 | 请求地址（可使用相对路径，拼接 `baseURL`） |
| options | object | 否 | 请求级配置，会覆盖全局配置 |

**返回值**：`Promise<ResponseData>` — 自动 JSON 解析后的响应体

**示例**：
```js
// 基本使用
const users = await client.get('/users')
// → { data: [{ id: 1, name: "Alice" }], total: 1 }

// 带查询参数
const page2 = await client.get('/users', { params: { page: 2, size: 10 } })
// → { data: [...10 items], total: 42, page: 2 }

// 自定义请求头
const auth = await client.get('/me', { headers: { Authorization: 'Bearer xxx' } })
// → { id: 1, name: "Alice", email: "alice@example.com" }
```

**注意事项**：
- 当响应状态码 ≥ 400 时，`get()` 会抛出 `HTTPError`
- 如需获取原始 Response 对象，使用 `{ raw: true }` 选项
- URL 参数自动编码，无需手动 `encodeURIComponent`

### `client.post(url, body, options?)`

发送 POST 请求。

**参数**：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| url | string | 是 | 请求地址 |
| body | object \| string \| FormData | 否 | 请求体，对象自动序列化为 JSON |
| options | object | 否 | 请求级配置 |

**返回值**：`Promise<ResponseData>`

**示例**：
```js
// JSON 请求体
const newUser = await client.post('/users', { name: "Bob", email: "bob@example.com" })
// → { id: 2, name: "Bob", email: "bob@example.com", createdAt: "2025-06-11T08:00:00Z" }

// FormData 上传
const form = new FormData()
form.append('file', fileBlob)
const uploaded = await client.post('/upload', form)
// → { url: "https://cdn.example.com/files/abc123.png", size: 102400 }

// 空请求体
const triggered = await client.post('/webhooks/redeploy')
// → { status: "ok", deployedAt: "2025-06-11T08:01:00Z" }
```

**注意事项**：
- Body 为对象时，自动设置 `Content-Type: application/json`
- Body 为 FormData 时，自动设置 `Content-Type: multipart/form-data`

### ...（其余 10 个 API，均按黄金模板格式）

---

## 类型定义

```ts
interface ResponseData<T = any> {
  data: T
  status: number
  headers: Record<string, string>
}

interface RequestOptions {
  params?: Record<string, string | number>
  headers?: Record<string, string>
  timeout?: number
  retries?: number
  raw?: boolean
}
```

## 相关文档
- [README](./README.md) — 项目概述与快速开始
- [配置指南](./configuration.md) — 所有配置项
- [高级用法](./advanced-usage.md) — 拦截器与中间件
````

### configuration.md（节选）

````markdown
# 配置指南

## 概述

`easy-fetch` 支持三层配置体系，优先级从高到低：请求级 > 实例级 > 默认值。

## 配置方式

### 实例初始化时配置

```js
const client = new EasyFetch({
  baseURL: 'https://api.example.com',
  timeout: 5000,
  retries: 3
})
```

### 运行时修改配置

```js
client.configure({ timeout: 10000 })
// 之后所有请求的超时时间变为 10 秒
```

### 单个请求配置

```js
client.get('/slow-endpoint', { timeout: 30000 })
// 仅此请求超时 30 秒，不影响其他请求
```

## 配置项详解

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `baseURL` | string | `""` | 所有请求的基础 URL |
| `timeout` | number | `10000` | 请求超时时间（毫秒），0 表示无超时 |
| `retries` | number | `0` | 失败后自动重试次数 |
| `retryDelay` | number | `1000` | 重试间隔（毫秒） |
| `headers` | object | `{}` | 全局请求头 |
| `responseType` | `"json"` \| `"text"` \| `"blob"` | `"json"` | 响应体解析方式 |
| `validateStatus` | function | `s < 400` | 自定义成功判定函数 |
| `maxRedirects` | number | `5` | 最大重定向次数 |
| `withCredentials` | boolean | `false` | 是否携带凭证（浏览器端） |
| `proxy` | string \| false | `false` | 代理服务器地址 |
| `decompress` | boolean | `true` | 是否自动解压响应 |
| `maxContentLength` | number | `Infinity` | 响应体最大字节数 |
| `maxBodyLength` | number | `Infinity` | 请求体最大字节数 |
| `httpAgent` | Agent | `undefined` | 自定义 HTTP Agent（Node.js） |
| `httpsAgent` | Agent | `undefined` | 自定义 HTTPS Agent（Node.js） |

## 典型配置场景

### 生产环境 API 客户端

```js
const api = new EasyFetch({
  baseURL: 'https://api.myapp.com/v1',
  timeout: 5000,
  retries: 2,
  retryDelay: 2000,
  headers: {
    'Authorization': `Bearer ${process.env.API_TOKEN}`,
    'User-Agent': 'myapp/1.0'
  }
})
```

### 代理环境开发

```js
const dev = new EasyFetch({
  baseURL: 'http://localhost:3000',
  proxy: 'http://127.0.0.1:8888',
  timeout: 30000  // 开发环境调试时可设更长的超时
})
```

## 相关文档
- [README](./README.md) — 项目概述与快速开始
- [API 参考](./api-reference.md) — 完整 API
- [高级用法](./advanced-usage.md) — 拦截器与中间件
````
