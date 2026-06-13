---
description: 文档或代码编写完成后，自动调用 auto-review skill 进行质量审查和修复闭环。审查完成后自动判断是否属于复杂场景，若属于则调用 challenger skill 进行二次质疑。
alwaysApply: true
enabled: true
updatedAt: 2026-06-13T16:48:00.000Z
provider:
---

# Writing Pipeline

## 规则

当 AI 完成以下任一操作后，**必须自动调用 `auto-review` skill** 执行审查修复闭环：

| 触发条件 | 操作类型 |
|----------|----------|
| 写入或修改 `.md` 文件 | `write_to_file` / `replace_in_file` |
| 写入或修改代码文件（`.py` `.sh` `.ps1` `.js` `.ts` `.java` `.go` `.rs` `.c` `.cpp` `.h` `.toml` `.yaml` `.yml` `.json` `.css` `.vue` `.tsx` `.jsx`） | `write_to_file` / `replace_in_file` |

## 执行流程

```
写完文件 → use_skill("auto-review") → 判断复杂场景 → (若复杂) use_skill("challenger")
```

### 第一步：auto-review 审查修复

按上述触发条件自动调用 `auto-review`。

### 第二步：复杂场景判断

auto-review 完成后，自动评估本次修改是否属于**复杂场景**。满足以下**任一条件**即视为复杂：

| 判断维度 | 复杂场景特征 |
|----------|-------------|
| 变更规模 | 涉及 3 个以上文件，或单文件变更超过 50 行 |
| 核心逻辑 | 修改涉及控制流（条件/循环）、错误处理、并发/异步逻辑 |
| Bug 修复 | 修复了运行时错误、逻辑缺陷、数据一致性问题 |
| 新增功能 | 添加了新的函数/方法/类/模块，或新增了外部接口 |
| 重构优化 | 重命名公共接口、提取模块、调整依赖关系、性能优化 |
| 关键路径 | 涉及认证、权限、数据持久化、支付、事务等关键业务逻辑 |
| 跨模块影响 | 变更影响多个模块之间的调用或数据流 |

**注意**：仅文档措辞修改、注释补充、格式调整、typo 修复等**不属于**复杂场景。

### 第三步：调用 challenger

判定为复杂场景后，**自动调用 `challenger` skill** 进行二次质疑审查：

```
use_skill("challenger")
```

调用时将本次修改的变更内容作为上下文传入，challenger 会根据变更类型（Bug 修复/新增功能/优化）选择对应质疑策略进行深度审查。

## 例外

以下情况跳过整条流水线：
- 用户明确说"不用审查"、"跳过审查"、"skip review"
- 单字符/标点修改

以下情况跳过 challenger（但不跳过 auto-review）：
- 用户明确说"不用质疑"、"跳过 challenger"
- 修改明确属于非复杂场景（见上表）
