# 网页索引 · 执行细则

配套资源：`skills/web-index/SKILL.md`（SSOT，规则定义在此）、`scripts/fetch_site_map.py`（确定性抓取）。本文件只写落地口径。

---

## 1. 地图抓取四级链

脚本内部自动按此链降级，**AI 不要手工重实现**：

| 级 | 目标 | 命中判据 | 失败后 |
|----|------|----------|--------|
| ① | `{scheme}://{host}/llms.txt` | 200 且内容含 markdown 链接或 URL | 降级 ② |
| ② | `{scheme}://{host}/sitemap.xml` | 200 且为 `<urlset>` 或 `<sitemapindex>` | 降级 ③ |
| ③ | `--sitemap` 手工指定的地址 | 同上（`sitemap_index.xml` / `sitemap.txt` / 页面里写明的地图地址） | 退出码 2 |
| ④ | 无地图 | — | AI 用 `web_fetch` 抓起始页从导航提取（见下） |

**② 的递归**：`sitemapindex` 会递归取子 sitemap，**最深 2 层**、子 sitemap 最多 20 个，防止套娃。

**① `llms.txt` 的格式要点**：标准形如 `# 标题` 分区 + `- [页面名](url)：描述`。脚本会保留**最近一级标题**作为分区建议、`()` 后的描述作为「我要…」的第一手素材——这是四级链里唯一自带用途描述的来源，命中它时质量最高。

**①-a 分层索引（Section indexes）**：有些站点的根 `llms.txt` **不列页面，只列各分区的子 `llms.txt` 指针**（实测 `docs.langchain.com` 即如此，根索引 176 条全是 `.../llms.txt`）。脚本会自动检测：根条目若以 `/llms.txt` 结尾即视为分层索引，按**起点 URL 所在分区、最长前缀匹配**跟随一层子索引（如起点 `/oss/python/langchain/overview` → 跟到 `/oss/python/langchain/llms.txt`）。起点不落在任何分区内时，根内容无页面可用 → 转下一级数据源。

> 匹配错了用 `--llms /oss/python` 手工钉死（脚本 `try_llms_txt` 只跟随**一层**，不递归）。

**① 的两个实操发现（实测 Anthropic 文档站得出）**：
- **`.md` 端点要直接照抄**：`llms.txt` 常给出 `…/xxx.md`（站点专为 LLM 提供的 Markdown 版）。**原样保留，不要改回 `.html`**——后续 `web_fetch` 它拿到的是干净 Markdown，省掉 HTML→MD 转换与正文噪声。
- **地图 URL 可能跨主机**：`docs.example.com/llms.txt` 给出的链接可能全部指向 `platform.example.com`。一切 URL 已做绝对化解析，但 robots 检查只针对**起始 URL 的 host**（见 §4 已知局限）。

**④ 无地图时的抓取纪律**：
1. `web_fetch` 起始页，只提取导航/侧边栏里的链接与锚文本
2. 沿一级导航页再 fetch 一轮收集二级链接，**总共不超过 5 次 fetch**
3. 每个链接若没有锚文本可用，`[待确认]` 标在「我要…」列，不要自己编

---

## 2. 脚本参数与退出码

```bash
timeout 30s python3 {skill-dir}/scripts/fetch_site_map.py <起始URL> [选项]
```

零第三方依赖，Python 3.8+ 直接跑。脚本内部对每个请求都带 `--timeout`，但**命令仍要前置 `timeout`** 兜住"卡在连接建立 / 超大 sitemap 解析"这类内部超时管不到的场景。

| 参数 | 默认 | 说明 |
|------|------|------|
| `<起始URL>` | 必填 | 站点任意页面 URL，脚本自动取 scheme + host |
| `--scope <前缀>` | 无 | 只保留 URL 路径以该前缀开头的条目；可重复传参取并集 |
| `--exclude <子串>` | 无 | 丢弃含该子串的 URL；可重复（用于排 blog / changelog / 多语言）。**注意口径**：它匹配整条 URL（含主机名），而 `--scope` 只匹配 path 前缀——`--exclude team` 会连主机名含 team 的条目一起杀掉 |
| `--max <N>` | 300 | 硬上限 1000 |
| `--sitemap <URL>` | 无 | 手工指定地图地址（跳过 ①② 直接走 ③） |
| `--llms <路径>` | 自动 | 手工指定要跟随的 `llms.txt` 子索引（如 `/oss/python`），分层索引自动匹配错误时使用 |
| `--out <文件>` | stdout | 输出到文件，Markdown 表格 |
| `--format {md,tsv}` | md | `tsv` 便于管道给 AI 直接看 |
| `--timeout <秒>` | 15 | 单个请求超时 |
| `--verbose` | 关 | 打印每一步尝试了哪个地址、拿到多少条 |

**退出码**

| 码 | 含义 | AI 处置 |
|----|------|---------|
| 0 | 成功 | 用输出进阶段 3 |
| 2 | 无地图可用 | 转人工提取（见 §1 ④） |
| 3 | 网络失败 / 超时 / 非预期响应 | 报告用户；换入口页重试一次，仍失败则结束 |
| 4 | 有地图但过滤后为空 | 多半 `--scope` 前缀写错，去掉或用更短前缀重试一次 |
| 5 | 入参非法（URL 缺 scheme/host、`--max` 超硬上限、`--sitemap` 指向的地图为空） | **修正参数后重跑**——属于调用方错误，重试同一命令必然复现 |

> `--sitemap` 的两种失败分开算：**地址不可达 / 404 → 3**（网络层）；**地址可达但解析出 0 条 → 5**（给错了地图）。实机验证：`--sitemap https://example.com/nope.xml` → 3。

脚本只用 Python 3 标准库（`urllib.request` + `xml.etree` + `re`），**零依赖**；单次请求、串行拉取，不做并发。

---

## 3. 分区拆分算法

**分区字段从哪来**（决定上面的分组能不能生效，务必照抄而非自造）：

| 来源 | 分区取值 | 说明 |
|------|----------|------|
| `llms.txt` | 该条之前最近的一级标题 | 站点自己维护的分类，质量最高，直接用 |
| `sitemap` | **`--scope` 前缀之后**的第一个路径段 | 不给 scope 时退化为绝对路径首段；若该段是叶子页（带扩展名）则用其父目录，没有父目录则返回空串（表示无天然分区） |

> 为什么是"scope 之后"：文档站常把全部页面放在同一一级目录下（`/docs/...`），取绝对路径首段会得到恒定的 `docs`，几百条挤进一个分区 = 分区失效。实机对照（postgresql.org，`--scope /docs`）：修复前分区全为 `docs`；修复后为 `faq` / `online-resources` / `19` 等可用分组。

```
输入：候选链接 N 条（带分区建议）

N ≤ 15        → 不分区，全部写进 index.md 的路由表
N > 15        → 按分区字段分组（字段来源见上表）
分区为空       → 先按页面名前缀人工归并再分组（空名分区会生成 topics/.md，属产物损坏，禁止）
某分区 > 60   → 该分区按二级路径段再拆，文件名 {分区}-{二级}.md
全是散层 URL（无共同目录） → 按「URL 首个路径段」分组；仍无规律则按字母序切 chunk-{a-h} 并如实标注"分区无语义"
```

**分区落在无语义层时**：多版本文档站的 URL 形如 `/docs/{版本}/{主题}/...`，「scope 之后第一段」会落到**版本号**上（postgresql.org 实测得到 `19` / `faq` / `online-resources` 混在一起）。版本号对用户没有导航价值 → 用 `--scope /docs/19` 把范围钉死在单版本内重跑，让分区落到主题层。

`index.md` 的「高频直达」取**跨分区覆盖面最广的 5-10 条**（概念入口、概览页、快速上手），不要按分区列表前几条机械截取——后者会把同一个分区塞满直达区。

---

## 4. robots / 限流 / 礼貌

- 脚本会读 `{host}/robots.txt`，被 `Disallow` 的路径（`Disallow: *` 除外所有路径）会被剔除并在 stderr 提示；**解析失败视为允许**（不作为放行依据的判断）
- 单站点单次运行只做一次"发现 + 拉取"，不循环重试
- 返回 403 / 429 立即停止（退出码 3），**不换 UA 重试**——这是站点明确的拒绝信号
- 只抓地图与链接，不抓正文，天然低流量；若某次确实要 fetch 正文（阶段 3 补用途），控制在每次 1 页

**已知局限**：robots 检查只对**起始 URL 的 host** 生效。地图里出现跨主机链接时（如 `docs.x.com/llms.txt` 指向 `platform.x.com`），目标主机的 robots 不会被检查——AI 在该环节的把关责任是：发现索引条目明显属于私有/付费区域时剔除或标 `[待确认]`。

---

## 5. 完整示例：给 MinIO 文档建索引

**用户**："我要按 MinIO 官方文档做对象存储，后面会反复查，先给这个站建个索引。"

阶段 0：明确"后面反复查" → ✅ 建。

阶段 1：确认范围。

```text
站点：MinIO Docs  (https://min.io/docs/minio/linux/index.html)
产出目录：.web-index/minio/
覆盖范围：/docs/minio/linux/
条目上限：300
```

阶段 2：

```bash
python3 scripts/fetch_site_map.py https://min.io/docs/minio/linux/index.html \
  --scope /docs/minio/linux --exclude /blog --max 300 --out /tmp/minio-map.md
```

输出片段（`--format md`）：

```markdown
| # | URL | 来源 |
|---|-----|------|
| 1 | https://min.io/docs/minio/linux/reference/minio-mc.html | sitemap |
| 2 | https://min.io/docs/minio/linux/operations/network-encryption.html | sitemap |
```

阶段 3：补齐用途列后的产物片段（`topics/operations.md`）：

```markdown
| 我要… | 去哪一页 | 锚点 | 关键词 |
|-------|----------|------|--------|
| 给 MinIO 配 TLS 证书 | [Network Encryption](https://min.io/docs/minio/linux/operations/network-encryption.html) | #tls | TLS、证书、HTTPS |
| 查服务端加密怎么开 | [Server-Side Encryption](https://min.io/docs/minio/linux/operations/server-side-encryption.html) | | SSE、KMS、加密 |
```

阶段 4 落盘时除 `index.md` / `topics/operations.md` 外，**同步在 `.web-index/INDEX.md` 追加一行**（站点 / slug / 起始 URL / 范围 / 条数 / 日期）。缺这行，下一次会话的 AI 不会知道索引存在。

阶段 5 输出结算后，本次会话后续遇到"MinIO 怎么配证书"时按使用协议处理：

1. 读 `.web-index/minio/index.md` → 分区索引显示 `operations` 分区含"网络加密"
2. 读 `topics/operations.md` → 命中第 1 行
3. `web_fetch` 带 `#tls` 锚点的 URL 取正文作答

对比无索引时：至少 1 次 `web_search` + 2-3 次试探性 `web_fetch` 才知道该翻哪页，且下次会话要重来一遍。

---

## 6. 示例 B：sitemap 来源（没有 llms.txt 的站）

这类站点占多数，也最容易在分区上翻车，单独给一份：

```bash
timeout 30s python3 {skill-dir}/scripts/fetch_site_map.py https://www.postgresql.org \
  --scope /docs/19 --exclude blog --max 300 --out temp/web-index-postgres-map.md
```

输出（实机）：

```markdown
| # | URL | 来源 | 分区建议 | 标题 / 描述 |
|---|-----|------|----------|-------------|
| 1 | https://www.postgresql.org/docs/19/sql-copy.html | sitemap | | |
| 2 | https://www.postgresql.org/docs/19/backup-manifest-format.html | sitemap | | |
```

两列都空。原因是 sitemap 不带用途描述，而这座站的页面是**扁平贴在 `/docs/19/` 下的叶子页**：

- 阶段 3 的「我要…」只能靠 URL 语义推断（`sql-copy.html` → "查 COPY 命令的语法与参数"）
- 分区为**空串**而非每个页面各一个分区——脚本遇到"叶子页直接贴在 scope 下、没有父目录"时故意返回空，意思是"这个结构没有天然分区"，避免编出 300 个每页一分区的假分区
- 处置：按**页面名前缀人工归并**（`sql-*` → `sql`、`backup-*` → `backup`），并在 `index.md` 如实标注"分区为人工归并，非站点原结构"
- 换成 `--scope /docs` 重跑则分区为 `19` / `faq` / `online-resources`（有中间目录时脚本能自动分）——**范围钉死得多深，直接决定分区质量**

**消费模式对照**：两周后用户问"Postgres 的 COPY 怎么写"，AI 读到 `.web-index/INDEX.md` 有 `postgres` 一行 → 只读 `.web-index/postgres/index.md` 定位分区 → 读 `topics/sql.md` → `web_fetch` 命中行 → **不再跑一次脚本**。
