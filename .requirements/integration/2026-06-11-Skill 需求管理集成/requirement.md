---
id: REQ-002
feature: Skill 需求管理集成
status: 已确认
created: 2026-06-11
updated: 2026-06-11
version: 1
tags: [feat, tool, integration]
depends_on: [REQ-001]
author: AI
document_type: requirement
---

# Skill 需求管理集成

## 核心诉求

将各 Skill 的产出物与 `meta.json` 需求元数据关联，形成完整的需求-设计-实现-验收链路，避免文档散落。

## 核心场景

- **场景 1**：design-craft 生成设计文档后，自动写入需求目录并更新 meta.json 状态
- **场景 2**：data-flow-model 生成数据流图后，自动回写路径到 meta.json
- **场景 3**：implementation-report 生成实现报告后，自动更新状态为"已完成"并追加 commit

## 需求清单

| 优先级 | 需求 ID | 需求描述 | 预期效果 | 依赖 |
|:---:|--------|----------|----------|------|
| P0 | REQ-002-01 | design-craft 集成 | 设计文档写入 `{dir}/design/`，状态→设计中 | REQ-001 |
| P0 | REQ-002-02 | data-flow-model 集成 | 数据流文档写入 `{dir}/data-flow.md`，回写路径 | REQ-001 |
| P0 | REQ-002-03 | implementation-report 集成 | 实现报告写入 `{dir}/report.md`，状态→已完成 | REQ-001 |
| P1 | REQ-002-04 | work-breakdown 集成 | 工作项清单写入需求目录 | REQ-001 |
| P1 | REQ-002-05 | interaction-design 集成 | 交互设计文档写入需求目录 | REQ-001 |
| P1 | REQ-002-06 | design-review 集成 | 评审结果关联到需求 changelog | REQ-001 |
| P2 | REQ-002-07 | code-review / challenger 集成 | 读取需求上下文作为 review 参照 | REQ-001 |
| P2 | REQ-002-08 | demo-verify 集成 | 验证 demo 代码写入 `{dir}/demo/`，验证结果写入 `{dir}/demo/result.md` | REQ-001 |

## 需求依赖图

```
REQ-001 (需求管理脚本系统)
    ↓
REQ-002 (Skill 需求管理集成)
    ├─ REQ-002-01 design-craft
    ├─ REQ-002-02 data-flow-model
    ├─ REQ-002-03 implementation-report
    ├─ REQ-002-04 work-breakdown
    ├─ REQ-002-05 interaction-design
    ├─ REQ-002-06 design-review
    ├─ REQ-002-07 code-review / challenger
    └─ REQ-002-08 demo-verify
```

## 集成模式

### 写入型（产出落盘）

design-craft, data-flow-model, implementation-report, interaction-design, work-breakdown

```bash
# 1. 获取需求上下文
uv run python scripts/requirement-mgr/list-requirements.py --id REQ-NNN --deps

# 2. Skill 生成文档 → 写入需求目录

# 3. 回写文档路径和状态
# --docs add PATH,TYPE：追加文档记录到 meta.json 的 docs 数组
uv run python scripts/requirement-mgr/update-requirement.py REQ-NNN \
  --docs add data-flow.md,data_flow --status 设计中

# 其他写入型示例：
# design-craft → --docs add design/main.md,design --status 设计中
# implementation-report → --docs add report.md,report --status 已完成 --commit abc1234
```

### 读取型（消费需求上下文）

code-review, challenger, design-review, expert-panel

```bash
# 获取需求背景
uv run python scripts/requirement-mgr/list-requirements.py --id REQ-NNN
```

## 元数据字段生命周期

```
create (requirement-mining)
  ├─ status = "已确认"
  ├─ docs = []
  └─ commits = []
       │
       ▼
data-flow-model
  ├─ docs += [{path: "data-flow.md", type: "data_flow"}]
  └─ 写入 data-flow.md
       │
       ▼
design-craft
  ├─ status = "设计中"
  └─ 写入 design/*.md → docs += [{path: "design/main.md", type: "design"}]
       │
       ▼
开发实现
  └─ commits 追加 commit hash
       │
       ▼
implementation-report
  ├─ status = "已完成"
  ├─ docs += [{path: "report.md", type: "report"}]
  └─ 写入 report.md
```

## 实施建议

1. 先改造 P0 Skill（design-craft, data-flow-model, implementation-report）
2. 再改造 P1 Skill（work-breakdown, interaction-design, design-review）
3. P2/P3 暂不改造，保持独立运行

改造方式：在每个 Skill 的 SKILL.md 中增加"需求管理集成"章节。

## 验收标准

- [ ] P0 Skill 改造完成，可自动写入需求目录并更新 meta.json
- [ ] P1 Skill 改造完成
- [ ] 集成分析文档已更新（含改造后的具体步骤）

## 错误处理策略

各 Skill 在调用需求管理脚本时，可能遇到以下异常情况：

| 异常场景 | 处理方式 | 脚本退出码 |
|----------|----------|-----------|
| 需求 ID 不存在 | 提示用户先创建需求，跳过集成步骤 | 1 |
| 文件锁超时（并发冲突） | 自动重试 1 次，仍失败则告知用户稍后重试 | 2 |
| 标签/状态校验失败 | 提示具体校验错误，不自动修复（需用户确认） | 1 |
| 写入文件失败（权限/磁盘） | 告知用户具体错误，保留已生成的文档内容 | 1 |

**重试策略**：仅对文件锁超时（退出码 2）自动重试 1 次，其余错误直接报告用户。

## 关键假设

| 假设 ID | 假设内容 | 验证难度 |
|---------|----------|----------|
| H-01 | 各 Skill 的 SKILL.md 可以被修改以增加集成章节 | 低 |
| H-02 | AI Agent 在执行 Skill 时能正确调用 CRUD 脚本 | 中 |
| H-03 | 需求目录结构（{category}/{date}-{feature}）能容纳所有产出物 | 低 |
| H-04 | 设计文档多文件结构（design-craft SUB_TEMPLATE）使用子目录 design/ 组织，不与根目录文件冲突 | 低 |