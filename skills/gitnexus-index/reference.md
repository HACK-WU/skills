# GitNexus 索引参考

详细命令选项与配置参考。主指令见 SKILL.md。

## analyze 完整选项

```
Usage: gitnexus analyze [options] [path]

Index a repository (full analysis)
```

| 选项 | 说明 |
|------|------|
| `-f, --force` | 强制全量重索引（重新解析 + 图重建 + FTS 重建） |
| `--repair-fts` | 仅修复/重建全文搜索索引，不重新解析代码 |
| `--embeddings [limit]` | 启用向量嵌入（默认关）；`[limit]` 覆盖 50000 节点安全上限，`0` 禁用上限 |
| `--drop-embeddings` | 重建时丢弃已有向量（默认不带 `--embeddings` 的 analyze 保留已有向量） |
| `--skills` | 从检测到的社区生成仓库专属 skill 文件 |
| `--skip-agents-md` | 跳过更新 AGENTS.md / CLAUDE.md 的 gitnexus 区块 |
| `--pdg` | 构建控制流图/PDG 基座（BasicBlock 节点 + CFG 边，opt-in） |
| `--default-branch <branch>` | 回归对比示例的 base_ref；回退 .gitnexusrc → origin/HEAD → main |
| `--branch <name>` | 钉住工作树到独立 per-branch 索引槽（多分支索引） |
| `--no-stats` | AGENTS.md/CLAUDE.md 中省略易变文件/符号计数 |
| `--skip-skills` | 跳过安装标准 GitNexus skill 文件（.claude/skills/gitnexus/） |
| `--index-only` | 纯索引模式：跳过所有 AI 上下文文件注入 |
| `--skip-git` | 将给定路径/当前目录作为索引根，跳过父 git-root 发现 |
| `--name <alias>` | 在 registry 用自定义名注册仓库（消歧同 basename 仓库） |
| `--allow-duplicate-name` | 允许另一路径复用同 `--name` 别名（用 `-r <path>` 消歧） |
| `-v, --verbose` | 详细输出 |
| `--max-file-size <kb>` | 跳过大于此 KB 的文件（默认 512，硬上限 32768） |
| `--embedding-auth-token <token>` | embeddings 端点 Bearer token |
| `--embedding-dims <number>` | 向量维度（需与索引构建时一致） |
| `-h, --help` | 帮助 |

## analyze 环境变量

| 变量 | 作用 | 默认 |
|------|------|------|
| `GITNEXUS_NO_GITIGNORE=1` | 跳过 .gitignore 解析（仍读 .gitnexusignore） | - |
| `GITNEXUS_MAX_FILE_SIZE=N` | 大文件跳过阈值（KB） | 512，max 32768 |
| `GITNEXUS_WORKER_SUB_BATCH_TIMEOUT_MS=N` | worker 空闲超时（ms） | 30000 |
| `GITNEXUS_WAL_CHECKPOINT_THRESHOLD=N` | LadybugDB WAL 自动 checkpoint 阈值（字节） | 64MiB |
| `GITNEXUS_WORKER_SUB_BATCH_MAX_BYTES=N` | worker 作业字节预算 | 8388608 |
| `GITNEXUS_WORKER_POOL_SIZE=N` | 解析 worker 数覆盖 | 内核数-1，cap 16 |
| `GITNEXUS_PARSE_CHUNK_CONCURRENCY=N` | 并发解析块数 | 2 |
| `GITNEXUS_WORKER_MAX_RESPAWNS_PER_SLOT=N` | 每槽最大替换 spawn 数 | 3 |
| `GITNEXUS_WORKER_MAX_CUMULATIVE_TIMEOUT_MS=N` | 每作业重试总墙钟时间 | 5x sub-batch 超时 |
| `GITNEXUS_WORKER_CONSECUTIVE_FAILURE_THRESHOLD=N` | 熔断阈值 | max(3, poolSize) |
| `GITNEXUS_EMBEDDING_THREADS=N` | 本地 ONNX CPU 线程（--embeddings） | - |
| `GITNEXUS_SEMANTIC_EXACT_SCAN_LIMIT=N` | exact-scan 回退最大 chunk 数 | 10000 |
| `GITNEXUS_VECTOR_MAX_DISTANCE=N` | 最大余弦距离（0 < N ≤ 2） | MCP 0.6，其他 0.5 |

标志优先于对应环境变量。

## 其他命令

| 命令 | 功能 |
|------|------|
| `gitnexus status` | 当前仓库索引状态（是否过期） |
| `gitnexus list` | 列出所有已索引仓库 |
| `gitnexus clean` | 删除当前仓库索引 |
| `gitnexus clean --all --force` | 删除所有仓库索引 |
| `gitnexus setup` | 一次性配置 MCP 到编辑器（Cursor/Claude/Codex 等） |

## 多仓库 / 分组（可选，非默认能力）

微服务场景可分别索引各仓库，再建组提取跨仓库契约：

```bash
gitnexus analyze /path/to/auth-service
gitnexus analyze /path/to/user-service

gitnexus group create my-platform
gitnexus group add my-platform auth/backends auth-service
gitnexus group sync my-platform
gitnexus group contracts my-platform
```

## 性能建议

- 大型仓库：`--skip-embeddings` 或 `--embeddings 0` 自定义上限
- 增加并行：`--workers 8`（等价 `GITNEXUS_WORKER_POOL_SIZE=8`）
- 限制文件：`GITNEXUS_MAX_FILE_SIZE` 设跳过阈值；配 `.gitnexusignore`
- 无 C++ 工具链：`GITNEXUS_SKIP_OPTIONAL_GRAMMARS=1` 跳过可选语法树编译

## .gitnexusignore 提示

支持 `.gitignore` 式取反，例如 `!__tests__/` 收录被默认过滤的目录（#771）。
