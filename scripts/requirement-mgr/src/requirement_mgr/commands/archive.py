# -*- coding: utf-8 -*-
"""req archive: 归档需求（整体）或文档（单个），移动到 archive/ 目录。

模式：
  - 整体归档（无 --doc）：移动整个需求目录到 .requirements/archive/，状态→已归档
  - 文档级归档（--doc <path>）：移动单个文档到该需求目录下的 archive/ 子目录，不改需求状态
"""

import os
import shutil
import sys

from requirement_mgr.core.config_loader import ConfigLoader
from requirement_mgr.core.meta_store import MetaStore
from requirement_mgr.core.file_lock import FileLock
from requirement_mgr.core.requirement_utils import find_req, find_rev_deps, find_children
from requirement_mgr.core.time_utils import now_cst_str


ARCHIVE_DIR = "archive"
ARCHIVE_STATUS = "已归档"


def cmd_archive(args):
    """执行 req archive 命令。"""
    req_id = args.req_id.strip()

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

    # 文档级归档分支：指定 --doc 时归档单个文档
    if args.doc:
        return _archive_doc(args, storage_root, dir_name, req, ms, lock_timeout)

    # 检查是否已归档
    if req.get("status") == ARCHIVE_STATUS:
        print(f"错误: 需求 {req_id} 已处于归档状态", file=sys.stderr)
        sys.exit(1)

    # 检查子需求和反向依赖
    children = find_children(requirements, req_id)
    # 仅保留活跃（非已归档）的子需求
    active_children = [c for c in children if c.get("status") != ARCHIVE_STATUS]
    rev_deps = find_rev_deps(requirements, req_id)

    # 归档 parent 时，若有活跃子需求，需交互确认（除非 --force 或 --dry-run）
    if active_children and not args.dry_run and not args.force:
        child_ids = ", ".join(c["id"] for c in active_children)
        print(f"⚠ 警告: 需求 {req_id} 有 {len(active_children)} 个活跃子需求（{child_ids}）", file=sys.stderr)
        print(f"  归档后子需求仍引用此父需求，可能导致语义混淆", file=sys.stderr)
        try:
            answer = input("确认归档？[y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return
        if answer != "y":
            print("已取消")
            return

    if rev_deps and not args.dry_run:
        rev_ids = ", ".join(r["id"] for r in rev_deps)
        print(f"⚠ 警告: 需求 {req_id} 被 {len(rev_deps)} 个需求依赖（{rev_ids}），归档后依赖关系仍然保留", file=sys.stderr)

    src_path = storage_root / dir_name
    archive_base = storage_root / ARCHIVE_DIR
    dst_path = archive_base / dir_name

    # dry-run 预览
    if args.dry_run:
        print(f"\n🔍 预归档检查")
        print(f"\n将执行：")
        print(f"  ① 移动目录: {src_path}")
        print(f"     → {dst_path}")
        print(f"  ② 更新状态: {req.get('status', '')} → {ARCHIVE_STATUS}")
        print(f"  ③ 更新 meta.json 键: {dir_name} → {ARCHIVE_DIR}/{dir_name}")
        if args.reason:
            print(f"  ④ 归档原因: {args.reason}")
        if active_children:
            child_ids = ", ".join(c["id"] for c in active_children)
            print(f"\n⚠ 警告: 有 {len(active_children)} 个活跃子需求（{child_ids}）仍引用此父需求")
        if children and not active_children:
            print(f"\nℹ 提示: 有 {len(children)} 个子需求（均已归档），无活跃子需求")
        if rev_deps:
            rev_ids = ", ".join(r["id"] for r in rev_deps)
            print(f"⚠ 警告: 被 {len(rev_deps)} 个需求依赖（{rev_ids}），依赖关系仍保留")
        print(f"\n⚠ --dry-run 模式，未做任何修改。")
        return

    # 检查源目录是否存在
    if not src_path.exists():
        print(f"错误: 需求目录不存在: {src_path}", file=sys.stderr)
        sys.exit(1)

    # 检查目标目录是否冲突
    if dst_path.exists():
        print(f"错误: 归档目标目录已存在: {dst_path}", file=sys.stderr)
        sys.exit(1)

    # 加锁 + 归档
    meta_path = storage_root / "meta.json"
    try:
        with FileLock(str(meta_path), timeout=lock_timeout):
            data = ms.load()
            requirements = data["requirements"]

            dir_name, req = find_req(requirements, req_id)
            if req is None:
                print(f"错误: 未找到需求 {req_id}（并发删除）", file=sys.stderr)
                sys.exit(1)

            # 二次检查已归档
            if req.get("status") == ARCHIVE_STATUS:
                print(f"错误: 需求 {req_id} 已被归档（并发操作）", file=sys.stderr)
                sys.exit(1)

            # 二次检查目标冲突
            if dst_path.exists():
                print(f"错误: 归档目标目录已存在（并发操作）: {dst_path}", file=sys.stderr)
                sys.exit(1)

            # 确保归档基目录存在
            archive_base.mkdir(parents=True, exist_ok=True)
            # 如果原目录有分类前缀（如 tool/），创建对应的子目录
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # ① 移动目录
            try:
                shutil.move(str(src_path), str(dst_path))
            except OSError as e:
                # 清理移动失败后遗留的空归档目录
                _cleanup_empty_archive_dirs(archive_base, dst_path.parent)
                print(f"错误: 目录移动失败: {e}", file=sys.stderr)
                sys.exit(1)

            # 清理空的分类目录（如 tool/ 空了就删）
            if "/" in dir_name:
                category_dir = src_path.parent
                if category_dir != storage_root and category_dir.exists():
                    try:
                        if not any(category_dir.iterdir()):
                            category_dir.rmdir()
                    except OSError:
                        pass

            # ② 更新 meta.json：改键名 + 更新字段
            new_dir_name = f"{ARCHIVE_DIR}/{dir_name}"
            old_entry = requirements.pop(dir_name)

            timestamp = now_cst_str()
            old_entry["status"] = ARCHIVE_STATUS
            old_entry["updated"] = timestamp
            old_entry["archived_at"] = timestamp
            if args.reason:
                old_entry["archive_reason"] = args.reason.strip()

            # 版本自增 + changelog
            old_entry["version"] = old_entry.get("version", 1) + 1
            changelog_msg = f"归档"
            if args.reason:
                changelog_msg += f": {args.reason.strip()}"
            old_entry.setdefault("changelog", [])
            old_entry["changelog"].append(
                f"{timestamp} v{old_entry['version']}: {changelog_msg}"
            )

            requirements[new_dir_name] = old_entry
            ms.save(data)

    except TimeoutError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"✓ 需求已归档")
    print(f"  ID:        {req_id}")
    print(f"  原目录:    {src_path}")
    print(f"  归档位置:  {dst_path}")
    print(f"  状态:      {ARCHIVE_STATUS}")
    if args.reason:
        print(f"  归档原因:  {args.reason.strip()}")


def _cleanup_empty_archive_dirs(archive_base, target_parent):
    """清理移动失败后遗留的空归档子目录。"""
    try:
        # 从 target_parent 向上清理直到 archive_base，遇到非空目录停止
        current = target_parent
        while current != archive_base and current.exists():
            if any(current.iterdir()):
                break
            current.rmdir()
            current = current.parent
    except OSError:
        pass


def _archive_doc(args, storage_root, dir_name, req, ms, lock_timeout):
    """文档级归档：移动单个文档到需求内 archive/ 子目录。

    - 源：{需求目录}/{doc_path}
    - 目标：{需求目录}/archive/{doc_path}
    - 不改变需求状态，仅记录 changelog
    - 若文档在 docs 列表中登记，归档后从 docs 移除（已不活跃）
    """
    req_id = args.req_id.strip()
    doc_path = args.doc.strip()
    # 仅去除前导 ./，不用 lstrip("./")（会把 ../.. 误处理）
    if doc_path.startswith("./"):
        doc_path = doc_path[2:]
    doc_path = doc_path.rstrip("/")

    if not doc_path:
        print("错误: --doc 路径不能为空", file=sys.stderr)
        sys.exit(1)

    # 已归档需求不允许文档级归档
    if req.get("status") == ARCHIVE_STATUS:
        print(f"错误: 需求 {req_id} 已整体归档，不支持文档级归档", file=sys.stderr)
        sys.exit(1)

    req_dir = storage_root / dir_name
    src_path = req_dir / doc_path
    dst_path = req_dir / ARCHIVE_DIR / doc_path

    # 路径穿越防护：确保源和目标都在需求目录内
    try:
        src_resolved = src_path.resolve()
        req_dir_resolved = req_dir.resolve()
        if not str(src_resolved).startswith(str(req_dir_resolved) + os.sep) \
           and src_resolved != req_dir_resolved:
            print(f"错误: --doc 路径不能超出需求目录范围", file=sys.stderr)
            sys.exit(1)
    except OSError as e:
        print(f"错误: 路径解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 检查源文件/目录存在
    if not src_path.exists():
        print(f"错误: 文档不存在: {src_path}", file=sys.stderr)
        sys.exit(1)

    # 检查目标不冲突
    if dst_path.exists():
        print(f"错误: 归档目标已存在: {dst_path}", file=sys.stderr)
        sys.exit(1)

    # dry-run 预览
    if args.dry_run:
        print(f"\n🔍 预归档检查（文档级）")
        print(f"\n将执行：")
        print(f"  ① 移动文档: {src_path}")
        print(f"     → {dst_path}")
        print(f"  ② 不改变需求状态（当前: {req.get('status', '')}）")
        if args.reason:
            print(f"  ③ 归档原因: {args.reason}")
        print(f"\n⚠ --dry-run 模式，未做任何修改。")
        return

    # 加锁 + 归档
    meta_path = storage_root / "meta.json"
    try:
        with FileLock(str(meta_path), timeout=lock_timeout):
            data = ms.load()
            requirements = data["requirements"]
            dir_name2, req2 = find_req(requirements, req_id)
            if req2 is None:
                print(f"错误: 未找到需求 {req_id}（并发删除）", file=sys.stderr)
                sys.exit(1)
            if req2.get("status") == ARCHIVE_STATUS:
                print(f"错误: 需求 {req_id} 已被整体归档（并发操作）", file=sys.stderr)
                sys.exit(1)

            # 二次检查源存在、目标不存在
            if not src_path.exists():
                print(f"错误: 文档不存在（并发操作）: {src_path}", file=sys.stderr)
                sys.exit(1)
            if dst_path.exists():
                print(f"错误: 归档目标已存在（并发操作）: {dst_path}", file=sys.stderr)
                sys.exit(1)

            # 确保归档目录存在
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # 移动文件/目录
            doc_archive_base = req_dir / ARCHIVE_DIR
            try:
                shutil.move(str(src_path), str(dst_path))
            except OSError as e:
                # 清理移动失败后遗留的空归档子目录
                _cleanup_empty_archive_dirs(doc_archive_base, dst_path.parent)
                print(f"错误: 文件移动失败: {e}", file=sys.stderr)
                sys.exit(1)

            # 更新 meta.json
            timestamp = now_cst_str()
            req2["updated"] = timestamp
            req2["version"] = req2.get("version", 1) + 1

            # 从 docs 列表移除已归档文档（若已登记）
            docs = req2.get("docs", [])
            new_docs = [d for d in docs if d.get("path") != doc_path]
            if len(new_docs) != len(docs):
                req2["docs"] = new_docs

            # changelog
            changelog_msg = f"归档文档: {doc_path}"
            if args.reason:
                changelog_msg += f"（{args.reason.strip()}）"
            req2.setdefault("changelog", []).append(
                f"{timestamp} v{req2['version']}: {changelog_msg}"
            )
            ms.save(data)

    except TimeoutError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"✓ 文档已归档")
    print(f"  ID:        {req_id}")
    print(f"  原路径:    {src_path}")
    print(f"  归档位置:  {dst_path}")
    if args.reason:
        print(f"  归档原因:  {args.reason.strip()}")

