# 分发与集成（deploy）

> `build_atlas.py` 产出的 `atlas.html` 是**自包含单文件**：配置、图源 SVG、base64 字体、代码片段全部内联，运行时不再发起任何请求。所以"打包"的本质是**拷一个文件**，不是打包目录。

## 一、标准流程

### 1.1 一条命令（推荐）

```bash
python3 <skill>/scripts/pack_atlas.py <图集目录> dist/
# 压缩包：--zip    自定义文件名：--name 项目知识地图
# 连源文件一起（对方要维护）：--with-source —— 带上 site.json / nav/ / views/ / snippets.json
# 清空输出目录（避免上一版遗留文件混进来）：--clean
```

清单只统计**本次产出**；若 `dist/` 里还有上一版遗留的文件，会单独提示并以 `--clean` 清空。

它依次做四件事，**任何一步失败即终止，不产出"半个包"**：

```
① build    → dist/atlas.html（自包含）
② check    → 0 error 才继续，否则终止并保留产物供排查
③ 收拢依赖 → interactive 指向的 HTML 按原相对路径拷进 dist/
④ 写清单   → MANIFEST.txt（文件 / 大小 / sha256 前 12 位 / 分支与 commit）
```

跑完看 `dist/MANIFEST.txt` 就知道该拷什么、多大、哪个版本。

**`--with-source` 的可重建性**（已实测）：把 `dist/` 整个拷到另一台机器，直接当图集目录跑 `build_atlas.py dist/ out.html`，产物与原 `atlas.html` **字节完全一致**（sha256 相同）。所以带源文件分发后，对方既能看也能改。

### 1.2 分步执行（需要单独控制时）

```bash
SKILL_DIR=<project-atlas skill 目录>

python3 $SKILL_DIR/scripts/build_atlas.py <图集目录> dist/atlas.html
python3 $SKILL_DIR/scripts/check_atlas.py <图集目录> --html dist/atlas.html
cp dist/atlas.html <目标位置>
```

分步时 `interactive` 依赖**不会自动拷贝**，需要自己按第四节 4.1 处理。

### 1.3 另一个出口：Markdown 目录包（可选）

给"要改、要进 Wiki"的人，同一份内容导成 Markdown（页面上的「导出 ↓」按钮与它等价）：

```bash
python3 <skill>/scripts/export_markdown.py <图集目录> dist-md/        # 输出目录
python3 <skill>/scripts/export_markdown.py <图集目录> atlas-md.zip    # 直接出 zip
python3 <skill>/scripts/export_markdown.py <图集目录> dist-md/ --no-images
```

产物：`README.md` + 每分类一个目录 + `<页面>.md` + `images/<页面>.svg`（图源原样导出，含内联字体）。
图用 SVG：GitHub / Typora / Obsidian / VSCode 支持；部分企业 Wiki 不支持内联 SVG，会显示空白。

> 两个出口别混用：HTML 给"看"，Markdown 给"改"。`pack_atlas.py` 不生成 Markdown，见 1.1。

## 二、打包范围

| 文件 | 是否随产物发放 | 依据 |
|---|---|---|
| `atlas.html` | ✅ **唯一必带** | 含全部图源 `<template>`、字体 `@font-face`、页面配置、`snippets`（`baked: true`） |
| `views/*.svg` | ❌ | 已内联 |
| `snippets.json` | ❌ | 已内联 |
| `atlas.config.json` | ❌ | 已内联 |
| `site.json` / `nav/` | ❌ | 已内联 |
| `framework/index.html` | ❌ | 已在产物里 |
| `interactive` 指向的 HTML | ⚠️ **条件带上** | 见第四节陷阱 1 |

实测：把 `atlas.html` 拷进一个空目录改名 `index.html`，`file://` 双击可正常翻页、点节点看代码、字体正常。

## 三、四种落地形态

### 3.1 本地 / U 盘 / 邮件附件

```bash
cp dist/atlas.html ~/Desktop/项目知识地图.html
```

- 双击即开，无需服务、无需联网
- 直接发文件给同事即可
- 体积参考：4 页 ≈ 238 KB，8 页 ≈ 450 KB，20 页 ≈ 1.1 MB

### 3.2 静态服务器（nginx / OSS / GitHub Pages）

```bash
# 建议放进独立子目录，避免与其他站点抢 root
mkdir -p /var/www/atlas && cp dist/atlas.html /var/www/atlas/index.html
```

nginx 最小配置：

```nginx
location /atlas/ {
    alias /var/www/atlas/;
    index index.html;
    # 单文件、无接口，不需要额外 proxy 规则
}
```

- 纯静态，无后端依赖
- 若要让别人直接访问，注意机构内的资源发布规范（内网/外网、是否需要审批）

### 3.3 嵌进其他系统（iframe）

```html
<iframe src="/atlas/index.html" title="项目知识地图"
        style="width:100%;height:100vh;border:0;display:block"></iframe>
```

- 框架不设 `X-Frame-Options`，可被同源/跨源引用
- 高度用 `100vh` 或由外层 flex 决定；框架自身按视口做响应式
- 容器宽度 < 1080px 时自动切窄屏形态（侧栏折叠为「目录」按钮、抽屉改底部）

### 3.4 企业 Wiki / 文档系统 / 邮件正文

这类系统通常**只允许粘贴 HTML 片段**，或有两种典型限制：

| 限制 | 现象 | 处理 |
|---|---|---|
| 过滤 `<script>` | 图能显示，但点节点、翻页全失效 | 改为「附件下载」或「iframe 引子目录」，不要内联进正文 |
| 只接受 http(s) 图片，剥离内联 base64 | 图标/字体丢失，版式错乱 | 走 3.2 起静态服务，用 iframe 引 |
| 限制单文件大小 | 上传失败 | 减页数（每页约 60 KB） |

**判定方法**：先发一个 4 页的小图集试水，能点开节点再发完整版。

## 四、已知陷阱

### 4.1 `interactive` 外链（pack 已自动处理）

如果某页配置了：

```jsonc
{ "interactive": "views/overview.architecture.html" }
```

build 只内联 **SVG**，这个 HTML 是外链，不会自动进产物。

| 做法 | 结果 |
|---|---|
| `pack_atlas.py` | ✅ 自动把它拷到 `dist/views/...`，保持相对路径，并写进清单 |
| 手动 `build` + `cp` | ⚠️ 需要自己拷，否则分发后点「交互版 ↗」404 |

**建议**：不需要交互版就别配这个字段——少一个依赖，产物永远只有一个文件。

### 4.2 别在目标系统上二次编辑

产物是 build 的结果，任何手工修改在下次 build 时都会被覆盖。要改就改 `site.json` / `nav/` / `views/`，再重新 build。

### 4.3 版本信息要跟着走

顶栏基线条（`基于 master @ commit 生成 · 时间`）来自配置，会随产物一起走。分发后看这条就知道内容对应哪个代码版本——**别在拷贝后改文件名或删除这行**。

### 4.4 大图集的打开耗时

单文件 1 MB 左右浏览器解析无感；超过 3 MB 会有明显首屏延迟（`check_atlas.py` 会在此区间告警）。超过 10 MB 直接拒绝产出。

## 五、分发前自检

```text
- [ ] check_atlas.py --html 返回 0 error
- [ ] 目标系统上实际打开过一次（不是只看构建机）
- [ ] 点开至少两个节点，代码行号与内容对得上
- [ ] 翻到最后一个分类，图完整、无空白区
- [ ] 若配了 interactive：对应 HTML 已一并拷贝且能打开
- [ ] 基线条显示的 commit 与当前发布版本一致
- [ ] 窄屏（<1080px）打开一次，侧栏折叠与底部抽屉正常
```

## 六、回滚

单文件分发的好处是回滚简单：保留上一版 `atlas-YYYYMMDD.html`，出问题换回文件即可，无数据库、无缓存失效问题。

建议命名带上日期与 commit 短哈希：

```
atlas-20261124-1c3dabf.html
```
