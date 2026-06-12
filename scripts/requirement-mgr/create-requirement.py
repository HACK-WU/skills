#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S-03: 新建需求，创建目录 + 写入 meta.json。"""

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
from id_generator import gen_next_id

VALID_STATUSES = {"草案", "已确认", "设计中", "实施中", "已完成", "已取消"}


def main():
    parser = argparse.ArgumentParser(description="新建需求")
    parser.add_argument("--feature", required=True, help="功能名称（中文）")
    parser.add_argument("--tags", default="feat", help="标签，逗号分隔（默认 feat）")
    parser.add_argument("--depends-on", default="", help="依赖的需求 ID，逗号分隔")
    parser.add_argument("--status", default="草案", help="初始状态（默认：草案）")
    parser.add_argument("--dir-name", default="", help="自定义目录名（默认 {date}-{feature}）")
    args = parser.parse_args()

    # 解析参数
    feature = args.feature.strip()
    if not feature:
        print("错误: --feature 不能为空", file=sys.stderr)
        sys.exit(1)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    if not tags:
        print("错误: 至少需要一个标签", file=sys.stderr)
        sys.exit(1)

    depends_on = [d.strip() for d in args.depends_on.split(",") if d.strip()]

    status = args.status.strip()
    if status not in VALID_STATUSES:
        print(f"错误: 无效状态 '{status}'，有效值: {', '.join(sorted(VALID_STATUSES))}", file=sys.stderr)
        sys.exit(1)

    # 加载配置
    try:
        cl = ConfigLoader()
        storage_root = cl.read()
        feature_categories = cl.get_feature_categories()
        requirement_tags = cl.get_requirement_tags()
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 标签验证
    category_tags = []

    # 1. 验证标签来源（必须来自 requirement_tags 配置）
    if requirement_tags:
        invalid_tags = [t for t in tags if t not in requirement_tags]
        if invalid_tags:
            print(f"错误: 标签 {invalid_tags} 不在 requirement_tags 配置中", file=sys.stderr)
            print(f"  允许的标签: {', '.join(requirement_tags)}", file=sys.stderr)
            sys.exit(1)
    
    # 2. 验证功能分类标签（如果配置了 feature_categories）
    if feature_categories:
        category_tags = [t for t in tags if t in feature_categories]
        if len(category_tags) == 0:
            print(f"错误: 必须包含一个功能分类标签", file=sys.stderr)
            print(f"  功能分类标签: {', '.join(feature_categories)}", file=sys.stderr)
            sys.exit(1)
        elif len(category_tags) > 1:
            print(f"错误: 功能分类标签只能有一个，当前有: {', '.join(category_tags)}", file=sys.stderr)
            sys.exit(1)

    ms = MetaStore(storage_root)

    # 前置校验（加锁前）—— 检查依赖 ID 是否都存在
    data = ms.load()
    requirements = data["requirements"]

    # meta.json 为空或不存在时，depends_on 不能有值
    for rid in depends_on:
        found = any(req.get("id") == rid for req in requirements.values())
        if not found:
            print(f"错误: 依赖需求 {rid} 不存在", file=sys.stderr)
            sys.exit(1)

    # 提取功能分类标签
    category = category_tags[0] if category_tags else ""
    
    # 生成目录名
    today = date.today().isoformat()
    if args.dir_name:
        dir_name = args.dir_name.strip()
    else:
        safe_feature = feature[:20]
        dir_name = f"{today}-{safe_feature}"

    # 目录路径：{storage_root}/{category}/{dir_name}
    if category:
        dir_path = storage_root / category / dir_name
    else:
        dir_path = storage_root / dir_name

    # 加锁 + 原子写入 + 创建目录
    meta_path = storage_root / "meta.json"

    # 确保目录结构存在
    if not storage_root.exists():
        storage_root.mkdir(parents=True, exist_ok=True)
    if category:
        (storage_root / category).mkdir(parents=True, exist_ok=True)

    try:
        with FileLock(str(meta_path)):
            # TOCTOU 防护：重新加载
            data = ms.load()
            requirements = data["requirements"]

            # 二次校验依赖（meta.json 为空时 depends_on 自动失败）
            for rid in depends_on:
                found = any(req.get("id") == rid for req in requirements.values())
                if not found:
                    print(f"错误: 依赖需求 {rid} 不存在（并发变更）", file=sys.stderr)
                    sys.exit(1)

            # 二次校验目录冲突
            if dir_path.exists():
                print(f"错误: 目录已存在: {dir_path}", file=sys.stderr)
                sys.exit(1)

            # 生成 ID
            req_id = gen_next_id(requirements)

            # ① 先创建目录（失败则 meta.json 不受影响）
            dir_path.mkdir(parents=True, exist_ok=False)

            # ② 构建条目并写入 meta.json
            entry = {
                "id": req_id,
                "feature": feature,
                "created": today,
                "updated": today,
                "status": status,
                "tags": tags,
                "version": 1,
                "depends_on": depends_on,
                "changelog": ["初始创建"],
                "commits": [],
                "docs": [],
            }
            # 使用包含 category 的路径作为键名
            if category:
                meta_key = f"{category}/{dir_name}"
            else:
                meta_key = dir_name
            requirements[meta_key] = entry
            ms.save(data)

    except TimeoutError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"✓ 需求已创建")
    print(f"  ID:      {req_id}")
    print(f"  目录:    {dir_path}")
    print(f"  元数据:  {meta_path}")


if __name__ == "__main__":
    main()
