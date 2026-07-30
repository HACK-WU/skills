"""list 命令的单元测试。"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from argparse import Namespace

# 将项目根目录添加到 sys.path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from requirement_mgr.commands.list import cmd_list, _normalize_ts, ARCHIVE_STATUS


class TestNormalizeTs:
    """测试时间戳归一化函数。"""
    
    def test_empty_string(self):
        """测试空字符串返回空。"""
        assert _normalize_ts("") == ""
    
    def test_old_format_date(self):
        """测试旧格式日期（YYYY-MM-DD）。"""
        assert _normalize_ts("2026-07-23") == "2026-07-23 00:00:00"
    
    def test_new_format_datetime(self):
        """测试新格式日期时间（YYYY-MM-DD HH:MM:SS）。"""
        assert _normalize_ts("2026-07-23 15:21:47") == "2026-07-23 15:21:47"
    
    def test_length_check(self):
        """测试长度检查逻辑。"""
        # 正好 10 个字符（YYYY-MM-DD）
        assert _normalize_ts("2026-07-23") == "2026-07-23 00:00:00"
        # 11 个字符（带空格的旧格式？不应该出现）
        assert _normalize_ts("2026-07-23 ") == "2026-07-23 "  # 会被当作新格式处理（长度>10）
        # 19 个字符（新格式）
        assert _normalize_ts("2026-07-23 15:21:47") == "2026-07-23 15:21:47"


class TestListCommand:
    """测试列表命令。"""
    
    def setup_method(self):
        """每个测试前的设置。"""
        # 模拟需求数据
        self.mock_requirements = {
            "tool/2026-07-23-需求A": {
                "id": "REQ-001",
                "feature": "需求A",
                "status": "草案",
                "created": "2026-07-23 10:00:00",
                "updated": "2026-07-23 10:00:00",
                "version": 1
            },
            "tool/2026-07-23-需求B": {
                "id": "REQ-002",
                "feature": "需求B",
                "status": "已完成",
                "created": "2026-07-22 09:00:00",
                "updated": "2026-07-23 15:30:00",
                "version": 2
            },
            "tool/2026-07-20-需求C": {
                "id": "REQ-003",
                "feature": "需求C",
                "status": "已归档",
                "created": "2026-07-20 08:00:00",
                "updated": "2026-07-20 08:00:00",
                "version": 1
            },
            "tool/2026-07-19-需求D": {
                "id": "REQ-004",
                "feature": "需求D",
                "status": "草案",
                "created": "2026-07-19",  # 旧格式
                "updated": "2026-07-19",  # 旧格式
                "version": 1
            }
        }
        
        self.mock_data = {"requirements": self.mock_requirements}
        
        # 基础参数
        self.base_args = Namespace(
            id=None,
            status=None,
            tag=None,
            role=None,
            parent_id=None,
            category=None,
            date_from=None,
            date_to=None,
            search=None,
            include_archived=False,
            json_output=False,
            columns=None,
            deps=False,
            deps_depth=1,
            rev_deps=False,
            no_color=False,
            limit=0
        )

    @staticmethod
    def _stub_config(mock_config_loader_instance):
        """为 mock ConfigLoader 配置白名单 getter，供筛选值校验使用。"""
        mock_config_loader_instance.get_requirement_statuses.return_value = [
            "草案", "已确认", "设计中", "实施中", "已完成", "已取消", "已归档"
        ]
        mock_config_loader_instance.get_requirement_roles.return_value = [
            "standalone", "parent", "child"
        ]
        mock_config_loader_instance.get_feature_categories.return_value = ["tool"]
        mock_config_loader_instance.get_requirement_tags.return_value = [
            "feat", "fix", "refactor", "tool", "security"
        ]
    
    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_default_hides_archived(self, mock_config_loader, mock_meta_store):
        """测试默认隐藏已归档需求。"""
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = MagicMock()
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 捕获输出
        import io
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            cmd_list(self.base_args)
        
        output = captured_output.getvalue()
        # 验证不包含已归档需求
        assert "REQ-003" not in output
    
    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_include_archived_shows_all(self, mock_config_loader, mock_meta_store):
        """测试 --include-archived 显示所有需求。"""
        # 设置 --include-archived
        self.base_args.include_archived = True
        
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = MagicMock()
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 捕获输出
        import io
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            cmd_list(self.base_args)
        
        output = captured_output.getvalue()
        # 验证包含已归档需求
        assert "REQ-003" in output
    
    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_id_mode_shows_archived(self, mock_config_loader, mock_meta_store):
        """测试 --id 模式可以查询已归档需求。"""
        # 设置 --id 为已归档需求
        self.base_args.id = "REQ-003"
        
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = MagicMock()
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 捕获输出
        import io
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            cmd_list(self.base_args)
        
        output = captured_output.getvalue()
        # 验证包含已归档需求
        assert "REQ-003" in output
    
    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_status_filter(self, mock_config_loader, mock_meta_store):
        """测试 --status 筛选。"""
        # 设置 --status 为"草案"
        self.base_args.status = "草案"
        
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = MagicMock()
        self._stub_config(mock_config_loader_instance)
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 捕获输出
        import io
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            cmd_list(self.base_args)
        
        output = captured_output.getvalue()
        # 验证只有草案需求
        assert "REQ-001" in output
        assert "REQ-004" in output
        assert "REQ-002" not in output
        assert "REQ-003" not in output
    
    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_sorting_normalization(self, mock_config_loader, mock_meta_store):
        """测试排序归一化。"""
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = MagicMock()
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 捕获输出
        import io
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            cmd_list(self.base_args)
        
        output = captured_output.getvalue()
        # 验证排序：REQ-002 (2026-07-23 15:30:00) 应该排在 REQ-001 (2026-07-23 10:00:00) 前面
        req002_pos = output.find("REQ-002")
        req001_pos = output.find("REQ-001")
        assert req002_pos < req001_pos, "REQ-002 应该排在 REQ-001 前面"
    
    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_date_range_filter_normalization(self, mock_config_loader, mock_meta_store):
        """测试日期范围筛选归一化。"""
        # 设置 --from 和 --to
        self.base_args.date_from = "2026-07-23"
        self.base_args.date_to = "2026-07-23"
        
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = MagicMock()
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 捕获输出
        import io
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            cmd_list(self.base_args)
        
        output = captured_output.getvalue()
        # 验证只有 2026-07-23 的需求被筛选出来
        # REQ-001 (2026-07-23 10:00:00) 和 REQ-002 (2026-07-23 15:30:00) 应该被包含
        assert "REQ-001" in output
        assert "REQ-002" in output
        # REQ-004 (2026-07-19) 应该被排除
        assert "REQ-004" not in output
    
    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_search_filter(self, mock_config_loader, mock_meta_store):
        """测试 --search 搜索。"""
        # 设置 --search
        self.base_args.search = "需求B"
        
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = MagicMock()
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 捕获输出
        import io
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            cmd_list(self.base_args)
        
        output = captured_output.getvalue()
        # 验证只有匹配的需求被筛选出来
        assert "REQ-002" in output
        assert "需求B" in output


class TestListStatusConstant:
    """测试列表状态常量。"""
    
    def test_archive_status_value(self):
        """测试归档状态值是否正确。"""
        assert ARCHIVE_STATUS == "已归档"


class TestListFilterValidation:
    """测试筛选值校验与 --limit（O-04 / O-01）。"""

    def setup_method(self):
        self.mock_data = {"requirements": {
            "tool/2026-07-23-A": {
                "id": "REQ-001", "feature": "A", "status": "草案",
                "created": "2026-07-23 10:00:00", "updated": "2026-07-23 10:00:00", "version": 1
            }
        }}
        self.base_args = Namespace(
            id=None, status=None, tag=None, role=None, parent_id=None,
            category=None, date_from=None, date_to=None, search=None,
            include_archived=False, json_output=False, columns=None,
            deps=False, deps_depth=1, rev_deps=False, no_color=False, limit=0
        )

    def _stub(self, mock_config_loader, mock_meta_store):
        ci = MagicMock()
        ci.read.return_value = MagicMock()
        ci.get_requirement_statuses.return_value = ["草案", "已完成", "已归档"]
        ci.get_requirement_roles.return_value = ["standalone", "parent", "child"]
        ci.get_feature_categories.return_value = ["tool"]
        ci.get_requirement_tags.return_value = ["feat", "fix"]
        mock_config_loader.return_value = ci
        mi = MagicMock()
        mi.load.return_value = self.mock_data
        mock_meta_store.return_value = mi
        return ci

    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_invalid_status_errors(self, mock_config_loader, mock_meta_store):
        """无效状态报错退出而非静默空结果。"""
        self._stub(mock_config_loader, mock_meta_store)
        self.base_args.status = "sjaksa"
        with pytest.raises(SystemExit) as exc:
            cmd_list(self.base_args)
        assert exc.value.code == 1

    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_archived_status_is_valid_query(self, mock_config_loader, mock_meta_store):
        """list --status 已归档 是正当查询，不报错。"""
        self._stub(mock_config_loader, mock_meta_store)
        self.base_args.status = "已归档"
        # 不应抛 SystemExit（无匹配但正常返回）
        import io
        with patch('sys.stdout', io.StringIO()):
            cmd_list(self.base_args)

    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_empty_whitelist_skips_tag_validation(self, mock_config_loader, mock_meta_store):
        """白名单为空（不限制）时 --tag 不校验。"""
        ci = self._stub(mock_config_loader, mock_meta_store)
        ci.get_requirement_tags.return_value = []
        self.base_args.tag = ["anything"]
        import io
        with patch('sys.stdout', io.StringIO()):
            cmd_list(self.base_args)  # 不应报错

    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_negative_limit_errors(self, mock_config_loader, mock_meta_store):
        """--limit 负值报错退出。"""
        self._stub(mock_config_loader, mock_meta_store)
        self.base_args.limit = -1
        with pytest.raises(SystemExit) as exc:
            cmd_list(self.base_args)
        assert exc.value.code == 1

    @patch('requirement_mgr.commands.list.MetaStore')
    @patch('requirement_mgr.commands.list.ConfigLoader')
    def test_limit_truncates_and_hints(self, mock_config_loader, mock_meta_store):
        """--limit 截断并提示总量。"""
        # 构造 3 条数据
        self.mock_data = {"requirements": {
            f"tool/2026-07-2{i}-X{i}": {
                "id": f"REQ-00{i}", "feature": f"X{i}", "status": "草案",
                "created": f"2026-07-2{i} 10:00:00", "updated": f"2026-07-2{i} 10:00:00", "version": 1
            } for i in (1, 2, 3)
        }}
        self._stub(mock_config_loader, mock_meta_store)
        self.base_args.limit = 2
        import io
        out = io.StringIO()
        with patch('sys.stdout', out):
            cmd_list(self.base_args)
        text = out.getvalue()
        assert "共 3 个需求，显示最近 2 个" in text