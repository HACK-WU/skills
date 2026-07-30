# -*- coding: utf-8 -*-
"""写命令的 --json 结构化输出与非交互约定（O-09）。

契约：
  - 成功：stdout 输出 {"ok": true, ...payload}
  - 失败：stdout 输出 {"ok": false, "error": "..."}（由 cli 层统一捕获 stderr 转换）
  - 退出码：0=成功，1=校验/业务错误，2=锁超时（各命令自身控制，--json 不改变）
  - --json 隐含非交互：需要 input() 确认的命令若未带 --force，直接报错退出
"""

import json
import sys


def is_json(args) -> bool:
    """当前命令是否为 --json 模式。"""
    return getattr(args, "json_output", False)


def emit_success(args, payload: dict, human_lines: list[str]) -> None:
    """成功输出：json 模式打印结构化结果，否则打印人类文案。"""
    if is_json(args):
        obj = {"ok": True}
        obj.update(payload)
        print(json.dumps(obj, ensure_ascii=False))
    else:
        for line in human_lines:
            print(line)


def guard_interactive(args, message: str) -> None:
    """json 模式下走到需要交互确认的分支时，直接报错退出（非交互约定）。

    调用点应置于任何 input()/人类预览打印之前。
    """
    if is_json(args):
        print(f"错误: {message}（--json 为非交互模式，请加 --force）", file=sys.stderr)
        sys.exit(1)


def extract_error(text: str) -> str:
    """从捕获的 stderr 文本中提炼错误信息。

    - 剥离 '错误: '/'严重: ' 前缀；
    - 过滤 warning/提示 行（⚠/警告/ℹ/提示 开头），避免非阻断提示污染 error 字段。
    """
    error_prefixes = ("错误: ", "错误:", "严重: ", "严重:")
    warn_prefixes = ("⚠", "警告", "ℹ", "提示")
    cleaned = []
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if ln.startswith(warn_prefixes):
            continue
        for pfx in error_prefixes:
            if ln.startswith(pfx):
                ln = ln[len(pfx):]
                break
        cleaned.append(ln)
    return "；".join(cleaned) if cleaned else "命令执行失败"
