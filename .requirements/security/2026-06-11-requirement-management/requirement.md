---
id: REQ-001
feature: 需求管理脚本系统
status: 草案
created: 2026-06-11
updated: 2026-06-11
version: 3
tags: [feat, tool]
depends_on: []
author: AI
document_type: requirement
---

# 需求摘要：需求管理脚本系统

## 核心诉求
为 `.requirements/` 需求管理系统提供脚本工具，支持需求的增删改查和元数据集中管理。

## 需求形态
真实需求

## 核心场景
- 场景 1：用户在项目中执行脚本，列出所有已有需求及其状态
- 场景 2：用户新建一个需求，脚本自动创建目录并写入 meta.json
- 场景 3：用户修改需求状态/标签/依赖等元数据
- 场景 4：用户删除一个需求，脚本清理目录和元数据

## 根本性分析结论
- 核心问题：需求信息分散在各个 YAML frontmatter 中，查询和更新效率低
- 方案评估：情况 A（方案对症）
- 建议：使用集中式 meta.json 管理所有需求的元数据，脚本统一操作 meta.json 和目录结构

## 需求清单
| 优先级 | 需求 ID | 需求描述 | 验收标准 |
|--------|--------|----------|----------|
| P0 | REQ-01 | list-requirements.py — 列出所有需求，支持按状态/标签/日期筛选 | 执行脚本可输出格式化的需求列表 |
| P0 | REQ-02 | create-requirement.py — 创建新需求目录 + 写入 meta.json | 执行后目录和元数据同步创建 |
| P0 | REQ-03 | update-requirement.py — 修改需求的元数据字段 | 执行后 meta.json 对应条目更新 |
| P0 | REQ-04 | delete-requirement.py — 删除目录 + 移除 meta.json 条目 | 执行后目录和元数据同步清理 |

## 关键假设
| 假设 | 验证状态 |
|------|----------|
| meta.json 作为单一元数据源，通过文件锁保证并发安全 | 待验证 |
| 多个 AI Agent 或进程可能同时操作 meta.json，必须支持并发 | 已确认 |

## 技术选型
- **语言**：Python 3.x（零依赖，标准库覆盖原子写入 + 跨平台文件锁）
- **原子写入**：`tempfile` + `os.replace()` 保证写入完整性
- **并发安全**：`fcntl.flock`（Unix）/ `msvcrt.locking`（Windows）排他锁 + 5s 超时

## 非功能性约束
- 脚本跨平台兼容（Windows/Linux/Mac）
- 输出格式支持文本表格和 JSON 两种模式
- 零外部依赖，仅使用 Python 标准库
- 并发安全：多个进程同时操作 meta.json 不会导致数据丢失或损坏

## 潜在风险
- ~~meta.json 写入中途崩溃可能导致数据不一致~~ → 已通过原子写入策略解决
- 文件锁超时场景下，调用方需实现重试逻辑（如 AI Agent 收到 TimeoutError 后重试整个操作）
