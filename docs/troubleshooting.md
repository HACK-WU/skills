# 故障排查

使用 `req` 命令行工具时常见问题及解决方案。

## 配置相关问题

### `.requirements/config 不存在`

**现象**：运行 `req` 命令时提示配置文件不存在。

**原因**：未运行 `req init` 初始化配置。

**解决方案**：
```bash
# 初始化配置
req init

# 或手动创建配置文件
mkdir -p .requirements
cat > .requirements/config << 'EOF'
storage_path=.requirements
feature_categories=
requirement_tags=feat,fix,refactor,tool,security
EOF
```

### `标签 XXX 不在 requirement_tags 配置中`

**现象**：创建或更新需求时提示标签不在配置中。

**原因**：使用的标签不在 `.requirements/config` 的 `requirement_tags` 配置中。

**解决方案**：
```bash
# 1. 查看当前配置的标签
cat .requirements/config | grep requirement_tags

# 2. 使用配置中的标签
req create --feature "功能" --tags feat,security  # 使用配置中的标签

# 3. 或更新配置添加新标签
# 编辑 .requirements/config，在 requirement_tags 中添加新标签
```

### `必须包含一个功能分类标签`

**现象**：创建需求时提示必须包含功能分类标签。

**原因**：配置了 `feature_categories`，但创建需求时未指定功能分类标签。

**解决方案**：
```bash
# 1. 查看配置的功能分类
cat .requirements/config | grep feature_categories

# 2. 添加功能分类标签
req create --feature "功能" --tags feat,security  # security 是功能分类标签

# 3. 或移除功能分类配置（不推荐）
# 编辑 .requirements/config，清空 feature_categories
```

### `功能分类标签只能有一个`

**现象**：创建需求时提示功能分类标签只能有一个。

**原因**：指定了多个功能分类标签。

**解决方案**：
```bash
# 错误示例
req create --feature "功能" --tags feat,security,performance  # 两个功能分类标签

# 正确示例（只保留一个）
req create --feature "功能" --tags feat,security  # 只保留 security
```

### `不能删除功能分类标签`

**现象**：更新需求时提示不能删除功能分类标签。

**原因**：功能分类标签与目录位置关联，不允许删除。

**解决方案**：
```bash
# 如果需要更改功能分类，必须删除并重新创建需求
req delete REQ-20260611-001 --force
req create --feature "功能" --tags feat,performance  # 使用新的功能分类标签
```

## 并发相关问题

### `无法在 5s 内获取文件锁`

**现象**：执行 `req create`、`req update` 或 `req delete` 时提示无法获取文件锁。

**原因**：其他进程持有锁或残留 `.lock` 文件。

**解决方案**：
```bash
# 1. 等待后重试（其他进程可能很快释放锁）
sleep 2
req create --feature "功能" --tags feat

# 2. 检查是否有残留锁文件
ls -la .requirements/.meta.json.lock

# 3. 手动删除残留锁文件（谨慎操作）
rm -f .requirements/.meta.json.lock

# 4. 或增加锁超时时间
# 编辑 .requirements/config，增加 lock_timeout 值
# 或设置环境变量
export REQ_LOCK_TIMEOUT=10
```

## 依赖相关问题

### `依赖需求 REQ-XXX 不存在`

**现象**：创建或更新需求时提示依赖的需求不存在。

**原因**：`depends-on` 指向不存在的需求 ID。

**解决方案**：
```bash
# 1. 检查需求 ID 是否正确
req list --id REQ-20260611-001

# 2. 先创建依赖的需求
req create --feature "依赖功能" --tags feat

# 3. 再创建带依赖的需求
req create --feature "功能" --tags feat --depends-on REQ-20260611-001
```

### `会形成循环依赖`

**现象**：更新需求依赖时提示会形成循环依赖。

**原因**：添加依赖后形成 A→B→A 的循环。

**解决方案**：
```bash
# 1. 查看当前依赖关系
req list --id REQ-20260611-001 --deps

# 2. 调整依赖关系，避免循环
# 删除有问题的依赖
req update REQ-20260611-001 --depends-on remove REQ-20260611-002

# 3. 重新设计依赖关系
```

### `不能删除最后一个标签`

**现象**：更新需求标签时提示不能删除最后一个标签。

**原因**：标签列表至少保留 1 个标签。

**解决方案**：
```bash
# 1. 先添加其他标签
req update REQ-20260611-001 --tag add documentation

# 2. 再删除目标标签
req update REQ-20260611-001 --tag remove feat
```

## 归档相关问题

### `需求 XXX 已处于归档状态`

**现象**：归档需求时提示已处于归档状态。

**原因**：需求已经是"已归档"状态，不能重复归档。

**解决方案**：
```bash
# 查看需求当前状态
req list --id REQ-20260611-001

# 如果需要恢复归档需求，手动修改 meta.json 中的状态
```

### `归档目标目录已存在`

**现象**：归档需求时提示目标目录已存在。

**原因**：`archive/` 目录下已有同名目录（可能是之前的归档残留）。

**解决方案**：
```bash
# 1. 检查归档目录
ls -la .requirements/archive/

# 2. 清理残留归档目录（谨慎操作）
rm -rf .requirements/archive/security/2026-06-11-功能名称/

# 3. 重新归档
req archive REQ-20260611-001
```

### `需求目录不存在`

**现象**：归档时提示需求目录不存在。

**原因**：需求目录已被手动删除或移动。

**解决方案**：
```bash
# 1. 检查目录是否存在
ls -la .requirements/security/

# 2. 如果目录已丢失，先删除需求记录，再手动清理
req delete REQ-20260611-001 --force
```

### 归档后子需求引用混乱

**现象**：归档 parent 后，子需求的 `parent` 字段仍指向已归档的需求。

**原因**：这是设计行为。归档操作不会修改子需求的 `parent` 字段，因为子需求的文档中也保留了关系。

**解决方案**：
```bash
# 如果需要解除父子关系
req update REQ-20260611-002 --role standalone

# 或重新指定新 parent
req update REQ-20260611-002 --parent REQ-20260611-010
```

## 目录相关问题

### `目录已存在` (create)

**现象**：创建需求时提示目录已存在。

**原因**：同名目录残留（可能是之前删除操作未完全清理）。

**解决方案**：
```bash
# 1. 检查目录是否存在
ls -la .requirements/security/2026-06-11-功能名称/

# 2. 使用自定义目录名
req create --feature "功能" --tags feat --dir-name "custom-dir-name"

# 3. 或清理旧目录（谨慎操作）
rm -rf .requirements/security/2026-06-11-功能名称/
```

## 版本相关问题

### Python 版本不兼容

**现象**：运行 `req` 命令时提示 Python 版本不兼容。

**原因**：包需要 Python 3.10+。

**解决方案**：
```bash
# 1. 检查 Python 版本
python3 --version

# 2. 升级 Python（如果版本低于 3.10）
# macOS
brew install python@3.10

# Ubuntu
sudo apt update
sudo apt install python3.10

# 3. 或使用 uv 管理 Python 版本
uv python install 3.10
```

## 其他问题

### 命令无输出

**现象**：运行 `req list` 等命令无输出。

**原因**：可能是没有匹配的需求，或输出被重定向。

**解决方案**：
```bash
# 1. 检查是否有需求数据
cat .requirements/meta.json

# 2. 使用 JSON 格式查看详细输出
req list --json

# 3. 检查是否有错误输出
req list 2>&1
```

### 权限问题

**现象**：运行命令时提示权限不足。

**原因**：`.requirements/` 目录或文件权限不足。

**解决方案**：
```bash
# 1. 检查目录权限
ls -la .requirements/

# 2. 修改目录权限
chmod 755 .requirements/
chmod 644 .requirements/config
chmod 644 .requirements/meta.json

# 3. 或重新初始化
rm -rf .requirements/
req init
```

## 获取帮助

如果以上方法都无法解决问题：

1. **查看命令帮助**：
   ```bash
   req --help
   req create --help
   ```

2. **查看详细错误信息**：
   ```bash
   # 启用调试输出（如果支持）
   REQ_DEBUG=1 req create --feature "功能" --tags feat
   ```

3. **检查日志文件**（如果有）：
   ```bash
   # 查看系统日志
   tail -f /var/log/system.log | grep req
   ```

4. **联系维护者**：
   - 提供完整的错误信息
   - 提供 `.requirements/config` 配置内容
   - 提供 `req --version` 输出

## 相关文档
- [README](./README.md) — 项目概述与快速开始
- [命令参考](./command-reference.md) — 所有命令
- [配置指南](./configuration.md) — 配置文件详解
- [架构文档](./requirement-mgr-guide.md) — 系统架构与技术实现