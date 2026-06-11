# -*- coding: utf-8 -*-
"""需求 ID 生成器，自增编号 REQ-NNN。"""

import re


def gen_next_id(requirements: dict) -> str:
    """根据现有需求生成下一个 ID。

    Args:
        requirements: meta.json 中的 requirements 字典

    Returns:
        str: "REQ-001" (首条) 或 "REQ-NNN"

    Raises:
        ValueError: 编号超过 999
    """
    max_num = 0
    for req in requirements.values():
        rid = req.get("id", "")
        m = re.match(r"^REQ-(\d{3})$", rid)
        if m:
            num = int(m.group(1))
            if num > max_num:
                max_num = num

    next_num = max_num + 1
    if next_num > 999:
        raise ValueError("需求编号已达上限 (REQ-999)")
    return f"REQ-{next_num:03d}"
