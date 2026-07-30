# -*- coding: utf-8 -*-
"""delete 命令的集成测试：级联清理、父子关系降级。"""

import json
from argparse import Namespace
from pathlib import Path

import pytest

from requirement_mgr.commands.create import cmd_create
from requirement_mgr.commands.delete import cmd_delete


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


def make_delete_args(req_id, **kw):
    return Namespace(
        req_id=req_id,
        force=kw.get("force", True),
        dry_run=kw.get("dry_run", False),
    )


def load_meta(workspace: Path) -> dict:
    return json.loads(
        (workspace / ".requirements" / "meta.json").read_text(encoding="utf-8")
    )


def create_one(workspace, **kw) -> str:
    before = set(
        r["id"] for r in load_meta(workspace)["requirements"].values()
    ) if (workspace / ".requirements" / "meta.json").exists() else set()
    cmd_create(make_create_args(**kw))
    new_ids = [
        r["id"] for r in load_meta(workspace)["requirements"].values()
        if r["id"] not in before
    ]
    assert len(new_ids) == 1
    return new_ids[0]


class TestDelete:
    def test_delete_removes_entry_and_dir(self, workspace):
        rid = create_one(workspace, dir_name="d1")
        assert (workspace / ".requirements" / "tool" / "d1").is_dir()

        cmd_delete(make_delete_args(rid))

        meta = load_meta(workspace)
        assert all(r["id"] != rid for r in meta["requirements"].values())
        assert not (workspace / ".requirements" / "tool" / "d1").exists()

    def test_delete_cleans_depends_on_refs(self, workspace):
        rid_a = create_one(workspace, feature="A", dir_name="da")
        rid_b = create_one(workspace, feature="B", dir_name="db",
                           depends_on=rid_a)

        cmd_delete(make_delete_args(rid_a))

        meta = load_meta(workspace)
        req_b = next(
            r for r in meta["requirements"].values() if r["id"] == rid_b
        )
        assert rid_a not in req_b["depends_on"]

    def test_delete_parent_orphans_children(self, workspace):
        rid_p = create_one(workspace, feature="父", dir_name="dp")
        rid_c = create_one(workspace, feature="子", dir_name="dc",
                           role="child", parent_id=rid_p)

        cmd_delete(make_delete_args(rid_p))

        meta = load_meta(workspace)
        child = next(
            r for r in meta["requirements"].values() if r["id"] == rid_c
        )
        assert child["role"] == "standalone"
        assert child["parent_id"] is None

    def test_delete_child_downgrades_lonely_parent(self, workspace):
        rid_p = create_one(workspace, feature="父", dir_name="dp")
        rid_c = create_one(workspace, feature="子", dir_name="dc",
                           role="child", parent_id=rid_p)

        cmd_delete(make_delete_args(rid_c))

        meta = load_meta(workspace)
        parent = next(
            r for r in meta["requirements"].values() if r["id"] == rid_p
        )
        assert parent["role"] == "standalone"
        assert parent["child_ids"] == []

    def test_dry_run_no_changes(self, workspace):
        rid = create_one(workspace, dir_name="d1")
        cmd_delete(make_delete_args(rid, force=False, dry_run=True))
        meta = load_meta(workspace)
        assert any(r["id"] == rid for r in meta["requirements"].values())
        assert (workspace / ".requirements" / "tool" / "d1").is_dir()

    def test_dry_run_with_force_rejected(self, workspace):
        rid = create_one(workspace, dir_name="d1")
        with pytest.raises(SystemExit) as exc_info:
            cmd_delete(make_delete_args(rid, force=True, dry_run=True))
        assert exc_info.value.code == 1
