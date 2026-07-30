# -*- coding: utf-8 -*-
"""branch 字段（O-02）与 list 展示列（O-03）的单元测试。"""

import io
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from argparse import Namespace

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from requirement_mgr.commands.update import cmd_update, _validate_update
from requirement_mgr.commands.list import cmd_list


def _update_args(**overrides):
    """构造 update 的完整 Namespace（默认全部不修改）。"""
    args = Namespace(
        req_id="REQ-001", status=None, feature=None, role=None, parent_id=None,
        tag=None, depends_on_ops=None, commit=None, branch=None,
        docs_ops=None, changelog=None,
    )
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


def _sample_requirements():
    return {
        "tool/2026-07-30-A": {
            "id": "REQ-001", "feature": "A", "status": "草案",
            "tags": ["tool"], "version": 1,
            "created": "2026-07-30 10:00:00", "updated": "2026-07-30 10:00:00",
            "commits": ["abc1234", "def5678"],
            "branch": "feat/a",
        },
        "tool/2026-07-29-B": {
            "id": "REQ-002", "feature": "B", "status": "草案",
            "tags": ["tool"], "version": 1,
            "created": "2026-07-29 10:00:00", "updated": "2026-07-29 10:00:00",
            # 旧数据：无 branch / commits 字段
        },
    }


VALID_STATUSES = ["草案", "已完成", "已归档"]
VALID_ROLES = ["standalone", "parent", "child"]


class TestBranchValidation:
    """_validate_update 的 branch 规则：空串清除、纯空白拒绝、正常值放行。"""

    def _validate(self, args):
        return _validate_update(
            _sample_requirements(), "REQ-001", args, None, None,
            VALID_STATUSES, VALID_ROLES, [], [],
        )

    def test_whitespace_only_rejected(self):
        errors = self._validate(_update_args(branch="   "))
        assert any("--branch" in e for e in errors)

    def test_empty_string_means_clear_no_error(self):
        assert self._validate(_update_args(branch="")) == []

    def test_normal_value_no_error(self):
        assert self._validate(_update_args(branch="feat/xyz")) == []

    def test_none_means_untouched(self):
        # branch=None 且无其他变更：校验层不报错（changes=0 在应用层处理）
        assert self._validate(_update_args()) == []


class TestBranchUpdateApply:
    """cmd_update 的 branch 写入/清除。"""

    def _run(self, args, requirements):
        data = {"requirements": requirements}
        ci = MagicMock()
        ci.read.return_value = MagicMock()
        ci.get_feature_categories.return_value = []
        ci.get_requirement_tags.return_value = []
        ci.get_requirement_statuses.return_value = VALID_STATUSES
        ci.get_requirement_roles.return_value = VALID_ROLES
        ci.get_lock_timeout.return_value = 5
        ci.get_backup_enabled.return_value = False
        mi = MagicMock()
        mi.load.return_value = data
        with patch('requirement_mgr.commands.update.ConfigLoader', return_value=ci), \
             patch('requirement_mgr.commands.update.MetaStore', return_value=mi), \
             patch('requirement_mgr.commands.update.FileLock', MagicMock()), \
             patch('sys.stdout', io.StringIO()):
            cmd_update(args)
        return data

    def test_set_branch(self):
        reqs = _sample_requirements()
        self._run(_update_args(req_id="REQ-002", branch="feat/b"), reqs)
        assert reqs["tool/2026-07-29-B"]["branch"] == "feat/b"

    def test_clear_branch_with_empty_string(self):
        reqs = _sample_requirements()
        self._run(_update_args(req_id="REQ-001", branch=""), reqs)
        assert reqs["tool/2026-07-30-A"]["branch"] is None

    def test_whitespace_branch_exits(self):
        reqs = _sample_requirements()
        with pytest.raises(SystemExit) as exc:
            with patch('requirement_mgr.commands.update.ConfigLoader') as mcl:
                ci = MagicMock()
                ci.read.return_value = MagicMock()
                ci.get_feature_categories.return_value = []
                ci.get_requirement_tags.return_value = []
                ci.get_requirement_statuses.return_value = VALID_STATUSES
                ci.get_requirement_roles.return_value = VALID_ROLES
                ci.get_lock_timeout.return_value = 5
                ci.get_backup_enabled.return_value = False
                mcl.return_value = ci
                with patch('requirement_mgr.commands.update.MetaStore') as mms:
                    mi = MagicMock()
                    mi.load.return_value = {"requirements": reqs}
                    mms.return_value = mi
                    cmd_update(_update_args(req_id="REQ-001", branch="  "))
        assert exc.value.code == 1

    def test_clear_absent_branch_is_noop(self):
        """旧数据无 branch 字段时 --branch "" 无变更，报 exit 1（未指定修改字段）。"""
        reqs = _sample_requirements()
        with pytest.raises(SystemExit) as exc:
            self._run(_update_args(req_id="REQ-002", branch=""), reqs)
        assert exc.value.code == 1


class TestListBranchColumns:
    """list 默认列的 branch 与 commits 数量展示。"""

    def _list_args(self, **overrides):
        args = Namespace(
            id=None, status=None, tag=None, role=None, parent_id=None,
            category=None, date_from=None, date_to=None, search=None,
            include_archived=False, json_output=False, columns=None,
            deps=False, deps_depth=1, rev_deps=False, no_color=False, limit=0,
        )
        for k, v in overrides.items():
            setattr(args, k, v)
        return args

    def _run(self, args):
        ci = MagicMock()
        ci.read.return_value = MagicMock()
        mi = MagicMock()
        mi.load.return_value = {"requirements": _sample_requirements()}
        out = io.StringIO()
        with patch('requirement_mgr.commands.list.ConfigLoader', return_value=ci), \
             patch('requirement_mgr.commands.list.MetaStore', return_value=mi), \
             patch('sys.stdout', out):
            cmd_list(args)
        return out.getvalue()

    def test_default_columns_show_branch_and_commit_count(self):
        output = self._run(self._list_args())
        assert "分支" in output
        assert "feat/a" in output
        # commits 显示数量而非 hash 列表
        assert "abc1234" not in output

    def test_old_data_branch_dash_and_zero_commits(self):
        output = self._run(self._list_args())
        # REQ-002 无 branch → —，无 commits → 0
        assert "—" in output

    def test_detail_view_shows_branch_and_full_commits(self):
        output = self._run(self._list_args(id="REQ-001"))
        assert "feat/a" in output
        assert "abc1234" in output
        assert "def5678" in output
        assert "关联提交（2 项）" in output

    def test_json_output_keeps_raw_commits(self):
        """--json 输出原始数据，commits 不被替换为数量。"""
        output = self._run(self._list_args(json_output=True))
        assert "abc1234" in output
