---
description: 指导AI调试/验证涉及临时文件时统一在 workspace temp 目录创建且只增不删；执行可能耗时（10秒以上）的终端命令必须加 timeout 限制防挂起。
alwaysApply: true
enabled: true
updatedAt: 2026-08-12T00:00:00.000Z
provider:
---

# 临时文件与命令超时

## 规则

### 1. 临时文件管理

- 调试/验证涉及的临时文件必须在当前工作空间 `temp` 目录下创建。
- **只增不删**：临时文件的清理由用户手动完成，AI 不得主动删除 `temp` 下任何文件。

### 2. 终端命令超时

- 可能执行 10 秒以上的命令必须加 timeout 限制，防止进程挂住：
  - **Linux**：`timeout 30s <command>`
  - **Mac**：`gtimeout 30s <command>`（需 `brew install coreutils`）

## 执行

### 临时文件

1. 确认 `{workspace}/temp/` 存在，不存在则创建。
2. 所有临时文件写入该目录，命名清晰。
3. 完成后报告临时文件位置，由用户决定是否清理。

### 命令超时

1. 评估命令耗时：安装、构建、测试、网络请求、长时运行服务/脚本等均判定为可能超时。
2. 为可能超时命令前置 `timeout 30s`（Linux）或 `gtimeout 30s`（Mac），阈值可按命令性质调整。
3. 含管道/子进程时，timeout 置于命令最外层。
4. 优先使用非交互参数（如 `--yes`）配合 timeout 双重防挂起。

## 例外

- 用户明确指定临时文件位置或允许删除。
- 命令必然瞬时完成（明显 < 10 秒）。
- 用户明确要求不加 timeout。
- Mac 未装 `gtimeout` 时改用 `timeout` 或向用户说明并等待确认。
