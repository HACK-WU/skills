"""time_utils 模块的单元测试。"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

# 将项目根目录添加到 sys.path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from requirement_mgr.core.time_utils import now_cst_str, today_cst_str


class TestTimeUtils:
    """测试时间工具函数。"""
    
    @patch('requirement_mgr.core.time_utils.datetime')
    def test_now_cst_str_format(self, mock_datetime):
        """测试 now_cst_str 返回正确的格式（YYYY-MM-DD HH:MM:SS）。"""
        # 模拟东八区时间
        cst = timezone(timedelta(hours=8))
        mock_now = datetime(2026, 7, 23, 15, 21, 47, tzinfo=cst)
        mock_datetime.now.return_value = mock_now
        
        result = now_cst_str()
        assert result == "2026-07-23 15:21:47"
    
    @patch('requirement_mgr.core.time_utils.datetime')
    def test_now_cst_str_timezone(self, mock_datetime):
        """测试 now_cst_str 使用东八区时区。"""
        # 模拟 UTC 时间
        utc = timezone.utc
        mock_utc_now = datetime(2026, 7, 23, 7, 21, 47, tzinfo=utc)
        mock_datetime.now.return_value = mock_utc_now
        
        # 调用时应该传入东八区时区
        mock_datetime.now.assert_not_called()
        now_cst_str()
        
        # 验证调用时使用了东八区时区
        call_args = mock_datetime.now.call_args
        assert call_args[1].get('tz') is not None or call_args[0][0] is not None
    
    @patch('requirement_mgr.core.time_utils.datetime')
    def test_today_cst_str_format(self, mock_datetime):
        """测试 today_cst_str 返回正确的格式（YYYY-MM-DD）。"""
        cst = timezone(timedelta(hours=8))
        mock_now = datetime(2026, 7, 23, 15, 21, 47, tzinfo=cst)
        mock_datetime.now.return_value = mock_now
        
        result = today_cst_str()
        assert result == "2026-07-23"
    
    def test_now_cst_str_actual(self):
        """测试 now_cst_str 实际调用（不 mock）。"""
        result = now_cst_str()
        # 验证格式
        assert len(result) == 19  # YYYY-MM-DD HH:MM:SS
        assert result[4] == '-'
        assert result[7] == '-'
        assert result[10] == ' '
        assert result[13] == ':'
        assert result[16] == ':'
    
    def test_today_cst_str_actual(self):
        """测试 today_cst_str 实际调用（不 mock）。"""
        result = today_cst_str()
        # 验证格式
        assert len(result) == 10  # YYYY-MM-DD
        assert result[4] == '-'
        assert result[7] == '-'