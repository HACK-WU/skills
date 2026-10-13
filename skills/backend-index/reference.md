# backend-index 落地口径

> `SKILL.md` 的补充材料：设计依据、提取规则明细、脚本全参数与退出码、证据分级、实测数据与已知坑。
> 需要改脚本或换框架时读本文；日常建库 / 查表只读 `SKILL.md`。

---

## 1. 为什么是模块级（设计依据）

### 1.1 接口级索引与专家团重复，且过期更快

| 证据 | 结论 |
|---|---|
| `expert-team/SKILL.md` Step 8.3：「后端模块（暴露 API）→ 识别其暴露接口 → 按子功能聚合写 ki（`tags=api`，`group=接口信息/{模块名}`）」 | **接口清单已有人做**，且是可检索原子 |
| 同规范：`implementation/05-接口.md`（公开入口 / 契约 / 错误码 / 版本策略）；`C4-数据流向与消费.md`（数据实体 → 来源接口 → 去向 → 消费方） | 接口**契约**与**数据流**也有 |
| 同规范：专家包是"重载体（多子 agent 深挖 + 双层文档），只应为**领域专属且复杂度较高**的模块创建" | 覆盖**稀疏且按需**——它替代不了"全量、便宜、随时可重建"的索引层 |
| 接口数量随迭代天天变（实测一仓 806 个路由），模块边界低频变化 | 接口级索引**过期风险高**，模块级**稳** |

**结论**：索引做**路由层**（去哪看 / 动了谁），专家做**说明书层**（是什么 / 怎么用），二者**零重叠**；且索引顺带成为专家团的发现入口。

### 1.2 什么必须机械做，什么必须 AI 做

| 内容 | 性质 | 谁做 |
|---|---|---|
| 模块全集、目录、定义位置 | 穷举 | 脚本 |
| 挂载前缀（全局前缀 + controller 前缀跨文件合成） | 合成 | 脚本 |
| 依赖边，**尤其"被依赖"** | **穷举反查**（扫完全部模块才知道谁 import 我） | 脚本 |
| 表 → 模块 | **穷举反查** | 脚本 |
| 非 HTTP 入口、守卫 | 穷举 | 脚本 |
| 模块中文职责 | 语义 | AI |
| 专家资产关联确认 | 判断 | AI |
| 待确认项回源码核实 | 判断 | AI |

**反查类漏检是静默的**——报告看起来完整，缺失的边不会自曝。所以 `被依赖` / `表 → 模块` 只接受机械提取的结果。

---

## 2. 提取规则明细

### 2.1 NestJS

| 索引项 | 提取规则 | 备注 |
|---|---|---|
| 模块 | 文件含 `@Module({...})`；类名取 `@Module` 之后 400 字符内的 `class X` | 模块目录 = 模块文件所在目录 |
| 模块归属文件 | **最长目录前缀**（嵌套模块各拿自己的文件）+ `controllers`/`providers` 声明的类解析到的文件 | 避免父子模块互相吞并 |
| 挂载前缀 | `setGlobalPrefix('api')`（支持字面量 / 同文件 const） + `@Controller('x')` | `@Controller()` 无路径时改用方法路径首段提示 |
| 接口数 | controller 文件里 `@Get/@Post/@Put/@Patch/@Delete/@Head/@Options/@All` 装饰器计数 | 不建逐接口表 |
| 依赖 | `@Module imports` 的 PascalCase token → 命中"是模块类"（定义文件为 `*.module.ts`）的才算依赖 | 框架模块（见 `FRAMEWORK_MODULES`）只进 `libs`，不报未解析 |
| 被依赖 | 全部模块的依赖边做反向 | 穷举 |
| 数据表 | `TypeOrmModule/MongooseModule.forFeature([...])` 的实体 + 归属文件里 `@InjectRepository(X)` / `@InjectModel(X)` / `getRepository(X)` / `Repository<X>` → `@Entity('表名')` | 引用次数 = 命中次数；证据记首个命中的 `file:line` |
| 非 HTTP 入口 | `@Processor('q')` / `@CommandHandler(X)`·`@QueryHandler`·`@EventsHandler` / `@Cron`·`@Interval`·`@Timeout` | 按 scope_files（含组合进来的外部文件） |
| **事件/命令边（CQRS）** | 模块**自有文件**里 `.execute/.send/.publish/.dispatch(new X)` → 全局 `@(Command\|Query\|Events)Handler(X)` 的承载模块目录 | 不经 imports 的耦合；只取自有文件，每条边可 `grep 模块目录` 复验 |
| **事件/命令边（MQ）** | 模块自有文件里 `@InjectQueue('q')` → 全局 `@Processor('q')` 的承载模块目录 | 同名队列多消费者时取首个；无 `@InjectQueue` 的项目为 0 条 |
| 守卫 | 归属文件里 `@UseGuards(...)` 去重 | 模块级（不区分方法级） |
| 数组展开 | `controllers: [...Controllers]` / `imports: [...X]` → 跟随**常量数组**（先同目录，再全仓）展开，支持 3 层嵌套 | 展不开 → 「展开未解析」待确认 |
| 前后端同仓 | 含 `@angular/core`/`react`/`vue` 等标记的文件被剔除 | 同名类（前后端同名 Service）会污染类→文件解析，实测踩过 |

### 2.2 Django

| 索引项 | 提取规则 | 备注 |
|---|---|---|
| 模块（app） | 目录含 `apps.py`（优先）；老项目兜底：含 `models.py` + `__init__.py` + (`views.py` 或 `urls.py`)，且目录名不是 `models` | 只认 `models.py` 会把 `pkg/xxx/models/` 子包误判成 app（实测误判 9 个） |
| 挂载前缀 | 全仓 `urls*.py` 里 `path('x/', include('...{app}.urls'))`；`re_path` 的 `^`/`$` 锚点会被剥离 | 前端 join 用得到 |
| 视图入口（约） | `@api_view` 数 + `@action` 数 + `ViewSet/APIView` 类数 + `router.register` 数 | 只作规模参考 |
| 依赖 | 归属文件里 `from {其他app}...` / `import {其他app}` | 只认本仓已知 app 名 |
| 数据表（定义） | `models.py` 或 `models/` 下 `class X(...Model...)`（大小写不敏感，或类体内有 `db_table`）→ `Meta.db_table`，否则 Django 默认命名 `{app}_{模型名小写}` | `abstract = True` 跳过；`db_table` 在**真实类体**内查找（Meta 常在字段之后） |
| 数据表（使用） | 归属文件 `from x.models import A` / `apps.get_model('x','A')` → A 定义为其他 app 时记为**使用** | 这是"跨模块共享表"的来源（实测 180/310 张跨模块） |
| 非 HTTP 入口 | `@shared_task`·`@app.task`·`@periodic_task` 计数；`@receiver(` 计数 | |

### 2.3 扩展新框架

规则集中在脚本的 `scan_<framework>()` 与正则块；新增框架需实现同样 8 项：模块来源 / 目录归属 / 挂载前缀 / 接口数 / 依赖 / 表（定义 + 使用）/ 非 HTTP 入口 / 守卫。骨架层（`Result` / `build_dependents` / `build_tables_reverse` / 渲染 / `--check` / `--emit-tree`）无需改动。

---

## 3. 脚本参数与退出码

```bash
python3 scan_backend.py --root <根> [选项]
```

| 参数 | 说明 |
|---|---|
| `--root` | 必填。仓库根（monorepo 可给应用根，用 `--include` 收窄） |
| `--config` | 声明文件路径（默认 `{root}/.fe-index/config.json`，**存在则自动读取**） |
| `--app` | 声明文件含多个后端应用时选哪个（按 slug；也可用 `--slug`） |
| `--framework` | `auto`（默认）/ `nestjs` / `django`；声明文件可覆盖 |
| `--include` / `--exclude` | 路径 glob，可重复。`**/` 按 gitignore 语义（可匹配零层目录） |
| `--experts-dir` | 额外专家资产目录，可重复（默认探测 `{root}/.module-experts/`、`{root}/module-experts/`） |
| `--slug` | 应用标识（默认取根目录名） |
| `--format` / `--out` | `md`（默认，单文件全文）/ `tsv` / `json`；`--out` 写文件 |
| `--emit-tree <dir>` | **一键落盘**：`index.md` + `modules/*.md` + `tables.md` + `meta.json` |
| `--max` | 模块数上限（默认 500，硬上限 5000）；超限时截断并记「待确认」 |
| `--dump-config` | 只探测框架与约定（阶段 1 用） |
| `--check --index <dir>` | 新鲜度闸门（消费模式必跑） |
| `--verbose` / `--version` | 统计到 stderr / 版本 |

**退出码族（与 `frontend-index` 同口径）**：

| 码 | 含义 | 处置 |
|---|---|---|
| 0 | 成功 / 索引新鲜 / 范围内无变化 | 继续 |
| 2 | 未识别框架与路由约定 | `--framework` 指定或收窄 `--include` |
| 3 | 根目录不存在 / git 不可用 / 记录的 commit 不可达 | 修正参数；不可达时建议重建 |
| 4 | 识别到框架但零模块 | 检查 `--include` |
| 5 | 入参非法（如 `--max` 超硬上限、`--check` 缺 `--index`） | 修正参数 |
| 6 | 索引过期（范围文件有变化） | 先问用户是否重建（`--emit-tree` 覆盖） |
| 7 | `--check` 时 `meta.json` 缺失或没有 commit | 按"无新鲜度信息"处理，建议重建 |

---

## 4. 证据分级与「待确认」规则

| 级别 | 含义 | 表现 |
|---|---|---|
| 🟢 | 模块边界有框架声明（`@Module` / `AppConfig`） | 模块卡「置信度」 |
| 🟡 | 模块由兜底规则认定（无 `AppConfig` 的 Django app） | 同上 |
| 🟡 | 表名是框架默认命名（Django `{app}_{模型}` / TypeORM 类名推断） | 表名后标 `⚠︎默认命名` |
| `[待确认]` | 展不开的数组 / 找不到声明的 token / 同类多候选 | `index.md` 第 5 节 |

**待确认的 6 种类型（实测分布）**：

| 类型 | 触发条件 | 处置建议 |
|---|---|---|
| `展开未解析` | `...X` 的定义不在扫描范围（跨包）或不是简单数组（条件表达式） | 跨包 → 扩大 `--include` 后重跑；条件表达式 → 人工确认后可在阶段 3 补注 |
| `模块未解析` | `imports` 里 `*Module` 但全仓无该模块类（且非框架模块） | 多为动态模块 / 共享包 → 模块卡里如实保留 |
| `控制器未解析` | `controllers` 声明的类全仓无定义 | 共享包 → 扩大范围或保留 |
| `非实体 token（接口）` | `@InjectRepository(IEmail)` 用的是接口 token（自定义 provider） | **正常**：无表可映射，不是缺陷 |
| `表名未解析` | 实体类全仓无 `@Entity` 声明 | 跨包实体 / 动态注册 → 扩大范围或保留 |
| `默认命名表名` | 未显式声明表名 | Django 默认命名是框架规范（聚合一条）；TypeORM 逐条列出待核对 |

**待确认条数上限**：`MAX_PENDING = 200`。超限时**不静默丢弃**——追加一条 `待确认已截断` 记录（否则"待确认 N 条"会被误读成全部）。遇到它说明扫描范围过宽，收窄 `--include` 或分应用建库后重跑。

**纪律**：宁可缺，不给错。任何"看起来完整"的补全（猜表名、猜模块、猜接口）都比缺失更糟。

### 4.1 声明文件（`.fe-index/config.json`，与 `frontend-index` 共用）

```json
{
  "apps": [
    { "kind": "frontend", "slug": "xpert-cloud", "root": "/root/xpert",
      "include": ["apps/cloud/src/app/**"], "routes": ["apps/cloud/src/app/**/*routing*.ts"] },
    { "kind": "backend", "slug": "xpert-server", "root": "/root/xpert",
      "include": ["packages/server-ai/src/**", "apps/api/src/**"], "framework": "nestjs" }
  ]
}
```

- **一个应用一条**；两个 skill **只取自己 `kind` 的条目**（缺省：本 skill 视为 `backend`），互不干扰
- **查找顺序**：`--config` 显式路径 → `{root}/.fe-index/config.json` → **逐级向上 ≤3 层**（monorepo 里 `--root` 给应用子目录、声明在仓库根时必需；用上层声明会打印来源路径，不静默）
- **分级失效（关键）**：显式 `--config` 或默认路径的声明不可用 → **报错退出 5**（那是用户/本项目自己的声明）；**向上找到的上层声明**不可用（非法 JSON / 无后端应用 / slug 不匹配 / 多应用且未指定）→ **打印一行说明后忽略**，按 CLI 参数继续。**上层声明不得拦下原本正常的扫描**（实测踩过）
- `root` 相对声明文件所在目录解析（声明在 `{root}/.fe-index/` 时基准上移一级）
- 支持注释（JSONC）；CLI 显式传入的参数**优先于**声明
- 声明不可用（非法 JSON / 无匹配 slug）→ 退出码 5，**不静默回退**到猜测

---

## 5. 实测数据与已知坑

### 5.1 两靶子实测

| 靶子 | 框架 | 规模 | 扫描耗时 | 产出 |
|---|---|---|---|---|
| `/root/xpert` | NestJS | 3183 个 TS 文件（含前端 1016 个被剔除） | **0.5s** | 模块 125 · 接口 806 · 表 122 · 依赖边 428 · **事件/命令边 116** · 待确认 9 |
| `/root/bk-monitor/bkmonitor` | Django | 5530 个 PY 文件 | **1.3s** | 模块 22 · 表 310（跨模块共享 180）· 依赖边 112 · 待确认 1 |

**交叉验证**：
- NestJS 侧"接口 806"与接口级实现（v1，逐 `@Get` 提取 + handler 归属）完全一致 → controller 解析正确
- **事件/命令边抽样 10/10 双向通过**（源模块目录 `grep -rlF "new X("` + 目标模块目录 `grep -rlF "Handler(X)"` 都能命中）
- 表反查抽样：`data_source` → 7 个模块（metadata 36 次使用）等，与源码 import 关系一致

### 5.2 已知坑（都在实现里修过，改脚本时别退回去）

| # | 坑 | 现象 | 修法 |
|---|---|---|---|
| 1 | `@Controller()` 无路径很常见 | 模块前缀显示为空，被误读成"没有 API" | 用方法路径首段做提示（`/api` + 方法路径 `x`、`y`） |
| 2 | `controllers: [...Controllers]` 数组展开 | 控制器全丢 | 建常量数组索引，跟随 import 展开（最多 3 层） |
| 3 | `@Entity('import-record')` 带连字符 | 真实体漏检 | 表名字符集放宽为 `[^'"]+` |
| 4 | `@Entity` 与 `class` 之间隔 13 行装饰器 | 实体漏检（模型表变"未解析"） | 窗口 400 → 1500 字符 |
| 5 | `getRepository(url)` / `parseGithubRepository(x)` | 假实体 `url` / `existing` / `item` | 实体名限定 `[A-Z]` 开头 + `\bRepository` |
| 6 | `TypeOrmModule` / `CqrsModule` 等框架模块 | 刷「模块未解析」噪声 | 框架模块白名单 + 前缀正则，只进 `libs` |
| 7 | `Repository<T>` 泛型参数 | 假实体 `T` | 泛型名黑名单 + 长度过滤 |
| 8 | Django `db_table` 在 `Meta` 里（字段之后） | 显式表名被误判为默认命名 | 用**类体边界**（缩进回顶层）取值，不用固定窗口 |
| 9 | Django `class X(BaseModel)` 自定义基类 | 模型漏检（248 处 `db_table` 只认一半） | 基类名含 `model`（忽略大小写）或类体内有 `db_table` |
| 10 | Django `pkg/xxx/models/` 子包 | 误判成 app（实测 9 个） | app 识别只认 `apps.py`；兜底规则排除目录名 `models` |
| 11 | Django 只记"谁定义表" | 「改表通知谁」答不出（跨模块共享 0） | 两遍：先建全局模型索引，再按 import / `get_model` 记**使用** |
| 12 | `re_path(r'^uptime_check/')` | 前缀带 `^` | 剥离 `^` / `$` 锚点 |
| 13 | **各模块各有一个同名 `CommandHandlers` 数组**（在各自的 `commands/handlers/index.ts`） | 展开时盲选第一个候选 → 把别模块的 handler 算进本模块（实测 **54 个模块"都发送"同一个 Command**） | 展开只在「同目录 → **模块目录树内唯一** → 同包唯一」时进行；多候选不猜并记「展开未解析」 |
| 14 | 同名类跨包回退（`Symbols.resolve_class` 的 ambiguous 标记） | `controllers`/`providers` 声明解析到**别的包的同名文件** → 跨包文件混入模块归属（实测 AIModule 混入 5 个 `packages/server/src` 文件） | 歧义时**不猜**：跳过并记「同名类未归属」 |
| 15 | `--check` 的 `scope` 多范围 | 拼成 `"packages/**, apps/**"` 当**单个** pathspec → git 匹配不到 → 变化全漏 → 错报"索引可用"（**静默假阴性**） | `scope` 存数组，一个 glob 一条 pathspec；`frontend-index` 同口径已修 |
| 16 | 事件边的来源文件被"组合"进多个模块 | 同一 handler 文件被多个模块 spread 引进 → 多个模块都被算成"发送方" | 事件边只取**模块自有文件**（`owned`），组合文件里的发送归其 home 模块 |
| 17 | **文档承诺了脚本没实现的能力**（声明文件"零猜测"） | 首版 SKILL.md 写了"有 config.json → 直接用其 apps[] 声明"，但脚本当时**根本没有读取逻辑**（`--config` 参数都不存在） | 补实现（`load_jsonc` + `merge_config` + `--config`/`--app`）；**纪律：写进文档的能力必须在同轮实现并实跑验证** |
| 18 | 两个 skill 共用 `config.json` 时互相选中对方的 app | 前端脚本原来取 `apps[0]` | 两端都按 `kind` 分流（缺省各自认自己） |
| 19 | 声明文件只查 `{root}/.fe-index/` | `--root` 给应用子目录、声明在仓库根时**静默没读到** → 重建退化回猜测 | 逐级向上查找 ≤3 层，命中即提示来源路径（两端同口径） |
| 20 | 向上查找到**别人的/过期的**上层声明 | 被当成本项目声明 → **拦下原本正常的扫描**（实测：`--root bkmonitor` 撞上上层的前端声明，直接退出 5） | 分级失效：显式/默认路径报错，**上层声明只在无歧义时采用**，否则说明一行后忽略 |
| 21 | 老声明（无 `kind`）被对方认领 | 前端声明被后端当成自己的 → 无后端应用/拦路 | 按特征键推断 kind（`routes`/`pagesDirs`/`apiDirs`/`aliases` → frontend；`framework`/`expertsDir` → backend），推不出才归"双方兼容" |

---

## 6. 抽样核对方法（可选验收）

脚本给的是机械结果，抽 5-8 条回源码核对即可建立信任：

```bash
# A. 模块依赖：抽一个模块，把 JSON 的 deps 与源码 imports 对比
sed -n '1,60p' <模块目录>/<x>.module.ts | grep -n "imports:\|Module,"

# B. 表反查：抽一张表，确认它确实是那些模块在用
grep -rn "db_table = \"<表名>\"\|@Entity('<表名>')" --include=*.py --include=*.ts <根>

# C. 挂载前缀：抽一个模块，确认 controller 前缀与全局前缀合成正确
grep -rn "@Controller(" <模块目录>/*.controller.ts

# D. 事件/命令边：抽一条边，双向验证（应两边都命中）
grep -rlF "new <CommandName>(" <源模块目录>          # 发送侧
grep -rlF "Handler(<CommandName>)" <目标模块目录>     # 接收侧
```

**判定标准**：核对项与源码一致即通过；不一致要么是脚本缺陷（回 `5.2` 对照），要么是该进「待确认」的项——**不允许"看起来对"就放过**。

---

## 7. 跨端 join 口径（与 `frontend-index` 组合）

```
后端 index.md:  模块 → 挂载前缀（"/" + global_prefix + controller前缀）
                          ↓ 前缀匹配
前端 apis/*.md: 接口路径 → 页面（file:line）
```

- 匹配用**前缀包含**，不是全等（前端 baseURL 可能已含 `/api`）
- `@Controller()` 无前缀的模块：用模块卡的「方法路径」提示（`x`、`y`）与前端接口路径做包含匹配
- 前端接口路径中的路径参数（`:id` / `${id}`）在比较前归一化
- 结论表述要带**两端口径**：`改 POST /api/x/plans → 影响后端模块 membership（定义表 plans）+ 前端页面 3 个`
