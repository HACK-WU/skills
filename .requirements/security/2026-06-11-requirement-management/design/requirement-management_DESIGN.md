---
id: REQ-001
feature: 需求管理脚本系统
status: 设计中
created: 2026-06-11
updated: 2026-06-11
version: 4
tags: [feat, tool]
depends_on: []
author: AI
document_type: design
---

# 需求管理脚本系统 — 设计文档

> 状态：草案

## 1. 需求背景 & 目标

### 背景

`.requirements/` 目录下的需求信息分散在各文档的 YAML frontmatter 中，AI Agent 查询和更新效率低。

### 目标

提供一套零依赖的 Python CRUD 脚本工具，使用集中式 `meta.json` 管理所有需求元数据，支持并发安全操作。

### 不在范围内

- Web 界面或 GUI
- 需求文档内容自动生成（文档由 AI 管理）
- 与外部系统（Jira、TAPD 等）的同步
- 多项目/多仓库需求聚合

---

## 2. 关键环节一览图

```mermaid
flowchart TB
    subgraph S01["S-01 基础设施层"]
        Config["ConfigLoader"]
        Lock["FileLock<br/>fcntl / msvcrt"]
        Meta["MetaStore<br/>原子读写"]
    end

    subgraph UserOps["用户 / AI Agent"]
        CMD2["create-requirement.py<br/>--feature --tags --depends-on"]
        CMD3["update-requirement.py<br/>REQ-ID --status --tag --depends-on"]
        CMD4["delete-requirement.py<br/>REQ-ID --dry-run --force"]
        CMD1["list-requirements.py<br/>--id --status --tag --deps"]
    end

    CMD1 -->|"S-02 只读"| Meta
    CMD2 -->|"S-03 加锁写"| Meta
    CMD3 -->|"S-04 加锁写"| Meta
    CMD4 -->|"S-05 加锁写"| Meta

    Meta --> Lock
    Config --> Meta
```

> S-02 ~ S-05 全部依赖 S-01，四脚本之间无互依赖，可并行开发。

---

## 3. 总体方案设计

### 架构分层

```mermaid
graph TB
    subgraph CLI["CLI 层（4 脚本）"]
        S2["S-02 list"]
        S3["S-03 create"]
        S4["S-04 update"]
        S5["S-05 delete"]
    end
    subgraph Core["核心层"]
        MetaS["MetaStore"]
        LockF["FileLock"]
        ConfigL["ConfigLoader"]
    end
    subgraph Store["存储层"]
        FS["文件系统"]
    end
    CLI --> Core --> Store
```

### 技术选型

- **语言**：Python 3.x（零依赖）
- **原子写入**：`tempfile` + `os.replace()`
- **并发安全**：`fcntl.flock` / `msvcrt.locking` 排他锁 + 5s 超时
- **CLI**：`argparse` 标准库

### 共享术语速查

| 术语 | 定义 | 引用子需求 |
|------|------|:---:|
| `meta.json` | 集中元数据存储文件 | S-01 |
| `REQ-NNN` | 需求唯一 ID 格式，自增编号 | S-01 |
| 原子写入 | 先写临时文件再 `os.replace` 替换 | S-01 |
| `depends_on` | 需求间依赖关系，存储 ID 列表 | S-01, S-03, S-04, S-05 |
| 反向依赖 | 哪些需求的 `depends_on` 包含本 ID | S-02, S-05 |
| 循环依赖 | A→B→A 的依赖链 | S-04 |

---

## 4. 全局风险 & 跨子需求依赖

### 跨子需求风险

| 风险 | 影响范围 | 缓解措施 |
|------|----------|----------|
| `meta.json` 结构变更 | S-01 ~ S-05 全部 | 版本号管理，向下兼容 |
| ID 生成策略调整 | S-01, S-03 | 封装在 `gen_next_id()` 中 |
| 锁超时导致操作失败 | S-03, S-04, S-05 | 调用方实现重试，脚本返回明确错误码 |
| Frontmatter 与 meta.json 不一致 | 文档读取方 | AI 承诺同步，明确分工，脚本不校验 frontmatter |

### 接口契约

| 接口 | 提供方 | 消费方 | 关键约束 |
|------|:---:|:---:|------|
| `ConfigLoader.read() → Path` | S-01 | S-02~S-05 | 读取失败时立即退出 |
| `MetaStore.load() → dict` | S-01 | S-02~S-05 | 返回 `{"requirements": {...}}` |
| `MetaStore.save(data: dict)` | S-01 | S-03~S-05 | 内部原子写入，调用方需先获取锁 |
| `FileLock` 上下文管理器 | S-01 | S-03~S-05 | 5s 超时，异常抛出 `TimeoutError` |
| `gen_next_id(reqs: dict) → str` | S-01 | S-03 | 返回 `"REQ-NNN"` |
