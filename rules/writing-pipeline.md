---
name: writing-pipeline
description: >-
  文档或代码编写完成后，自动调用 auto-review skill 进行质量审查和修复闭环。
---

# Writing Pipeline

## 规则

当 AI 完成以下任一操作后，**必须自动调用 `auto-review` skill** 执行审查修复闭环：

| 触发条件 | 操作类型 |
|----------|----------|
| 写入或修改 `.md` 文件 | `write_to_file` / `replace_in_file` |
| 写入或修改代码文件（`.py` `.sh` `.ps1` `.js` `.ts` `.java` `.go` `.rs` `.c` `.cpp` `.h` `.toml` `.yaml` `.yml` `.json` `.css` `.vue` `.tsx` `.jsx`） | `write_to_file` / `replace_in_file` |

## 执行

```
写完文件 → use_skill("auto-review")
```

## 例外

以下情况跳过：
- 用户明确说"不用审查"、"跳过审查"、"skip review"
- 单字符/标点修改
