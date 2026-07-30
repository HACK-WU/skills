# -*- coding: utf-8 -*-
"""需求操作共享工具函数。"""

from collections import deque

# 归档状态（系统保留状态：仅 archive 命令可设置，update 不得设置或修改已归档需求）
ARCHIVED_STATUS = "已归档"


def find_req(requirements: dict, req_id: str) -> tuple[str | None, dict | None]:
    """通过 ID 查找需求，返回 (dir_name, req)。"""
    for dir_name, req in requirements.items():
        if req.get("id") == req_id:
            return dir_name, req
    return None, None


def has_circular_dep(requirements: dict, start_id: str, target_id: str) -> bool:
    """检测添加 target_id 到 start_id 的 depends_on 后是否形成环。

    BFS：从 target_id 出发，看能否回到 start_id。
    """
    if start_id == target_id:
        return True
    visited = set()
    queue = deque([target_id])
    while queue:
        current = queue.popleft()
        if current == start_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        _, req = find_req(requirements, current)
        if req:
            for dep in req.get("depends_on", []):
                if dep not in visited:
                    queue.append(dep)
    return False


def find_rev_deps(requirements: dict, target_id: str) -> list[dict]:
    """反向依赖：找到所有 depends_on 中包含 target_id 的需求。"""
    result = []
    for req in requirements.values():
        if target_id in req.get("depends_on", []):
            result.append({"id": req["id"], "feature": req.get("feature", "")})
    return result


def find_children(requirements: dict, parent_id: str) -> list[dict]:
    """查找某父需求的所有子需求。"""
    result = []
    for req in requirements.values():
        if req.get("parent_id") == parent_id:
            result.append(req)
    return result


def validate_parent_child_op(
    requirements: dict,
    req_id: str,
    new_role: str,
    new_parent_id: str | None,
) -> list[str]:
    """校验 role 变更的合法性，返回错误列表。"""
    errors = []
    _, req = find_req(requirements, req_id)
    if req is None:
        return [f"需求 {req_id} 不存在"]

    old_role = req.get("role", "standalone")

    # child 必须有 parent_id
    if new_role == "child" and not new_parent_id:
        errors.append("role=child 时必须指定 --parent-id")

    # standalone 不能同时指定 parent_id
    if new_role == "standalone" and new_parent_id:
        errors.append("role=standalone 时不能指定 --parent-id")

    # child 不能再挂子需求
    if new_role == "child" and req.get("child_ids"):
        errors.append("已有子需求的需求不能变为 child 角色")

    # parent→standalone 时 child_ids 必须为空
    if old_role == "parent" and new_role == "standalone" and req.get("child_ids"):
        errors.append("仍有子需求，不能变为 standalone。请先处理子需求")

    # parent→child 时 child_ids 必须为空
    if old_role == "parent" and new_role == "child" and req.get("child_ids"):
        errors.append("仍有子需求，不能变为 child。请先处理子需求")

    # parent_id 目标必须存在且角色允许
    if new_parent_id:
        _, parent_req = find_req(requirements, new_parent_id)
        if parent_req is None:
            errors.append(f"父需求 {new_parent_id} 不存在")
        elif parent_req.get("role") not in ("parent", "standalone"):
            errors.append(
                f"目标需求 {new_parent_id} 的角色为 {parent_req.get('role')}，不能作为父需求"
            )
        elif new_parent_id == req_id:
            errors.append("不能将自己设为父需求")

    return errors
