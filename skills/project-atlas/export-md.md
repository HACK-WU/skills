# 导出为 Markdown（export-md）

> 与 HTML 分发并列的第二个出口：HTML 给"看"，Markdown 给"改 / 进 Wiki / 进文档库"。
> 两个入口输出**逐字节一致**（md 部分实测），共用同一份模板。

## 一、两个入口

| 入口 | 命令 / 操作 | 适用 |
|---|---|---|
| **页面按钮** | 页面顶部「导出 ↓」 | 已经打开图集的人随手导一份 |
| **命令行** | `export_markdown.py` | CI 产物、批量、不想开浏览器 |

```bash
# 页面：点一下即可（纯前端，不依赖脚本）
# 命令行：
python3 <skill>/scripts/export_markdown.py <图集目录> dist-md/          # 输出目录
python3 <skill>/scripts/export_markdown.py <图集目录> atlas-md.zip      # 直接出 zip
python3 <skill>/scripts/export_markdown.py <图集目录> dist-md/ --no-images   # 不带图（md 也不写图引用）
python3 <skill>/scripts/export_markdown.py <图集目录> dist-md/ --clean      # 先清空目标目录
```

`<图集目录>` 可以是目录树（`site.json` + `nav/`），也可以是单文件 `atlas.config.json`。

## 二、产物结构

```
<站点名>-<日期>.zip
├── README.md                      标题 / 副标 / 导语 / notice / 基线 / 目录树（带相对链接）
└── 01-架构总览/                    数字前缀 = 侧栏顺序
    ├── 运行时架构总览.md           ← 文件名 = page.title（不是 pid）
    └── images/
        └── overview.svg            图源仍用 pid，原样导出，含内联字体，可单独打开
```

- **md 文件名用页面标题**，读者在文件树里就能认出是哪一页；图片仍用 `pid`（内部资源，读者不常翻）
- 文件名规则（`safe_name` / `safeName`，两处同口径）：
  - 非法字符换成连字符：`/ \ : * ? " < > |` 以及**中英文冒号**（`后台进程：从写入到被读到的闭环` → `后台进程-从写入到被读到的闭环`）
  - 超过 60 字截断并加 `…`（完整标题仍在正文 H1）
  - **同一分类目录内**重名追加 `-2`、`-3`（不同目录允许同名）
  - 标题为空时回退用 `pid`
- 目录层级与侧栏大纲**一一对应**；两级分类（`_group.json` 里带 `page`）同样是"分类目录 + 一个 md"
- 图片用 SVG：矢量、文本可搜、GitHub / Typora / Obsidian / VSCode 均支持

## 三、单页 md 模板

**单图页**：

```markdown
# {title}

> {type} · 生成于 {generated_at} · 基线 {branch}@{baseline}

{summary}

![{title}](./images/{pid}.svg)

## 怎么读这张图

- **{point[0]}**：{point[1]}

## 对应代码

> 生成时的代码快照，不代表仓库当前 HEAD。

### `src/mcp-server.ts:1065-1080` · daemon · startMcpServer
MCP 入口：三种运行形态与会话在这里分流

```ts
export async function startMcpServer(ctx) {
  // …
}
```

## 外部依赖                       ← 仅当有 external 条目

| 外部服务 | 归属 | 契约 | 回程 |
| --- | --- | --- | --- |
| etl | 数据平台团队 | MQ · topic kb.changed · at-least-once | → callback（回写 zvec + POST /internal/index-ready） |

## 衔接关系                       ← 仅当有 links

**标识符（后续操作靠它定位）**

| 衔接键 | 流转路径 | 形态 | 持久化 | 说明 |
| --- | --- | --- | --- | --- |
| data_id（1:N） | etl → callback → store → query | string(32) | scope_meta.remote_id | 后续查详情、对账都靠它 |

**传递内容（不构成标识符）**

| 内容 | 产出 → 消费 | 说明 |
| --- | --- | --- |
| kb.changed | outbox → etl | 异步投递，at-least-once |

> 另有 1 条状态型返回（成功 / 失败）不构成衔接键：callback → etl

## 参考文档

- docs/architecture.md
```

**多图页**：每张图各成一节，图下的解读降一级；**代码表 / 外部依赖 / 衔接关系仍是整页一份**（同一 id 不在两张图下面各列一遍）：

```markdown
# {title}

> {N} 张图 · 生成于 … · 基线 …

{summary}

## 图 1 · {figures[0].name}

> 这张图回答：{figures[0].q}

![{figures[0].name}](./images/{pid}.svg)

### 怎么读这张图

- **…**：…

## 图 2 · {figures[1].name}

> 这张图回答：{figures[1].q}

![{figures[1].name}](./images/{pid}-{figId}.svg)

### 怎么读这张图

…

## 对应代码                      ← 整页合并
…
```

规则：

- 图源命名：第 1 张 `images/{pid}.svg`，其后 `images/{pid}-{figId}.svg`
- 每个有 `file` 的节点一节：`### \`路径:起-止\` · id · 符号` + why + **代码块**（按扩展名加语言标记）
- 代码块取 `snippets[pid][id].snippet`；没采集到给一行提示，不静默留空
- `concept` 不进「对应代码」；`external` 进「外部依赖」
- 同一标识符的多段流转**合并成一行**（`etl → callback → store → query`），不是三行重复
- 不想带代码正文（体积敏感）加 `--no-code`：只留路径与说明；页面「导出 ↓」与命令行默认**都带代码**，保证两者逐字节一致

## 四、实现要点（逐个踩过）

| 点 | 说明 |
|---|---|
| ZIP 的 UTF-8 标志位 | 本地文件头与中央目录都要置 `0x0800`（bit 11），否则 Windows 解压中文目录名乱码 |
| 图源取值优先级 | 内置示例态取 `template[data-demo="1"]`；运行时真实配置必须 `fetch(page.svg)`——框架自带示例图与真实页 **id 同名**，直接取 template 会拿到 3 KB 的示例图而不是 170 KB 的真图 |
| `<svg>` 补 xmlns | archify 导出的 SVG 省略 xmlns（内联进 HTML 时不需要）。导出成独立文件必须补；判断要针对 `<svg ...>` 整个标签——`indexOf('>')` 会先命中 XML 声明，固定截断前 N 字符也会误判 |
| 字体要补回去 | build 会把各图 `@font-face` 抽到壳层去重，从 DOM 取图时字体已不在 SVG 里；导出需从 `document.styleSheets` 取回并注入 |
| 别给手绘图补字体 | 手绘 SVG 本就用系统字体。无差别补会让每张图凭空多 90 KB（4 页包 89 KB → 440 KB）；靠 build 打的 `data-fonts="1"` 标记判断 |
| md 与图必须同步 | 缺图源 / `--no-images` 时，md 里**不能**再写 `![](./images/x.svg)`，否则解压后是碎图。两个入口都要按"这张图真的导出了"来决定是否写引用 |

命令行实现更简单：直接读 `views/*.svg` 原文件，字体本就在原位，不需要补字体那套逻辑（因此两边的 SVG 会有几百字节结构差异，但渲染结果一致）。

## 五、已知限制

| 限制 | 影响 | 应对 |
|---|---|---|
| 企业 Wiki 不支持内联 SVG | md 里图片显示空白 | 用 `atlas.html` 交互版；或后续加 PNG 栅格化 |
| 包体积 | 4 页约 89 KB（压缩后），20 页约 400 KB | 图片占大头（archify 单图约 170 KB，含字体） |
| 不含代码正文 | 只有「路径:行号 + 符号」表 | 需要完整代码回页面点节点 |
| 图源缺陷原样带走 | md 里的 `images/*.svg` 是图源原样（只补 xmlns），黑块/缺样式会一起进文档库 | 导出前跑 `check_svg.py`；`export_markdown.py` 遇到图源 error 会直接中止 |
| 需解压后查看 | zip 内预览时相对路径 `./images/*.svg` 解析不到，且部分查看器不渲染 md | 解压后再看，或直接看 `atlas.html` |

## 六、验证方法

```bash
# 1. 导一份出来
python3 <skill>/scripts/export_markdown.py <图集目录> /tmp/md-out.zip

# 2. 解压后确认三件事
#    - 目录结构与侧栏一致
#    - 随手打开一张 images/*.svg 能独立渲染（不是空白/丢字体）
#    - md 里的图片相对路径指向 images/<id>.svg

# 3. 有 VSCode 的话：Ctrl+Shift+V 开预览，确认图能显示
```

## 七、维护提醒

md 模板有**两份实现**，改动需同步：

| 端 | 位置 |
|---|---|
| 页面内 | `framework/index.html` 的 `pageMarkdown` / `readmeMarkdown` |
| 命令行 | `scripts/export_markdown.py` 的 `page_md` / `readme_md` |

当前靠"两边各导一份、diff md"保证一致（已实测逐字节相同）。新增字段时两边都要改，否则页面导出与命令行导出会分叉。
