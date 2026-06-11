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

# S-03 create-requirement.py 设计

## 1. 术语

| 术语 | 定义 |
|------|------|
| ID 自增 | 读取现有最大编号 +1 生成新 ID |
| 目录冲突 | 目标目录 `{date}-{feature}` 已存在 |
| 依赖预校验 | 写入前检查 `--depends-on` 中所有 ID 是否已在 meta.json 中存在 |

## 2. 现状分析 (AS-IS)

无现有实现。

## 3. 方案设计 (TO-BE)

### 处理流程

```mermaid
flowchart TB
    Args["解析 CLI 参数"] --> Validate["校验：feature 非空<br/>tags 至少一个"]
    Validate --> Load["ConfigLoader → MetaStore.load()"]
    Load --> Check{"--depends-on<br/>中的 ID 都存在？"}
    Check -->|否| Err["报错退出：<br/>依赖 ID 不存在"]
    Check -->|是| GenID["gen_next_id()"]
    GenID --> Lock["获取 FileLock"]
    Lock -->|超时| TO["TimeoutError → 退出"]
    Lock -->|成功| Reload["重新加载 meta.json<br/>（防 TOCTOU）"]
    Reload --> Build["构建新条目"]
    Build --> Save["MetaStore.save() 原子写"]
    Save --> Mkdir["os.makedirs(目录)"]
    Mkdir --> Unlock["释放锁"]
    Unlock --> Out["输出: ID / 目录 / 路径"]
```

### 条目构建

```python
today = date.today().isoformat()
new_entry = {
    "id": req_id,                    # 自动生成
    "feature": args.feature,         # 用户输入
    "created": today,                # 自动
    "updated": today,                # 自动
    "status": args.status or "草案",  # 默认
    "tags": args.tags or ["feat"],    # 默认
    "version": 1,                    # 固定
    "depends_on": args.depends_on or [],
    "changelog": ["初始创建"],
    "commits": [],
    "data_flow": "",
    "report": "",
}
```

### 目录名生成

```
默认：{date}-{feature}
     2026-06-11-需求管理脚本系统

--dir-name：直接使用用户输入，冲突时报错
```

## 4. 接口设计

### CLI 参数

```
create-requirement.py --feature "名称"
                      [--tags feat,tool]
                      [--depends-on REQ-001,REQ-002]
                      [--status 草案]
                      [--dir-name custom-name]
```

| 参数 | 类型 | 必填 | 默认 | 校验 |
|------|------|:---:|------|------|
| `--feature` | str | ✅ | — | 非空 |
| `--tags` | str (逗号分隔) | ❌ | `"feat"` | 至少 1 个 |
| `--depends-on` | str (逗号分隔) | ❌ | — | 每个 ID 必须存在 |
| `--status` | str | ❌ | `"草案"` | 枚举值之一 |
| `--dir-name` | str | ❌ | `{date}-{feature}` | 目录不冲突 |

### 函数签名

```python
def create_requirement(
    storage_root: Path,
    feature: str,
    tags: list[str] | None = None,
    depends_on: list[str] | None = None,
    status: str = "草案",
    dir_name: str | None = None,
) -> dict:
    """创建需求，返回 {"id": "...", "dir": "...", "meta_path": "..."}
    
    Raises:
        ValueError: feature 为空 / tags 为空 / 依赖 ID 不存在
        FileExistsError: 目录名冲突
        TimeoutError: 获取锁超时
    """
    ...
```

## 5. 关键决策点

### 决策 1：目录名生成策略

| 方案 | 优劣 |
|------|------|
| 纯日期 `2026-06-11-1` | ❌ 无法从目录名识别功能 |
| 纯功能名 `需求管理脚本系统` | ❌ 无时间信息，URL 不安全 |
| **日期+功能名** `2026-06-11-requirement-management` | ✅ 兼顾时间和可读性 |

**决定**：日期+功能名。用户可通过 `--dir-name` 覆盖。

### 决策 2：ID 并发分配

问题：两个 create 同时执行，读到相同的最大编号。

| 方案 | 优劣 |
|------|------|
| 不加锁直接分配 | ❌ ID 重复 |
| **加锁后重新读取** | ✅ 防 TOCTOU ✅ 简单 |

**决定**：获取锁后重新读取 `meta.json`（防 TOCTOU 窗口），再计算 ID。

### 决策 3：依赖 ID 不存在时的处理

**决定**：前置校验阶段报错，拒绝创建。不允许创建指向不存在的依赖。

## 6. 异常处理

| 场景 | 行为 | 退出码 |
|------|------|:---:|
| `--feature` 为空 | "feature 不能为空" | 1 |
| `--tags` 为空 | "至少需要一个标签" | 1 |
| `--depends-on` 含不存在 ID | "依赖需求 REQ-XXX 不存在" | 1 |
| 目录名冲突 | "目录已存在: ..." | 1 |
| 锁超时 | "无法获取锁，请稍后重试" | 2 |
| ID 编号超过 999 | "需求编号已达上限" | 1 |
| 磁盘满 | OS 异常透传 | 1 |

## 7. 关键流程时序图

```mermaid
sequenceDiagram
    participant User
    participant CLI as create-requirement
    participant CL as ConfigLoader
    participant MS as MetaStore
    participant FL as FileLock
    participant FS as 文件系统

    User->>CLI: --feature "xxx" --tags feat --depends-on REQ-001
    CLI->>CL: read()
    CL-->>CLI: Path(".requirements")
    CLI->>MS: load()
    MS-->>CLI: data
    Note over CLI: 校验 depends_on ID 存在
    Note over CLI: gen_next_id() = "REQ-002"
    CLI->>FL: acquire() [5s 超时]
    FL-->>CLI: 获取成功
    CLI->>MS: load() [TOCTOU 重读]
    MS-->>CLI: fresh_data
    Note over CLI: 构建新条目
    CLI->>MS: save(data)
    MS->>FS: atomic_write(meta.json)
    MS-->>CLI: 写入成功
    CLI->>FS: os.makedirs(目录)
    CLI->>FL: release()
    CLI->>User: ID: REQ-002, 目录: ..., meta.json: ...
```
