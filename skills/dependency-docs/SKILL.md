---
name: dependency-docs
description: 在设计前识别并整理第三方依赖文档。扫描需求中的外部系统、API、SDK 等依赖，每个依赖生成独立文档，存入需求目录。依赖数量 ≥ 2 时自动调用 task-dispatch 并行收集信息以加速。适用于"整理第三方依赖"、"收集 API 文档"、"外部依赖梳理"等场景。
---

# 第三方依赖文档整理器

## 概述

**目的**：在设计阶段前识别并整理第三方依赖文档，为技术设计提供完整的外部依赖信息。

**功能**：扫描需求中的外部系统、API、SDK 等依赖，每个依赖生成**独立文档**。依赖 ≥ 2 个时自动调用 `task-dispatch` 并行收集信息以加速。

**使用场景**：
- 需求涉及第三方 API、SDK、外部服务时
- 设计前需要梳理外部依赖关系时
- 需要整理第三方文档供后续设计参考时

## 核心原则

1. **前置整理**：在设计阶段前完成，为设计提供输入
2. **一依赖一文档**：每个第三方依赖独立成文，便于按需引用和维护
3. **并行加速**：依赖 ≥ 2 时自动用 task-dispatch 并行收集，I/O 密集型任务天然适合并行
4. **结构化输出**：统一模板，每个依赖文档结构一致

---

## 工作流总览

```
阶段 1：依赖识别       → 扫描需求，识别所有第三方依赖
阶段 2：并行信息收集    → 依赖 ≥ 2 时 task-dispatch 并行收集，1 个时直接收集
阶段 3：索引生成 + 落盘 → 主 agent 写 README.md 索引 + 写入各依赖文档
```

**未得到用户对当前阶段的确认前，不进入下一阶段。**

---

## 阶段 1：依赖识别

### 输入

需求描述或需求挖掘报告。

### 识别维度

| 依赖类型 | 识别信号 | 示例 |
|----------|---------|------|
| 第三方 API | 调用外部 HTTP 接口 | OpenAI API、Stripe 支付 |
| 第三方 SDK | 引入外部库/包 | AWS SDK、Google Maps SDK |
| 外部服务 | 依赖外部系统能力 | Redis、消息队列、CDN |
| 数据源 | 连接外部数据库/数据源 | 第三方数据提供商 |

### 输出格式

```text
📦 第三方依赖清单
━━━━━━━━━━━━━━━━

| # | 依赖名称 | 类型 | 用途 | 信息完整度 |
|---|----------|------|------|-----------|
| 1 | OpenAI API | 第三方 API | 文本生成 | 需补充 |
| 2 | Stripe | 第三方 API | 支付处理 | 需补充 |

共识别 N 个第三方依赖。

[若 N ≥ 2]
  → 将使用 task-dispatch 并行收集信息，预计加速 {N} 倍。

请确认清单是否完整？是否有遗漏的依赖？
```

---

## 阶段 2：并行信息收集

### 子任务拆分

每个依赖拆为一个子任务，编号 `D-{NN}`：

```text
| 编号 | 子任务 | 依赖 | 类型 | 信息收集目标 |
|------|--------|------|------|-------------|
| D-01 | OpenAI API 文档整理 | OpenAI API | 第三方 API | 官方文档、接口清单、认证方式 |
| D-02 | Stripe 文档整理 | Stripe | 第三方 API | 官方文档、接口清单、认证方式 |
```

独立性校验：各依赖之间完全独立（无文件冲突、无接口依赖、无共享资源），可同批并行。

### 执行策略

| 依赖数量 | 策略 |
|----------|------|
| 1 个 | 主 agent 直接收集，不走 task-dispatch |
| ≥ 2 个 | 调用 `task-dispatch` skill 并行收集 |

### task-dispatch 调度要点

**task-name**：`dependency-docs-{功能简称}`（如 `dependency-docs-user-auth`）

**子 agent prompt 要点**（每个子 agent 负责一个依赖）：

```
你是子 agent，负责整理第三方依赖 D-{NN}：{依赖名称}

## 任务目标
收集 {依赖名称} 的完整信息，生成结构化文档。

## 输出目录
代码/文档产出：.codebuddy/task-dispatch/dependency-docs-{功能简称}/subtasks/D-{NN}/code/
  - 产出文件：{依赖名称}.md（按下方模板生成）
执行报告：.codebuddy/task-dispatch/dependency-docs-{功能简称}/subtasks/D-{NN}/report.md

## 信息收集要求
1. 优先使用 WebFetch 抓取官方文档页面获取最新信息
2. 若文档信息不足，使用 WebSearch 搜索补充
3. 按以下模板生成 {依赖名称}.md，所有必填字段不得为空：

## {依赖名称}

### 基本信息
| 字段 | 内容 |
|------|------|
| 类型 | API / SDK / 服务 / 数据源 |
| 官方文档 | 文档链接 |
| 用途 | 在本需求中的具体作用 |
| 版本要求 | 最低/推荐版本 |

### 接口清单
| 接口/方法 | 用途 | 请求方式 | 关键参数 | 返回格式 |
|-----------|------|----------|----------|----------|
| ... | ... | ... | ... | ... |

### 认证与配置
- 认证方式：API Key / OAuth / 其他
- 配置项：所需的环境变量、配置文件等

### 限流与配额
- 频率限制：
- 配额上限：

### 备选方案
- 可替代的其他服务及对比：

### 风险与注意事项
- 稳定性：
- 成本：
- 合规：

4. 完成后写 report.md，说明信息收集来源和关键发现
5. 遇到无法获取的信息，标注"待补充"，不编造
```

### task-dispatch 执行

按照 `task-dispatch` skill 的标准流程执行：
- 批次划分：所有子任务同批并行（无依赖关系）
- 并行执行：team_create + Task 并行启动各子 agent
- 合并集成：主 agent 收集各子 agent 产出的 `.md` 文件

### 合并后进入阶段 3

```text
🔨 依赖文档收集完成

| 依赖 | 状态 | 产出文件 |
|------|------|----------|
| OpenAI API | ✅ 完成 | openai-api.md |
| Stripe | ✅ 完成 | stripe.md |

进入阶段 3 生成索引并落盘。
```

---

## 阶段 3：索引生成 + 落盘

### 目录结构（固定多文档模式）

```
dependencies/
├── README.md              # 总览索引
├── {依赖1名称}.md          # 依赖1详情（子 agent 产出）
├── {依赖2名称}.md          # 依赖2详情（子 agent 产出）
└── verify/                # 可选：Demo 验证脚本
    ├── verify_{依赖名}.py
    └── README.md
```

### README.md（索引）

主 agent 写入，汇总所有依赖：

```markdown
# 第三方依赖文档索引

## 依赖总览

| 依赖名称 | 类型 | 用途 | 详情文档 | 信息完整度 |
|----------|------|------|----------|-----------|
| OpenAI API | 第三方 API | 文本生成 | [详情](./openai-api.md) | ✅ 完整 |
| Stripe | 第三方 API | 支付处理 | [详情](./stripe.md) | ✅ 完整 |

## 使用说明

- 每个依赖的详细信息见独立文档
- 设计时按需查阅相关依赖文档
- 如需 Demo 验证，参考 verify/ 目录
```

### 单个依赖文档

子 agent 已按模板生成，主 agent 校验完整性后直接落盘，不重新生成。

### 落盘

1. 创建目录：`dependencies/`（位于需求文档目录下）
2. 写入 README.md + 各依赖文档
3. 需求管理集成（如已配置 `.requirements/config`）：

```bash
req update {REQ-NNN} \
  --docs add dependencies/README.md,reference \
  --docs add dependencies/{依赖1}.md,reference \
  --docs add dependencies/{依赖2}.md,reference \
  --changelog "整理第三方依赖文档"
```

### 输出格式

```text
✅ 第三方依赖文档已生成

文档位置：{path}/dependencies/
文档数量：{N+1} 个文件（1 个索引 + N 个依赖文档）

| 文件 | 说明 |
|------|------|
| README.md | 依赖总览索引 |
| openai-api.md | OpenAI API 详情 |
| stripe.md | Stripe 详情 |

是否需要对外部依赖进行 Demo 验证？
  - 验证内容：编写验证脚本，确认第三方 API/SDK 的可用性
  - 安全要求：敏感信息从环境变量读取，不写入代码

请选择 [是/否]：
```

---

## 阶段 4（可选）：Demo 验证

当用户选择对依赖进行 Demo 验证时触发。

### 验证脚本规范

**安全要求（强制）**：
- **禁止硬编码**：API Key、Token、密码不写入脚本
- **环境变量读取**：所有敏感配置从环境变量获取

```python
import os
import requests

API_KEY = os.environ.get("SERVICE_API_KEY")
if not API_KEY:
    raise ValueError("请设置环境变量 SERVICE_API_KEY")

def test_api_connection():
    response = requests.get(
        "https://api.example.com/health",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    return response.status_code == 200
```

### 存储位置

```
dependencies/
├── README.md
├── {依赖}.md
└── verify/
    ├── verify_{依赖名}.py
    └── README.md（运行说明）
```

验证脚本存放于 `dependencies/verify/`，`verify/README.md` 包含运行说明。

---

## 反模式

- ❌ 只列名称不整理详情：文档必须包含接口清单、认证方式等关键信息
- ❌ 信息过时：优先使用 WebFetch 获取最新文档
- ❌ 遗漏依赖：设计阶段才发现未整理的依赖会打断流程
- ❌ 文档无结构：必须使用统一模板，便于后续引用
- ❌ 硬编码敏感信息：API Key、Token 不得写入脚本，必须从环境变量读取
- ❌ 多个依赖合成一个大文档：每个依赖独立成文，便于按需引用

---

## 需求管理集成

当项目配置了 `.requirements/config` 时自动执行：

### 存储路径映射

| 产出物 | 存储路径 | docs 类型 |
|--------|----------|----------|
| 依赖索引 | `dependencies/README.md` | `reference` |
| 单个依赖文档 | `dependencies/{名称}.md` | `reference` |
| 验证脚本 | `dependencies/verify/verify_{依赖名}.py` | `reference` |
| 验证说明 | `dependencies/verify/README.md` | `reference` |
