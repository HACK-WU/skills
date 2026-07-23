# 需求管理脚本系统

一个零依赖的 Python CLI 工具，用于管理项目需求文档的元数据。

## 概述

`req` 是一个零依赖的 Python CLI 工具，专门用于管理项目需求文档的元数据，提供并发安全、原子写入、依赖追踪等能力。

## 安装

### 前置条件
- Python 3.10+
- `uv`（推荐）或直接使用 `python`

### 方式一：自动安装脚本（推荐）

```bash
curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/install-latest.sh | bash
# 包含预发布版本：
curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/install-latest.sh | bash -s -- --pre
```

### 方式二：指定版本安装

```bash
uv tool install https://github.com/HACK-WU/skills/releases/download/requirement-mgr-v0.1.0-beta/requirement_mgr-0.1.0b0-py3-none-any.whl
```

> 📦 [所有 Release 版本](https://github.com/HACK-WU/skills/releases/tag/requirement-mgr-v0.1.0-beta)

### 方式三：从源码安装

```bash
cd /path/to/project
uv tool install scripts/requirement-mgr/
```

### 验证安装
```bash
req --version
# → req 0.1.0-beta
```

> Windows PowerShell 及其他高级安装方式详见 [配置指南](./configuration.md)

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

### `req archive`
```bash
$ req archive REQ-20260611-001 --reason "功能已完成"
✓ 需求已归档
  ID:        REQ-20260611-001
  原目录:    security/2026-06-11-用户认证模块
  归档位置:  archive/security/2026-06-11-用户认证模块
  状态:      已归档
  归档原因:  功能已完成
```

> 更多命令（`req update`、`req delete`、`req archive` 等）详见 [命令参考](./command-reference.md)

## 测试运行

项目包含完整的单元测试，可以验证所有命令和核心模块的功能。

```bash
# 运行所有测试
cd scripts/requirement-mgr && python run_tests.py

# 或者使用 pytest 直接运行
cd scripts/requirement-mgr && python -m pytest tests/ -v

# 运行特定模块的测试
cd scripts/requirement-mgr && python -m pytest tests/test_archive.py -v
cd scripts/requirement-mgr && python -m pytest tests/test_list.py -v
cd scripts/requirement-mgr && python -m pytest tests/test_time_utils.py -v
```

测试覆盖内容：
- **时间工具模块**：`now_cst_str()` 和 `today_cst_str()` 函数验证
- **归档命令**：成功归档、二次归档拦截、不存在需求拦截、dry-run 模式、--force 跳过确认、目录冲突拦截
- **列表命令**：`_normalize_ts()` 函数归一化验证、默认隐藏已归档需求、`--include-archived` 显示所有需求、`--id` 模式查询、状态筛选、排序归一化、日期范围筛选、搜索过滤

## 文档导航

| 文档 | 内容 |
|------|------|
| [命令参考](./command-reference.md) | 6 个命令的完整参数、选项和输出示例 |
| [配置指南](./configuration.md) | 配置文件格式、9 个配置项详解、约束规则 |
| [架构文档](./requirement-mgr-guide.md) | 系统架构、技术实现细节、数据模型 |
| [故障排查](./troubleshooting.md) | 常见问题及解决方案 |

---

> **文档版本**：v1.0  
> **最后更新**：2026-06-14  
> **维护者**：AI Agent