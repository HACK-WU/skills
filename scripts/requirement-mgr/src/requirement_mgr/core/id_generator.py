# -*- coding: utf-8 -*-
"""需求 ID 生成器，支持日期+序号格式。"""

import re
from datetime import date


def gen_next_id(requirements: dict, prefix: str = "REQ", digits: int = 3) -> str:
    """根据现有需求生成下一个 ID（日期+序号格式）。

    序号规则：同日期内自增，不回填空洞。
    兼容旧格式 REQ-NNN，但新创建的用新格式。

    Args:
        requirements: meta.json 中的 requirements 字典
        prefix: ID 前缀（从 config 读取）
        digits: 序号位数（从 config 读取）

    Returns:
        str: "{prefix}-{YYYYMMDD}-{NNN}"

    Raises:
        ValueError: 当日编号超过上限
    """
    today = date.today().strftime("%Y%m%d")
    pattern = re.compile(rf"^{re.escape(prefix)}-{today}-(\d{{{digits}}})$")
    max_seq = 0
    for req in requirements.values():
        rid = req.get("id", "")
        m = pattern.match(rid)
        if m:
            seq = int(m.group(1))
            if seq > max_seq:
                max_seq = seq
    next_seq = max_seq + 1
    max_val = 10 ** digits - 1
    if next_seq > max_val:
        raise ValueError(f"当日需求编号已达上限 ({prefix}-{today}-{max_val:0{digits}d})")
    return f"{prefix}-{today}-{next_seq:0{digits}d}"
