# -*- coding: utf-8 -*-
"""req unarchive: 归档恢复，将已归档需求移回原分类目录并恢复状态。

archive 的逆操作：
  - meta 键去掉 `archive/` 前缀，目录从 archive/ 移回原位置
  - 状态恢复为 `pre_archive_status`（归档时结构化记录）；
    存量已归档需求无该字段时，恢复为配置默认状态（fallback）
  - 不改动 role/parent_id/child_ids（父子关系原样保留）
"""

import copy
import shutil
import sys

from requirement_mgr.core.config_loader import ConfigLoader
from requirement_mgr.core.meta_store import MetaStore
from requirement_mgr.core.file_lock import FileLock
from requirement_mgr.core.requirement_utils import ARCHIVED_STATUS, find_req
from requirement_mgr.core.time_utils import now_cst_str
from requirement_mgr.core.output import emit_success, guard_interactive


ARCHIVE_DIR = "archive"
ARCHIVE_PREFIX = "archive/"
ARCHIVE_STATUS = ARCHIVED_STATUS

# 存量已归档需求无 pre_archive_status 时的默认恢复状态（决策点 5）
FALLBACK_RESTORE_STATUS = "已完成"


def _resolve_restore_status(req: dict, valid_statuses: list[str]) -> tuple[str, bool]:
    """确定恢复状态，返回 (status, is_fallback)。

    优先用归档时记录的 pre_archive_status；缺失或不在白名单内时回退默认状态。
    """
    pre = req.get("pre_archive_status")
    if pre and pre in valid_statuses and pre != ARCHIVE_STATUS:
        return pre, False
    return FALLBACK_RESTORE_STATUS, True


def cmd_unarchive(args):
    """执行 req unarchive 命令。"""
    req_id = args.req_id.strip()

    try:
        cl = ConfigLoader()
        storage_root = cl.read()
        lock_timeout = cl.get_lock_timeout()
        backup_enabled = cl.get_backup_enabled()
        valid_statuses = cl.get_requirement_statuses()
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

    # 仅已归档需求可恢复
    if req.get("status") != ARCHIVE_STATUS:
        print(f"错误: 需求 {req_id} 未处于归档状态，无需恢复", file=sys.stderr)
        sys.exit(1)

    # 计算恢复后的键与路径（去掉 archive/ 前缀）
    if dir_name.startswith(ARCHIVE_PREFIX):
        original_dir = dir_name[len(ARCHIVE_PREFIX):]
    else:
        # 数据异常：状态为已归档但键无 archive/ 前缀，拒绝自动处理
        print(f"错误: 需求 {req_id} 的存储键 '{dir_name}' 缺少 '{ARCHIVE_PREFIX}' 前缀，", file=sys.stderr)
        print(f"  meta 与归档约定不一致，请运行 req doctor 检查后手工处置", file=sys.stderr)
        sys.exit(1)

    restore_status, is_fallback = _resolve_restore_status(req, valid_statuses)

    src_path = storage_root / dir_name
    dst_path = storage_root / original_dir

    # dry-run 预览
    if args.dry_run:
        human = [
            "\n🔍 预恢复检查",
            "\n将执行：",
            f"  ① 移动目录: {src_path}",
            f"     → {dst_path}",
            f"  ② 恢复状态: {ARCHIVE_STATUS} → {restore_status}",
        ]
        if is_fallback:
            human.append(f"     ⚠ 无 pre_archive_status 记录，回退为默认状态 '{FALLBACK_RESTORE_STATUS}'")
        human.append(f"  ③ 更新 meta.json 键: {dir_name} → {original_dir}")
        human.append("\n⚠ --dry-run 模式，未做任何修改。")
        emit_success(args, {
            "dry_run": True, "id": req_id, "src": str(src_path), "dst": str(dst_path),
            "meta_key": original_dir, "status": restore_status, "is_fallback": is_fallback,
        }, human)
        return

    # 存量无 pre_archive_status 且非 --force：交互确认恢复状态
    if is_fallback and not args.force:
        # --json 隐含非交互：无归档前状态且未带 --force 时直接报错
        guard_interactive(args, f"恢复 {req_id} 无归档前状态，需确认回退默认状态")
        print(f"⚠ 需求 {req_id} 无归档前状态记录，将恢复为默认状态 '{FALLBACK_RESTORE_STATUS}'", file=sys.stderr)
        try:
            answer = input("确认恢复？[y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return
        if answer != "y":
            print("已取消")
            return

    # 源目录存在性、目标冲突（锁外快速失败）
    if not src_path.exists():
        print(f"错误: 归档目录不存在: {src_path}", file=sys.stderr)
        sys.exit(1)
    if dst_path.exists():
        print(f"错误: 恢复目标目录已存在: {dst_path}", file=sys.stderr)
        print(f"  原分类目录下已有同名目录，请先处理后再恢复", file=sys.stderr)
        sys.exit(1)

    meta_path = storage_root / "meta.json"
    try:
        with FileLock(str(meta_path), timeout=lock_timeout):
            data = ms.load()
            requirements = data["requirements"]

            dir_name, req = find_req(requirements, req_id)
            if req is None:
                print(f"错误: 未找到需求 {req_id}（并发删除）", file=sys.stderr)
                sys.exit(1)
            if req.get("status") != ARCHIVE_STATUS:
                print(f"错误: 需求 {req_id} 已非归档状态（并发操作）", file=sys.stderr)
                sys.exit(1)

            # 连带修复：锁内基于重读的 dir_name 重算路径，避免陈旧路径
            if dir_name.startswith(ARCHIVE_PREFIX):
                original_dir = dir_name[len(ARCHIVE_PREFIX):]
            else:
                print(f"错误: 需求 {req_id} 存储键 '{dir_name}' 缺少归档前缀（并发变更）", file=sys.stderr)
                sys.exit(1)
            src_path = storage_root / dir_name
            dst_path = storage_root / original_dir

            # 二次检查源存在、目标不冲突
            if not src_path.exists():
                print(f"错误: 归档目录不存在（并发操作）: {src_path}", file=sys.stderr)
                sys.exit(1)
            if dst_path.exists():
                print(f"错误: 恢复目标目录已存在（并发操作）: {dst_path}", file=sys.stderr)
                sys.exit(1)

            # 重新确定恢复状态（基于重读数据）
            restore_status, is_fallback = _resolve_restore_status(req, valid_statuses)

            # 确保目标父目录存在（原分类目录可能在归档后被清理）
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # ① 先更新 meta.json（meta 是唯一可信源，与 archive 同序）
            snapshot = copy.deepcopy(req)
            old_entry = requirements.pop(dir_name)

            timestamp = now_cst_str()
            old_entry["status"] = restore_status
            old_entry["updated"] = timestamp
            # 清理归档态字段（下次归档会重新写入）
            old_entry.pop("pre_archive_status", None)
            old_entry.pop("archived_at", None)
            old_entry.pop("archive_reason", None)

            old_entry["version"] = old_entry.get("version", 1) + 1
            changelog_msg = f"恢复归档 → {restore_status}"
            if is_fallback:
                changelog_msg += "（无归档前状态记录，回退默认）"
            old_entry.setdefault("changelog", [])
            old_entry["changelog"].append(
                f"{timestamp} v{old_entry['version']}: {changelog_msg}"
            )

            requirements[original_dir] = old_entry
            ms.save(data)

            # ② 再移动目录，失败则回滚 meta
            try:
                shutil.move(str(src_path), str(dst_path))
            except OSError as e:
                requirements.pop(original_dir, None)
                requirements[dir_name] = snapshot
                try:
                    ms.save(data)
                except Exception as rollback_err:
                    print(f"严重: meta 回滚失败，请手工检查 meta.json: {rollback_err}", file=sys.stderr)
                print(f"错误: 目录移动失败，已回滚恢复状态: {e}", file=sys.stderr)
                sys.exit(1)

            # 清理空的 archive 分类子目录（如 archive/tool/ 空了就删）
            src_parent = src_path.parent
            archive_base = storage_root / ARCHIVE_DIR
            try:
                current = src_parent
                while current != archive_base and current != storage_root and current.exists():
                    if any(current.iterdir()):
                        break
                    current.rmdir()
                    current = current.parent
            except OSError:
                pass

    except TimeoutError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)

    emit_success(args, {
        "id": req_id,
        "meta_key": original_dir,
        "src": str(src_path),
        "dst": str(dst_path),
        "status": restore_status,
        "is_fallback": is_fallback,
    }, [
        "✓ 需求已恢复",
        f"  ID:        {req_id}",
        f"  原归档:    {src_path}",
        f"  恢复位置:  {dst_path}",
        f"  状态:      {restore_status}",
    ] + (["  ⚠ 无归档前状态记录，已回退为默认状态"] if is_fallback else []))
