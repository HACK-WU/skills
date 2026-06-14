# 需求管理脚本系统

一个零依赖的 Python CLI 工具，用于管理项目需求文档的元数据。

## 概述

`req` 是一个零依赖的 Python CLI 工具，专门用于管理项目需求文档的元数据，提供并发安全、原子写入、依赖追踪等能力。

## 安装

### 前置条件
- Python 3.10+
- `uv`（推荐）或直接使用 `python`

### 安装命令
```bash
cd /path/to/project
uv tool install scripts/requirement-mgr/
```

### 验证安装
```bash
req --version
# → requirement_mgr, version 1.0.0
```

> 其他安装方式（GitHub Release、开发模式、Windows PowerShell）详见 [配置指南](./configuration.md)

## 快速开始

```bash
# 1. 初始化项目配置
req init

# 2. 创建第一个需求
req create --feature "用户认证模块" --tags feat,security

# 3. 查看创建的需求
req list --id REQ-20260611-001

# 4. 更新需求状态
req update REQ-20260611-001 --status 已确认 --changelog "需求评审通过"
```

## 核心命令速览

### `req init`
```bash
$ req init
✔ 配置文件已生成: .requirements/config
✔ 存储目录已创建: .requirements/
```

### `req create`
```bash
$ req create --feature "JWT 鉴权" --tags feat,security
✔ 需求已创建: REQ-20260611-001
✔ 目录已创建: security/2026-06-11-jwt-鉴权/
```

### `req list`
```bash
$ req list
ID               状态    角色       功能名称           更新时间
REQ-20260611-001 已确认  standalone 用户认证模块       2026-06-11
REQ-20260611-002 草案    child      JWT 鉴权          2026-06-11
```

> 更多命令（`req update`、`req delete` 等）详见 [命令参考](./command-reference.md)

## 文档导航

| 文档 | 内容 |
|------|------|
| [命令参考](./command-reference.md) | 5 个命令的完整参数、选项和输出示例 |
| [配置指南](./configuration.md) | 配置文件格式、9 个配置项详解、约束规则 |
| [架构文档](./requirement-mgr-guide.md) | 系统架构、技术实现细节、数据模型 |
| [故障排查](./troubleshooting.md) | 常见问题及解决方案 |

---

> **文档版本**：v1.0  
> **最后更新**：2026-06-14  
> **维护者**：AI Agent