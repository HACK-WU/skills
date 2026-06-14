# 配置指南

`req` 命令行工具的配置方式，包括配置文件格式、配置项详解和约束规则。

## 配置文件

配置文件位于 `.requirements/config`，采用 INI 格式。

**文件路径**：`{项目根目录}/.requirements/config`

**生成方式**：
```bash
# 自动生成默认配置
req init

# 手动创建（参考下方模板）
```

**配置文件模板**：
```ini
storage_path=.requirements

# 需求功能分类配置
# 多个分类用逗号分隔
# 默认值为空，表示不进行功能分类
feature_categories=security,performance,integration,monitoring,logging

# 需求标签配置
# tags 字段的可选值必须从此配置中选取，不能凭空创造
# 多个标签用逗号分隔
requirement_tags=feat,fix,refactor,tool,integration,security,performance,ux,infra,bugfix,optimization,documentation
```

## 配置项详解

### 存储配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `storage_path` | string | `.requirements` | 需求文档存储根路径，相对于项目根目录 |

### 功能分类配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `feature_categories` | string | 空 | 功能分类配置，多个分类用逗号分隔。配置后，创建需求时必须指定一个功能分类标签 |

### 标签配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `requirement_tags` | string | `feat,fix,refactor,tool,security` | 需求标签配置，tags 字段的可选值必须从此配置中选取 |

### 状态配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `requirement_statuses` | string | `草案,已确认,设计中,实施中,已完成,已取消` | 需求状态列表，用于状态流转 |

### 角色配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `requirement_roles` | string | `standalone,parent,child` | 需求角色列表，用于父子需求管理 |

### ID 生成配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `id_prefix` | string | `REQ` | ID 前缀，用于生成 `REQ-YYYYMMDD-NNN` 格式的 ID |
| `id_digits` | integer | `3` | ID 日期后序号位数，如 `001`、`002` |

### 并发控制配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `lock_timeout` | integer | `5` | 文件锁超时秒数，超时后退出码为 2 |

### 备份配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `backup_enabled` | boolean | `false` | 写入前是否备份 meta.json，启用后会在写入前创建 `.meta.json.bak` 备份文件 |

## 约束规则

### 标签来源约束
tags 字段的值必须从 `requirement_tags` 配置中选取，不能凭空创造。

**示例**：
```ini
# 配置
requirement_tags=feat,fix,refactor,tool,security

# 正确
req create --feature "功能" --tags feat,security

# 错误（"new-tag" 不在配置中）
req create --feature "功能" --tags feat,new-tag
# → 错误: 标签 "new-tag" 不在 requirement_tags 配置中
```

### 功能分类约束
如果配置了 `feature_categories`，创建需求时必须包含一个功能分类标签，该标签必须从 `feature_categories` 配置中选取。

**示例**：
```ini
# 配置
feature_categories=security,performance,integration

# 正确（"security" 是功能分类标签）
req create --feature "认证模块" --tags feat,security

# 错误（缺少功能分类标签）
req create --feature "认证模块" --tags feat
# → 错误: 必须包含一个功能分类标签

# 错误（"ux" 不是功能分类标签）
req create --feature "认证模块" --tags feat,ux
# → 错误: "ux" 不是功能分类标签，请使用 security, performance 或 integration
```

### 功能分类唯一性
功能分类标签有且只能有一个。

**示例**：
```bash
# 正确（只有一个功能分类标签）
req create --feature "认证模块" --tags feat,security

# 错误（有两个功能分类标签）
req create --feature "认证模块" --tags feat,security,performance
# → 错误: 功能分类标签只能有一个，当前有 2 个: security, performance
```

### 功能分类变更限制
功能分类标签与目录位置关联，不允许删除或更改功能分类标签。

**示例**：
```bash
# 需求 REQ-20260611-001 的目录是 security/2026-06-11-认证模块/

# 错误（尝试删除功能分类标签）
req update REQ-20260611-001 --tag remove security
# → 错误: 不能删除功能分类标签，功能分类标签与目录位置关联

# 错误（尝试更改功能分类标签）
req update REQ-20260611-001 --tag set feat,performance
# → 错误: 不能更改功能分类标签，如需更改请删除并重新创建需求
```

### 标签删除约束
不能删除最后一个标签，至少保留一个标签。

**示例**：
```bash
# 需求 REQ-20260611-001 当前标签: ["feat", "security"]

# 正确（删除后仍有标签）
req update REQ-20260611-001 --tag remove feat
# → 标签已更新: ["security"]

# 错误（删除后没有标签）
req update REQ-20260611-001 --tag remove security
# → 错误: 不能删除最后一个标签，请先添加其他标签
```

### 依赖存在性校验
依赖的 ID 必须已存在。

**示例**：
```bash
# 正确（REQ-20260611-001 已存在）
req create --feature "功能" --tags feat --depends-on REQ-20260611-001

# 错误（REQ-99999999-999 不存在）
req create --feature "功能" --tags feat --depends-on REQ-99999999-999
# → 错误: 依赖需求 REQ-99999999-999 不存在
```

### 自依赖禁止
不能依赖自己。

**示例**：
```bash
# 错误
req update REQ-20260611-001 --depends-on add REQ-20260611-001
# → 错误: 不能依赖自己
```

### 循环依赖检测
不能形成 A→B→A 的循环依赖。

**示例**：
```bash
# 假设 REQ-20260611-001 依赖 REQ-20260611-002
req update REQ-20260611-001 --depends-on add REQ-20260611-002

# 错误（形成循环）
req update REQ-20260611-002 --depends-on add REQ-20260611-001
# → 错误: 添加 REQ-20260611-001 会形成循环依赖 (REQ-20260611-002→REQ-20260611-001→REQ-20260611-002)
```

## 配置优先级

配置优先级从高到低：
1. 命令行参数
2. 环境变量（如 `REQ_LOCK_TIMEOUT`）
3. 配置文件 `.requirements/config`
4. 默认值

## 典型配置场景

### 默认配置（推荐）
```ini
storage_path=.requirements
feature_categories=
requirement_tags=feat,fix,refactor,tool,security
```

### 安全项目配置
```ini
storage_path=.requirements
feature_categories=security,authentication,authorization,encryption
requirement_tags=feat,fix,refactor,tool,security,vulnerability,compliance
```

### 性能优化项目配置
```ini
storage_path=.requirements
feature_categories=performance,optimization,caching,monitoring
requirement_tags=feat,fix,refactor,tool,performance,optimization,benchmark
```

### 多团队协作配置
```ini
storage_path=.requirements
feature_categories=frontend,backend,devops,qa,design
requirement_tags=feat,fix,refactor,tool,bug,feature,improvement,documentation
```

## 相关文档
- [README](./README.md) — 项目概述与快速开始
- [命令参考](./command-reference.md) — 所有命令
- [架构文档](./requirement-mgr-guide.md) — 系统架构与技术实现
- [故障排查](./troubleshooting.md) — 常见问题及解决方案