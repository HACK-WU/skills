# -*- coding: utf-8 -*-
"""CLI 入口：req 命令分发。"""

import argparse
import os
import sys
from pathlib import Path

from requirement_mgr import __version__
from requirement_mgr.commands.init import cmd_init
from requirement_mgr.commands.create import cmd_create
from requirement_mgr.commands.list import cmd_list
from requirement_mgr.commands.update import cmd_update
from requirement_mgr.commands.delete import cmd_delete
from requirement_mgr.commands.archive import cmd_archive
from requirement_mgr.commands.restore import cmd_restore
from requirement_mgr.commands.unarchive import cmd_unarchive
from requirement_mgr.commands.doctor import cmd_doctor
from requirement_mgr.core.meta_store import MetaCorruptedError
from requirement_mgr.core.output import extract_error


def find_config_upward() -> Path | None:
    """从当前目录逐级向上查找 .requirements/config，直到文件系统根目录。

    Returns:
        Path: config 文件路径，未找到返回 None
    """
    current = Path.cwd()
    while True:
        config_path = current / ".requirements" / "config"
        if config_path.exists():
            return config_path
        parent = current.parent
        if parent == current:  # 到达根目录
            return None
        current = parent


def main():
    parser = argparse.ArgumentParser(prog="req", description="需求管理工具")
    parser.add_argument("-v", "-V", "--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    # req init
    init_parser = subparsers.add_parser("init", help="初始化项目配置")
    init_parser.add_argument("--yes", "-y", action="store_true", help="非交互模式")
    init_parser.add_argument("--force", action="store_true", help="覆盖已有配置")

    # req create
    create_parser = subparsers.add_parser("create", help="创建需求")
    create_parser.add_argument("--feature", required=True, help="功能名称")
    create_parser.add_argument("--tags", default="", help="标签，逗号分隔")
    create_parser.add_argument("--status", default=None, help="初始状态")
    create_parser.add_argument("--role", default=None, help="需求角色（standalone/parent/child）")
    create_parser.add_argument("--parent-id", default=None, help="父需求 ID（指定时自动推断 role=child）")
    create_parser.add_argument("--depends-on", default="", help="依赖需求 ID，逗号分隔")
    create_parser.add_argument("--dir-name", default="", help="自定义目录名")
    create_parser.add_argument("--branch", default=None, help="主开发分支名称")
    create_parser.add_argument("--json", dest="json_output", action="store_true", help="结构化 JSON 输出（隐含非交互）")

    # req list
    list_parser = subparsers.add_parser("list", help="列出需求")
    list_parser.add_argument("--id", help="精确匹配需求 ID")
    list_parser.add_argument("--status", help="按状态筛选")
    list_parser.add_argument("--tag", action="append", help="按标签筛选")
    list_parser.add_argument("--role", help="按角色筛选")
    list_parser.add_argument("--parent-id", help="按父需求筛选")
    list_parser.add_argument("--category", help="按功能分类筛选")
    list_parser.add_argument("--from", dest="date_from", help="更新日期起")
    list_parser.add_argument("--to", dest="date_to", help="更新日期止")
    list_parser.add_argument("--search", help="模糊搜索功能名称")
    list_parser.add_argument("--deps", action="store_true", help="展开 depends_on 依赖")
    list_parser.add_argument("--rev-deps", action="store_true", help="反向依赖查询（depends_on）")
    list_parser.add_argument("--deps-depth", type=int, default=1)
    list_parser.add_argument("--json", dest="json_output", action="store_true")
    list_parser.add_argument("--columns", default=None)
    list_parser.add_argument("--limit", type=int, default=10, help="最多展示条数（默认 10，0 表示全部）")
    list_parser.add_argument("--include-archived", action="store_true", help="包含已归档需求（默认隐藏）")

    # req update
    update_parser = subparsers.add_parser("update", help="修改需求")
    update_parser.add_argument("req_id", help="需求 ID")
    update_parser.add_argument("--status", help="更新状态")
    update_parser.add_argument("--feature", help="更新功能名称")
    update_parser.add_argument("--role", help="更新角色")
    update_parser.add_argument("--parent-id", help="更新父需求 ID")
    update_parser.add_argument("--tag", nargs=2, action="append")
    update_parser.add_argument("--depends-on", nargs=2, action="append", dest="depends_on_ops")
    update_parser.add_argument("--commit", help="追加 git commit")
    update_parser.add_argument("--branch", default=None, help="更新分支名称（传空字符串 \"\" 清除）")
    update_parser.add_argument("--docs", nargs=2, action="append", dest="docs_ops")
    update_parser.add_argument("--changelog", help="追加变更记录")
    update_parser.add_argument("--json", dest="json_output", action="store_true", help="结构化 JSON 输出（隐含非交互）")

    # req delete
    delete_parser = subparsers.add_parser("delete", help="删除需求")
    delete_parser.add_argument("req_id", help="需求 ID")
    delete_parser.add_argument("--force", action="store_true")
    delete_parser.add_argument("--dry-run", action="store_true")
    delete_parser.add_argument("--json", dest="json_output", action="store_true", help="结构化 JSON 输出（隐含非交互）")

    # req archive
    archive_parser = subparsers.add_parser("archive", help="归档需求或文档")
    archive_parser.add_argument("req_id", help="需求 ID")
    archive_parser.add_argument("--reason", default=None, help="归档原因")
    archive_parser.add_argument("--dry-run", action="store_true", help="预览，不实际执行")
    archive_parser.add_argument("--force", action="store_true", help="跳过交互确认（如归档有子需求的 parent）")
    archive_parser.add_argument("--doc", default=None, help="归档单个文档（相对需求目录的路径，如 design/old.md）；不指定则归档整个需求")
    archive_parser.add_argument("--json", dest="json_output", action="store_true", help="结构化 JSON 输出（隐含非交互）")

    # req restore
    restore_parser = subparsers.add_parser("restore", help="从 meta.json.bak 恢复元数据")
    restore_parser.add_argument("--dry-run", action="store_true", help="预览，不实际执行")
    restore_parser.add_argument("--force", action="store_true", help="跳过交互确认")
    restore_parser.add_argument("--json", dest="json_output", action="store_true", help="结构化 JSON 输出（隐含非交互）")

    # req unarchive
    unarchive_parser = subparsers.add_parser("unarchive", help="恢复已归档需求")
    unarchive_parser.add_argument("req_id", help="需求 ID")
    unarchive_parser.add_argument("--dry-run", action="store_true", help="预览，不实际执行")
    unarchive_parser.add_argument("--force", action="store_true", help="跳过交互确认（无归档前状态时直接恢复为默认状态）")
    unarchive_parser.add_argument("--json", dest="json_output", action="store_true", help="结构化 JSON 输出（隐含非交互）")

    # req doctor
    doctor_parser = subparsers.add_parser("doctor", help="meta 与文件系统一致性巡检")
    doctor_parser.add_argument("--fix", action="store_true", help="修复可自动处置的漂移（悬空引用）")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # 前置检查：除 init 外，所有命令必须检查 config
    # config 路径始终为 .requirements/config（相对于项目根目录），
    # 与 storage_path 配置无关。storage_path 控制的是需求数据的存储位置。
    if args.command != "init":
        config_path = find_config_upward()
        if not config_path:
            print("错误: .requirements/config 不存在", file=sys.stderr)
            print("请先运行 req init 初始化项目配置", file=sys.stderr)
            print("（或确保在项目根目录或其子目录中运行）", file=sys.stderr)
            sys.exit(1)
        # 切换到项目根目录（config 所在目录的父目录）
        project_root = config_path.parent.parent
        os.chdir(project_root)

    # 参数自动推断：--parent-id 存在但未指定 --role 时，自动推断 role=child
    if args.command == "create" and args.parent_id and not args.role:
        args.role = "child"
        print("提示: 检测到 --parent-id，自动设置 role=child", file=sys.stderr)

    # 分发到子命令
    commands = {
        "init": cmd_init,
        "create": cmd_create,
        "list": cmd_list,
        "update": cmd_update,
        "delete": cmd_delete,
        "archive": cmd_archive,
        "restore": cmd_restore,
        "unarchive": cmd_unarchive,
        "doctor": cmd_doctor,
    }
    try:
        _dispatch(commands[args.command], args)
    except MetaCorruptedError as e:
        # 统一友好报错：meta 损坏时给出恢复指引，不裸抛 traceback
        if getattr(args, "json_output", False):
            import json as _json
            print(_json.dumps(
                {"ok": False, "error": f"meta.json 已损坏，无法解析: {e.meta_path}"},
                ensure_ascii=False,
            ))
            sys.exit(1)
        print(f"错误: meta.json 已损坏，无法解析: {e.meta_path}", file=sys.stderr)
        print(f"  原因: {e.cause}", file=sys.stderr)
        print("  恢复指引:", file=sys.stderr)
        print(f"    1. 若存在备份 {e.meta_path}.bak，执行: req restore", file=sys.stderr)
        print("    2. 否则手工检查修复 JSON 语法（建议先复制一份再改）", file=sys.stderr)
        sys.exit(1)


def _dispatch(func, args):
    """分发到子命令。

    --json 模式下统一捕获失败：命令通过 sys.exit(非0) 报错时，
    将其打印到 stderr 的错误信息转换为 stdout 的 {"ok": false, "error": ...}，
    退出码保持不变（O-09 失败输出契约）。
    """
    if not getattr(args, "json_output", False):
        func(args)
        return

    import contextlib
    import io
    import json as _json

    err_buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(err_buf):
            func(args)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if code != 0:
            print(_json.dumps(
                {"ok": False, "error": extract_error(err_buf.getvalue())},
                ensure_ascii=False,
            ))
        raise
    except MetaCorruptedError:
        # 交由 main 的统一处理（含 json 分支与恢复指引），此处不重复输出
        raise
    except Exception as e:  # noqa: BLE001 - 未预期异常也需保证 json 失败契约
        err_text = err_buf.getvalue().strip()
        detail = extract_error(err_text) if err_text else f"{type(e).__name__}: {e}"
        print(_json.dumps({"ok": False, "error": detail}, ensure_ascii=False))
        sys.exit(1)
