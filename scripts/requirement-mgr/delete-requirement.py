#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S-05: 删除需求，含反向依赖检查、交互确认、级联清理。"""

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / ".requirements" / "scripts"))

# Windows GBK 编码修复
sys.stdout.reconfigure(encoding="utf-8")

from config_loader import ConfigLoader
from meta_store import MetaStore
from file_lock import FileLock
from requirement_utils import find_req, find_rev_deps


def _show_preview(dir_name: str, req: dict, rev_deps: list[dict]):
    """展示删除预览。"""
    print(f"\n{'─' * 50}")
    print(f"  ID:        {req['id']}")
    print(f"  名称:      {req.get('feature', '')}")
    print(f"  目录:      {dir_name}")
    print(f"  状态:      {req.get('status', '')}")
    if rev_deps:
        print(f"\n  反向依赖（{len(rev_deps)} 项将清理引用）：")
        for rd in rev_deps:
            print(f"    {rd['id']}  {rd['feature']}")
    print(f"{'─' * 50}")


def main():
    parser = argparse.ArgumentParser(description="删除需求")
    parser.add_argument("req_id", help="需求 ID，如 REQ-003")
    parser.add_argument("--force", action="store_true", help="跳过交互确认")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际删除")
    args = parser.parse_args()

    req_id = args.req_id.strip()

    if args.dry_run and args.force:
        print("错误: --dry-run 和 --force 不能同时使用", file=sys.stderr)
        sys.exit(1)

    # 加载
    try:
        cl = ConfigLoader()
        storage_root = cl.read()
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    ms = MetaStore(storage_root)
    data = ms.load()
    requirements = data["requirements"]

    dir_name, req = find_req(requirements, req_id)
    if req is None:
        print(f"错误: 未找到需求 {req_id}", file=sys.stderr)
        sys.exit(1)

    rev_deps = find_rev_deps(requirements, req_id)
    cleaned_count = len(rev_deps)

    # dry-run
    if args.dry_run:
        print(f"\n🔍 预删除检查")
        print(f"\n将执行：")
        print(f"  ① 从 meta.json 删除 {req_id} 条目")
        if cleaned_count:
            ids = ", ".join(r["id"] for r in rev_deps)
            print(f"  ② 从 {ids} 的 depends_on 中移除 {req_id}")
        dir_path = storage_root / dir_name
        print(f"  ③ 删除目录: {dir_path}")
        print(f"\n⚠ --dry-run 模式，未做任何修改。")
        return

    # 交互确认
    if not args.force:
        _show_preview(dir_name, req, rev_deps)
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
        with FileLock(str(meta_path)):
            data = ms.load()
            requirements = data["requirements"]

            if dir_name not in requirements:
                print(f"错误: 未找到需求 {req_id}（并发删除）", file=sys.stderr)
                sys.exit(1)

            # ① 删除条目
            del requirements[dir_name]

            # ② 清理引用
            actual_cleaned = 0
            for other in requirements.values():
                deps = other.get("depends_on", [])
                if req_id in deps:
                    deps.remove(req_id)
                    actual_cleaned += 1

            ms.save(data)

            # ③ 删除目录（失败不影响 meta.json 一致性，仅警告）
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
    if actual_cleaned:
        print(f"  清理引用: {actual_cleaned} 个需求的 depends_on")


if __name__ == "__main__":
    main()
