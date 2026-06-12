---
id: REQ-003
feature: 需求文档存储规范
status: 已确认
created: 2026-06-11
updated: 2026-06-11
version: 1
tags: [feat, tool, integration]
depends_on: [REQ-001]
author: AI
document_type: requirement
---

# 需求挖掘报告：需求文档存储规范

## 1. 核心诉求

将 `implementation-report` skill 重新定位为通用的 `requirement-doc-store`，为所有需求相关文档提供统一的存储规范，让 design-craft、data-flow-model、demo-verify、code-review 等多个 skill 都能通过同一入口将产出文档存入正确位置。

## 2. 核心场景

- 场景 1：design-craft 完成技术设计后，加载此 skill 将设计文档存入 `design/` 目录
- 场景 2：data-flow-model 完成数据流图后，加载此 skill 存入 `design/` 目录
- 场景 3：demo-verify 完成验证后，加载此 skill 将验证报告存入 `demo/` 目录
- 场景 4：code-review 完成审查后，加载此 skill 将审查报告存入 `review/` 目录
- 场景 5：需求开发完成后，加载此 skill 生成实现报告并存入根目录

## 3. 根本性分析结论

**情况 A：方案对症** — 当前 `implementation-report` 名称暗示只用于"实现完成后的报告"，实际上它是一个文档存储的指导规范，应定位为通用入口。重命名并扩展功能是直接正确的方案。

## 4. 需求清单

| 优先级 | 需求 ID | 需求描述 | 预期效果 | 依赖 | 验收标准 |
|--------|--------|----------|----------|------|----------|
| P0 | REQ-01 | 重命名 `implementation-report` → `requirement-doc-store`，重新定位为通用需求文档存储指导 skill | 名称无歧义，skill 可被多个下游 skill 复用 | - | 新 skill 创建，旧 skill 删除 |
| P0 | REQ-02 | 统一 feature-name 为中文格式 | 目录名可读，与 meta.json 中 feature 字段一致 | - | 所有文档路径使用中文 |
| P0 | REQ-03 | 明确文档目录结构：`design/`、`demo/`、`test/`、`review/`，以及根目录 `changelog.md` | 各 skill 产出文档有明确存储路径 | REQ-01 | 目录结构覆盖所有文档类型 |
| P1 | REQ-04 | 更新 `design-craft` SKILL.md 中的落盘路径引用，对齐新规范 | design-craft 接入统一存储规范 | REQ-01, REQ-03 | design-craft 阶段5引用 requirement-doc-store |
| P1 | REQ-05 | 更新 `requirement-mining` SKILL.md，Step 8 引用 `requirement-doc-store` | 需求挖掘完成后按统一规范落盘 | REQ-01 | requirement-mining 不再引旧 skill |

## 5. 文档目录结构

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

## 6. 关键假设

| 假设 ID | 假设内容 | 验证难度 | 验证建议 |
|---------|----------|----------|----------|
| H-01 | 所有下游 skill 遵循统一存储规范 | 低 | 逐个更新各 skill 引用 |
| H-02 | `design-craft` 的设计文档落盘逻辑可直接对接到 requirement-doc-store | 低 | 对比 design-craft 阶段5 与新规范 |
