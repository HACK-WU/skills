# -*- coding: utf-8 -*-
"""create 命令的集成测试：路径清洗、归档守卫、父子关系。"""

import json
from argparse import Namespace
from pathlib import Path

import pytest

from requirement_mgr.commands.create import cmd_create, _check_dir_name


def make_args(**kw):
    """构造 create 命令的参数对象。"""
    return Namespace(
        feature=kw.get("feature", "测试功能"),
        tags=kw.get("tags", "tool,feat"),
        status=kw.get("status"),
        role=kw.get("role"),
        parent_id=kw.get("parent_id"),
        depends_on=kw.get("depends_on", ""),
        dir_name=kw.get("dir_name", ""),
    )


def load_meta(workspace: Path) -> dict:
    return json.loads(
        (workspace / ".requirements" / "meta.json").read_text(encoding="utf-8")
    )


class TestCreateBasic:
    def test_create_success(self, workspace, capsys):
        cmd_create(make_args())
        meta = load_meta(workspace)
        assert len(meta["requirements"]) == 1
        key, entry = next(iter(meta["requirements"].items()))
        # 键名格式 category/dir_name（单层分类 + 单层目录名）
        assert key.startswith("tool/")
        assert len(key.split("/")) == 2
        # created 为完整时间戳
        assert len(entry["created"]) == 19
        # 目录已创建
        assert (workspace / ".requirements" / key).is_dir()

    def test_create_archived_status_rejected(self, workspace):
        with pytest.raises(SystemExit) as exc_info:
            cmd_create(make_args(status="已归档"))
        assert exc_info.value.code == 1


class TestDirNameSanitize:
    def test_check_dir_name_rules(self):
        assert _check_dir_name("") is not None
        assert _check_dir_name(".") is not None
        assert _check_dir_name("..") is not None
        assert _check_dir_name("a/b") is not None
        assert _check_dir_name("a\\b") is not None
        assert _check_dir_name("evil\x00name") is not None
        assert _check_dir_name("2026-07-30-正常名称") is None

    def test_dir_name_traversal_rejected(self, workspace):
        with pytest.raises(SystemExit) as exc_info:
            cmd_create(make_args(dir_name="../../evil"))
        assert exc_info.value.code == 1
        # 未在存储根之外创建任何目录
        assert not (workspace.parent / "evil").exists()
        assert not (workspace / ".requirements" / "meta.json").exists()

    def test_dir_name_dotdot_rejected(self, workspace):
        with pytest.raises(SystemExit) as exc_info:
            cmd_create(make_args(dir_name=".."))
        assert exc_info.value.code == 1

    def test_feature_with_slash_sanitized(self, workspace):
        cmd_create(make_args(feature="登录/注册模块"))
        meta = load_meta(workspace)
        key = next(iter(meta["requirements"]))
        # feature 中的 / 被清洗，键名仍是 category/dir_name 两层
        assert len(key.split("/")) == 2
        assert "登录-注册模块" in key
        # feature 字段保留原始值
        assert meta["requirements"][key]["feature"] == "登录/注册模块"


class TestParentChild:
    def _create_pair(self, workspace):
        """创建 parent（standalone 自动升级）+ child，返回两个 ID。"""
        cmd_create(make_args(feature="父需求", dir_name="dir-parent"))
        meta = load_meta(workspace)
        parent_id = next(iter(meta["requirements"].values()))["id"]
        cmd_create(make_args(
            feature="子需求", dir_name="dir-child",
            role="child", parent_id=parent_id,
        ))
        return parent_id

    def test_parent_auto_upgrade(self, workspace):
        parent_id = self._create_pair(workspace)
        meta = load_meta(workspace)
        parent = next(
            r for r in meta["requirements"].values() if r["id"] == parent_id
        )
        child = next(
            r for r in meta["requirements"].values() if r["role"] == "child"
        )
        assert parent["role"] == "parent"
        assert child["id"] in parent["child_ids"]
        assert child["parent_id"] == parent_id

    def test_archived_parent_rejected(self, workspace):
        cmd_create(make_args(feature="父需求", dir_name="dir-parent"))
        # 手工把父需求置为已归档
        meta_path = workspace / ".requirements" / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        key, entry = next(iter(meta["requirements"].items()))
        entry["status"] = "已归档"
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

        with pytest.raises(SystemExit) as exc_info:
            cmd_create(make_args(
                feature="子需求", dir_name="dir-child",
                role="child", parent_id=entry["id"],
            ))
        assert exc_info.value.code == 1
