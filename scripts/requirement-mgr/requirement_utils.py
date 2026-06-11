# -*- coding: utf-8 -*-
"""需求操作共享工具函数。"""

from collections import deque


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
