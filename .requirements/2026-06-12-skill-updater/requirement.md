# 需求：创建 skill-updater 技能

## 需求背景

每次添加新技能时，都需要手动更新 `skill-install.sh` 和 `skill-install.ps1` 中的文件列表，容易遗漏且维护成本高。

## 需求清单

| 优先级 | 需求 ID | 需求描述 | 预期效果 | 验收标准 |
|--------|---------|----------|----------|----------|
| P0 | REQ-201 | 创建 `skill-updater` skill | 指导AI自动更新安装脚本 | skill文档完整，AI可执行 |
| P0 | REQ-202 | 更新安装脚本，排除 `skill-updater` | 避免用户安装维护工具 | 安装脚本不包含该skill |
| P1 | REQ-203 | 更新skill安装脚本文件列表 | 与当前skills目录保持一致 | 文件列表准确无遗漏 |

## 实现结果

### REQ-201：创建 skill-updater 技能

**状态**：已完成

创建了 `skills/skill-updater/SKILL.md`，包含：
- 何时使用本技能
- 核心功能说明
- 详细执行步骤（扫描目录、过滤文件、生成列表、更新脚本）
- 完整示例
- 注意事项和触发短语

### REQ-202：更新安装脚本排除 skill-updater

**状态**：已完成

在两个安装脚本中添加了注释：
- `scripts/skill-install.sh`：添加注释 `# 注意: skill-updater 是内部维护工具，不包含在用户安装列表中`
- `scripts/skill-install.ps1`：添加注释 `# 注意: skill-updater 是内部维护工具，不包含在用户安装列表中`

### REQ-203：更新skill安装脚本文件列表

**状态**：已完成

验证了当前文件列表与 `skills/` 目录一致：
- 当前 `skills/` 目录包含 16 个技能目录
- 安装脚本文件列表包含 31 个文件（排除 `skill-updater`）
- 文件列表完整，无遗漏

## 文件变更清单

1. **新建文件**：
   - `skills/skill-updater/SKILL.md`

2. **修改文件**：
   - `scripts/skill-install.sh`（添加注释）
   - `scripts/skill-install.ps1`（添加注释）

## 验证方法

1. 使用 `skill-updater` 技能指导 AI 更新安装脚本
2. 验证更新后的文件列表与 `skills/` 目录一致
3. 验证 `skill-updater` 被正确排除
4. 测试安装脚本是否正常工作

## 后续改进建议

1. 考虑将文件列表生成逻辑提取为独立脚本
2. 添加自动化测试验证文件列表一致性
3. 考虑支持技能版本管理
