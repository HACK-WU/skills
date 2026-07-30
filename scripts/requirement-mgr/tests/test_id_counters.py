"""O-05 ID 复用防护 与 O-06 恢复相关的单元测试。"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from requirement_mgr.core.id_generator import gen_next_id
from requirement_mgr.core.meta_store import MetaCorruptedError, MetaStore
from requirement_mgr.commands.restore import _merge_id_counters, _salvage_counters_from_text


class TestIdCounters:
    """测试 id_counters 防 ID 复用（O-05）。"""

    @patch('requirement_mgr.core.id_generator.now_cst')
    def test_no_reuse_after_delete(self, mock_now):
        """删除当日最新需求后再创建，ID 不复用。"""
        mock_now.return_value.strftime.return_value = "20260730"
        counters = {}
        reqs = {}
        # 创建两个
        id1 = gen_next_id(reqs, id_counters=counters)
        reqs["a"] = {"id": id1}
        id2 = gen_next_id(reqs, id_counters=counters)
        reqs["b"] = {"id": id2}
        assert id2 == "REQ-20260730-002"
        # 删除最新的 002
        del reqs["b"]
        # 再创建：无计数器时会复用 002，有计数器应发 003
        id3 = gen_next_id(reqs, id_counters=counters)
        assert id3 == "REQ-20260730-003"

    @patch('requirement_mgr.core.id_generator.now_cst')
    def test_legacy_data_without_counter(self, mock_now):
        """存量数据无计数器：扫描值兜底，计数器补写。"""
        mock_now.return_value.strftime.return_value = "20260730"
        counters = {}
        reqs = {"a": {"id": "REQ-20260730-005"}}
        rid = gen_next_id(reqs, id_counters=counters)
        assert rid == "REQ-20260730-006"
        assert counters["REQ-20260730"] == 6

    @patch('requirement_mgr.core.id_generator.now_cst')
    def test_invalid_counter_value_ignored(self, mock_now):
        """计数器值非法（手工污染）时忽略，退回扫描值。"""
        mock_now.return_value.strftime.return_value = "20260730"
        counters = {"REQ-20260730": "bad"}
        rid = gen_next_id({}, id_counters=counters)
        assert rid == "REQ-20260730-001"

    @patch('requirement_mgr.core.id_generator.now_cst')
    def test_none_counters_backward_compatible(self, mock_now):
        """不传计数器时保持旧行为（纯扫描）。"""
        mock_now.return_value.strftime.return_value = "20260730"
        reqs = {"a": {"id": "REQ-20260730-002"}}
        assert gen_next_id(reqs) == "REQ-20260730-003"


class TestMetaCorrupted:
    """测试 meta 损坏友好异常（O-06）。"""

    def test_load_corrupted_raises_friendly_error(self, tmp_path):
        (tmp_path / "meta.json").write_text("{ not json", encoding="utf-8")
        ms = MetaStore(tmp_path)
        with pytest.raises(MetaCorruptedError):
            ms.load()

    def test_load_backup_missing_raises_filenotfound(self, tmp_path):
        ms = MetaStore(tmp_path)
        with pytest.raises(FileNotFoundError):
            ms.load_backup()

    def test_load_backup_ok(self, tmp_path):
        (tmp_path / "meta.json.bak").write_text(
            json.dumps({"requirements": {"k": {"id": "REQ-001"}}}), encoding="utf-8")
        ms = MetaStore(tmp_path)
        data = ms.load_backup()
        assert data["requirements"]["k"]["id"] == "REQ-001"


class TestMergeIdCounters:
    """测试 restore 的 id_counters 合并（防 ID 复用借道回归）。"""

    def test_takes_max_per_key(self):
        backup = {"id_counters": {"REQ-20260730": 3, "REQ-20260729": 5}}
        current = {"id_counters": {"REQ-20260730": 7}}
        merged = _merge_id_counters(backup, current)
        assert merged == {"REQ-20260730": 7, "REQ-20260729": 5}

    def test_current_corrupted_falls_back_to_backup(self):
        backup = {"id_counters": {"REQ-20260730": 3}}
        assert _merge_id_counters(backup, None) == {"REQ-20260730": 3}

    def test_invalid_current_value_ignored(self):
        backup = {"id_counters": {"REQ-20260730": 3}}
        current = {"id_counters": {"REQ-20260730": "bad"}}
        assert _merge_id_counters(backup, current) == {"REQ-20260730": 3}

    def test_salvaged_wins_when_current_corrupted(self):
        """当前 meta 损坏时，文本抢救值参与 max 合并。"""
        backup = {"id_counters": {"REQ-20260730": 1}}
        salvaged = {"REQ-20260730": 3}
        merged = _merge_id_counters(backup, None, salvaged)
        assert merged == {"REQ-20260730": 3}


class TestSalvageCounters:
    """测试从损坏 meta 文本抢救已发号信息。"""

    def test_extracts_req_ids(self):
        text = '{ broken "id": "REQ-20260730-002", "id": "REQ-20260730-003"'
        assert _salvage_counters_from_text(text, "REQ", 3) == {"REQ-20260730": 3}

    def test_extracts_counter_entries(self):
        text = '"id_counters": { "REQ-20260730": 7 } broken'
        assert _salvage_counters_from_text(text, "REQ", 3) == {"REQ-20260730": 7}

    def test_takes_max_of_both(self):
        text = '"REQ-20260730": 2, "id": "REQ-20260730-005"'
        assert _salvage_counters_from_text(text, "REQ", 3) == {"REQ-20260730": 5}

    def test_empty_text(self):
        assert _salvage_counters_from_text("", "REQ", 3) == {}
