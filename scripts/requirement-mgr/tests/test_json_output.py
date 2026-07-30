# -*- coding: utf-8 -*-
"""O-09：写命令 --json 结构化输出、非交互约定、失败契约的回归测试。"""

import json
from argparse import Namespace
from pathlib import Path

import pytest

from requirement_mgr.commands.create import cmd_create
from requirement_mgr.commands.update import cmd_update
from requirement_mgr.commands.delete import cmd_delete
from requirement_mgr.commands.archive import cmd_archive
from requirement_mgr.commands.unarchive import cmd_unarchive
from requirement_mgr.commands.restore import cmd_restore
from requirement_mgr.cli import _dispatch
from requirement_mgr.core.output import (
    is_json,
    emit_success,
    guard_interactive,
    extract_error,
)


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


def make_update_args(req_id, **kw):
    return Namespace(
        req_id=req_id,
        status=kw.get("status"),
        feature=kw.get("feature"),
        role=kw.get("role"),
        parent_id=kw.get("parent_id"),
        tag=kw.get("tag"),
        depends_on_ops=kw.get("depends_on_ops"),
        commit=kw.get("commit"),
        branch=kw.get("branch"),
        docs_ops=kw.get("docs_ops"),
        changelog=kw.get("changelog"),
        json_output=kw.get("json_output", False),
    )


def make_delete_args(req_id, **kw):
    return Namespace(
        req_id=req_id,
        force=kw.get("force", False),
        dry_run=kw.get("dry_run", False),
        json_output=kw.get("json_output", False),
    )


def make_archive_args(req_id, **kw):
    return Namespace(
        req_id=req_id,
        reason=kw.get("reason"),
        dry_run=kw.get("dry_run", False),
        force=kw.get("force", False),
        doc=kw.get("doc"),
        json_output=kw.get("json_output", False),
    )


def make_unarchive_args(req_id, **kw):
    return Namespace(
        req_id=req_id,
        dry_run=kw.get("dry_run", False),
        force=kw.get("force", False),
        json_output=kw.get("json_output", False),
    )


def make_restore_args(**kw):
    return Namespace(
        dry_run=kw.get("dry_run", False),
        force=kw.get("force", False),
        json_output=kw.get("json_output", False),
    )


def load_meta(workspace: Path) -> dict:
    return json.loads(
        (workspace / ".requirements" / "meta.json").read_text(encoding="utf-8")
    )


def _last_json(capsys) -> dict:
    """从 capsys 捕获的 stdout 中解析最后一行 JSON。"""
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "预期有 stdout 输出"
    return json.loads(out[-1])


def _single_json(capsys) -> dict:
    """断言 json 模式 stdout 恰好一行 JSON（洁净度契约），并返回解析结果。"""
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1, f"stdout 应恰好一行 JSON，实际 {len(out)} 行: {out}"
    return json.loads(out[0])


def _key_of(workspace: Path, req_id: str) -> str:
    """按 id 反查 meta 中的存储键（dir_name）。"""
    for key, entry in load_meta(workspace)["requirements"].items():
        if entry["id"] == req_id:
            return key
    raise AssertionError(f"未找到需求 {req_id}")


class TestOutputHelpers:
    """core/output.py 辅助函数的纯单元测试。"""

    def test_is_json_default_false(self):
        assert is_json(Namespace()) is False
        assert is_json(Namespace(json_output=False)) is False
        assert is_json(Namespace(json_output=True)) is True

    def test_emit_success_json(self, capsys):
        emit_success(Namespace(json_output=True), {"id": "R1"}, ["人类行"])
        out = capsys.readouterr().out.strip()
        assert json.loads(out) == {"ok": True, "id": "R1"}

    def test_emit_success_human(self, capsys):
        emit_success(Namespace(json_output=False), {"id": "R1"}, ["人类行1", "人类行2"])
        out = capsys.readouterr().out
        assert "人类行1" in out and "人类行2" in out
        assert "ok" not in out

    def test_guard_interactive_json_exits(self, capsys):
        with pytest.raises(SystemExit) as exc:
            guard_interactive(Namespace(json_output=True), "需确认")
        assert exc.value.code == 1
        assert "非交互" in capsys.readouterr().err

    def test_guard_interactive_human_noop(self):
        # 非 json 模式不应退出
        guard_interactive(Namespace(json_output=False), "需确认")

    def test_extract_error_strips_prefix(self):
        assert extract_error("错误: 依赖需求 X 不存在") == "依赖需求 X 不存在"
        assert extract_error("") == "命令执行失败"
        # 多行合并
        assert extract_error("错误: 行1\n严重: 行2") == "行1；行2"

    def test_extract_error_filters_warnings(self):
        # [M1] 回归：warning/提示 行不应污染 error 字段，仅保留真正的错误
        text = (
            "⚠ 警告: 需求 A 被 1 个需求依赖（B），归档后依赖关系仍然保留\n"
            "错误: 归档目标目录已存在: /x/archive/tool/a\n"
        )
        assert extract_error(text) == "归档目标目录已存在: /x/archive/tool/a"
        # 纯提示/警告行被全部过滤后回退默认文案
        assert extract_error("ℹ 提示: 仅供参考\n⚠ 警告: 注意") == "命令执行失败"


class TestCreateJson:
    def test_create_json_success(self, workspace, capsys):
        cmd_create(make_create_args(json_output=True))
        obj = _last_json(capsys)
        assert obj["ok"] is True
        assert obj["id"]
        assert obj["meta_key"].startswith("tool/")
        assert obj["warnings"] == []

    def test_create_json_archived_dependency_warning(self, workspace, capsys):
        # 先建一个需求并手工置为已归档
        cmd_create(make_create_args(dir_name="dep-parent"))
        capsys.readouterr()
        meta_path = workspace / ".requirements" / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        key, entry = next(iter(meta["requirements"].items()))
        entry["status"] = "已归档"
        dep_id = entry["id"]
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        cmd_create(make_create_args(
            dir_name="dep-child", depends_on=dep_id, json_output=True,
        ))
        obj = _last_json(capsys)
        assert obj["ok"] is True
        assert any("已归档" in w for w in obj["warnings"])


class TestUpdateJson:
    def test_update_json_success(self, workspace, capsys):
        cmd_create(make_create_args())
        rid = next(iter(load_meta(workspace)["requirements"].values()))["id"]
        capsys.readouterr()
        cmd_update(make_update_args(rid, status="实施中", json_output=True))
        obj = _last_json(capsys)
        assert obj["ok"] is True
        assert obj["id"] == rid
        assert obj["version"] >= 2


class TestDeleteJson:
    def test_delete_json_dry_run(self, workspace, capsys):
        cmd_create(make_create_args())
        rid = next(iter(load_meta(workspace)["requirements"].values()))["id"]
        capsys.readouterr()
        cmd_delete(make_delete_args(rid, dry_run=True, json_output=True))
        obj = _last_json(capsys)
        assert obj["ok"] is True
        assert obj["dry_run"] is True
        assert obj["id"] == rid
        assert obj["orphaned"] == 0 and obj["cleaned"] == 0
        assert obj["orphaned_ids"] == [] and obj["cleaned_ids"] == []
        # dry-run 未真正删除
        assert len(load_meta(workspace)["requirements"]) == 1

    def test_delete_json_without_force_is_noninteractive(self, workspace, capsys):
        cmd_create(make_create_args())
        rid = next(iter(load_meta(workspace)["requirements"].values()))["id"]
        capsys.readouterr()
        # --json 隐含非交互：未带 --force 直接退出 1，不挂起 input()
        with pytest.raises(SystemExit) as exc:
            cmd_delete(make_delete_args(rid, force=False, json_output=True))
        assert exc.value.code == 1
        assert "非交互" in capsys.readouterr().err
        # 未删除
        assert len(load_meta(workspace)["requirements"]) == 1

    def test_delete_json_success(self, workspace, capsys):
        cmd_create(make_create_args())
        rid = next(iter(load_meta(workspace)["requirements"].values()))["id"]
        capsys.readouterr()
        cmd_delete(make_delete_args(rid, force=True, json_output=True))
        obj = _last_json(capsys)
        assert obj["ok"] is True
        assert obj["id"] == rid
        assert len(load_meta(workspace)["requirements"]) == 0


class TestDispatchFailureContract:
    """_dispatch 在 --json 模式下将 stderr 错误转为 {"ok": false} 且保留退出码。"""

    def test_dispatch_failure_emits_json_error(self, workspace, capsys):
        args = make_create_args(depends_on="REQ-NOT-EXIST", json_output=True)
        with pytest.raises(SystemExit) as exc:
            _dispatch(cmd_create, args)
        assert exc.value.code == 1
        obj = _last_json(capsys)
        assert obj["ok"] is False
        assert "不存在" in obj["error"]

    def test_dispatch_success_passthrough(self, workspace, capsys):
        args = make_create_args(json_output=True)
        _dispatch(cmd_create, args)
        obj = _last_json(capsys)
        assert obj["ok"] is True

    def test_dispatch_non_json_no_wrapping(self, workspace, capsys):
        # 非 json 模式：失败直接抛 SystemExit，stdout 无 JSON 包装
        args = make_create_args(depends_on="REQ-NOT-EXIST", json_output=False)
        with pytest.raises(SystemExit) as exc:
            _dispatch(cmd_create, args)
        assert exc.value.code == 1
        assert "{" not in capsys.readouterr().out

    def test_dispatch_unexpected_exception_still_emits_json(self, capsys):
        # [B1] 非 SystemExit 的未预期异常，json 模式仍需输出失败契约并退出 1
        def boom(_args):
            raise RuntimeError("意外崩溃")

        with pytest.raises(SystemExit) as exc:
            _dispatch(boom, Namespace(json_output=True))
        assert exc.value.code == 1
        obj = _last_json(capsys)
        assert obj["ok"] is False
        assert "意外崩溃" in obj["error"]

    def test_dispatch_non_json_exception_propagates(self, capsys):
        # 非 json 模式：未预期异常原样传播（保留 traceback 供排查）
        def boom(_args):
            raise RuntimeError("意外崩溃")

        with pytest.raises(RuntimeError):
            _dispatch(boom, Namespace(json_output=False))


class TestArchiveJson:
    def test_archive_json_success_single_line(self, workspace, capsys):
        cmd_create(make_create_args(dir_name="arch-me"))
        rid = next(iter(load_meta(workspace)["requirements"].values()))["id"]
        capsys.readouterr()
        cmd_archive(make_archive_args(rid, json_output=True))
        # 成功路径：stdout 恰好一行 JSON
        obj = _single_json(capsys)
        assert obj["ok"] is True
        assert obj["id"] == rid
        assert obj["status"] == "已归档"
        assert obj["meta_key"].startswith("archive/")
        assert load_meta(workspace)["requirements"][obj["meta_key"]]["status"] == "已归档"

    def test_archive_json_dry_run(self, workspace, capsys):
        cmd_create(make_create_args(dir_name="arch-dry"))
        rid = next(iter(load_meta(workspace)["requirements"].values()))["id"]
        capsys.readouterr()
        cmd_archive(make_archive_args(rid, dry_run=True, json_output=True))
        obj = _last_json(capsys)
        assert obj["ok"] is True and obj["dry_run"] is True
        assert obj["to_status"] == "已归档"
        # dry-run 未真正归档
        assert load_meta(workspace)["requirements"][_key_of(workspace, rid)]["status"] != "已归档"

    def test_archive_parent_without_force_is_noninteractive(self, workspace, capsys):
        cmd_create(make_create_args(dir_name="arch-parent"))
        pid = next(iter(load_meta(workspace)["requirements"].values()))["id"]
        cmd_create(make_create_args(dir_name="arch-child", parent_id=pid, role="child"))
        capsys.readouterr()
        # 有活跃子需求且未带 --force：--json 隐含非交互，直接退出 1
        with pytest.raises(SystemExit) as exc:
            cmd_archive(make_archive_args(pid, force=False, json_output=True))
        assert exc.value.code == 1
        assert "非交互" in capsys.readouterr().err

    def test_dispatch_archive_warning_not_leaked_into_error(self, workspace, capsys):
        # [M1] 集成回归：归档前的 rev_deps 警告不得污染后续失败的 error 字段
        cmd_create(make_create_args(dir_name="leak-dep"))
        aid = next(iter(load_meta(workspace)["requirements"].values()))["id"]
        cmd_create(make_create_args(dir_name="leak-src", depends_on=aid))
        capsys.readouterr()
        # 预先创建归档目标目录，使归档在警告打印后、移动前失败
        dst = workspace / ".requirements" / "archive" / _key_of(workspace, aid)
        dst.mkdir(parents=True)
        with pytest.raises(SystemExit) as exc:
            _dispatch(cmd_archive, make_archive_args(aid, json_output=True))
        assert exc.value.code == 1
        obj = _last_json(capsys)
        assert obj["ok"] is False
        assert "已存在" in obj["error"]
        # 警告内容（“依赖”）不应泄漏到 error
        assert "依赖" not in obj["error"]


class TestUnarchiveJson:
    def test_unarchive_json_success_single_line(self, workspace, capsys):
        cmd_create(make_create_args(dir_name="un-me"))
        rid = next(iter(load_meta(workspace)["requirements"].values()))["id"]
        cmd_archive(make_archive_args(rid, json_output=True))
        capsys.readouterr()
        cmd_unarchive(make_unarchive_args(rid, json_output=True))
        obj = _single_json(capsys)
        assert obj["ok"] is True
        assert obj["id"] == rid
        # 有 pre_archive_status 记录，恢复为归档前的默认状态，非 fallback
        assert obj["is_fallback"] is False
        assert not obj["meta_key"].startswith("archive/")

    def test_unarchive_json_dry_run(self, workspace, capsys):
        cmd_create(make_create_args(dir_name="un-dry"))
        rid = next(iter(load_meta(workspace)["requirements"].values()))["id"]
        cmd_archive(make_archive_args(rid, json_output=True))
        capsys.readouterr()
        cmd_unarchive(make_unarchive_args(rid, dry_run=True, json_output=True))
        obj = _last_json(capsys)
        assert obj["ok"] is True and obj["dry_run"] is True
        # dry-run 仍处于归档键
        assert _key_of(workspace, rid).startswith("archive/")


class TestRestoreJson:
    def test_restore_json_success_single_line(self, workspace, capsys):
        # 创建两次使 meta.json.bak 生成（第二次 save 前备份第一次的 meta）
        cmd_create(make_create_args(dir_name="r1"))
        cmd_create(make_create_args(dir_name="r2"))
        capsys.readouterr()
        cmd_restore(make_restore_args(force=True, json_output=True))
        obj = _single_json(capsys)
        assert obj["ok"] is True
        assert isinstance(obj["restored_count"], int)

    def test_restore_json_dry_run(self, workspace, capsys):
        cmd_create(make_create_args(dir_name="r1"))
        cmd_create(make_create_args(dir_name="r2"))
        capsys.readouterr()
        cmd_restore(make_restore_args(dry_run=True, json_output=True))
        obj = _last_json(capsys)
        assert obj["ok"] is True and obj["dry_run"] is True
        assert isinstance(obj["backup_count"], int)

    def test_restore_without_force_is_noninteractive(self, workspace, capsys):
        cmd_create(make_create_args(dir_name="r1"))
        cmd_create(make_create_args(dir_name="r2"))
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            cmd_restore(make_restore_args(force=False, json_output=True))
        assert exc.value.code == 1
        assert "非交互" in capsys.readouterr().err
