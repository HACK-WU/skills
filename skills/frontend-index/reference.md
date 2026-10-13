# 前端页面接口索引 · 执行细则

配套资源：`skills/frontend-index/SKILL.md`（SSOT，规则定义在此）、`scripts/scan_frontend.py`（确定性扫描）。本文件只写落地口径。

---

## 1. 提取原理（脚本做了什么）

脚本用**正则 + 有界图搜索**（零依赖，不引入 AST），把源码里的三类事实提取出来再做归属：

```text
① 路由（页面入口）  ② 接口定义（符号 → 方法+URL）  ③ 调用点（谁在哪里调了什么）
        └────────────── ④ 归属：页面 → 其 import 图（≤深度）内的调用点 ──────────────┘
```

### 1.1 路由提取

| 形态 | 识别方式 | 说明 |
|------|----------|------|
| 配置式（Vue Router / React Router / Angular） | `path:` + `component:` / `components:{}` / 行内 `import()` | 组件名 → 同文件 `const X = () => import('...')` 映射，或按 import 表解析 |
| JSX `<Route path= element=>` | 标签属性配对 | React Router v5/v6 |
| Angular `loadChildren` | `loadChildren: () => import('...')` | **组合一层**：子路由文件的条目拼上父路径（如 `auth` + `login` → `auth/login`） |
| 文件式（Next / Nuxt / uni-app） | 无配置路由时的兜底：`pages/**`、`app/**/page.*` 推导 | 路径段转路由，`[id]`/`_id`/`index` 有约定处理 |

**懒加载说明容忍**：`import(/* webpackChunkName: 'X' */ '...')` 这类魔法注释会被跳过（实测 BlueKing Monitor 全量使用该写法）。

### 1.2 接口定义提取（符号 → 方法 + URL）

| 写法 | 归属符号 | 例 |
|------|----------|-----|
| 请求工厂 | `export const X = request('GET', 'url')` | `X`（严格 const：接口层文件里任何 const 都算符号） |
| 类方法 | `class S { m() { return this.http.get('url') } }` | `S.m` |
| 函数 / 箭头 | `export function f() { fetch('url') }`、`export const f = () => http.get('url')` | `f` |

**参数表按括号配平扫描**（关键）：`getAdminUsers(params?: { userId?: string; take?: number }) {` 这类带 `{ } ;` 的参数表必须配平识别，否则后续方法的调用会被算到上一个方法头上（实测 bug，见 §6）。

**接口层文件判定**：显式声明的 `apiDirs`，或自带 ≥2 个 `request('METHOD', url)` 工厂调用的模块。判定结果影响"严格 const 归属"与"遍历是否进入该文件"。

### 1.3 调用点提取

| 类型 | 识别 | 产出的 `via` |
|------|------|--------------|
| 直接 URL 调用 | `fetch('url')`、`axios.get('url')`、`http.post<...>('url')`、`request('GET','url')` | `direct` |
| 命名导入符号调用 | `import { f } from 'api/mod'` + 文件内 `f(` | `import:f` |
| 命名空间 / 默认导入 | `import * as api from '...'` / `import api from '...'` + `api.f(` | `ns:api.f` |
| 依赖注入实例方法（Angular 等） | 构造注入 `private prop: Class`；函数式注入 `private readonly #svc = inject(Svc)` + `this.#svc.m(` | `inject:prop.m` |

**符号定义查找 = 沿 import / re-export 边的有界 BFS**（默认 4 跳）：从调用点文件出发，穿过 barrel（`export * from`）、跨包（工作区包名）、别名，找到定义文件里的同名符号。找不到时不产出映射（不猜）。

**barrel 穿透**：`export * from './x'` 集合型的 `index.ts` 不参与"归属遍历"（否则一个 `@core/state` barrel 会让每个页面继承整个目录的接口）；但**按导入的符号名穿透**——`import { UsersService } from '@cloud/app/@core/state'` 只连到定义 `UsersService` 的那个文件。

### 1.4 别名与模块解析

| 来源 | 方式 |
|------|------|
| tsconfig | 扫 `root` 下（含 1 层子目录）及**向上 3 层父目录**的 `tsconfig*.json`，读 `compilerOptions.paths`（JSONC 容错） |
| webpack | 嗅探 `webpack*.js/ts` 里的 `'@alias': path.resolve(..., 'src/xxx')` |
| 工作区包名 | 扫非同层 `package.json` 的 `name` → 目录（`monitor-api/modules/shield` 这类跨包 import） |
| 兜底 | `@/` → `root/src`；裸包名 → `root/<包名>` |
| 扩展名探测 | `''`、`.ts/.tsx/.js/.jsx/.mjs/.cjs/.vue`、`/index.*` |
| 手工补 | `--alias k=v`（可重复） |

### 1.5 URL 归一化与常量求值

- **常量求值**：支持字面量、模板串（可含 `${CONST}`）、顶层 `+` 拼接（`API_PREFIX + '/auth'`），沿 import / re-export 链解析（≤4 跳）。不可静态求值 → 返回"不可解析"，**不猜**。
- **前缀常量 vs 路径参数**：首个 `/` 之前的插值保留名字（`${API_PREFIX}/x`、`${this.apiUrl}/x`），之后的插值归一到 `:param`（`/roles/${id}` → `/roles/:param`）；`{pk}` 之类占位符同样归一到 `:param`。这样"同一接口的不同参数名"能聚合，而"不同前缀来源"不会互相污染。
- **常量上下文**：归一化用的是 **URL 定义所在文件**的常量表（不是调用点文件）——页面通常没导入 `API_PREFIX`，服务里才有。
- **外部 URL 剔除**：`https://…` / `//…` 一律不进映射，单列到「外部 URL（已剔除）」。

### 1.6 深度语义（置信度根基）

| 深度 | 含义 | 置信度 | 用法 |
|------|------|--------|------|
| 0 | 调用点在**页面文件自身** | 🟢 | 反向表"直接调用页面" |
| 1 | 调用点在**直接依赖**里 | 🟡 | 反向表"直接调用页面" |
| ≥2 | 调用点在**依赖的依赖**里 | 🔵 | 只作"间接候选"，不给结论 |
| — | URL 含不可解析插值 | `[待确认]` | 保留源码形态，交人工判断 |

遍历规则：不进入接口层文件（服务内部的 `http` 调用是"定义"，不是页面的调用）、不跨越其他页面文件、不进入 barrel。

---

## 2. 脚本参数与退出码

```bash
timeout 300s python3 {skill-dir}/scripts/scan_frontend.py --root <项目根> [选项]
```

零第三方依赖，Python 3.8+ 直接跑。命令仍需前置 `timeout` 兜住"超大项目解析卡住"。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--root <目录>` | 必填 | 扫描根目录（同时是别名/包解析基准） |
| `--config <文件>` | `{root}/.fe-index/config.json` | 声明文件；支持 `apps[]` + `--app` 选择 |
| `--app <slug>` | 首个 | 声明文件含多个应用时选择 |
| `--include <glob>` | 无 | 只扫匹配的相对路径（可重复）；monorepo 建议给 `src/**` |
| `--exclude <glob>` | 无 | 排除（可重复），如 `**/*.mock.*`、`**/legacy/**` |
| `--routes <glob>` | 自动探测 | 路由文件 glob（可重复）。**`**/` 按 gitignore 语义可匹配零层目录** |
| `--pages-dir <目录>` | 自动 | 页面根（可重复，仅作展示与兜底） |
| `--api-dir <目录>` | 自动 | 接口定义层目录（可重复）——决定符号→URL 能否解析 |
| `--alias k=v` | 无 | 路径别名（可重复），如 `--alias @api=src/monitor-api` |
| `--request-object <名>` | 内置集合 | 追加"请求对象"尾名（如 `myHttp`） |
| `--max-depth <N>` | 2 | 归属深度（0/1/2，见 §1.6） |
| `--max <N>` | 1000 | 映射行数上限（硬上限 5000） |
| `--format {md,tsv,json}` | md | 输出格式（AI 处理建议 `json`） |
| `--out <文件>` | stdout | 写入文件（stdout 只留一行提示） |
| `--dump-config` | 关 | 只做约定探测，输出 JSON（供生成声明文件） |
| `--check` | 关 | 新鲜度检查（需 `--index`） |
| `--index <目录>` | 无 | 索引目录，如 `.fe-index/monitor-pc` |
| `--verbose` | 关 | 探测细节与统计打到 stderr |
| `--slug <名>` | 目录名 | `--dump-config` 建议配置里的 slug（默认取根目录名） |
| `--version` | — | 打印脚本版本后退出 |

**内置"请求对象"尾名**：`axios / http / httpClient / $http / $axios / request / req / client / instance / ajax / ky / api / httpService / service`。工厂调用要求函数名含 `request`（`request(...)`、`httpRequest(...)`、`apiRequest(...)`）。

**退出码**

| 码 | 含义 | 处置 |
|----|------|------|
| 0 | 成功（`--check`：新鲜） | 继续 |
| 2 | 未识别到路由或接口约定 | 校正声明文件（`--routes` / `--api-dir` / `--alias`）后重跑 |
| 3 | 环境或 IO 错误 / git 不可用 | 修路径或确认 git 环境 |
| 4 | 提取结果为空 | 检查 `--include`、`--max-depth` |
| 5 | 入参非法（config 非法 JSON、`--max` 超限、`--check` 缺 `--index`） | **修正参数**后重跑 |
| 6 | `--check`：索引过期（提交前进且范围内文件有变化） | 重建（重跑 + 重标注） |
| 7 | `--check`：`meta.json` 缺失或不可读 | 视为无新鲜度信息，建议重建 |

`--check` 的判定口径：`meta.json.commit` vs 当前 `HEAD`；若提交已前进，再看 `git diff --name-only {commit}..HEAD -- {scope}`——**范围内无变化则视为可用**（避免每次无关提交都误报过期）。

---

## 3. 声明文件（`.fe-index/config.json`）

```json
{
  "apps": [
    {
      "slug": "monitor-pc",
      "root": "/root/bk-monitor/bkmonitor/webpack",
      "include": ["src/**"],
      "exclude": ["**/*.spec.ts", "**/__mocks__/**"],
      "routes": ["src/**/router/**/*.ts", "src/monitor-pc/router/*.ts"],
      "pagesDirs": ["src/monitor-pc/pages"],
      "apiDirs": ["src/monitor-api/modules"],
      "aliases": {"@page": "src/monitor-pc/pages", "@api": "src/monitor-api"},
      "requestObjects": ["myHttp"],
      "maxDepth": 2
    }
  ]
}
```

- **`root` 相对谁（口径必须记准）**：声明文件放在 `{root}/.fe-index/config.json` 时，app 的 `root` 相对**该 `.fe-index/` 的上一级**（即 `{root}`），所以 `"root": "."` 就是项目根；用 `--config` 指向别处时，相对声明文件所在目录。绝对路径原样使用
- **优先级**：`--root` 只决定"去哪找声明文件"，**声明文件里的 `root` 优先**（monorepo 场景：`--root 仓库根` + `root: "apps/cloud"` → 扫应用目录）。`--out` 一律相对**当前工作目录**；`--include` / `--routes` / `--api-dir` 一律相对最终生效的 root
- 声明文件里的 `include` / `routes` / `apiDirs` / `aliases` / `requestObjects` 与 CLI **叠加**（CLI 追加）；`--max-depth` 例外——CLI 非默认值时**覆盖**声明文件
- 首次建造：`--dump-config` 产出探测结果 → **校正**（尤其 `apiDirs` / `aliases`）→ 存盘 → 之后重建零猜测

---

## 4. 已知局限（诚实清单）

| # | 局限 | 影响 | 缓解 |
|---|------|------|------|
| 1 | 嵌套路由只组合**一层**（Angular `loadChildren`）；更深的组合仍标"相对路径（父级待确认）" | 路由列可能缺父级前缀 | 标注已写明；必要时在 `--routes` 里同时给父子文件，或人工补 |
| 2 | 动态路由（后端菜单/权限驱动生成） | 页面枚举不全 | 退出码 2 或页面数与实际不符时如实说明 |
| 3 | 动态 URL、运行时前缀（`${this.apiUrl}`） | 无法给出确定路径 | 保留 `${}` 形态 + `[待确认]`，**不猜** |
| 4 | 多级请求封装（自研 request 层再加工 URL） | 只能定位到封装调用点 | 在索引里写明"经封装，最终路径见 X 文件" |
| 5 | GraphQL / WebSocket / RPC | 不提取 | 报告里明确"未覆盖" |
| 6 | 间接候选（🔵）≠"该页面在用" | 反向表可能偏大 | 反向表分开列，候选只给条数 |
| 7 | 正则 + 启发式（不做 AST） | 宏、装饰器生成、`import(变量)` 等极端写法会漏 | 抽样校验兜底；必要时用声明文件收窄范围 |
| 8 | **未在 React / Vue3 / Next / Nuxt 真实项目上实测** | 那些框架的探测规则未经压测 | 首次使用时用 §5 抽样核对；报告里如实标注"未实测" |
| 9 | 同一文件内多个同名方法/重载 | 可能取错重载 | 低概率；抽查发现后按 §1.2 修正声明或收窄 `apiDirs` |
| 10 | **"省时间"未做 A/B 实测** | 只验证了映射正确性（抽样 10/10），没做"有索引 vs 无索引"的耗时对比 | 首次真实使用时记录体验；若发现建索引成本高于收益，按「反模式」拒建 |
| 11 | `--max` 截断、超大文件（>1.5MB）跳过 | 产出静默少条目 | 截断会在 `stats.truncated` 与待确认区留痕，**必须处理后再交付**（SKILL.md 阶段 2 已卡） |

**已实测项目**（两个真实工程，非构造样例）：

| 项目 | 技术栈 | 规模 | 结果 |
|------|--------|------|------|
| BlueKing Monitor（`bkmonitor/webpack`） | Vue2 + TSX 微前端，路由分散 37 文件，接口在独立包 `monitor-api`（`request('GET', url)` 工厂 + 符号导入） | 扫描 2581 文件 | 页面 170 · 接口定义 1054 · 映射 2024 · 去重接口 480（🟢231/🟡722/🔵1071） |
| xpert/cloud | Angular 14+（`inject()` 注入 + `#私有字段`），30 个 `*routing*.ts`，服务层 `@core/services/*.service.ts` | 扫描 1297 文件 | 页面 129 · 路由 160 · 映射 377 · 去重接口 127（🟢90/🟡189/🔵98） |

> 上表 Angular 数字为**修复后**值（`inject()` 属性识别补 `re.M`、组件/工具文件开放遍历后覆盖率提升；修复前为 84/66）。bk-monitor 数字未受修复影响（逐行零差异）。改脚本后请重跑这两条命令核对（回归基线见 `tests/frontend_index/`）。

**抽样核对结果**：bk-monitor 随机抽 10 条 🟢 行，回源码核对"调用点确有该符号调用 + 定义处确有该请求" → **10/10 通过**；xpert/cloud 抽 8 条 → **8/8 通过**（多行链式调用 `this.#membership\n  .getAdminUsers(` 的证据行已指向方法名所在行）。

**单元测试**：`tests/frontend_index/`（pytest，34 项）：路由提取 7 项 · 接口定义与 URL 归一化 10 项 · 归属与深度 7 项 · CLI 与退出码 10 项（含 `--check` 四分支）。跑法见 `tests/README.md`；**改脚本前后各跑一次 `python3 -m pytest tests -q`**，再用 §4 的两条真实项目命令做端到端回归。

**复现命令**：

> ⚠️ bk-monitor 是**多微前端仓库**（`monitor-pc` / `apm` / `fta-solutions` / `trace` 各有自己的 router）。下面的 `src/**/router/**` 会把多个应用的路由合并进一份结果（同一页面被多应用注册时路由列出现重复串，脚本已按字符串去重）。按「一应用一 slug」原则，实际建造应收窄到单应用：
> `--include 'src/monitor-pc/**' --include 'src/monitor-api/**' --routes 'src/monitor-pc/router/**/*.ts'` → 页面 116 · 映射 1000（撞 `--max`，需提高）· 接口 272。

```bash
# BlueKing Monitor（Vue2 + TSX 微前端）
timeout 600s python3 {skill-dir}/scripts/scan_frontend.py \
  --root /root/bk-monitor/bkmonitor/webpack --include 'src/**' \
  --routes 'src/**/router/**/*.ts' --routes 'src/*/router/*.ts' \
  --api-dir src/monitor-api/modules --pages-dir src/monitor-pc/pages \
  --max 3000 --format json --out temp/fe-index-bk-scan.json

# xpert/cloud（Angular）
timeout 300s python3 {skill-dir}/scripts/scan_frontend.py \
  --root /root/xpert/apps/cloud --include 'src/app/**' \
  --routes 'src/app/**/*routing*.ts' --api-dir src/app/@core/services \
  --format json --out temp/fe-index-cloud-scan.json
```

---

## 5. 抽样校验（交付前的信任度闸门）

首次建造、或声明文件改动后，建议做一次抽样核对（10 分钟以内）：

1. 从扫描输出里随机取 5-10 条 **🟢 行**（`depth == 0`）
2. 按 `via` 类型核对：
   - `import:f` → 证据行应有 `f(`；同时 `api_defs` 里应有 `f → url` 的定义行
   - `inject:prop.m` → 证据行应有 `.m(`（注意多行链式调用：方法名可能在下一行）
   - `direct` → 证据行应有 `fetch(` / `axios.*(` / `http.*(` / `request(` 与 URL 字面量
3. 通过率低于 9/10：**不要交付**，先检查 `apiDirs`（是否漏了服务层）、`aliases`（是否解析不到跨包符号）、`--max-depth`
4. 浏览器可运行时的加强版：用 `use_skill("agent-browser")` / `use_skill("playwright-cli")` 实测 2-3 个高频页面，比对网络面板里实际请求的接口与索引条目是否一致

---

## 6. 实现坑（改本脚本前必读）

| 坑 | 症状 | 正确做法 |
|----|------|----------|
| 参数表含 `{ } ;` 的方法未按括号配平识别 | `getAdminUsers(params?: {...})` 的调用被算到**上一个方法**头上（产出错误 URL） | `balanced_scan()` 配平扫描参数表；方法名 + 参数 + 返回类型 + `{` 才算定义 |
| 常量归一化用错上下文 | 服务里写的 `${API_PREFIX}/x` 在页面上调用时解析不出来 | 用 **URL 定义文件**的常量表，不是调用点文件的 |
| 前缀常量标记被 `{pk} → :param` 规则二次吞掉 | 所有 `${前缀}` 塌缩成 `:param`，308 个页面挤进一个 key | 前缀标记保留 `${NAME}` 带 `$` 形态；`{pk}` 规则加 `(?<!\$)` |
| barrel 文件参与归属遍历 | 页面导入 `@core/state` barrel 就"继承"整个目录的接口（980 条间接噪声） | barrel 不入遍历图；按导入符号名穿透到定义文件 |
| glob 的 `**/` 当"至少一层目录" | `src/app/**/*routing*.ts` 漏掉顶层 `app-routing.module.ts` → 整个顶层路由丢失 | `match_glob()`：`**/` 可匹配零层（gitignore 语义） |
| 泛型参数含嵌套 `<>` | `http.get<IPagination<IRole>>(` 整个调用丢失 | 泛型段用 `[^()]{0,160}`（允许尖括号嵌套，禁跨括号） |
| 方法体内数据常量抢占符号 | `const data = ...` 把方法名顶掉，产出 `S.data` 假符号 | 页面/组件文件只在"函数式 const（箭头/function）"时切换符号；接口层文件才严格按 const 归属 |
| 魔法注释 | `import(/* webpackChunkName: 'X' */ '...')` 解析失败 → 页面全灭 | 懒加载 import 规格统一容忍 `/* */` 与 `//` 注释 |
| 多路由同一页面文件 | 行数按路由数翻倍（`grafana.tsx` × 6） | 按**页面文件**聚合，路由列显示"多路由合并" |
| 外部绝对 URL 混入 | `https://registry.npmjs.org/...` 被当成业务接口并挂到无关页面 | `is_external_url()` 剔除，单列到「外部 URL（已剔除）」 |
