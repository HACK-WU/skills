# -*- coding: utf-8 -*-
"""update 命令的集成测试：TOCTOU 复验逻辑、组合操作模拟、归档守卫、依赖校验。"""

import json
from argparse import Namespace
from pathlib import Path

import pytest

from requirement_mgr.commands.create import cmd_create
from requirement_mgr.commands.update import cmd_update


def make_create_args(**kw):
    return Namespace(
        feature=kw.get("feature", "测试功能"),
        tags=kw.get("tags", "tool,feat"),
        status=kw.get("status"),
        role=kw.get("role"),
        parent_id=kw.get("parent_id"),
        depends_on=kw.get("depends_on", ""),
        dir_name=kw.get("dir_name", ""),
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
        docs_ops=kw.get("docs_ops"),
        changelog=kw.get("changelog"),
    )


def load_meta(workspace: Path) -> dict:
    return json.loads(
        (workspace / ".requirements" / "meta.json").read_text(encoding="utf-8")
    )


def get_req(workspace: Path, req_id: str) -> dict:
    for req in load_meta(workspace)["requirements"].values():
        if req["id"] == req_id:
            return req
    raise AssertionError(f"未找到 {req_id}")


def create_one(workspace, **kw) -> str:
    """创建需求并返回 ID。"""
    before = set(
        r["id"] for r in load_meta(workspace)["requirements"].values()
    ) if (workspace / ".requirements" / "meta.json").exists() else set()
    cmd_create(make_create_args(**kw))
    after = load_meta(workspace)["requirements"].values()
    new_ids = [r["id"] for r in after if r["id"] not in before]
    assert len(new_ids) == 1
    return new_ids[0]


class TestStatusUpdate:
    def test_status_update_ok(self, workspace):
        rid = create_one(workspace, dir_name="d1")
        cmd_update(make_update_args(rid, status="已确认"))
        req = get_req(workspace, rid)
        assert req["status"] == "已确认"
        assert req["version"] == 2

    def test_set_archived_status_rejected(self, workspace):
        rid = create_one(workspace, dir_name="d1")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(rid, status="已归档"))
        assert exc_info.value.code == 1

    def test_update_archived_req_rejected(self, workspace):
        rid = create_one(workspace, dir_name="d1")
        # 手工模拟归档状态
        meta_path = workspace / ".requirements" / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for req in meta["requirements"].values():
            req["status"] = "已归档"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(rid, status="已确认"))
        assert exc_info.value.code == 1


class TestTagOps:
    def test_remove_combo_cannot_empty_tags(self, workspace_no_categories):
        rid = create_one(workspace_no_categories, tags="feat,fix", dir_name="d1")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(
                rid, tag=[["remove", "feat"], ["remove", "fix"]]
            ))
        assert exc_info.value.code == 1
        # 标签未被修改
        assert get_req(workspace_no_categories, rid)["tags"] == ["feat", "fix"]

    def test_remove_category_tag_rejected(self, workspace):
        rid = create_one(workspace, tags="tool,feat", dir_name="d1")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(rid, tag=[["remove", "tool"]]))
        assert exc_info.value.code == 1

    def test_set_change_category_rejected(self, workspace):
        rid = create_one(workspace, tags="tool,feat", dir_name="d1")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(rid, tag=[["set", "web,feat"]]))
        assert exc_info.value.code == 1
        assert get_req(workspace, rid)["tags"] == ["tool", "feat"]

    def test_add_and_remove_combo_ok(self, workspace):
        rid = create_one(workspace, tags="tool,feat", dir_name="d1")
        cmd_update(make_update_args(
            rid, tag=[["add", "p1"], ["remove", "feat"]]
        ))
        assert get_req(workspace, rid)["tags"] == ["tool", "p1"]

    def test_unknown_tag_op_rejected(self, workspace):
        rid = create_one(workspace, dir_name="d1")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(rid, tag=[["foo", "bar"]]))
        assert exc_info.value.code == 1


class TestDependsOnOps:
    def test_set_nonexistent_rejected(self, workspace):
        rid = create_one(workspace, dir_name="d1")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(
                rid, depends_on_ops=[["set", "REQ-99999999-999"]]
            ))
        assert exc_info.value.code == 1
        assert get_req(workspace, rid)["depends_on"] == []

    def test_set_self_dependency_rejected(self, workspace):
        rid = create_one(workspace, dir_name="d1")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(rid, depends_on_ops=[["set", rid]]))
        assert exc_info.value.code == 1

    def test_set_circular_dependency_rejected(self, workspace):
        rid_a = create_one(workspace, feature="需求A", dir_name="da")
        rid_b = create_one(workspace, feature="需求B", dir_name="db",
                           depends_on=rid_a)
        # A --set--> B 会形成 A→B→A 环
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(rid_a, depends_on_ops=[["set", rid_b]]))
        assert exc_info.value.code == 1
        assert get_req(workspace, rid_a)["depends_on"] == []

    def test_set_valid_ok(self, workspace):
        rid_a = create_one(workspace, feature="需求A", dir_name="da")
        rid_b = create_one(workspace, feature="需求B", dir_name="db")
        cmd_update(make_update_args(rid_b, depends_on_ops=[["set", rid_a]]))
        assert get_req(workspace, rid_b)["depends_on"] == [rid_a]

    def test_add_then_remove_combo_ok(self, workspace):
        rid_a = create_one(workspace, feature="需求A", dir_name="da")
        rid_b = create_one(workspace, feature="需求B", dir_name="db")
        rid_c = create_one(workspace, feature="需求C", dir_name="dc")
        cmd_update(make_update_args(
            rid_c,
            depends_on_ops=[["add", f"{rid_a},{rid_b}"], ["remove", rid_a]],
        ))
        assert get_req(workspace, rid_c)["depends_on"] == [rid_b]


class TestRoleUpdate:
    def test_promote_to_child(self, workspace):
        rid_p = create_one(workspace, feature="父", dir_name="dp")
        rid_c = create_one(workspace, feature="子", dir_name="dc")
        cmd_update(make_update_args(rid_c, role="child", parent_id=rid_p))
        parent = get_req(workspace, rid_p)
        child = get_req(workspace, rid_c)
        assert parent["role"] == "parent"
        assert child["parent_id"] == rid_p
        assert rid_c in parent["child_ids"]

    def test_parent_with_children_cannot_be_standalone(self, workspace):
        rid_p = create_one(workspace, feature="父", dir_name="dp")
        rid_c = create_one(workspace, feature="子", dir_name="dc",
                           role="child", parent_id=rid_p)
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(rid_p, role="standalone"))
        assert exc_info.value.code == 1
        assert rid_c in get_req(workspace, rid_p)["child_ids"]


class TestNoChanges:
    def test_blank_feature_rejected(self, workspace):
        rid = create_one(workspace, dir_name="d1")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(rid, feature="   "))
        assert exc_info.value.code == 1
        assert get_req(workspace, rid)["feature"] == "测试功能"

    def test_no_fields_rejected(self, workspace):
        rid = create_one(workspace, dir_name="d1")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args(rid))
        assert exc_info.value.code == 1

    def test_nonexistent_req_rejected(self, workspace):
        create_one(workspace, dir_name="d1")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(make_update_args("REQ-00000000-000", status="已确认"))
        assert exc_info.value.code == 1
