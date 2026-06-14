# -*- coding: utf-8 -*-
"""req init: 初始化项目配置。"""

import os
import shutil
import sys
from pathlib import Path


CONFIG_TEMPLATE = """\
# ──────────────────────────────────────────────
# requirement-mgr 项目配置
# 由 req init 自动生成
# ──────────────────────────────────────────────

# 存储路径（相对于项目根目录）
storage_path=.requirements

# 需求功能分类（为空表示不进行功能分类）
feature_categories=

# 需求标签（为空表示不限制标签）
requirement_tags=

# 需求状态（第一个值为默认初始状态）
requirement_statuses=草案,已确认,设计中,实施中,已完成,已取消

# 需求角色（第一个值为默认角色）
requirement_roles=standalone,parent,child

# ID 前缀
id_prefix=REQ

# ID 日期后序号位数
id_digits=3

# 文件锁超时秒数
lock_timeout=5

# 写入前备份 meta.json
backup_enabled=false
"""


def _find_project_root(max_depth: int = 2) -> Path:
    """从当前目录向上查找项目根目录（包含 .requirements 或 .git 的目录）。

    Args:
        max_depth: 最大向上查找层数（默认 2）

    Returns:
        Path: 项目根目录，兜底返回当前目录
    """
    current = Path.cwd()
    for _ in range(max_depth):
        if (current / ".requirements").is_dir() or (current / ".git").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path.cwd()  # 兜底：返回当前目录


def cmd_init(args):
    """执行 req init 命令。"""
    # 向上查找项目根目录，确保在子目录中运行也能正确定位
    project_root = _find_project_root()
    os.chdir(project_root)

    config_path = Path(".requirements/config")

    if config_path.exists():
        if args.force:
            # 覆盖前先备份旧 config 为 config.bak
            backup_path = Path(str(config_path) + ".bak")
            shutil.copy2(config_path, backup_path)
            # 覆盖前显示提示（除非 --yes）
            if not args.yes:
                print(f"当前配置将被覆盖（已备份到 {backup_path}）：")
                print(f"  文件: {config_path}")
                try:
                    answer = input("确认覆盖？[y/N]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\n已取消，备份已保留")
                    return
                if answer != "y":
                    print("已取消，备份已保留")
                    return
        else:
            print(f"配置文件已存在: {config_path}")
            print("使用 req init --force 覆盖")
            return

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    print(f"✓ 配置文件已创建: {config_path}")
