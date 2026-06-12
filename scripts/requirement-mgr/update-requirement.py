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
    parser.add_argument("--docs", nargs=2, action="append", dest="docs_ops",
                        metavar=("OP", "VALUE"),
                        help="文档操作: add PATH,TYPE / remove PATH / set PATH1,TYPE1;PATH2,TYPE2")
    parser.add_argument("--changelog", help="追加变更记录")
    args = parser.parse_args()

    req_id = args.req_id.strip()

    # 加载
    try:
        cl = ConfigLoader()
        storage_root = cl.read()
        feature_categories = cl.get_feature_categories()
        requirement_tags = cl.get_requirement_tags()
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

    # tag 操作校验
    current_tags = list(req.get("tags", []))
    current_category_tag = next((t for t in current_tags if t in feature_categories), None) if feature_categories else None
    if args.tag:
        for op, value in args.tag:
            if op == "remove":
                if len(current_tags) <= 1:
                    print("错误: 不能删除最后一个标签", file=sys.stderr)
                    sys.exit(1)
                # 功能分类标签不得删除（目录位置依赖此标签）
                if feature_categories and value in feature_categories:
                    print(f"错误: 不能删除功能分类标签 '{value}'，目录位置依赖此标签", file=sys.stderr)
                    print(f"  如需更改分类，请删除并重新创建需求", file=sys.stderr)
                    sys.exit(1)
            elif op == "add":
                # 验证标签来源
                if requirement_tags and value not in requirement_tags:
                    print(f"错误: 标签 '{value}' 不在 requirement_tags 配置中", file=sys.stderr)
                    print(f"  允许的标签: {', '.join(requirement_tags)}", file=sys.stderr)
                    sys.exit(1)
                # 验证功能分类标签唯一性
                if feature_categories and value in feature_categories:
                    if any(t in feature_categories for t in current_tags):
                        print(f"错误: 已存在功能分类标签，不能添加另一个功能分类标签 '{value}'", file=sys.stderr)
                        sys.exit(1)
            elif op == "set":
                new_tags = [t.strip() for t in value.split(",") if t.strip()]
                if not new_tags:
                    print("错误: --tag set 不能设置为空", file=sys.stderr)
                    sys.exit(1)
                # 验证标签来源
                if requirement_tags:
                    invalid_tags = [t for t in new_tags if t not in requirement_tags]
                    if invalid_tags:
                        print(f"错误: 标签 {invalid_tags} 不在 requirement_tags 配置中", file=sys.stderr)
                        print(f"  允许的标签: {', '.join(requirement_tags)}", file=sys.stderr)
                        sys.exit(1)
                # 验证功能分类标签
                if feature_categories:
                    new_category_tags = [t for t in new_tags if t in feature_categories]
                    if len(new_category_tags) == 0:
                        print(f"错误: 必须包含一个功能分类标签", file=sys.stderr)
                        print(f"  功能分类标签: {', '.join(feature_categories)}", file=sys.stderr)
                        sys.exit(1)
                    elif len(new_category_tags) > 1:
                        print(f"错误: 功能分类标签只能有一个，当前有: {', '.join(new_category_tags)}", file=sys.stderr)
                        sys.exit(1)
                    # 功能分类标签变更会导致目录位置不匹配，拒绝操作
                    new_category = new_category_tags[0]
                    if current_category_tag and new_category != current_category_tag:
                        print(f"错误: 不能更改功能分类标签（'{current_category_tag}' → '{new_category}'），目录位置依赖此标签", file=sys.stderr)
                        print(f"  如需更改分类，请删除并重新创建需求", file=sys.stderr)
                        sys.exit(1)

    # docs 操作校验
    if args.docs_ops:
        for op, value in args.docs_ops:
            if op == "add":
                parts = value.split(",")
                if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
                    print("错误: --docs add 格式: PATH,TYPE（两者均不可为空）", file=sys.stderr)
                    sys.exit(1)
            elif op == "remove":
                if not value.strip():
                    print("错误: --docs remove 需要指定路径", file=sys.stderr)
                    sys.exit(1)
            elif op == "set":
                docs_specs = [s.strip() for s in value.split(";") if s.strip()]
                for spec in docs_specs:
                    parts = spec.split(",")
                    if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
                        print(f"错误: --docs set 格式错误: {spec}（应为 PATH,TYPE，两者不可为空）", file=sys.stderr)
                        sys.exit(1)
            else:
                print(f"错误: 未知的 docs 操作 '{op}'，支持 add/remove/set", file=sys.stderr)
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

            # docs add/remove/set
            if args.docs_ops:
                req.setdefault("docs", [])
                for op, value in args.docs_ops:
                    if op == "add":
                        parts = value.split(",")
                        doc_path = parts[0].strip()
                        doc_type = parts[1].strip()
                        # 存在则跳过（幂等）
                        if not any(d["path"] == doc_path for d in req["docs"]):
                            req["docs"].append({"path": doc_path, "type": doc_type})
                            changes += 1
                    elif op == "remove":
                        target_path = value.strip()
                        before = len(req["docs"])
                        req["docs"] = [d for d in req["docs"] if d["path"] != target_path]
                        if len(req["docs"]) < before:
                            changes += 1
                    elif op == "set":
                        docs_specs = [s.strip() for s in value.split(";") if s.strip()]
                        new_docs = []
                        for spec in docs_specs:
                            parts = spec.split(",")
                            new_docs.append({"path": parts[0].strip(), "type": parts[1].strip()})
                        req["docs"] = new_docs
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
