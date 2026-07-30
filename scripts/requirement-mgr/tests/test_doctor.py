# -*- coding: utf-8 -*-
"""doctor 命令的集成测试：漂移检测与 --fix 修复。"""

import json
from argparse import Namespace
from pathlib import Path

import pytest

from requirement_mgr.commands.create import cmd_create
from requirement_mgr.commands.doctor import cmd_doctor, _collect_issues


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
    )


def make_doctor_args(**kw):
    return Namespace(fix=kw.get("fix", False))


def _meta_path(workspace):
    return workspace / ".requirements" / "meta.json"


def _load(workspace):
    return json.loads(_meta_path(workspace).read_text(encoding="utf-8"))


def _save(workspace, meta):
    _meta_path(workspace).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


class TestDoctorClean:
    def test_no_issues(self, workspace, capsys):
        cmd_create(make_create_args(dir_name="d1"))
        cmd_doctor(make_doctor_args())  # 干净时不 sys.exit
        out = capsys.readouterr().out
        assert "未发现一致性问题" in out


class TestDoctorDetect:
    def test_dangling_depends_on(self, workspace):
        cmd_create(make_create_args(dir_name="d1"))
        meta = _load(workspace)
        key = next(iter(meta["requirements"]))
        meta["requirements"][key]["depends_on"] = ["REQ-GHOST"]
        _save(workspace, meta)
        with pytest.raises(SystemExit) as exc:
            cmd_doctor(make_doctor_args())
        assert exc.value.code == 1

    def test_dangling_parent_id(self, workspace):
        cmd_create(make_create_args(dir_name="d1"))
        meta = _load(workspace)
        key = next(iter(meta["requirements"]))
        meta["requirements"][key]["parent_id"] = "REQ-GHOST"
        meta["requirements"][key]["role"] = "child"
        _save(workspace, meta)
        with pytest.raises(SystemExit) as exc:
            cmd_doctor(make_doctor_args())
        assert exc.value.code == 1

    def test_missing_dir_detected(self, workspace):
        cmd_create(make_create_args(dir_name="d1"))
        meta = _load(workspace)
        key = next(iter(meta["requirements"]))
        # 删除目录，制造 meta 指向不存在
        import shutil
        shutil.rmtree(workspace / ".requirements" / key)
        _save(workspace, meta)
        with pytest.raises(SystemExit):
            cmd_doctor(make_doctor_args())

    def test_orphan_dir_detected(self, workspace):
        cmd_create(make_create_args(dir_name="d1"))
        # 在 tool/ 下手工建一个 meta 未登记的目录
        orphan = workspace / ".requirements" / "tool" / "2026-07-30-orphan"
        orphan.mkdir(parents=True)
        (orphan / "requirement.md").write_text("孤儿", encoding="utf-8")
        with pytest.raises(SystemExit):
            cmd_doctor(make_doctor_args())

    def test_duplicate_id_detected(self, workspace):
        cmd_create(make_create_args(dir_name="d1"))
        meta = _load(workspace)
        key = next(iter(meta["requirements"]))
        rid = meta["requirements"][key]["id"]
        # 复制一条同 ID 记录到另一个键
        dup = dict(meta["requirements"][key])
        meta["requirements"]["tool/2026-07-30-dup"] = dup
        (workspace / ".requirements" / "tool" / "2026-07-30-dup").mkdir(parents=True)
        _save(workspace, meta)
        report, _ = _collect_issues(
            _load(workspace), workspace / ".requirements",
            ["草案", "已完成"], ["standalone", "parent", "child"], [],
        )
        assert any("重复ID" in r and rid in r for r in report)


class TestDoctorFix:
    def test_fix_removes_dangling_depends_on(self, workspace):
        cmd_create(make_create_args(dir_name="d1"))
        meta = _load(workspace)
        key = next(iter(meta["requirements"]))
        meta["requirements"][key]["depends_on"] = ["REQ-GHOST", "REQ-ALSO-GHOST"]
        _save(workspace, meta)
        cmd_doctor(make_doctor_args(fix=True))
        meta = _load(workspace)
        assert meta["requirements"][key]["depends_on"] == []

    def test_fix_clears_dangling_parent_and_demotes(self, workspace):
        cmd_create(make_create_args(dir_name="d1"))
        meta = _load(workspace)
        key = next(iter(meta["requirements"]))
        meta["requirements"][key]["parent_id"] = "REQ-GHOST"
        meta["requirements"][key]["role"] = "child"
        _save(workspace, meta)
        cmd_doctor(make_doctor_args(fix=True))
        meta = _load(workspace)
        assert meta["requirements"][key]["parent_id"] is None
        assert meta["requirements"][key]["role"] == "standalone"

    def test_fix_removes_dangling_child_ids(self, workspace):
        cmd_create(make_create_args(dir_name="d1"))
        meta = _load(workspace)
        key = next(iter(meta["requirements"]))
        meta["requirements"][key]["child_ids"] = ["REQ-GHOST"]
        _save(workspace, meta)
        cmd_doctor(make_doctor_args(fix=True))
        meta = _load(workspace)
        assert meta["requirements"][key]["child_ids"] == []

    def test_fix_only_report_items_exit_1(self, workspace):
        """仅有不可自动修复项时 --fix 退出 1。"""
        cmd_create(make_create_args(dir_name="d1"))
        meta = _load(workspace)
        key = next(iter(meta["requirements"]))
        meta["requirements"][key]["status"] = "不存在的状态"
        _save(workspace, meta)
        with pytest.raises(SystemExit) as exc:
            cmd_doctor(make_doctor_args(fix=True))
        assert exc.value.code == 1
