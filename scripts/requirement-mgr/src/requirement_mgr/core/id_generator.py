# -*- coding: utf-8 -*-
"""需求 ID 生成器，支持日期+序号格式。"""

import re

from requirement_mgr.core.time_utils import now_cst


def gen_next_id(requirements: dict, prefix: str = "REQ", digits: int = 3,
                id_counters: dict | None = None) -> str:
    """根据现有需求生成下一个 ID（日期+序号格式）。

    序号规则：同日期内自增，不回填空洞。
    兼容旧格式 REQ-NNN，但新创建的用新格式。

    防 ID 复用：传入 id_counters（meta 顶层只增不减计数器，键为
    "{prefix}-{YYYYMMDD}"）时，序号取 max(现存需求扫描值, 计数器值)+1
    并回写计数器，保证删除当日最新需求后再创建不会复用已删 ID。

    Args:
        requirements: meta.json 中的 requirements 字典
        prefix: ID 前缀（从 config 读取）
        digits: 序号位数（从 config 读取）
        id_counters: meta 顶层计数器字典（原地回写），None 时退化为纯扫描

    Returns:
        str: "{prefix}-{YYYYMMDD}-{NNN}"

    Raises:
        ValueError: 当日编号超过上限
    """
    # 与目录名/created 时间戳同源（东八区），避免本地时区差异导致 ID 日期与目录日期不一致
    today = now_cst().strftime("%Y%m%d")
    pattern = re.compile(rf"^{re.escape(prefix)}-{today}-(\d{{{digits}}})$")
    max_seq = 0
    for req in requirements.values():
        rid = req.get("id", "")
        m = pattern.match(rid)
        if m:
            seq = int(m.group(1))
            if seq > max_seq:
                max_seq = seq
    counter_key = f"{prefix}-{today}"
    if id_counters is not None:
        # 取两者较大值：计数器记录历史已发号，扫描值兼容无计数器的存量数据
        counter_val = id_counters.get(counter_key, 0)
        if not isinstance(counter_val, int) or counter_val < 0:
            counter_val = 0
        max_seq = max(max_seq, counter_val)
    next_seq = max_seq + 1
    max_val = 10 ** digits - 1
    if next_seq > max_val:
        raise ValueError(f"当日需求编号已达上限 ({prefix}-{today}-{max_val:0{digits}d})")
    if id_counters is not None:
        id_counters[counter_key] = next_seq
    return f"{prefix}-{today}-{next_seq:0{digits}d}"
