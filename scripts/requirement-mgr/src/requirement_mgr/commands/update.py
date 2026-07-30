# -*- coding: utf-8 -*-
"""req update: 修改需求元数据，支持字段增删改、循环依赖检测、role 变更、版号自增。

校验策略：所有校验收敛在 _validate_update() 中，锁外调用一次快速失败，
加锁重读后再调用一次（TOCTOU 复验），通过后才应用变更。
"""

import sys

from requirement_mgr.core.config_loader import ConfigLoader
from requirement_mgr.core.meta_store import MetaStore
from requirement_mgr.core.file_lock import FileLock
from requirement_mgr.core.requirement_utils import (
    ARCHIVED_STATUS,
    find_req,
    has_circular_dep,
    validate_parent_child_op,
)
from requirement_mgr.core.time_utils import now_cst_str
from requirement_mgr.core.output import emit_success


def _simulate_tag_ops(current_tags, tag_ops, requirement_tags):
    """按顺序模拟应用 tag 操作，返回 (最终标签列表, 错误列表)。

    校验组合操作的最终结果（而非逐项独立判断），
    避免 "--tag remove a --tag remove b" 之类组合绕过约束。
    """
    errors = []
    sim = list(current_tags)
    for op, value in tag_ops:
        if op == "add":
            if requirement_tags and value not in requirement_tags:
                errors.append(
                    f"标签 '{value}' 不在 requirement_tags 配置中（允许: {', '.join(requirement_tags)}）"
                )
                continue
            if value not in sim:
                sim.append(value)
        elif op == "remove":
            if value in sim:
                sim.remove(value)
        elif op == "set":
            new_tags = [t.strip() for t in value.split(",") if t.strip()]
            if not new_tags:
                errors.append("--tag set 不能设置为空")
                continue
            if requirement_tags:
                invalid = [t for t in new_tags if t not in requirement_tags]
                if invalid:
                    errors.append(
                        f"标签 {invalid} 不在 requirement_tags 配置中（允许: {', '.join(requirement_tags)}）"
                    )
                    continue
            sim = new_tags
        else:
            errors.append(f"未知的 tag 操作 '{op}'，支持 add/remove/set")
    return sim, errors


def _simulate_deps_ops(current_deps, deps_ops):
    """按顺序模拟应用 depends_on 操作，返回 (最终依赖列表, 错误列表)。"""
    errors = []
    sim = list(current_deps)
    for op, ids_str in deps_ops:
        ids = [i.strip() for i in ids_str.split(",") if i.strip()]
        if op == "add":
            for rid in ids:
                if rid not in sim:
                    sim.append(rid)
        elif op == "remove":
            sim = [d for d in sim if d not in ids]
        elif op == "set":
            sim = ids
        else:
            errors.append(f"未知的 depends-on 操作 '{op}'，支持 add/remove/set")
    return sim, errors


def _validate_update(requirements, req_id, args, new_role, new_parent_id,
                     valid_statuses, valid_roles, feature_categories, requirement_tags):
    """校验本次 update 的全部变更，返回错误列表。

    锁外与锁内各调用一次：锁内基于重读后的最新数据复验，防止 TOCTOU。
    """
    errors = []
    _, req = find_req(requirements, req_id)
    if req is None:
        return [f"未找到需求 {req_id}"]

    # 已归档需求只读
    if req.get("status") == ARCHIVED_STATUS:
        return [f"需求 {req_id} 已归档，不允许修改"]

    # feature 不能更新为空白
    if args.feature is not None and not args.feature.strip():
        errors.append("--feature 不能为空")

    # branch：空字符串表示显式清除，纯空白（如 "  "）拒绝
    if args.branch is not None and args.branch != "" and not args.branch.strip():
        errors.append("--branch 不能为纯空白（清除请用 --branch \"\"）")

    # status
    if args.status:
        if args.status == ARCHIVED_STATUS:
            errors.append(f"不能通过 update 设置状态为 '{ARCHIVED_STATUS}'，请使用 req archive")
        elif args.status not in valid_statuses:
            errors.append(f"无效状态 '{args.status}'，有效值: {', '.join(valid_statuses)}")

    # role / parent_id
    if new_role:
        if new_role not in valid_roles:
            errors.append(f"无效角色 '{new_role}'，有效值: {', '.join(valid_roles)}")
        else:
            errors.extend(validate_parent_child_op(requirements, req_id, new_role, new_parent_id))
    if new_parent_id:
        _, parent_req = find_req(requirements, new_parent_id)
        if parent_req is not None and parent_req.get("status") == ARCHIVED_STATUS:
            errors.append(f"父需求 {new_parent_id} 已归档，不能挂载子需求")

    # tags：模拟顺序应用后校验最终状态
    if args.tag:
        current_tags = list(req.get("tags", []))
        final_tags, tag_errors = _simulate_tag_ops(current_tags, args.tag, requirement_tags)
        errors.extend(tag_errors)
        if not tag_errors:
            if not final_tags:
                errors.append("操作后标签为空，至少需要保留一个标签")
            if feature_categories:
                current_cat = next((t for t in current_tags if t in feature_categories), None)
                final_cats = [t for t in final_tags if t in feature_categories]
                if len(final_cats) > 1:
                    errors.append(f"功能分类标签只能有一个，操作后有: {', '.join(final_cats)}")
                elif current_cat and not final_cats:
                    errors.append(
                        f"不能删除功能分类标签 '{current_cat}'，目录位置依赖此标签"
                        f"（如需更改分类，请删除并重新创建需求）"
                    )
                elif current_cat and final_cats and final_cats[0] != current_cat:
                    errors.append(
                        f"不能更改功能分类标签（'{current_cat}' → '{final_cats[0]}'），目录位置依赖此标签"
                        f"（如需更改分类，请删除并重新创建需求）"
                    )

    # docs 格式校验
    if args.docs_ops:
        for op, value in args.docs_ops:
            if op == "add":
                parts = value.split(",")
                if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
                    errors.append("--docs add 格式: PATH,TYPE（两者均不可为空）")
            elif op == "remove":
                if not value.strip():
                    errors.append("--docs remove 需要指定路径")
            elif op == "set":
                for spec in [s.strip() for s in value.split(";") if s.strip()]:
                    parts = spec.split(",")
                    if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
                        errors.append(f"--docs set 格式错误: {spec}（应为 PATH,TYPE，两者不可为空）")
            else:
                errors.append(f"未知的 docs 操作 '{op}'，支持 add/remove/set")

    # depends_on：模拟最终依赖集后逐项校验（add/set 同等约束）
    if args.depends_on_ops:
        final_deps, dep_errors = _simulate_deps_ops(req.get("depends_on", []), args.depends_on_ops)
        errors.extend(dep_errors)
        if not dep_errors:
            for rid in final_deps:
                if rid == req_id:
                    errors.append("不能依赖自身")
                    continue
                _, target = find_req(requirements, rid)
                if target is None:
                    errors.append(f"依赖需求 {rid} 不存在")
                elif has_circular_dep(requirements, req_id, rid):
                    errors.append(f"添加 {rid} 会形成循环依赖")

    return errors


def cmd_update(args):
    """执行 req update 命令。"""
    req_id = args.req_id.strip()

    # 加载配置
    try:
        cl = ConfigLoader()
        storage_root = cl.read()
        feature_categories = cl.get_feature_categories()
        requirement_tags = cl.get_requirement_tags()
        valid_statuses = cl.get_requirement_statuses()
        valid_roles = cl.get_requirement_roles()
        lock_timeout = cl.get_lock_timeout()
        backup_enabled = cl.get_backup_enabled()
    except (FileNotFoundError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 如果只指定了 --parent-id 但没指定 --role，推断为 child
    new_role = args.role
    new_parent_id = args.parent_id.strip() if args.parent_id else None
    if new_parent_id and not new_role:
        new_role = "child"

    ms = MetaStore(storage_root, backup_enabled=backup_enabled)

    # 锁外校验（快速失败）
    data = ms.load()
    errors = _validate_update(
        data["requirements"], req_id, args, new_role, new_parent_id,
        valid_statuses, valid_roles, feature_categories, requirement_tags,
    )
    if errors:
        for err in errors:
            print(f"错误: {err}", file=sys.stderr)
        sys.exit(1)

    changes = 0

    # ---- 加锁 + 复验 + 应用变更 ----
    meta_path = storage_root / "meta.json"
    try:
        with FileLock(str(meta_path), timeout=lock_timeout):
            data = ms.load()
            requirements = data["requirements"]

            # TOCTOU 复验：基于重读后的最新数据重新校验
            errors = _validate_update(
                requirements, req_id, args, new_role, new_parent_id,
                valid_statuses, valid_roles, feature_categories, requirement_tags,
            )
            if errors:
                for err in errors:
                    print(f"错误: {err}（可能由并发变更引起）", file=sys.stderr)
                sys.exit(1)

            dir_name, req = find_req(requirements, req_id)

            # status
            if args.status:
                req["status"] = args.status
                changes += 1

            # feature
            if args.feature:
                req["feature"] = args.feature.strip()
                changes += 1

            # role 变更（含双向关系维护）
            if new_role:
                old_role = req.get("role", "standalone")
                if new_role != old_role or new_parent_id:
                    # 从旧 parent 的 child_ids 中移除自身
                    old_parent_id = req.get("parent_id")
                    if old_parent_id:
                        _, old_parent = find_req(requirements, old_parent_id)
                        if old_parent:
                            child_ids = old_parent.get("child_ids", [])
                            if req_id in child_ids:
                                child_ids.remove(req_id)
                            # 如果旧 parent 没有其他子需求了，降级为 standalone
                            if not child_ids and old_parent.get("role") == "parent":
                                old_parent["role"] = "standalone"

                    # 更新自身 role 和 parent_id
                    req["role"] = new_role
                    req["parent_id"] = new_parent_id if new_parent_id else None

                    # 加入新 parent 的 child_ids + 自动升级新 parent role
                    if new_parent_id:
                        _, new_parent = find_req(requirements, new_parent_id)
                        if new_parent:
                            if new_parent.get("role") == "standalone":
                                new_parent["role"] = "parent"
                            new_parent.setdefault("child_ids", [])
                            if req_id not in new_parent["child_ids"]:
                                new_parent["child_ids"].append(req_id)

                    # standalone / parent 均不应有 parent_id
                    if new_role in ("standalone", "parent"):
                        req["parent_id"] = None

                    changes += 1

            # tags：应用模拟结果（与校验同一份逻辑）
            if args.tag:
                final_tags, _ = _simulate_tag_ops(
                    list(req.get("tags", [])), args.tag, requirement_tags
                )
                if final_tags != req.get("tags", []):
                    req["tags"] = final_tags
                    changes += 1

            # depends_on：应用模拟结果
            if args.depends_on_ops:
                final_deps, _ = _simulate_deps_ops(req.get("depends_on", []), args.depends_on_ops)
                if final_deps != req.get("depends_on", []):
                    req["depends_on"] = final_deps
                    changes += 1

            # commit
            if args.commit:
                req.setdefault("commits", [])
                if args.commit not in req["commits"]:
                    req["commits"].append(args.commit)
                    changes += 1

            # branch：空字符串清除（置 None），非空值写入
            if args.branch is not None:
                new_branch = args.branch.strip() or None
                if new_branch != req.get("branch"):
                    req["branch"] = new_branch
                    changes += 1

            # docs add/remove/set
            if args.docs_ops:
                req.setdefault("docs", [])
                for op, value in args.docs_ops:
                    if op == "add":
                        parts = value.split(",")
                        doc_path = parts[0].strip()
                        doc_type = parts[1].strip()
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
            req["updated"] = now_cst_str()

            if args.changelog:
                req.setdefault("changelog", [])
                req["changelog"].append(
                    f"{req['updated']} v{req['version']}: {args.changelog.strip()}"
                )

            ms.save(data)

    except TimeoutError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)

    emit_success(args, {
        "id": req_id,
        "version": req["version"],
        "changes": changes,
    }, [
        "✓ 需求已更新",
        f"  ID:      {req_id}",
        f"  版本:    v{req['version']}",
        f"  变更数:  {changes}",
    ])
