# -*- coding: utf-8 -*-
"""unarchive 命令的集成测试：archive→unarchive 往返、状态恢复、目录移动、冲突。"""

import json
from argparse import Namespace
from pathlib import Path

import pytest

from requirement_mgr.commands.create import cmd_create
from requirement_mgr.commands.archive import cmd_archive
from requirement_mgr.commands.unarchive import cmd_unarchive, FALLBACK_RESTORE_STATUS


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


def make_archive_args(req_id, **kw):
    return Namespace(
        req_id=req_id, reason=kw.get("reason"),
        dry_run=kw.get("dry_run", False), force=kw.get("force", False),
        doc=kw.get("doc"),
    )


def make_unarchive_args(req_id, **kw):
    return Namespace(
        req_id=req_id, dry_run=kw.get("dry_run", False), force=kw.get("force", True),
    )


def load_meta(workspace: Path) -> dict:
    return json.loads(
        (workspace / ".requirements" / "meta.json").read_text(encoding="utf-8")
    )


def _create_and_get_id(workspace, **kw):
    cmd_create(make_create_args(**kw))
    meta = load_meta(workspace)
    # 取最新创建的需求
    for key, entry in meta["requirements"].items():
        if not key.startswith("archive/"):
            return entry["id"], key
    raise AssertionError("未找到创建的需求")


class TestUnarchiveRoundTrip:
    def test_archive_records_pre_status(self, workspace):
        """archive 应结构化记录 pre_archive_status。"""
        rid, _ = _create_and_get_id(workspace, status="实施中", dir_name="d1")
        cmd_archive(make_archive_args(rid, force=True))
        meta = load_meta(workspace)
        key = next(k for k in meta["requirements"] if k.startswith("archive/"))
        assert meta["requirements"][key]["pre_archive_status"] == "实施中"
        assert meta["requirements"][key]["status"] == "已归档"

    def test_unarchive_restores_pre_status(self, workspace):
        """unarchive 恢复为归档前状态并移回目录。"""
        rid, orig_key = _create_and_get_id(workspace, status="实施中", dir_name="d1")
        cmd_archive(make_archive_args(rid, force=True))
        # 归档后目录应在 archive/ 下
        assert (workspace / ".requirements" / "archive" / orig_key).exists()

        cmd_unarchive(make_unarchive_args(rid, force=True))
        meta = load_meta(workspace)
        # 键恢复原样（无 archive/ 前缀）
        assert orig_key in meta["requirements"]
        assert not any(k.startswith("archive/") for k in meta["requirements"])
        entry = meta["requirements"][orig_key]
        assert entry["status"] == "实施中"
        # 归档态字段已清理
        assert "pre_archive_status" not in entry
        assert "archived_at" not in entry
        # 目录移回原位
        assert (workspace / ".requirements" / orig_key).exists()
        assert not (workspace / ".requirements" / "archive" / orig_key).exists()

    def test_unarchive_fallback_status(self, workspace):
        """存量无 pre_archive_status 时回退默认状态。"""
        rid, orig_key = _create_and_get_id(workspace, status="实施中", dir_name="d1")
        cmd_archive(make_archive_args(rid, force=True))
        # 模拟存量：手工移除 pre_archive_status
        meta_path = workspace / ".requirements" / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        arch_key = next(k for k in meta["requirements"] if k.startswith("archive/"))
        del meta["requirements"][arch_key]["pre_archive_status"]
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        cmd_unarchive(make_unarchive_args(rid, force=True))
        meta = load_meta(workspace)
        assert meta["requirements"][orig_key]["status"] == FALLBACK_RESTORE_STATUS


class TestUnarchiveGuards:
    def test_unarchive_non_archived_rejected(self, workspace):
        """未归档需求恢复被拒。"""
        rid, _ = _create_and_get_id(workspace, dir_name="d1")
        with pytest.raises(SystemExit) as exc:
            cmd_unarchive(make_unarchive_args(rid, force=True))
        assert exc.value.code == 1

    def test_unarchive_nonexistent_rejected(self, workspace):
        with pytest.raises(SystemExit) as exc:
            cmd_unarchive(make_unarchive_args("REQ-NOPE", force=True))
        assert exc.value.code == 1

    def test_unarchive_target_conflict_rejected(self, workspace):
        """恢复目标目录已存在时拒绝。"""
        rid, orig_key = _create_and_get_id(workspace, status="实施中", dir_name="d1")
        cmd_archive(make_archive_args(rid, force=True))
        # 在原位置重建同名目录制造冲突
        (workspace / ".requirements" / orig_key).mkdir(parents=True, exist_ok=True)
        with pytest.raises(SystemExit) as exc:
            cmd_unarchive(make_unarchive_args(rid, force=True))
        assert exc.value.code == 1
        # meta 未变（仍归档）
        meta = load_meta(workspace)
        assert any(k.startswith("archive/") for k in meta["requirements"])

    def test_unarchive_dry_run_no_change(self, workspace):
        """dry-run 不改动 meta 与目录。"""
        rid, orig_key = _create_and_get_id(workspace, status="实施中", dir_name="d1")
        cmd_archive(make_archive_args(rid, force=True))
        cmd_unarchive(make_unarchive_args(rid, dry_run=True, force=True))
        meta = load_meta(workspace)
        # 仍处于归档态
        assert any(k.startswith("archive/") for k in meta["requirements"])
        assert (workspace / ".requirements" / "archive" / orig_key).exists()
