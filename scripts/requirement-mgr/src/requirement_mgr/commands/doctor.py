# -*- coding: utf-8 -*-
"""req doctor: meta 与文件系统一致性巡检，默认只读；--fix 修复可自动处置的漂移。

检查项：
  1. meta 键指向的目录不存在
  2. storage 下存在目录但 meta 无记录（孤儿目录）
  3. 同一 ID 出现在多条记录（手工编辑 meta 造成）
  4. status/role/tags 不在当前 config 白名单内（config 收缩后遗留）
  5. depends_on / parent_id / child_ids 指向不存在的需求 ID（悬空引用）

--fix 仅修复低风险项（持锁执行）：
  - 悬空 depends_on / child_ids 引用 → 自动移除
  - 悬空 parent_id → 置空并降级 role
  其余（目录缺失/孤儿/重复 ID/白名单外值）仅报告 + 给出建议命令。
"""

import sys

from requirement_mgr.core.config_loader import ConfigLoader
from requirement_mgr.core.meta_store import MetaStore
from requirement_mgr.core.file_lock import FileLock
from requirement_mgr.core.requirement_utils import ARCHIVED_STATUS


ARCHIVE_DIR = "archive"


def _collect_issues(data, storage_root, valid_statuses, valid_roles, requirement_tags):
    """扫描所有漂移，返回 (report_issues, fixable_issues)。

    report_issues: 仅报告的问题列表（str）
    fixable_issues: 可 --fix 处置的问题，形如 (kind, dir_name, detail)
    """
    requirements = data.get("requirements", {})
    report = []
    fixable = []

    # 全部有效 ID + ID → dir_name 列表（查重）
    id_to_dirs = {}
    for dir_name, req in requirements.items():
        rid = req.get("id")
        if rid:
            id_to_dirs.setdefault(rid, []).append(dir_name)
    valid_ids = set(id_to_dirs.keys())

    # 3. 同 ID 多条记录
    for rid, dirs in id_to_dirs.items():
        if len(dirs) > 1:
            report.append(
                f"[重复ID] {rid} 出现在 {len(dirs)} 条记录: {', '.join(dirs)}"
                f"（find_req 静默取第一个，请手工合并/删除多余记录）"
            )

    # 1 + 4 + 5：逐需求检查
    status_whitelist = list(valid_statuses)
    if ARCHIVED_STATUS not in status_whitelist:
        status_whitelist.append(ARCHIVED_STATUS)

    for dir_name, req in requirements.items():
        rid = req.get("id", "?")

        # 1. 目录存在性
        req_path = storage_root / dir_name
        if not req_path.exists():
            report.append(
                f"[目录缺失] {rid} 的键 '{dir_name}' 指向的目录不存在: {req_path}"
                f"（建议: 确认后手工恢复目录或 req delete {rid} 清理记录）"
            )

        # 4. 白名单检查
        status = req.get("status")
        if status and status not in status_whitelist:
            report.append(f"[白名单外] {rid} 状态 '{status}' 不在当前 config（建议: req update {rid} --status <合法值>）")
        role = req.get("role", "standalone")
        if role not in valid_roles:
            report.append(f"[白名单外] {rid} 角色 '{role}' 不在当前 config（建议: req update {rid} --role <合法值>）")
        if requirement_tags:  # 空表示不限制
            bad_tags = [t for t in req.get("tags", []) if t not in requirement_tags]
            if bad_tags:
                report.append(f"[白名单外] {rid} 标签 {bad_tags} 不在当前 config（建议: req update {rid} --tag ...）")

        # 5. 悬空引用
        dangling_deps = [d for d in req.get("depends_on", []) if d not in valid_ids]
        if dangling_deps:
            fixable.append(("depends_on", dir_name, dangling_deps))
            report.append(f"[悬空依赖] {rid} 的 depends_on 含不存在的 ID: {dangling_deps}（可 --fix 自动移除）")

        parent_id = req.get("parent_id")
        if parent_id and parent_id not in valid_ids:
            fixable.append(("parent_id", dir_name, parent_id))
            report.append(f"[悬空父需求] {rid} 的 parent_id '{parent_id}' 不存在（可 --fix 置空并降级 role）")

        dangling_children = [c for c in req.get("child_ids", []) if c not in valid_ids]
        if dangling_children:
            fixable.append(("child_ids", dir_name, dangling_children))
            report.append(f"[悬空子需求] {rid} 的 child_ids 含不存在的 ID: {dangling_children}（可 --fix 自动移除）")

    # 2. 孤儿目录：文件系统有目录但 meta 无记录
    report.extend(_scan_orphan_dirs(requirements, storage_root))

    return report, fixable


def _scan_orphan_dirs(requirements, storage_root):
    """扫描孤儿目录：与 meta 键既不重合、也非其祖先/后代的需求目录。"""
    issues = []
    if not storage_root.exists():
        return issues

    # 预期需求目录 + 其祖先容器目录
    expected_dirs = set()
    expected_ancestors = set()
    for key in requirements.keys():
        d = (storage_root / key).resolve()
        expected_dirs.add(d)
        p = d.parent
        while p != storage_root.resolve() and p != p.parent:
            expected_ancestors.add(p)
            p = p.parent

    storage_resolved = storage_root.resolve()

    def walk(current):
        for child in current.iterdir():
            if not child.is_dir():
                continue
            rc = child.resolve()
            if rc in expected_dirs:
                continue  # 是需求目录本身，其内部是需求文件，不下钻
            if rc in expected_ancestors or child.name == ARCHIVE_DIR:
                walk(child)  # 是容器目录（分类/archive），继续下钻
                continue
            # 既非需求目录也非已知容器 → 孤儿候选（跳过空目录，减少噪声）
            try:
                if any(rc.iterdir()):
                    rel = rc.relative_to(storage_resolved)
                    issues.append(
                        f"[孤儿目录] {rel} 存在于 storage 但 meta 无记录"
                        f"（建议: 确认后手工删除或补录 meta）"
                    )
            except OSError:
                pass

    try:
        walk(storage_root)
    except OSError:
        pass
    return issues


def _apply_fix(data, fixable):
    """应用低风险修复，返回已修复动作描述列表。"""
    requirements = data["requirements"]
    # dir_name → req 直接引用
    fixed = []
    for kind, dir_name, detail in fixable:
        req = requirements.get(dir_name)
        if req is None:
            continue
        rid = req.get("id", "?")
        if kind == "depends_on":
            before = req.get("depends_on", [])
            req["depends_on"] = [d for d in before if d not in detail]
            fixed.append(f"{rid}: 移除悬空依赖 {detail}")
        elif kind == "child_ids":
            before = req.get("child_ids", [])
            req["child_ids"] = [c for c in before if c not in detail]
            fixed.append(f"{rid}: 移除悬空子需求 {detail}")
        elif kind == "parent_id":
            req["parent_id"] = None
            # 降级 role：child 失去 parent 后降为 standalone（与 delete 孤儿处理同规则）
            if req.get("role") == "child":
                req["role"] = "standalone"
            fixed.append(f"{rid}: parent_id '{detail}' 置空并降级 role → standalone")
    return fixed


def cmd_doctor(args):
    """执行 req doctor 命令。"""
    try:
        cl = ConfigLoader()
        storage_root = cl.read()
        lock_timeout = cl.get_lock_timeout()
        backup_enabled = cl.get_backup_enabled()
        valid_statuses = cl.get_requirement_statuses()
        valid_roles = cl.get_requirement_roles()
        requirement_tags = cl.get_requirement_tags()
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    ms = MetaStore(storage_root, backup_enabled=backup_enabled)
    data = ms.load()

    report, fixable = _collect_issues(
        data, storage_root, valid_statuses, valid_roles, requirement_tags
    )

    total = len(report)
    if total == 0:
        print("✓ 未发现一致性问题")
        return

    print(f"🔍 发现 {total} 个一致性问题：\n")
    for i, issue in enumerate(report, 1):
        print(f"  {i}. {issue}")

    if not args.fix:
        if fixable:
            print(f"\nℹ 其中 {len(fixable)} 项可用 `req doctor --fix` 自动修复（悬空引用）")
        print("\n（默认只读模式，未做任何修改）")
        sys.exit(1)

    # --fix：持锁修复可自动处置项
    if not fixable:
        print("\nℹ 无可自动修复的项（其余需手工处置，见上方建议）")
        sys.exit(1)

    meta_path = storage_root / "meta.json"
    try:
        with FileLock(str(meta_path), timeout=lock_timeout):
            data = ms.load()
            # 锁内基于最新数据重新计算可修复项
            _, fixable = _collect_issues(
                data, storage_root, valid_statuses, valid_roles, requirement_tags
            )
            if not fixable:
                print("\nℹ 重读后无可修复项（可能已被并发修复）")
                return
            fixed = _apply_fix(data, fixable)
            ms.save(data)
    except TimeoutError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"\n✓ 已修复 {len(fixed)} 项：")
    for f in fixed:
        print(f"  - {f}")
    remaining = total - len(fixed)
    if remaining > 0:
        print(f"\nℹ 仍有 {remaining} 项需手工处置（见上方建议）")
