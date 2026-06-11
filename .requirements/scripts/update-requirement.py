#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S-04: 修改需求元数据，支持字段增删改、循环依赖检测、版号自增。"""

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / ".requirements" / "scripts"))

# Windows GBK 编码修复
sys.stdout.reconfigure(encoding="utf-8")

from config_loader import ConfigLoader
from meta_store import MetaStore
from file_lock import FileLock
from requirement_utils import find_req, has_circular_dep

VALID_STATUSES = {"草案", "已确认", "设计中", "实施中", "已完成", "已取消"}


def main():
    parser = argparse.ArgumentParser(description="修改需求")
    parser.add_argument("req_id", help="需求 ID，如 REQ-001")
    parser.add_argument("--status", help="更新状态")
    parser.add_argument("--feature", help="更新功能名称")
    parser.add_argument("--tag", nargs=2, action="append",
                        help="标签操作: add/remove/set VALUE（可重复）")
    parser.add_argument("--depends-on", nargs=2, action="append", dest="depends_on_ops",
                        help="依赖操作: add/remove/set IDS（逗号分隔）")
    parser.add_argument("--commit", help="追加 git commit hash")
    parser.add_argument("--data-flow", help="设置数据流图路径")
    parser.add_argument("--report", help="设置实现报告路径")
    parser.add_argument("--changelog", help="追加变更记录")
    args = parser.parse_args()

    req_id = args.req_id.strip()

    # 加载
    try:
        cl = ConfigLoader()
        storage_root = cl.read()
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    ms = MetaStore(storage_root)

    # 前置校验
    data = ms.load()
    requirements = data["requirements"]
    dir_name, req = find_req(requirements, req_id)
    if req is None:
        print(f"错误: 未找到需求 {req_id}", file=sys.stderr)
        sys.exit(1)

    changes = 0

    # ---- 前置校验 ----
    # status
    if args.status and args.status not in VALID_STATUSES:
        print(f"错误: 无效状态 '{args.status}'", file=sys.stderr)
        sys.exit(1)

    # tag remove 最后一个
    current_tags = list(req.get("tags", []))
    if args.tag:
        for op, value in args.tag:
            if op == "remove" and len(current_tags) <= 1:
                print("错误: 不能删除最后一个标签", file=sys.stderr)
                sys.exit(1)

    # depends_on 校验
    if args.depends_on_ops:
        for op, ids_str in args.depends_on_ops:
            ids = [i.strip() for i in ids_str.split(",") if i.strip()]
            if op == "add":
                for rid in ids:
                    _, target = find_req(requirements, rid)
                    if target is None:
                        print(f"错误: 依赖需求 {rid} 不存在", file=sys.stderr)
                        sys.exit(1)
                    if rid == req_id:
                        print("错误: 不能依赖自身", file=sys.stderr)
                        sys.exit(1)
                    if has_circular_dep(requirements, req_id, rid):
                        print(f"错误: 添加 {rid} 会形成循环依赖", file=sys.stderr)
                        sys.exit(1)

    # ---- 加锁 + 应用变更 ----
    meta_path = storage_root / "meta.json"
    try:
        with FileLock(str(meta_path)):
            data = ms.load()
            requirements = data["requirements"]
            dir_name, req = find_req(requirements, req_id)
            if req is None:
                print(f"错误: 未找到需求 {req_id}（并发删除）", file=sys.stderr)
                sys.exit(1)

            # status
            if args.status:
                req["status"] = args.status
                changes += 1

            # feature
            if args.feature:
                req["feature"] = args.feature.strip()
                changes += 1

            # tag add/remove/set
            if args.tag:
                for op, value in args.tag:
                    if op == "add":
                        if value not in req["tags"]:
                            req["tags"].append(value)
                            changes += 1
                    elif op == "remove":
                        if value in req["tags"]:
                            req["tags"].remove(value)
                            changes += 1
                    elif op == "set":
                        new_tags = [t.strip() for t in value.split(",") if t.strip()]
                        if new_tags:
                            req["tags"] = new_tags
                            changes += 1

            # depends_on add/remove/set
            if args.depends_on_ops:
                for op, ids_str in args.depends_on_ops:
                    ids = [i.strip() for i in ids_str.split(",") if i.strip()]
                    if op == "add":
                        for rid in ids:
                            if rid not in req.get("depends_on", []):
                                req.setdefault("depends_on", [])
                                req["depends_on"].append(rid)
                                changes += 1
                    elif op == "remove":
                        deps = req.get("depends_on", [])
                        for rid in ids:
                            if rid in deps:
                                deps.remove(rid)
                                changes += 1
                    elif op == "set":
                        req["depends_on"] = ids
                        changes += 1

            # commit
            if args.commit:
                req.setdefault("commits", [])
                if args.commit not in req["commits"]:
                    req["commits"].append(args.commit)
                    changes += 1

            # data-flow / report
            if args.data_flow is not None:
                req["data_flow"] = args.data_flow
                changes += 1
            if args.report is not None:
                req["report"] = args.report
                changes += 1

            if changes == 0 and not args.changelog:
                print("提示: 未指定任何要修改的字段", file=sys.stderr)
                sys.exit(1)

            # 版本 + 日期 + changelog
            req["version"] = req.get("version", 1) + 1
            req["updated"] = date.today().isoformat()

            if args.changelog:
                req.setdefault("changelog", [])
                req["changelog"].append(
                    f"{req['updated']} v{req['version']}: {args.changelog.strip()}"
                )

            ms.save(data)

    except TimeoutError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"✓ 需求已更新")
    print(f"  ID:      {req_id}")
    print(f"  版本:    v{req['version']}")
    print(f"  变更数:  {changes}")


if __name__ == "__main__":
    main()
