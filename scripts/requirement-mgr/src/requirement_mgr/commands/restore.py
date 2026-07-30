# -*- coding: utf-8 -*-
"""req restore: 从 meta.json.bak 恢复元数据。"""

import re
import shutil
import sys

from requirement_mgr.core.config_loader import ConfigLoader
from requirement_mgr.core.file_lock import FileLock
from requirement_mgr.core.meta_store import MetaCorruptedError, MetaStore
from requirement_mgr.core.output import emit_success, guard_interactive, is_json


def _salvage_counters_from_text(text: str, prefix: str, digits: int) -> dict:
    """从损坏的 meta 文本中 best-effort 抢救已发号信息。

    JSON 损坏通常是局部的，文本里的需求 ID 与 id_counters 键值往往仍在。
    提取两类信息取 max，防止恢复旧备份后复用损坏现场中较新需求的 ID。
    """
    counters: dict = {}
    # 需求 ID：{prefix}-{YYYYMMDD}-{NNN}
    for m in re.finditer(rf"{re.escape(prefix)}-(\d{{8}})-(\d{{{digits}}})", text):
        key = f"{prefix}-{m.group(1)}"
        seq = int(m.group(2))
        if seq > counters.get(key, 0):
            counters[key] = seq
    # id_counters 键值："{prefix}-{YYYYMMDD}": N
    for m in re.finditer(rf'"{re.escape(prefix)}-(\d{{8}})"\s*:\s*(\d+)', text):
        key = f"{prefix}-{m.group(1)}"
        val = int(m.group(2))
        if val > counters.get(key, 0):
            counters[key] = val
    return counters


def _merge_id_counters(backup_data: dict, current_data: dict | None,
                       salvaged: dict | None = None) -> dict:
    """合并 id_counters：逐键取 max(.bak 值, 当前值, 损坏现场抢救值)。

    防止恢复旧 meta 后计数器回退，导致 ID 复用风险借道回归。
    当前 meta 损坏不可读时用 salvaged（文本级提取）兜底。
    """
    merged = dict(backup_data.get("id_counters", {}))
    sources = []
    if current_data:
        sources.append(current_data.get("id_counters", {}))
    if salvaged:
        sources.append(salvaged)
    for source in sources:
        for key, val in source.items():
            if isinstance(val, int) and val > merged.get(key, 0):
                merged[key] = val
    return merged


def cmd_restore(args):
    """执行 req restore 命令。"""
    try:
        cl = ConfigLoader()
        storage_root = cl.read()
        lock_timeout = cl.get_lock_timeout()
        backup_enabled = cl.get_backup_enabled()
        id_prefix = cl.get_id_prefix()
        id_digits = cl.get_id_digits()
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    # restore 的 save 必须禁用备份：否则会把当前（可能已损坏的）meta
    # 复制到 .bak，摧毁唯一可用的好备份
    ms = MetaStore(storage_root, backup_enabled=False)

    # 读取备份
    try:
        backup_data = ms.load_backup()
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        if not backup_enabled:
            print("提示: 当前 backup_enabled=false，写入时不会生成备份。", file=sys.stderr)
            print("      请在 .requirements/config 中设置 backup_enabled=true", file=sys.stderr)
        sys.exit(1)
    except MetaCorruptedError as e:
        print(f"错误: 备份文件也已损坏，无法恢复: {e}", file=sys.stderr)
        sys.exit(1)

    # 读取当前 meta（可能损坏）
    current_data = None
    current_corrupted = False
    try:
        current_data = ms.load()
    except MetaCorruptedError:
        current_corrupted = True

    # 预览信息
    backup_count = len(backup_data.get("requirements", {}))
    if not is_json(args):
        print("恢复预览:")
        print(f"  备份文件:  {ms.backup_path}")
        print(f"  备份需求数: {backup_count}")
        if current_corrupted:
            print(f"  当前 meta:  已损坏（无法解析），恢复前将另存为 {ms.meta_path}.corrupt")
        elif current_data is not None:
            current_count = len(current_data.get("requirements", {}))
            print(f"  当前需求数: {current_count}")
            if current_count > backup_count:
                print(f"  ⚠️  当前需求数多于备份，恢复将丢失 {current_count - backup_count} 条较新记录")
        print("  说明: 仅回滚 meta.json，不回滚需求目录；id_counters 取备份与当前的较大值（防 ID 复用）")

    if args.dry_run:
        emit_success(args, {
            "dry_run": True, "backup_count": backup_count,
            "current_corrupted": current_corrupted,
        }, ["\n[dry-run] 未执行任何变更"])
        return

    # 交互确认（--force 跳过）
    if not args.force:
        # --json 隐含非交互：未带 --force 时直接报错退出
        guard_interactive(args, "restore 需确认")
        try:
            answer = input("\n确认恢复？[y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return
        if answer != "y":
            print("已取消")
            return

    meta_path = ms.meta_path
    try:
        with FileLock(str(meta_path), timeout=lock_timeout):
            # 锁内重读备份与当前值，避免确认等待期间的并发变更被忽略
            backup_data = ms.load_backup()
            current_data = None
            salvaged = None
            try:
                current_data = ms.load()
            except MetaCorruptedError:
                if meta_path.exists():
                    # 损坏现场另存，便于事后排查
                    shutil.copy2(meta_path, str(meta_path) + ".corrupt")
                    # 文本级抢救已发号信息，防恢复后复用损坏现场中较新需求的 ID
                    try:
                        text = meta_path.read_text(encoding="utf-8", errors="replace")
                        salvaged = _salvage_counters_from_text(text, id_prefix, id_digits)
                    except OSError:
                        pass

            backup_data["id_counters"] = _merge_id_counters(backup_data, current_data, salvaged)
            ms.save(backup_data)
    except TimeoutError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)
    except (FileNotFoundError, MetaCorruptedError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    emit_success(args, {
        "restored_count": len(backup_data.get("requirements", {})),
    }, [
        "✓ 已从备份恢复 meta.json",
        f"  恢复需求数: {len(backup_data.get('requirements', {}))}",
        "  提示: 备份可能落后于需求目录的实际状态，请核对目录与元数据一致性",
    ])
