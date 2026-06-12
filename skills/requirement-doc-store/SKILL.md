---
name: requirement-doc-store
description: >-
  需求相关文档的通用存储规范。根据文档类型自动决定存储路径，确保各 skill
  产出文档统一归位到需求目录下的正确子目录。
  适用场景：(1) 任何 skill 生成需求相关文档后需要落盘时，(2) design-craft
  完成设计文档需要存储时，(3) data-flow-model 完成数据流图需要存储时，
  (4) demo-verify 完成验证报告需要存储时，(5) code-review 完成审查报告
  需要存储时，(6) 需求完成后生成实现报告时。
---

# Requirement Doc Store（需求文档存储）

指导 AI 将需求相关的各类文档存入需求管理系统的正确路径，确保目录结构统一、可追溯。

## 核心原则

- **按文档类型分目录**：不同阶段产出的文档放入不同子目录
- **中文命名**：目录名和文件名使用中文，与 meta.json 中 feature 字段一致
- **只负责存储规范**：不生成文档内容，只指导存储位置和格式

## 目录结构

```
{功能名称}/
├── requirement.md              # 需求分析报告
├── changelog.md                # 变更追踪
├── report.md                   # 实现报告
├── design/
│   ├── DESIGN.md               # 技术设计文档
│   ├── data-flow.md            # 数据流/数据模型
│   ├── interaction-design.md   # 交互设计
│   └── design-review.md        # 设计评审报告
├── demo/
│   ├── verify-report.md        # 验证报告
│   └── [demo 代码文件]
├── test/
│   ├── test-plan.md            # 测试计划
│   └── test-report.md          # 测试报告
└── review/
    ├── code-review.md          # 代码审查报告
    └── challenge-report.md     # 质疑/二次审查报告
```

## 存储路径映射

| 文档类型 | 来源 Skill | 存储路径 |
|----------|-----------|----------|
| 需求分析 | requirement-mining | `requirement.md` |
| 技术设计 | design-craft | `design/DESIGN.md` |
| 数据流/模型 | data-flow-model | `design/data-flow.md` |
| 交互设计 | interaction-design | `design/interaction-design.md` |
| 设计评审 | design-review | `design/design-review.md` |
| Demo 验证 | demo-verify | `demo/verify-report.md` + 代码 |
| 测试计划 | - | `test/test-plan.md` |
| 测试报告 | - | `test/test-report.md` |
| 代码审查 | code-review | `review/code-review.md` |
| 质疑审查 | challenger | `review/challenge-report.md` |
| 实现报告 | 需求完成时 | `report.md` |
| 变更记录 | 全局 | `changelog.md` |

## 触发方式

任何 skill 在生成需求相关文档后，通过以下方式加载本 skill：

```markdown
请加载 requirement-doc-store skill，存储以下文档：

需求 ID：{REQ-NNN}
文档类型：{design / data-flow / review / test / demo / report}
文档内容：[Markdown 内容]
```

## 存储流程

### Step 1：确定需求目录

1. 从 `.requirements/config` 读取 `storage_path`
2. 通过 meta.json 或 `list-requirements.py --id {REQ-NNN}` 找到需求目录
3. 拼出完整路径：`{storage_path}/{需求目录}/`

### Step 2：确定子目录

根据文档类型映射表，确定目标子目录：

- `design`、`demo`、`test`、`review` 子目录如不存在，先创建
- 根目录文件（`requirement.md`、`report.md`、`changelog.md`）直接写入

### Step 3：写入文档

- Markdown 文档顶部包含 YAML frontmatter，至少包含 `feature`、`created`、`type` 字段
- 使用原子写入（tempfile → os.replace）

### Step 4：更新元数据（如需要）

文档落盘后，使用 `update-requirement.py` 更新 meta.json 的 `docs` 字段，**不要直接编辑 meta.json**：

```bash
# 添加关联文档
uv run python scripts/requirement-mgr/update-requirement.py <REQ-ID> --docs add <path>,<type>

# 示例：设计文档落盘后
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --docs add design/DESIGN.md,design

# 示例：实现报告落盘后
uv run python scripts/requirement-mgr/update-requirement.py REQ-001 --docs add report.md,report
```

| 文档类型 | `--docs add` 参数 |
|----------|--------------------|
| 需求分析 | `requirement.md,requirement` |
| 技术设计 | `design/DESIGN.md,design` |
| 数据流/模型 | `design/data-flow.md,data_flow` |
| 交互设计 | `design/interaction-design.md,design` |
| 设计评审 | `design/design-review.md,design` |
| Demo 验证 | `demo/verify-report.md,demo` |
| 测试计划 | `test/test-plan.md,test` |
| 测试报告 | `test/test-report.md,test` |
| 代码审查 | `review/code-review.md,review` |
| 质疑审查 | `review/challenge-report.md,review` |
| 实现报告 | `report.md,report` |

变更记录追加到 `changelog.md`（通过 `--changelog` 参数）。

## 行为边界

- **不生成文档**：只指导存储，不生成文档内容
- **不创建需求目录**：需求目录由 `create-requirement.py` 创建
- **中文命名**：目录名和文件名使用中文
- **只处理已存在的需求**：必须有对应的 meta.json 条目

## 参考

- 需求管理脚本使用指南：`docs/requirement-mgr-guide.md`
- CRUD 脚本路径：`scripts/requirement-mgr/`
