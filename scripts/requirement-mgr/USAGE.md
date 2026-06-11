# 需求管理脚本 — 使用文档

基于 `meta.json` 集中元数据的需求 CRUD 命令行工具，支持原子写入、并发锁、依赖追踪。

## 环境要求

- Python 3.10+
- `uv`（推荐）或直接 `python` 执行
- 项目根目录存在 `.requirements/config`

## 快速安装

```bash
# 从 GitHub 一键安装
curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.sh | bash -s -- /path/to/your-project --scripts
```

## 运行方式

所有命令从项目根目录执行：

```bash
uv run python scripts/requirement-mgr/list-requirements.py [选项]
uv run python scripts/requirement-mgr/create-requirement.py --feature "名称" [选项]
uv run python scripts/requirement-mgr/update-requirement.py REQ-NNN [选项]
uv run python scripts/requirement-mgr/delete-requirement.py REQ-NNN [选项]
```

---

## 1. list-requirements.py — 查询需求

### 基本用法

```bash
# 列出所有需求（表格模式）
uv run python scripts/requirement-mgr/list-requirements.py

# JSON 格式
uv run python scripts/requirement-mgr/list-requirements.py --json
```

### 筛选

```bash
# 按状态
uv run python scripts/requirement-mgr/list-requirements.py --status 进行中

# 按标签（--tag 可重复，AND 关系）
uv run python scripts/requirement-mgr/list-requirements.py --tag feat --tag tool

# 按日期范围
uv run python scripts/requirement-mgr/list-requirements.py --from 2026-01-01 --to 2026-12-31

# 模糊搜索功能名称
uv run python scripts/requirement-mgr/list-requirements.py --search "需求管理"
```

### 详情模式

```bash
# 查看指定需求完整信息
uv run python scripts/requirement-mgr/list-requirements.py --id REQ-001

# 展开直接依赖
uv run python scripts/requirement-mgr/list-requirements.py --id REQ-001 --deps

# 展开间接依赖（深度 2）
uv run python scripts/requirement-mgr/list-requirements.py --id REQ-001 --deps --deps-depth 2

# 反向依赖：哪些需求依赖了本需求
uv run python scripts/requirement-mgr/list-requirements.py --id REQ-001 --rev-deps

# 自定义显示列
uv run python scripts/requirement-mgr/list-requirements.py --columns id,status,version,updated
```

### 全参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `--id` | str | 精确匹配需求 ID |
| `--status` | str | 按状态筛选 |
| `--tag` | str (可重复) | 按标签筛选 (AND) |
| `--from` | date (YYYY-MM-DD) | 更新日期起 |
| `--to` | date (YYYY-MM-DD) | 更新日期止 |
| `--search` | str | 模糊搜索功能名称 |
| `--deps` | flag | 展开依赖需求 |
| `--rev-deps` | flag | 反向依赖查询 |
| `--deps-depth` | int (默认 1) | 依赖递归深度 |
| `--json` | flag | JSON 输出 |
| `--columns` | str | 自定义显示列 |
| `--no-color` | flag | 禁用颜色 |

### 退出码

| 码 | 含义 |
|:--:|------|
| 0 | 成功（含无匹配结果） |
| 1 | config 不存在 / ID 不存在 |

---

## 2. create-requirement.py — 新建需求

### 基本用法

```bash
# 最简创建
uv run python scripts/requirement-mgr/create-requirement.py --feature "用户认证模块"

# 带标签
uv run python scripts/requirement-mgr/create-requirement.py --feature "用户认证模块" --tags feat,backend

# 指定依赖
uv run python scripts/requirement-mgr/create-requirement.py --feature "用户认证模块" --depends-on REQ-001,REQ-002

# 指定初始状态
uv run python scripts/requirement-mgr/create-requirement.py --feature "用户认证模块" --status 设计中

# 自定义目录名
uv run python scripts/requirement-mgr/create-requirement.py --feature "用户认证模块" --dir-name auth-module
```

### 行为

1. 读取 `meta.json`，自增生成 `REQ-NNN` 全局 ID
2. 校验 `--depends-on` 中所有 ID 是否存在
3. 获取文件锁 → 二次校验 → 创建目录 → 原子写入 `meta.json`
4. 输出：ID、目录路径、meta.json 路径

### 自动填充

| 字段 | 值 |
|------|-----|
| `id` | `REQ-NNN`（取最大 +1） |
| `created` | 当前日期 |
| `updated` | 当前日期 |
| `version` | 1 |
| `changelog` | `["初始创建"]` |
| `commits` | `[]` |

### 全参数

| 参数 | 必填 | 默认值 | 说明 |
|------|:--:|--------|------|
| `--feature` | ✅ | — | 功能名称 |
| `--tags` | — | `feat` | 逗号分隔标签 |
| `--depends-on` | — | — | 逗号分隔依赖 ID |
| `--status` | — | `草案` | 初始状态（枚举值） |
| `--dir-name` | — | `{date}-{feature}` | 自定义目录名 |

### 校验规则

- `--feature` 不能为空
- `--tags` 至少一个
- `--depends-on` 中每个 ID 必须已在 meta.json 中存在
- `--status` 必须为合法枚举值
- 目录名不能与已有目录冲突

### 退出码

| 码 | 含义 |
|:--:|------|
| 0 | 创建成功 |
| 1 | 参数错误 / 依赖不存在 / 目录冲突 |
| 2 | 获取文件锁超时 |

---

## 3. update-requirement.py — 修改需求

### 基本用法

```bash
# 更新状态
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --status 已完成

# 更新功能名称
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --feature "新名称"

# 标签增删改
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --tag add deploy
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --tag remove deprecated
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --tag set feat,core

# 依赖管理
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --depends-on add REQ-003
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --depends-on remove REQ-002
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --depends-on set REQ-001,REQ-003

# 追加变更记录
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --changelog "需求评审通过"

# 关联 git commit
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --commit abc1234

# 设置文档路径
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --data-flow data-flow.md --report report.md
```

### 组合操作

```bash
# 一次命令修改多个字段
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 \
  --status 实施中 \
  --tag add deploy \
  --depends-on add REQ-003 \
  --changelog "开始开发"
```

### 自动行为

每次成功修改自动：
- `version` +1
- `updated` 刷新为当前日期
- `changelog` 追加 `"YYYY-MM-DD v{version}: {message}"`

### 操作语义

| 操作 | 语法 | 幂等性 |
|------|------|:--:|
| `--status X` | 直接覆盖 | ✅ |
| `--feature X` | 直接覆盖 | ✅ |
| `--tag add X` | 追加，已存在则跳过 | ✅ |
| `--tag remove X` | 删除，不存在则跳过 | ✅ |
| `--tag set A,B` | 覆盖整个列表 | ✅ |
| `--depends-on add X` | 追加 + 循环依赖检测 | ✅ |
| `--depends-on remove X` | 删除，不存在则跳过 | ✅ |
| `--depends-on set A,B` | 覆盖列表 | ✅ |
| `--commit X` | 追加 + 去重 | ✅ |

### 循环依赖检测

添加依赖时自动 BFS 检测循环引用：

```bash
$ uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --depends-on add REQ-001
错误: 不能依赖自身

$ uv run python scripts/requirement-mgr/update-requirement.py REQ-003 --depends-on add REQ-001
错误: 添加 REQ-001 会形成循环依赖
```

### 全参数

| 参数 | 说明 |
|------|------|
| `req_id` (位置) | 需求 ID，如 `REQ-001` |
| `--status` | 更新状态 |
| `--feature` | 更新功能名称 |
| `--tag add\|remove\|set VALUE` | 标签操作 |
| `--depends-on add\|remove\|set IDS` | 依赖操作 |
| `--commit` | 追加 commit hash |
| `--data-flow` | 设置数据流图路径 |
| `--report` | 设置实现报告路径 |
| `--changelog` | 追加变更记录 |

### 退出码

| 码 | 含义 |
|:--:|------|
| 0 | 更新成功 |
| 1 | REQ-ID 不存在 / 循环依赖 / 删最后一个标签 |
| 2 | 获取文件锁超时 |

---

## 4. delete-requirement.py — 删除需求

### 基本用法

```bash
# 交互确认模式
uv run python scripts/requirement-mgr/delete-requirement.py REQ-003
# → 展示摘要，等待 y/N 确认

# 跳过确认
uv run python scripts/requirement-mgr/delete-requirement.py REQ-003 --force

# 预览模式（不实际删除）
uv run python scripts/requirement-mgr/delete-requirement.py REQ-003 --dry-run
```

### dry-run 输出示例

```
🔍 预删除检查

将执行：
  ① 从 meta.json 删除 REQ-003 条目
  ② 从 REQ-001 的 depends_on 中移除 REQ-003
  ③ 删除目录: .requirements/2026-06-10-旧模块迁移

⚠ --dry-run 模式，未做任何修改。
```

### 行为

1. 前置检查：ID 是否存在 + 扫描反向依赖
2. (dry-run 则到此为止)
3. 交互确认 / force
4. 获取文件锁 → 删除条目 → 清理所有 `depends_on` 引用 → 原子写入
5. 删除需求目录（`shutil.rmtree`）
6. 目录删除失败时打警告不崩溃

### 全参数

| 参数 | 说明 |
|------|------|
| `req_id` (位置) | 需求 ID |
| `--force` | 跳过交互确认 |
| `--dry-run` | 仅预览，不实际执行 |

> `--dry-run` 和 `--force` 互斥。

### 退出码

| 码 | 含义 |
|:--:|------|
| 0 | 删除成功 / dry-run 完成 |
| 1 | REQ-ID 不存在 |
| 2 | 获取文件锁超时 |

---

## 5. meta.json 结构

```json
{
  "requirements": {
    "2026-06-11-requirement-management": {
      "id": "REQ-001",
      "feature": "需求管理脚本系统",
      "created": "2026-06-11",
      "updated": "2026-06-11",
      "status": "已确认",
      "tags": ["feat", "tool"],
      "version": 2,
      "depends_on": [],
      "changelog": [
        "初始创建",
        "2026-06-11 v2: 确定技术选型为 Python"
      ],
      "commits": [],
      "data_flow": "data-flow.md",
      "report": ""
    }
  }
}
```

### 状态枚举

| 状态 | 含义 |
|------|------|
| `草案` | 需求初建，内容尚未确认 |
| `已确认` | 需求评审通过 |
| `设计中` | 设计文档编写中 |
| `实施中` | 开发编码阶段 |
| `已完成` | 开发和验收均通过 |
| `已取消` | 需求废弃 |

### 字段速查

| 字段 | create | list | update | delete |
|------|:---:|:---:|:---:|:---:|
| `id` | 自动生成 | 筛选/展示 | 不可改 | — |
| `feature` | 必填 | 展示/搜索 | 可选改 | — |
| `status` | 默认"草案" | 筛选 | 覆盖 | — |
| `tags` | 默认["feat"] | 筛选 | 增/删/改 | — |
| `version` | =1 | 展示 | 自增+1 | — |
| `created` | 自动 | 筛选/展示 | 不可改 | — |
| `updated` | =created | 展示 | 自动刷新 | — |
| `depends_on` | 可选 | 展示/展开 | 增/删/改+循环检测 | 清理引用 |
| `changelog` | ["初始创建"] | 展示 | 追加 | — |
| `commits` | [] | 展示 | 追加+去重 | — |
| `data_flow` | "" | 展示 | 设置 | — |
| `report` | "" | 展示 | 设置 | — |

---

## 6. 常见工作流

### 新需求落地全流程

```bash
# 1. 创建需求
uv run python scripts/requirement-mgr/create-requirement.py \
  --feature "用户认证模块" \
  --tags feat,backend \
  --depends-on REQ-001

# 2. 查看确认
uv run python scripts/requirement-mgr/list-requirements.py --id REQ-003

# 3. 进入设计阶段
uv run python scripts/requirement-mgr/update-requirement.py REQ-003 \
  --status 设计中 \
  --changelog "需求评审通过"

# 4. 开发中关联提交
uv run python scripts/requirement-mgr/update-requirement.py REQ-003 \
  --status 实施中 \
  --commit abc1234

# 5. 完成
uv run python scripts/requirement-mgr/update-requirement.py REQ-003 \
  --status 已完成 \
  --changelog "功能验收通过"
```

### 查看全貌

```bash
# 所有需求
uv run python scripts/requirement-mgr/list-requirements.py

# 进行中的需求
uv run python scripts/requirement-mgr/list-requirements.py --status 实施中

# 某需求的依赖链
uv run python scripts/requirement-mgr/list-requirements.py --id REQ-001 --deps --deps-depth 3
```

---

## 7. 并发安全

- 写入操作自动获取排他文件锁（`meta.json.lock`），超时 5s
- 锁超时时抛出 `TimeoutError`（退出码 2），调用方可重试
- 写入使用 **原子替换**（`tempfile` → `os.replace`），崩溃不损坏数据
- `list` 只读操作无锁（读取的是原子写入保证的完整快照）
- 可通过环境变量 `REQ_LOCK_TIMEOUT` 自定义锁超时

---

## 8. 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| `配置文件不存在` | `.requirements/config` 未创建 | 创建 `config` 文件，写 `storage_path=.requirements` |
| `无法在 5s 内获取文件锁` | 其他进程持有锁未释放 | 等待后重试，或删除残留 `.meta.json.lock` |
| `依赖需求 REQ-XXX 不存在` | depends_on 中的 ID 无效 | 先创建依赖需求，或修正 ID |
| `不能删除最后一个标签` | 标签列表至少保留 1 个 | 使用 `--tag set` 或先 add 再 remove |
| `会形成循环依赖` | 添加依赖后 A→B→A | 检查依赖链，调整设计 |
