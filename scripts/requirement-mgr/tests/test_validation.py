# -*- coding: utf-8 -*-
"""O-10：输入校验同类展开的回归测试。

覆盖：
  - list --columns 无效列名 / 空值报错
  - list --from/--to 日期格式校验 + 区间合法性
  - create --depends-on 去重
"""

import json
from argparse import Namespace
from pathlib import Path

import pytest

from requirement_mgr.commands.create import cmd_create
from requirement_mgr.commands.list import cmd_list, ALL_COLUMNS


def make_create_args(**kw):
    return Namespace(
        feature=kw.get("feature", "测试功能"),
        tags=kw.get("tags", "tool,feat"),
        status=kw.get("status"),
        role=kw.get("role"),
        parent_id=kw.get("parent_id"),
        depends_on=kw.get("depends_on", ""),
        dir_name=kw.get("dir_name", ""),
        branch=kw.get("branch"),
        json_output=kw.get("json_output", False),
    )


def make_list_args(**kw):
    return Namespace(
        id=None,
        status=None,
        tag=None,
        role=None,
        parent_id=None,
        category=None,
        date_from=kw.get("date_from"),
        date_to=kw.get("date_to"),
        search=None,
        include_archived=False,
        json_output=kw.get("json_output", False),
        columns=kw.get("columns"),
        deps=False,
        deps_depth=1,
        rev_deps=False,
        no_color=True,
        limit=0,
    )


def load_meta(workspace: Path) -> dict:
    return json.loads(
        (workspace / ".requirements" / "meta.json").read_text(encoding="utf-8")
    )


class TestListColumnsValidation:
    def test_invalid_column_rejected(self, workspace, capsys):
        with pytest.raises(SystemExit) as exc:
            cmd_list(make_list_args(columns="id,nonexistent"))
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "无效列名" in err
        assert "nonexistent" in err

    def test_empty_columns_rejected(self, workspace, capsys):
        with pytest.raises(SystemExit) as exc:
            cmd_list(make_list_args(columns=" , "))
        assert exc.value.code == 1
        assert "不能为空" in capsys.readouterr().err

    def test_valid_columns_accepted(self, workspace, capsys):
        cmd_create(make_create_args())
        capsys.readouterr()
        # 全部有效列名不应报错
        cmd_list(make_list_args(columns=",".join(ALL_COLUMNS)))
        # 未抛 SystemExit 即通过


class TestListDateValidation:
    def test_bad_from_format_rejected(self, workspace, capsys):
        with pytest.raises(SystemExit) as exc:
            cmd_list(make_list_args(date_from="2026/07/30"))
        assert exc.value.code == 1
        assert "--from" in capsys.readouterr().err

    def test_bad_to_format_rejected(self, workspace, capsys):
        with pytest.raises(SystemExit) as exc:
            cmd_list(make_list_args(date_to="20260730"))
        assert exc.value.code == 1
        assert "--to" in capsys.readouterr().err

    def test_calendar_invalid_date_rejected(self, workspace, capsys):
        # 格式匹配正则但日历非法（e2e 扫测发现的缺口）
        with pytest.raises(SystemExit) as exc:
            cmd_list(make_list_args(date_from="2026-13-99"))
        assert exc.value.code == 1
        assert "日历" in capsys.readouterr().err

    def test_calendar_invalid_time_rejected(self, workspace, capsys):
        with pytest.raises(SystemExit) as exc:
            cmd_list(make_list_args(date_to="2026-07-30 25:61:00"))
        assert exc.value.code == 1
        assert "--to" in capsys.readouterr().err

    def test_from_after_to_rejected(self, workspace, capsys):
        with pytest.raises(SystemExit) as exc:
            cmd_list(make_list_args(date_from="2026-08-01", date_to="2026-07-01"))
        assert exc.value.code == 1
        assert "区间为空" in capsys.readouterr().err

    def test_same_day_from_to_ok(self, workspace, capsys):
        # --to 为纯日期时补当天末尾 23:59:59，同日区间应合法
        cmd_create(make_create_args())
        capsys.readouterr()
        cmd_list(make_list_args(date_from="2026-07-30", date_to="2026-07-30"))

    def test_full_datetime_format_accepted(self, workspace, capsys):
        cmd_create(make_create_args())
        capsys.readouterr()
        cmd_list(make_list_args(
            date_from="2026-07-01 00:00:00", date_to="2026-12-31 23:59:59",
        ))


class TestCreateDependsOnDedup:
    def test_depends_on_deduplicated(self, workspace, capsys):
        # 先建两个可依赖的需求
        cmd_create(make_create_args(dir_name="dep-a"))
        cmd_create(make_create_args(dir_name="dep-b"))
        meta = load_meta(workspace)
        ids = [r["id"] for r in meta["requirements"].values()]
        capsys.readouterr()
        # 传入重复依赖
        dup = f"{ids[0]},{ids[1]},{ids[0]}"
        cmd_create(make_create_args(dir_name="dep-child", depends_on=dup))
        meta = load_meta(workspace)
        child = next(
            r for r in meta["requirements"].values()
            if r["id"] not in ids
        )
        # 去重且保序
        assert child["depends_on"] == [ids[0], ids[1]]
