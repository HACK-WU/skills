---
id: REQ-20260730-001
feature: req list 展示优化与分支元数据记录
status: 草案
created: 2026-07-30
updated: 2026-07-30
version: 4
tags: [feat, tool]
depends_on: []
author: AI
document_type: requirement
---

# req list 展示优化与分支元数据记录

## 背景

requirement-mgr（`req` 命令）在日常使用中暴露出两类体验问题：

1. **列表输出不可控**：`req list` 全量输出，需求数量增长后刷屏；无效筛选值（如 `--status sjaksa`）静默返回"（无匹配需求）"，用户和 AI 都会误判为"确实没有该状态的需求"。
2. **元数据与 Git 脱节**：需求生命周期通常对应一个 feature 分支，但 meta.json 无分支字段；`commits` 字段虽已存在，却不在默认展示列，`--id` 详情视图也未展示。

补充走查（delete/id_generator/meta_store/update）后又发现两类系统性盲区，一并纳入本需求：

3. **数据可靠性缺口**：ID 删除后可复用、meta.json 损坏无友好处理、无一致性巡检、归档不可逆。
4. **AI 工作流不友好**：写命令无机器可读输出，AI 只能靠正则抠人类文案。

## 需求清单

### O-01：`req list` 默认展示最近 10 个需求 + `--limit` 参数（P0）

- `req list` 默认只展示按 `updated` 降序的最近 10 个需求。
- 新增 `--limit N` 参数控制展示数量，`--limit 0` 表示展示全部。
- 截断时末行提示总量，如：`共 42 个需求，显示最近 10 个（--limit 0 查看全部）`。
- `--id` 详情模式不受 limit 影响；`--limit` 负值报错退出。
- 【待确认】`--json` 输出是否同样受 limit 约束（倾向一致生效，行为可预测）。
- 同步更新 guide，AI 工作流需全量清单时显式带 `--limit 0`（规避静默行为变更）。

### O-02：meta.json 记录需求对应的分支名称（P1）

- 需求条目新增 `branch` 字段（单值，记录主开发分支）。
- 【待确认】写入方式二选一：
  - 方案 A（推荐）：`req create --branch` / `req update --branch` 显式指定，保持工具零 git 依赖；
  - 方案 B：create 时自动 `git rev-parse --abbrev-ref HEAD` 取当前分支，失败留空（引入 git 依赖，detached HEAD 场景取到 `HEAD`）。
- 旧数据兼容：无 `branch` 字段展示 `—`，读取一律 `.get("branch")`，无需数据迁移。
- `update --branch` 规则（推演补充）：空字符串 `--branch ""` 表示**显式清除** branch 字段；纯空白（如 `"  "`）拒绝；含非空白字符正常写入。

### O-03：`req list` 展示分支名称与关联 commit（P1，依赖 O-02）

- `branch` 加入 `DEFAULT_COLUMNS` 默认列。
- commits 为 hash 列表，默认列仅展示 **commit 数量**（为 0 时显示 `0`），完整 hash 列表在 `--id` 详情视图查看。
- 补现有遗漏：`--id` 详情视图（`_format_detail`）当前不展示 commits，需一并补上 branch 与 commits 展示。

### O-04：`req list --status` 无效值应报错（P0）

- `--status` 传入不在 `requirement_statuses` 白名单内的值时，报错退出并列出有效值（与 create/update 校验风格一致）：
  `错误: 无效状态 'sjaksa'，有效值: 草案, 已确认, ...`
- "已归档"必须在合法集内（`list --status 已归档` 是正当查询）；对未含"已归档"的旧自定义 config，将 `ARCHIVED_STATUS` 并入白名单兜底。
- 同类展开：`--role`、`--category`、`--tag` 存在相同静默吞错问题，一并按各自 config 白名单校验。
- 白名单为空的语义（推演补充）：config 中 `requirement_tags`/`feature_categories` 为空表示"不限制"，此时对应参数**跳过校验**，不得把一切值判非法。

### O-05：删除后 ID 不复用（P0）

- 现状：`gen_next_id` 扫描现存需求取当日 max_seq，删除当日最新需求再创建会**复用同一个 ID**，历史 commit message / 外部文档中的 REQ 引用会指向新需求。
- 修法：meta.json 顶层新增 `id_counters`（按日计数器，只增不减），生成 ID 时取 `max(计数器, 现存扫描值) + 1` 并回写计数器；旧 meta 无该字段时按现状扫描兜底，无需迁移。
- 顺带：当日编号超上限的 `ValueError` 在 create 中友好捕获（当前用户会看到裸堆栈）。

### O-06：meta.json 损坏的友好处理与恢复（P0）

- 现状：`MetaStore.load()` 抛 `JSONDecodeError` 无人捕获，所有命令直接裸 traceback；`backup_enabled` 有 `.bak` 备份但**没有恢复命令**。
- 各命令入口统一捕获 JSON 解析错误，输出友好提示 + 恢复指引（指向 `.bak` 与 `req restore`）。
- 新增 `req restore`：从 `meta.json.bak` 恢复（带 `--dry-run` 预览与交互确认）。
- 推演补充（S3）：
  - `.bak` 不存在时报错退出，并提示开启 `backup_enabled`；
  - `restore` 必须持 FileLock 执行；
  - 恢复时 `id_counters` 取 `max(.bak 值, 当前值)`，防止 O-05 的 ID 复用风险借道回归；当前 meta 损坏不可读时，从损坏文本中正则抢救已发号信息参与合并（实施中发现：损坏场景恰是 restore 主场景，仅靠可读 meta 合并会失效）；损坏现场另存 `meta.json.corrupt`；
  - restore 只回滚 meta 不回滚目录，完成后提示执行 `req doctor` 检查漂移；
  - 【待确认】`backup_enabled` 默认值是否改为 `true`（当前默认 false，多数用户 restore 无备份可用）。

### O-07：`req doctor` 一致性巡检（P1）

检查并报告 meta 与文件系统的漂移（含 `archive/` 前缀键对应的归档目录），默认只读：

- meta 中键指向的目录不存在（如手工删除、delete 目录删除失败遗留的反向情况）；
- storage 下存在目录但 meta 无对应记录（孤儿目录）；
- 同 ID 多条记录（手工编辑 meta 造成，`find_req` 当前静默取第一个）；
- 存量需求的 status/tags/role 不在当前 config 白名单内（config 收缩后遗留）；
- depends_on / parent_id / child_ids 指向不存在的需求 ID。

`--fix` 修复动作枚举（推演补充，持锁执行）：

| 漂移类型 | --fix 动作 |
|----------|-----------|
| 悬空 depends_on / child_ids 引用 | ✅ 自动移除引用 |
| 悬空 parent_id | ✅ 置空并降级 role（与 delete 的孤儿处理同规则） |
| 键指向目录不存在 / 孤儿目录 / 同 ID 多条 / 白名单外值 | ❌ 仅报告 + 给出建议处置命令，不自动修（有损风险） |

### O-08：`req unarchive` 归档恢复（P1）

- 现状：归档单向，误归档只能手工改 meta + 挪目录，违反"禁止手工编辑 meta.json"规范。
- **前置子项（推演 #1，阻断修复）**：当前 archive 直接覆写 status，**未结构化记录归档前状态**（changelog 文本也不含旧状态）——archive 需先增加写入 `pre_archive_status` 字段，unarchive 据此恢复。
- 存量已归档需求（无 `pre_archive_status`）：恢复为默认状态并输出提示【✅ 已落定：回退恢复为"已完成"（第 4 批）】。
- 目录冲突（推演补充）：原分类目录下已存在同名目录时报错退出不移动，提示用户处置。
- 父子关系：unarchive 不改动 role/parent_id/child_ids，恢复原样。
- 文档级恢复（`archive --doc` 的逆操作）本期不做，列入备选项。
- ⚠️ 连带修复：archive 命令锁外计算 src/dst 路径、锁内不重算的快照问题——加入 unarchive 后该竞态从"不可达"变为"可达"，两者必须同批实施。

### O-09：写命令 `--json` 输出与退出码契约（P1） ✅ 已实现（第 5 批）

- req 的主要调用方是 AI，当前 create/update/delete/archive 只有人类文案，AI 靠正则抠 `ID: REQ-xxx`，脆弱。
- create/update/delete/archive/restore/unarchive 增加 `--json`，输出结构化结果（如 create 输出 `{"ok": true, "id": ..., "dir": ..., "meta_key": ...}`）。
- **非交互约定（推演 #2，阻断修复）**：`--json` 隐含非交互——需要交互确认的命令（delete、archive parent 等）若未带 `--force`，直接报错退出而非挂起等待 `input()`。
- 失败输出契约（推演补充）：`--json` 模式下失败时 stdout 输出 `{"ok": false, "error": "..."}`，退出码不变。
- 退出码写入 guide 成为契约：0=成功，1=校验/业务错误，2=锁超时。
- ✅ 落地说明：新增 `core/output.py`（`is_json`/`emit_success`/`guard_interactive`/`extract_error`）；**成功**由各命令 `emit_success` 输出，**失败**由 `cli._dispatch` 统一捕获 stderr 转 `{"ok": false, "error": ...}`（退出码不变）；`guard_interactive` 置于任何 `input()` 前实现非交互约定。delete 的 `orphaned`/`cleaned` 在 dry-run 与成功输出中统一为计数（int），dry-run 额外提供 `orphaned_ids`/`cleaned_ids` 明细。

### O-10：输入校验同类展开（P2） ✅ 已实现（第 5 批）

- `req list --columns` 无效列名当前静默输出空列 → 报错并列出有效列名。
- `req list --from/--to` 日期格式不校验，`"abc"` 参与字符串比较静默出错 → 校验 `YYYY-MM-DD[ HH:MM:SS]` 格式；`--from > --to` 报错。
- `req create --depends-on` 去重；依赖已归档需求时输出警告（不阻断）。
- ✅ 落地说明：list.py 新增 `_DATE_RE` 校验 `--from/--to` 格式与区间（`--to` 纯日期补 ` 23:59:59` 作当天末尾）、`--columns` 无效/空列名报错；create.py `depends_on` 用 `dict.fromkeys` 去重保序，依赖已归档需求时并入 warnings（json 模式并入 payload，人类模式打印 stderr）。

### 备选项（本期不排期，留档）

- 文档级归档恢复（`archive --doc` 的逆操作）；
- 状态流转轻量状态机（如"已取消"是否允许改回）；
- delete 交互确认在锁外、确认信息可能过时（数据一致性无损，低风险）；
- `--search` 扩展到 tags/changelog；`req stats` 统计视图；`--sort`；`req show <id>` 别名。

## 实施批次

| 批次 | 内容 | 工作量 |
|------|------|--------|
| 第 1 批 | O-04 筛选值校验（含 role/category/tag 同类展开）+ O-01 limit | 小（<1h），纯 list.py/cli.py 改动 |
| 第 2 批 | O-05 ID 不复用 + O-06 损坏友好处理与 restore | 小-中（1-2h），数据正确性优先 |
| 第 3 批 | O-02 branch 字段 + O-03 展示（含详情视图补 commits） | 中（1-2h），涉及 create/update/list/guide/测试 |
| 第 4 批 | O-08 unarchive（连带 archive 路径快照修复）+ O-07 doctor | 中-大（3-4h） |
| 第 5 批 | O-09 --json 输出与退出码契约 + O-10 校验展开 | 中（1-2h） |

每批需同步更新 `docs/requirement-mgr-guide.md` 并补回归测试。

## 待确认决策点

1. `--limit` 是否对 `--json` 输出同样生效（推荐：一致生效）。✅ 已落定：一致生效（第 1 批）。
2. branch 写入方式：方案 A 显式参数（推荐）还是方案 B git 自动检测。✅ 已落定：方案 A 显式 `--branch`（第 3 批）。
3. commits 默认列展示形态：数量（推荐）还是最后一个短 hash。✅ 已落定：默认列显示数量，完整 hash 列表在 `--id` 详情视图（第 3 批）。
4. `backup_enabled` 默认值是否改为 `true`（O-06 推演新增，推荐：改）。✅ 已落定：改为 true（第 2 批）。
5. 存量已归档需求（无 `pre_archive_status`）unarchive 默认恢复状态（O-08 推演新增，推荐："已完成"）。✅ 已落定：回退恢复为"已完成"（第 4 批）。

## 验收标准

- `req list` 默认输出 ≤10 行需求且有总量提示；`--limit 0` 输出全部。
- `req list --status <无效值>` 报错退出（exit code 1）并列出有效状态。
- `req create/update --branch` 可写入分支名，`req list` 默认列可见 branch 与 commit 数，`--id` 详情可见完整 commits。
- 删除当日最新需求后再创建，新需求 ID 不与被删需求重复。
- meta.json 损坏时所有命令输出友好错误与恢复指引（无裸 traceback）；`req restore` 可从 `.bak` 恢复。
- `req unarchive` 可将已归档需求恢复到归档前状态（新归档读 `pre_archive_status`；存量无该字段按默认策略并提示）；`req doctor` 能检出五类漂移，`--fix` 仅自动修复悬空引用类。
- 写命令 `--json` 输出（含失败场景）可被 `json.loads` 直接解析；`req delete X --json`（无 --force）立即失败退出而非挂起；退出码符合 guide 契约。
- config 白名单为空时对应筛选参数不校验（不限制语义）。
- 全量回归测试通过，guide 与实际行为一致。
