# Task Dispatch 参考文档

子 agent prompt 模板、冲突处理细节与产出文件格式。主文件见 [SKILL.md](SKILL.md)。

## 产出文件格式

### report.md（子任务执行报告）

```markdown
# 子任务 S-{NN} 执行报告

## 任务目标
{复述目标}

## 产出文件清单
| 文件路径 | 类型 | 说明 |
|----------|------|------|
| src/services/user_service.py | 新增 | 用户服务实现 |
| src/models/user.py | 修改 | 新增 email 字段 |

## 接口约定（供其他子任务/主 agent 参考）
- UserService.login(username, password) -> TokenPair
- UserService.register(data) -> User

## 修改点说明（针对修改现有文件）
- src/models/user.py：新增 email 字段（第 X 行），原因：...

## 注意事项
- {实现中的关键决策、假设、风险}

## 阻塞点（如有）
- {无法独立完成的问题，需主 agent 协调}
```

### merge-log.md（合并日志）

```markdown
# 合并日志

## 合并统计
- 子任务数：N
- 产出文件数：M
- 直接合并：X
- 冲突处理：Y
- 无法合并：Z

## 逐文件合并记录
| 文件路径 | 来源 | 合并方式 | 说明 |
|----------|------|----------|------|
| src/services/user_service.py | S-01 | 直接合并 | 新增文件 |
| src/models/user.py | S-01, S-02 | 三方合并 | 两子任务均修改，已合并 |

## 冲突处理记录
### {文件}
- 冲突类型：文件冲突
- 涉及子任务：S-01, S-02
- 处理方式：三方合并
- 处理结果：{说明}
```

### final-report.md（最终交付报告）

```markdown
# 任务并行调度报告

## 任务概述
- 任务名称：{名称}
- task-name：{task-name}
- 执行时间：{YYYY-MM-DD HH:MM}

## 拆分与执行
- 子任务数：N
- 并行批次：X
- 子任务清单：
  | 编号 | 子任务 | 批次 | 状态 | 产出文件数 |
  |------|--------|------|------|------------|

## 合并与校验
- 直接合并：P
- 冲突处理：Q
- 一致性校验：✅ 通过 / ⚠️ 存在问题

## 产出文件清单
| 文件路径 | 类型 | 来源子任务 |
|----------|------|------------|

## 过程文件索引
- 拆分方案：.codebuddy/task-dispatch/{task-name}/plan.md
- 子任务报告：.codebuddy/task-dispatch/{task-name}/subtasks/*/report.md
- 合并日志：.codebuddy/task-dispatch/{task-name}/merge-log.md
```

---

## 子 agent Prompt 模板

### 标准子 agent Prompt

```
你是子 agent，负责执行子任务 S-{NN}：{子任务名称}

## 任务目标
{目标描述}

## 涉及文件
{文件列表，标注新增/修改}

## 输入依赖
{依赖说明，如：无 / 依赖契约文件 .codebuddy/task-dispatch/{task-name}/contracts/user-service.md}

## 输出目录
代码产出：.codebuddy/task-dispatch/{task-name}/subtasks/S-{NN}/code/
  - 代码按项目相对路径摆放（如 src/services/user_service.py）
执行报告：.codebuddy/task-dispatch/{task-name}/subtasks/S-{NN}/report.md

## 工作要求
1. 只在输出目录内工作，不修改项目源码目录中的任何文件
2. 代码按项目实际相对路径摆放，便于主 agent 合并
3. 对于"修改现有文件"的任务：
   - 先用 read_file 读取项目中的原文件
   - 在输出目录中产出修改后的完整文件（不产出 diff）
   - 在 report.md 中说明修改点
4. 完成后写 report.md，包含：
   - 任务目标（复述）
   - 产出文件清单（路径 + 类型 + 说明）
   - 接口约定（供其他子任务/主 agent 参考）
   - 修改点说明（针对修改现有文件）
   - 注意事项（关键决策、假设、风险）
   - 阻塞点（如有，说明无法独立完成的问题）
5. 如需与其他子 agent 确认接口契约，通过 send_message 沟通（仅限接口确认，不传大段代码）
6. 遇到无法独立完成的问题，写入 report.md 的"阻塞点"章节，不要自行扩大范围

## 验收标准
{验收标准列表}

完成后通过 send_message 向 main 回报："S-{NN} 完成"。
```

### 弱依赖场景的补充说明

当子任务有弱依赖（需先定契约）时，在 prompt 中增加：

```
## 接口契约（必须遵守）
本子任务依赖以下接口契约，实现时必须严格遵循：
- 契约文件：.codebuddy/task-dispatch/{task-name}/contracts/{contract}.md
- 关键约定：
  {列出契约中的关键签名，便于子 agent 直接看到}

如发现契约与实际需求冲突，通过 send_message 向 main 报告，不要自行修改契约。
```

### 修改现有文件的补充指引

```
## 修改现有文件指引
本子任务涉及修改现有文件，遵循以下流程：
1. 用 read_file 读取原文件完整内容
2. 理解现有代码结构，确定修改点
3. 在输出目录中产出修改后的完整文件
4. 在 report.md 的"修改点说明"中列出：
   - 修改位置（文件 + 大致行号或函数名）
   - 修改内容（新增/删除/替换了什么）
   - 修改原因

注意：产出完整文件，不产出 diff 或 patch 格式。
```

---

## 冲突处理细节

### 文件冲突处理流程

当两个或多个子任务修改了同一文件时：

```
1. 主 agent 识别冲突：扫描所有 subtasks/*/code/ 下的文件路径，发现同一相对路径被多个子任务产出
2. 读取所有相关产出 + 项目原文件
3. 三方合并：
   a. 以项目原文件为基准
   b. 识别每个子任务的修改区域
   c. 若修改区域不重叠 → 合并所有修改
   d. 若修改区域重叠 → 进入人工合并决策
4. 人工合并决策（修改区域重叠时）：
   a. 分析每个子任务的修改意图
   b. 判断是否可以语义合并（如两者都新增方法，可都保留）
   c. 若无法语义合并 → 标记给用户决策，提供选项
5. 合并后写入项目源码目录
6. 记录到 merge-log.md
```

### 接口冲突处理流程

当不同子任务对同一接口的签名定义不一致时：

```
1. 主 agent 收集所有子任务 report.md 中的"接口约定"
2. 比对同名接口的签名（方法名、参数、返回值）
3. 若有契约文件 → 以契约为准，让偏离的子任务修复
4. 若无契约文件：
   a. 以先完成者为基准
   b. 通知后完成者适配
   c. 若后完成者已产出，主 agent 直接修改其产出以适配
5. 修复后重新校验接口一致性
6. 记录到 merge-log.md
```

### 逻辑冲突处理流程

当不同子任务的实现逻辑矛盾（如同一行为不同语义）时：

```
1. 主 agent 识别逻辑冲突（通常在一致性校验阶段发现）
2. 不静默选择，标记给用户决策
3. 提供冲突描述 + 选项：
   - 选项 A：采用子任务 S-0X 的实现，原因：...
   - 选项 B：采用子任务 S-0Y 的实现，原因：...
   - 选项 C：重新实现，原因：...
4. 用户决策后执行
5. 记录到 merge-log.md
```

---

## 一致性校验命令参考

### 编译/语法检查

| 语言 | 命令 |
|------|------|
| Python | `python -m py_compile {file}` 或 `python -m pyflakes {file}` |
| TypeScript | `tsc --noEmit` |
| Go | `go build ./...` |
| Java | `javac {file}` 或依赖构建工具 |
| Rust | `cargo check` |

### 导入完整性检查

扫描所有合并后文件的 import 语句，验证目标模块存在：

```
1. 用 search_content 搜索所有合并文件的 import/from/require 语句
2. 提取目标模块路径
3. 验证目标模块文件是否存在
4. 若不存在 → 标记为导入缺失
```

### 接口一致性检查

```
1. 收集所有子任务 report.md 的"接口约定"
2. 对每个被调用的接口，找到其定义所在文件
3. 比对调用方使用的签名与定义方的签名
4. 不一致 → 标记为接口冲突
```

---

## 批次内协调示例

### 接口确认场景

子 agent S-03 需要调用 S-01 的 UserService，但契约未完全明确：

```
S-03 → send_message → S-01：
"S-03 需要调用 UserService.login，确认签名是 login(username, password) 还是 login(cred: LoginRequest)？"

S-01 → send_message → S-03：
"签名是 login(username: str, password: str) -> TokenPair，返回 {access_token, refresh_token, expires_in}"

S-03 按确认后的签名实现
```

### 阻塞回报场景

子 agent S-02 遇到无法独立完成的问题：

```
S-02 → send_message → main：
"S-02 阻塞：需要修改 src/config.py 中的数据库配置，但该文件不在我的任务范围内。
建议：主 agent 协调，或扩展我的任务范围。"

主 agent 决策：
- 选项 A：主 agent 直接修改 config.py
- 选项 B：扩展 S-02 任务范围，允许其产出 config.py 的修改
- 选项 C：创建新子任务 S-04 处理 config.py
```

---

## 异常处理

### 子 agent 失败

| 情况 | 处理 |
|------|------|
| 子 agent 无响应 | 主 agent 等待合理时间后终止，标记该子任务失败，其他子任务继续 |
| 子 agent 产出为空 | 主 agent 标记"该子任务未产出"，记录到 final-report.md |
| 子 agent 超时 | 主 agent 主动终止，**产出不参与合并**（隔离目录中的部分文件可能不完整），标记为"未完成"，由主 agent 决定重试或自行补全 |
| 子 agent 扩大范围 | 主 agent 在合并阶段识别（产出文件超出任务范围），丢弃超范围产出 |

### 用户中断

- 用户随时可要求停止
- 主 agent 清理团队（team_delete）
- 输出当前阶段的中间结果到 final-report.md
- 已完成的子任务产出保留，未完成的标记为"未完成"

### 团队清理

- 所有批次完成且合并集成完成后，调用 `team_delete` 清理团队
- 产出文件保留在 `.codebuddy/task-dispatch/{task-name}/` 供用户查阅
