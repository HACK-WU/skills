# 命令参考

`req` 命令行工具的所有命令及其参数和输出示例。

## 全局选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--help` / `-h` | boolean | `false` | 显示帮助信息 |
| `--version` | boolean | `false` | 显示版本信息 |
| `--no-color` | boolean | `false` | 禁用 ANSI 颜色输出 |

---

## 命令列表

### `req init`

初始化项目配置，生成 `.requirements/config` 文件和 `.requirements/` 目录。

```bash
$ req init
✔ 配置文件已生成: .requirements/config
✔ 存储目录已创建: .requirements/
```

**选项**：
| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--force` | boolean | `false` | 强制覆盖已存在的配置文件 |

**配置文件模板**：
```ini
storage_path=.requirements

# 需求功能分类配置
# 多个分类用逗号分隔
# 默认值为空，表示不进行功能分类
feature_categories=

# 需求标签配置
# tags 字段的可选值必须从此配置中选取，不能凭空创造
# 多个标签用逗号分隔
requirement_tags=feat,fix,refactor,tool,security
```

### `req create`

创建新需求，自动生成 ID、创建目录、写入元数据。

```bash
$ req create --feature "用户认证模块" --tags feat,security
✔ 需求已创建: REQ-20260611-001
✔ 目录已创建: security/2026-06-11-用户认证模块/
```

```bash
# 带依赖创建
$ req create --feature "支付网关" --tags feat,integration --depends-on REQ-20260611-001
✔ 需求已创建: REQ-20260611-002
✔ 依赖已添加: REQ-20260611-001

# 创建子需求（父需求自动升级为 parent）
$ req create --feature "JWT 鉴权" --tags feat --parent-id REQ-20260611-001
✔ 需求已创建: REQ-20260611-003
✔ 父需求 REQ-20260611-001 已升级为 parent
```

**选项**：
| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--feature` | string | 必填 | 功能名称 |
| `--tags` | string | `["feat"]` | 标签列表（逗号分隔） |
| `--status` | string | `草案` | 初始状态 |
| `--role` | string | `standalone` | 需求角色 |
| `--parent-id` | string | - | 父需求 ID（创建子需求时使用） |
| `--depends-on` | string | - | 依赖的需求 ID（逗号分隔） |
| `--dir-name` | string | 自动生成 | 自定义目录名 |

**约束规则**：
1. 必须包含一个功能分类标签（如果配置了 `feature_categories`）
2. 标签必须来自 `requirement_tags` 配置
3. 功能分类标签有且只能有一个

### `req list`

查询需求，支持筛选、详情、依赖展开、反向依赖、父子层级查询。

```bash
# 列出所有需求
$ req list
ID               状态    角色       功能名称           更新时间
REQ-20260611-001 已确认  standalone 用户认证模块       2026-06-11
REQ-20260611-002 草案    child      JWT 鉴权          2026-06-11

# JSON 格式输出（适合脚本消费）
$ req list --json
[
  {
    "id": "REQ-20260611-001",
    "feature": "用户认证模块",
    "status": "已确认",
    "role": "standalone",
    "tags": ["feat", "security"],
    "version": 1,
    "created": "2026-06-11",
    "updated": "2026-06-11"
  }
]

# 精确查询 + 依赖展开
$ req list --id REQ-20260611-001 --deps
ID               状态    功能名称           依赖
REQ-20260611-001 已确认  用户认证模块       REQ-20260611-002, REQ-20260611-003

# 反向依赖查询（谁依赖了我）
$ req list --id REQ-20260611-001 --rev-deps
ID               状态    功能名称           依赖了 REQ-20260611-001
REQ-20260611-002 草案    JWT 鉴权          ✓
REQ-20260611-003 草案    OAuth2 鉴权       ✓
```

**筛选参数**：
| 参数 | 说明 | 示例 |
|------|------|------|
| `--id` | 精确匹配需求 ID | `--id REQ-20260611-001` |
| `--status` | 按状态筛选 | `--status 实施中` |
| `--tag` | 按标签筛选（可重复，AND 关系） | `--tag feat --tag security` |
| `--role` | 按角色筛选 | `--role parent` |
| `--parent-id` | 按父需求筛选子需求 | `--parent-id REQ-20260611-001` |
| `--category` | 按功能分类筛选 | `--category security` |
| `--from` | 更新日期起 | `--from 2026-01-01` |
| `--to` | 更新日期止 | `--to 2026-12-31` |
| `--search` | 模糊搜索功能名称 | `--search "用户认证"` |

**输出控制**：
| 参数 | 说明 |
|------|------|
| `--json` | JSON 格式输出 |
| `--columns` | 自定义显示列 |
| `--no-color` | 禁用 ANSI 颜色 |

**依赖查询**：
| 参数 | 说明 |
|------|------|
| `--deps` | 显示依赖树 |
| `--deps-depth` | 依赖展开深度（默认 3） |
| `--rev-deps` | 显示反向依赖（谁依赖了我） |

### `req update`

更新需求，支持状态流转、依赖管理、标签管理等。

```bash
# 状态流转
$ req update REQ-20260611-001 --status 已确认 --changelog "需求评审通过"
✔ 需求已更新: REQ-20260611-001
✔ 状态已变更为: 已确认

# 添加依赖
$ req update REQ-20260611-002 --depends-on add REQ-20260611-001
✔ 依赖已添加: REQ-20260611-001

# 循环检测（自动拒绝）
$ req update REQ-20260611-001 --depends-on add REQ-20260611-002
✗ 错误: 添加 REQ-20260611-002 会形成循环依赖 (REQ-20260611-001→REQ-20260611-002→REQ-20260611-001)

# 添加标签
$ req update REQ-20260611-001 --tag add documentation
✔ 标签已添加: documentation
```

**状态流转**：
| 当前状态 | 可转换状态 | 说明 |
|----------|------------|------|
| 草案 | 已确认 | 需求评审通过 |
| 已确认 | 设计中 | 开始技术设计 |
| 设计中 | 实施中 | 开始开发编码 |
| 实施中 | 已完成 | 验收通过 |
| 草案/已确认/设计中/实施中 | 已取消 | 需求废弃 |

**依赖管理**：
| 选项 | 说明 | 示例 |
|------|------|------|
| `--depends-on add` | 添加依赖 | `--depends-on add REQ-20260611-001` |
| `--depends-on remove` | 删除依赖 | `--depends-on remove REQ-20260611-001` |

**标签管理**：
| 选项 | 说明 | 示例 |
|------|------|------|
| `--tag add` | 添加标签 | `--tag add documentation` |
| `--tag remove` | 删除标签 | `--tag remove documentation` |
| `--tag set` | 覆盖标签 | `--tag set feat,security,documentation` |

**其他选项**：
| 选项 | 说明 | 示例 |
|------|------|------|
| `--changelog` | 添加变更日志 | `--changelog "需求评审通过"` |
| `--commit` | 关联提交 | `--commit abc1234` |
| `--docs add` | 添加文档 | `--docs add design/DESIGN.md,design` |
| `--docs remove` | 删除文档 | `--docs remove design/DESIGN.md` |

### `req delete`

删除需求，支持安全删除、预览模式和自动化删除。

```bash
# 安全删除（默认交互）
$ req delete REQ-20260612-001
──────────────────────────────────────────────────
  ID:        REQ-20260612-001
  名称:      旧模块迁移工具
  目录:      2026-05-15-legacy-migration
  状态:      已取消

  反向依赖（1 项将清理引用）：
    REQ-20260611-001  需求管理脚本系统
──────────────────────────────────────────────────
⚠ 警告: 有 1 个需求的 depends_on 将被清理

确认删除？[y/N]: y
✔ 需求已删除: REQ-20260612-001
✔ 目录已清理: integration/2026-05-15-legacy-migration/

# 预览模式
$ req delete REQ-20260612-001 --dry-run
──────────────────────────────────────────────────
  将删除以下需求（预览模式，不会实际执行）：
  ID:        REQ-20260612-001
  名称:      旧模块迁移工具
  目录:      2026-05-15-legacy-migration
──────────────────────────────────────────────────

# 自动化删除
$ req delete REQ-20260612-001 --force
✔ 需求已删除: REQ-20260612-001
✔ 目录已清理: integration/2026-05-15-legacy-migration/
```

**选项**：
| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--dry-run` | boolean | `false` | 预览模式，不实际删除 |
| `--force` | boolean | `false` | 跳过确认，直接删除 |

**安全机制**：
1. 反向依赖扫描：检查哪些需求依赖了当前需求
2. 确认提示：默认需要用户确认
3. 引用清理：自动清理其他需求的 `depends_on` 引用
4. 目录清理：删除对应的需求目录

### `req archive`

归档需求或文档，移动到 `archive/` 目录。支持两种模式：

- **整体归档**（不指定 `--doc`）：移动整个需求目录到 `.requirements/archive/`，状态更新为"已归档"
- **文档级归档**（指定 `--doc <path>`）：移动单个文档到该需求目录下的 `archive/` 子目录，不改变需求状态

```bash
# 整体归档需求
$ req archive REQ-20260612-001
✓ 需求已归档
  ID:        REQ-20260612-001
  原目录:    tool/2026-07-23-测试需求
  归档位置:  archive/tool/2026-07-23-测试需求
  状态:      已归档
  归档原因:  功能已完成

# 预览模式
$ req archive REQ-20260612-001 --dry-run

🔍 预归档检查

将执行：
  ① 移动目录: tool/2026-07-23-测试需求
     → archive/tool/2026-07-23-测试需求
  ② 更新状态: 进行中 → 已归档
  ③ 更新 meta.json 键: tool/2026-07-23-测试需求 → archive/tool/2026-07-23-测试需求
  ④ 归档原因: 功能已完成

⚠ --dry-run 模式，未做任何修改。

# 强制归档（跳过确认）
$ req archive REQ-20260612-001 --force --reason "功能已完成"
✓ 需求已归档
  ID:        REQ-20260612-001
  原目录:    tool/2026-07-23-测试需求
  归档位置:  archive/tool/2026-07-23-测试需求
  状态:      已归档
  归档原因:  功能已完成

# 带子需求归档（需要确认）
$ req archive REQ-20260612-001
⚠ 警告: 需求 REQ-20260612-001 有 2 个活跃子需求（REQ-20260612-002, REQ-20260612-003）
  归档后子需求仍引用此父需求，可能导致语义混淆
确认归档？[y/N]: y
✓ 需求已归档

# 文档级归档（归档单个文档）
$ req archive REQ-20260612-001 --doc design/old-design.md --reason "设计已废弃"
✓ 文档已归档
  ID:        REQ-20260612-001
  原路径:    tool/2026-07-23-测试需求/design/old-design.md
  归档位置:  tool/2026-07-23-测试需求/archive/design/old-design.md
  归档原因:  设计已废弃

# 文档级归档预览
$ req archive REQ-20260612-001 --doc legacy-notes.md --dry-run

🔍 预归档检查（文档级）

将执行：
  ① 移动文档: tool/2026-07-23-测试需求/legacy-notes.md
     → tool/2026-07-23-测试需求/archive/legacy-notes.md
  ② 不改变需求状态（当前: 草案）
  ③ 归档原因: 设计已废弃

⚠ --dry-run 模式，未做任何修改。
```

**选项**：
| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--dry-run` | boolean | `false` | 预览模式，不实际执行 |
| `--force` | boolean | `false` | 跳过确认，直接归档（仅整体归档） |
| `--reason` | string | `None` | 归档原因说明 |
| `--doc` | string | `None` | 归档单个文档（相对需求目录的路径，如 `design/old.md`）；不指定则整体归档 |

**整体归档安全机制**：
1. 子需求检查：归档 parent 时，如果有活跃子需求，需要用户确认
2. 反向依赖扫描：检查哪些需求依赖了当前需求
3. 目录存在性检查：确保源目录存在，目标目录不冲突
4. 二次检查：在锁内再次检查状态，防止并发操作

**整体归档操作**：
1. 移动需求目录到 `.requirements/archive/` 下
2. 更新 `meta.json` 中的状态为"已归档"
3. 更新 `meta.json` 中的键名，添加 `archive/` 前缀
4. 记录归档时间和原因

**文档级归档机制**：
1. 移动文档到该需求目录下的 `archive/` 子目录（保留相对路径结构）
2. 不改变需求状态，版本号自增，changelog 追加归档记录
3. 若文档在 `docs` 列表中登记，归档后从 `docs` 移除
4. 已整体归档的需求不支持文档级归档

---

## 退出码

| 退出码 | 含义 |
|:--:|------|
| 0 | 成功（含无匹配结果） |
| 1 | 参数/校验错误 |
| 2 | 锁超时（可重试） |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `REQ_LOCK_TIMEOUT` | 文件锁超时秒数 | 5 |

## 相关文档
- [README](./README.md) — 项目概述与快速开始
- [配置指南](./configuration.md) — 配置文件详解
- [架构文档](./requirement-mgr-guide.md) — 系统架构与技术实现
- [故障排查](./troubleshooting.md) — 常见问题及解决方案