# -*- coding: utf-8 -*-
"""req create: 新建需求，创建目录 + 写入 meta.json。"""

import sys
from datetime import date
from pathlib import Path

from requirement_mgr.core.config_loader import ConfigLoader
from requirement_mgr.core.meta_store import MetaStore
from requirement_mgr.core.file_lock import FileLock
from requirement_mgr.core.id_generator import gen_next_id
from requirement_mgr.core.requirement_utils import find_req


def cmd_create(args):
    """执行 req create 命令。"""
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

    # 加载配置
    try:
        cl = ConfigLoader()
        storage_root = cl.read()
        feature_categories = cl.get_feature_categories()
        requirement_tags = cl.get_requirement_tags()
        valid_statuses = cl.get_requirement_statuses()
        valid_roles = cl.get_requirement_roles()
        default_status = cl.get_default_status()
        default_role = cl.get_default_role()
        id_prefix = cl.get_id_prefix()
        id_digits = cl.get_id_digits()
        lock_timeout = cl.get_lock_timeout()
        backup_enabled = cl.get_backup_enabled()
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    # status 校验（从 config 驱动，非硬编码）
    status = (args.status or default_status).strip()
    if status not in valid_statuses:
        print(f"错误: 无效状态 '{status}'，有效值: {', '.join(valid_statuses)}", file=sys.stderr)
        sys.exit(1)

    # role 校验
    role = (args.role or default_role).strip()
    if role not in valid_roles:
        print(f"错误: 无效角色 '{role}'，有效值: {', '.join(valid_roles)}", file=sys.stderr)
        sys.exit(1)

    # --parent-id 存在但 role 非 child 时拒绝（除非 CLI 层已自动推断）
    parent_id = args.parent_id
    if parent_id:
        parent_id = parent_id.strip()
        if role == "standalone":
            print("错误: 指定 --parent-id 时 role 不能为 standalone", file=sys.stderr)
            sys.exit(1)
        if role == "parent":
            print("错误: 指定 --parent-id 时 role 不能为 parent（应该是 child）", file=sys.stderr)
            sys.exit(1)

    # 标签验证
    category_tags = []

    if requirement_tags:
        invalid_tags = [t for t in tags if t not in requirement_tags]
        if invalid_tags:
            print(f"错误: 标签 {invalid_tags} 不在 requirement_tags 配置中", file=sys.stderr)
            print(f"  允许的标签: {', '.join(requirement_tags)}", file=sys.stderr)
            sys.exit(1)

    if feature_categories:
        category_tags = [t for t in tags if t in feature_categories]
        if len(category_tags) == 0:
            print(f"错误: 必须包含一个功能分类标签", file=sys.stderr)
            print(f"  功能分类标签: {', '.join(feature_categories)}", file=sys.stderr)
            sys.exit(1)
        elif len(category_tags) > 1:
            print(f"错误: 功能分类标签只能有一个，当前有: {', '.join(category_tags)}", file=sys.stderr)
            sys.exit(1)

    ms = MetaStore(storage_root, backup_enabled=backup_enabled)

    # 前置校验（加锁前）
    data = ms.load()
    requirements = data["requirements"]

    # 检查依赖 ID
    for rid in depends_on:
        found = any(req.get("id") == rid for req in requirements.values())
        if not found:
            print(f"错误: 依赖需求 {rid} 不存在", file=sys.stderr)
            sys.exit(1)

    # 检查 parent_id
    if parent_id:
        _, parent_req = find_req(requirements, parent_id)
        if parent_req is None:
            print(f"错误: 父需求 {parent_id} 不存在", file=sys.stderr)
            sys.exit(1)
        if parent_req.get("role") not in ("parent", "standalone"):
            print(f"错误: 目标需求 {parent_id} 的角色为 {parent_req.get('role')}，不能作为父需求", file=sys.stderr)
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

    # 目录路径
    if category:
        dir_path = storage_root / category / dir_name
    else:
        dir_path = storage_root / dir_name

    # 确保目录结构存在
    if not storage_root.exists():
        storage_root.mkdir(parents=True, exist_ok=True)
    if category:
        (storage_root / category).mkdir(parents=True, exist_ok=True)

    meta_path = storage_root / "meta.json"

    try:
        with FileLock(str(meta_path), timeout=lock_timeout):
            # TOCTOU 防护：重新加载
            data = ms.load()
            requirements = data["requirements"]

            # 二次校验依赖
            for rid in depends_on:
                found = any(req.get("id") == rid for req in requirements.values())
                if not found:
                    print(f"错误: 依赖需求 {rid} 不存在（并发变更）", file=sys.stderr)
                    sys.exit(1)

            # 二次校验目录冲突
            if dir_path.exists():
                print(f"错误: 目录已存在: {dir_path}", file=sys.stderr)
                sys.exit(1)

            # 二次校验 parent_id（TOCTOU）
            if parent_id:
                _, parent_req = find_req(requirements, parent_id)
                if parent_req is None:
                    print(f"错误: 父需求 {parent_id} 不存在（并发删除）", file=sys.stderr)
                    sys.exit(1)

            # 生成 ID
            req_id = gen_next_id(requirements, prefix=id_prefix, digits=id_digits)

            # ① 先创建目录
            dir_path.mkdir(parents=True, exist_ok=False)

            # ② 构建条目
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
                "role": role,
                "parent_id": parent_id if parent_id else None,
                "child_ids": [],
            }

            # 使用包含 category 的路径作为键名
            if category:
                meta_key = f"{category}/{dir_name}"
            else:
                meta_key = dir_name
            requirements[meta_key] = entry

            # ③ 处理父子关系：追加 parent 的 child_ids + 自动升级 parent role
            if parent_id:
                _, parent_req = find_req(requirements, parent_id)
                if parent_req:
                    if parent_req.get("role") == "standalone":
                        # 自动升级 standalone → parent
                        parent_req["role"] = "parent"
                        parent_req["child_ids"] = [req_id]
                    else:
                        parent_req.setdefault("child_ids", [])
                        parent_req["child_ids"].append(req_id)

            ms.save(data)

    except TimeoutError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"✓ 需求已创建")
    print(f"  ID:      {req_id}")
    print(f"  角色:    {role}")
    if parent_id:
        print(f"  父需求:  {parent_id}")
    print(f"  目录:    {dir_path}")
    print(f"  元数据:  {meta_path}")
