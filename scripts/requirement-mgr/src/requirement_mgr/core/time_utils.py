# -*- coding: utf-8 -*-
"""时间工具，提供东八区（CST, UTC+8）时间戳。"""

from datetime import datetime, timezone, timedelta

# 东八区时区
CST = timezone(timedelta(hours=8))


def now_cst() -> datetime:
    """返回当前东八区时间。"""
    return datetime.now(CST)


def now_cst_str() -> str:
    """返回当前东八区时间字符串，格式 YYYY-MM-DD HH:MM:SS。"""
    return now_cst().strftime("%Y-%m-%d %H:%M:%S")


def today_cst_str() -> str:
    """返回当前东八区日期字符串，格式 YYYY-MM-DD（用于目录名）。"""
    return now_cst().strftime("%Y-%m-%d")
