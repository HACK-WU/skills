# -*- coding: utf-8 -*-
"""req create: 新建需求，创建目录 + 写入 meta.json。"""

import re
import shutil
import sys
from pathlib import Path

from requirement_mgr.core.config_loader import ConfigLoader
from requirement_mgr.core.meta_store import MetaStore
from requirement_mgr.core.file_lock import FileLock
from requirement_mgr.core.id_generator import gen_next_id
from requirement_mgr.core.requirement_utils import ARCHIVED_STATUS, find_req
from requirement_mgr.core.time_utils import now_cst_str, today_cst_str
from requirement_mgr.core.output import emit_success, is_json


# 目录名中禁止的字符（路径分隔符 / 空字符）
_UNSAFE_CHARS = re.compile(r"[/\\\x00]")


def _check_dir_name(name: str) -> str | None:
    """校验目录名是否为安全的单层目录组件，非法返回错误信息。

    防路径穿越：禁止 . / .. / 路径分隔符，避免写到 storage_root 之外
    或污染 meta.json 键名（键名格式为 category/dir_name）。
    """
    if not name:
        return "目录名不能为空"
    if name in (".", ".."):
        return f"目录名不能为 '{name}'"
    if _UNSAFE_CHARS.search(name):
        return f"目录名 '{name}' 含非法字符（不允许 / \\ 和空字符）"
    return None


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
    # O-10：去重且保序（避免重复依赖写入 meta）
    depends_on = list(dict.fromkeys(depends_on))

    # branch：可选单值，空/纯空白视为未指定（存为 None，展示时显示 —）
    branch = args.branch.strip() if args.branch else None
    branch = branch or None

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
    if status == ARCHIVED_STATUS:
        print(f"错误: 不能直接创建 '{ARCHIVED_STATUS}' 状态的需求，请使用 req archive", file=sys.stderr)
        sys.exit(1)
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
    warnings = []
    for rid in depends_on:
        found_req = next((req for req in requirements.values() if req.get("id") == rid), None)
        if found_req is None:
            print(f"错误: 依赖需求 {rid} 不存在", file=sys.stderr)
            sys.exit(1)
        # O-10：依赖已归档需求时警告（不阻断）
        if found_req.get("status") == ARCHIVED_STATUS:
            warnings.append(f"依赖需求 {rid} 已归档")

    # 检查 parent_id
    if parent_id:
        _, parent_req = find_req(requirements, parent_id)
        if parent_req is None:
            print(f"错误: 父需求 {parent_id} 不存在", file=sys.stderr)
            sys.exit(1)
        if parent_req.get("status") == ARCHIVED_STATUS:
            print(f"错误: 父需求 {parent_id} 已归档，不能挂载子需求", file=sys.stderr)
            sys.exit(1)
        if parent_req.get("role") not in ("parent", "standalone"):
            print(f"错误: 目标需求 {parent_id} 的角色为 {parent_req.get('role')}，不能作为父需求", file=sys.stderr)
            sys.exit(1)

    # 提取功能分类标签
    category = category_tags[0] if category_tags else ""

    # 生成目录名（仅日期）和时间戳（完整时间）
    today = today_cst_str()
    timestamp = now_cst_str()
    if args.dir_name:
        # 显式指定的目录名：非法直接拒绝
        dir_name = args.dir_name.strip()
        err = _check_dir_name(dir_name)
        if err:
            print(f"错误: --dir-name 非法: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        # 从 feature 推导：清洗路径分隔符后截断
        safe_feature = _UNSAFE_CHARS.sub("-", feature).strip("-. ")[:20]
        dir_name = f"{today}-{safe_feature}"
        err = _check_dir_name(dir_name)
        if err:
            print(f"错误: 无法从 feature 生成合法目录名: {err}，请使用 --dir-name 指定", file=sys.stderr)
            sys.exit(1)

    # 目录路径
    if category:
        dir_path = storage_root / category / dir_name
    else:
        dir_path = storage_root / dir_name

    # 防穿越兜底：解析后必须仍在 storage_root 内
    if not dir_path.resolve().is_relative_to(storage_root.resolve()):
        print(f"错误: 目录路径超出存储根目录: {dir_path}", file=sys.stderr)
        sys.exit(1)

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

            # 二次校验 parent_id（TOCTOU：存在性 + 角色 + 归档状态均复验）
            if parent_id:
                _, parent_req = find_req(requirements, parent_id)
                if parent_req is None:
                    print(f"错误: 父需求 {parent_id} 不存在（并发删除）", file=sys.stderr)
                    sys.exit(1)
                if parent_req.get("status") == ARCHIVED_STATUS:
                    print(f"错误: 父需求 {parent_id} 已归档（并发变更），不能挂载子需求", file=sys.stderr)
                    sys.exit(1)
                if parent_req.get("role") not in ("parent", "standalone"):
                    print(f"错误: 目标需求 {parent_id} 的角色为 {parent_req.get('role')}（并发变更），不能作为父需求", file=sys.stderr)
                    sys.exit(1)

            # 生成 ID（id_counters 为 meta 顶层只增不减计数器，防删除后 ID 复用）
            id_counters = data.setdefault("id_counters", {})
            try:
                req_id = gen_next_id(requirements, prefix=id_prefix, digits=id_digits,
                                     id_counters=id_counters)
            except ValueError as e:
                print(f"错误: {e}", file=sys.stderr)
                sys.exit(1)

            # ① 先创建目录
            dir_path.mkdir(parents=True, exist_ok=False)

            # ② 构建条目
            entry = {
                "id": req_id,
                "feature": feature,
                "created": timestamp,
                "updated": timestamp,
                "status": status,
                "tags": tags,
                "version": 1,
                "depends_on": depends_on,
                "changelog": ["初始创建"],
                "commits": [],
                "branch": branch,
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

            try:
                ms.save(data)
            except Exception:
                # meta 写入失败时回滚刚创建的空目录，避免遗留孤儿目录
                # 阻塞后续同名创建（目录由上方 mkdir(exist_ok=False) 独占创建）
                shutil.rmtree(dir_path, ignore_errors=True)
                raise

    except TimeoutError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)

    # O-10：归档依赖警告（非阻断），人类模式打印到 stderr，json 模式并入 payload
    if not is_json(args):
        for w in warnings:
            print(f"⚠ 警告: {w}", file=sys.stderr)

    human_lines = [
        "✓ 需求已创建",
        f"  ID:      {req_id}",
        f"  角色:    {role}",
    ]
    if branch:
        human_lines.append(f"  分支:    {branch}")
    if parent_id:
        human_lines.append(f"  父需求:  {parent_id}")
    human_lines.append(f"  目录:    {dir_path}")
    human_lines.append(f"  元数据:  {meta_path}")
    emit_success(args, {
        "id": req_id,
        "meta_key": meta_key,
        "dir": str(dir_path),
        "role": role,
        "branch": branch,
        "parent_id": parent_id if parent_id else None,
        "warnings": warnings,
    }, human_lines)
