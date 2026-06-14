# -*- coding: utf-8 -*-
"""req delete: 删除需求，含反向依赖检查、交互确认、级联清理、父子关系处理。"""

import shutil
import sys
from pathlib import Path

from requirement_mgr.core.config_loader import ConfigLoader
from requirement_mgr.core.meta_store import MetaStore
from requirement_mgr.core.file_lock import FileLock
from requirement_mgr.core.requirement_utils import find_req, find_rev_deps, find_children


def _show_preview(dir_name: str, req: dict, rev_deps: list[dict], children: list[dict]):
    """展示删除预览。"""
    print(f"\n{'─' * 50}")
    print(f"  ID:        {req['id']}")
    print(f"  名称:      {req.get('feature', '')}")
    print(f"  角色:      {req.get('role', 'standalone')}")
    print(f"  目录:      {dir_name}")
    print(f"  状态:      {req.get('status', '')}")
    if children:
        print(f"\n  子需求（{len(children)} 项将变为 standalone）：")
        for c in children:
            print(f"    {c['id']}  {c.get('feature', '')}")
    if rev_deps:
        print(f"\n  反向依赖（{len(rev_deps)} 项将清理引用）：")
        for rd in rev_deps:
            print(f"    {rd['id']}  {rd['feature']}")
    print(f"{'─' * 50}")


def cmd_delete(args):
    """执行 req delete 命令。"""
    req_id = args.req_id.strip()

    if args.dry_run and args.force:
        print("错误: --dry-run 和 --force 不能同时使用", file=sys.stderr)
        sys.exit(1)

    # 加载
    try:
        cl = ConfigLoader()
        storage_root = cl.read()
        lock_timeout = cl.get_lock_timeout()
        backup_enabled = cl.get_backup_enabled()
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    ms = MetaStore(storage_root, backup_enabled=backup_enabled)
    data = ms.load()
    requirements = data["requirements"]

    dir_name, req = find_req(requirements, req_id)
    if req is None:
        print(f"错误: 未找到需求 {req_id}", file=sys.stderr)
        sys.exit(1)

    rev_deps = find_rev_deps(requirements, req_id)
    cleaned_count = len(rev_deps)

    # 查找子需求
    role = req.get("role", "standalone")
    children = []
    if role == "parent":
        children = find_children(requirements, req_id)
        child_ids = req.get("child_ids", [])
        # 警告：有子需求
        if children or child_ids:
            if not args.force and not args.dry_run:
                pass  # 在交互确认中展示

    # dry-run
    if args.dry_run:
        print(f"\n🔍 预删除检查")
        print(f"\n将执行：")
        print(f"  ① 从 meta.json 删除 {req_id} 条目")
        if children:
            ids = ", ".join(c["id"] for c in children)
            print(f"  ② 子需求 {ids} 变为 standalone（role=standalone, parent_id=null）")
        if cleaned_count:
            ids = ", ".join(r["id"] for r in rev_deps)
            print(f"  ③ 从 {ids} 的 depends_on 中移除 {req_id}")
        dir_path = storage_root / dir_name
        print(f"  ④ 删除目录: {dir_path}")
        print(f"\n⚠ --dry-run 模式，未做任何修改。")
        return

    # 交互确认
    if not args.force:
        _show_preview(dir_name, req, rev_deps, children)
        if children:
            print(f"⚠ 警告: 有 {len(children)} 个子需求将变为 standalone")
        if cleaned_count:
            print(f"⚠ 警告: 有 {cleaned_count} 个需求的 depends_on 将被清理")
        try:
            answer = input("\n确认删除？[y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return
        if answer != "y":
            print("已取消")
            return

    # 加锁 + 删除
    meta_path = storage_root / "meta.json"
    try:
        with FileLock(str(meta_path), timeout=lock_timeout):
            data = ms.load()
            requirements = data["requirements"]

            dir_name, req = find_req(requirements, req_id)
            if req is None:
                print(f"错误: 未找到需求 {req_id}（并发删除）", file=sys.stderr)
                sys.exit(1)

            # ① 处理子需求：变为 standalone
            actual_orphaned = 0
            if req.get("role") == "parent":
                for other_req in requirements.values():
                    if other_req.get("parent_id") == req_id:
                        other_req["role"] = "standalone"
                        other_req["parent_id"] = None
                        actual_orphaned += 1

            # ② 如果自身是 child，从 parent 的 child_ids 中移除
            if req.get("role") == "child" and req.get("parent_id"):
                parent_id = req["parent_id"]
                _, parent_req = find_req(requirements, parent_id)
                if parent_req:
                    child_ids = parent_req.get("child_ids", [])
                    if req_id in child_ids:
                        child_ids.remove(req_id)
                    # 如果 parent 没有其他子需求了，降级为 standalone
                    if not child_ids and parent_req.get("role") == "parent":
                        parent_req["role"] = "standalone"

            # ③ 删除条目
            del requirements[dir_name]

            # ④ 清理 depends_on 引用
            actual_cleaned = 0
            for other in requirements.values():
                deps = other.get("depends_on", [])
                if req_id in deps:
                    deps.remove(req_id)
                    actual_cleaned += 1

            ms.save(data)

            # ⑤ 删除目录
            dir_path = storage_root / dir_name
            try:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
                # 清理空的分类目录
                if "/" in dir_name:
                    category_dir = dir_path.parent
                    if category_dir != storage_root and category_dir.exists() and not any(category_dir.iterdir()):
                        category_dir.rmdir()
            except OSError as e:
                print(f"警告: 目录删除失败 ({e})，请手动清理: {dir_path}", file=sys.stderr)

    except TimeoutError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"\n✓ 已删除需求 {req_id}")
    print(f"  目录:    {storage_root / dir_name}")
    if actual_orphaned:
        print(f"  子需求:  {actual_orphaned} 个需求已变为 standalone")
    if actual_cleaned:
        print(f"  清理引用: {actual_cleaned} 个需求的 depends_on")
