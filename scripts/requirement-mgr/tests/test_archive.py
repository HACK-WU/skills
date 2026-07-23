"""archive 命令的单元测试。"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from argparse import Namespace

# 将项目根目录添加到 sys.path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from requirement_mgr.commands.archive import cmd_archive, ARCHIVE_STATUS


class TestArchiveCommand:
    """测试归档命令。"""
    
    def setup_method(self):
        """每个测试前的设置。"""
        self.mock_args = Namespace(
            req_id="REQ-20260723-001",
            reason="测试归档",
            dry_run=False,
            force=False
        )
        
        # 模拟需求数据
        self.mock_requirements = {
            "tool/2026-07-23-测试需求": {
                "id": "REQ-20260723-001",
                "feature": "测试需求",
                "status": "草案",
                "created": "2026-07-23 10:00:00",
                "updated": "2026-07-23 10:00:00",
                "version": 1
            }
        }
        
        self.mock_data = {"requirements": self.mock_requirements}
    
    @patch('requirement_mgr.commands.archive.now_cst_str')
    @patch('requirement_mgr.commands.archive.find_children')
    @patch('requirement_mgr.commands.archive.find_rev_deps')
    @patch('requirement_mgr.commands.archive.find_req')
    @patch('requirement_mgr.commands.archive.FileLock')
    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    @patch('requirement_mgr.commands.archive.shutil')
    def test_successful_archive(self, mock_shutil, mock_config_loader, mock_meta_store, 
                               mock_file_lock, mock_find_req, mock_find_rev_deps, 
                               mock_find_children, mock_now_cst_str):
        """测试成功的归档操作。"""
        # 设置 mocks
        mock_find_req.return_value = ("tool/2026-07-23-测试需求", self.mock_requirements["tool/2026-07-23-测试需求"])
        mock_find_children.return_value = []
        mock_find_rev_deps.return_value = []
        mock_now_cst_str.return_value = "2026-07-23 15:00:00"
        
        # 模拟目录
        src_path = MagicMock(spec=Path)
        src_path.exists.return_value = True
        dst_path = MagicMock(spec=Path)
        dst_path.exists.return_value = False
        
        # 模拟存储根目录
        mock_storage_root = MagicMock(spec=Path)
        
        # 模拟多次除法操作
        archive_base = MagicMock(spec=Path)
        archive_base.__truediv__ = lambda self, key: dst_path
        mock_storage_root.__truediv__ = lambda self, key: src_path if key == "tool/2026-07-23-测试需求" else archive_base
        
        # 模拟 FileLock 上下文管理器
        mock_file_lock_instance = MagicMock()
        mock_file_lock.return_value.__enter__ = MagicMock(return_value=mock_file_lock_instance)
        mock_file_lock.return_value.__exit__ = MagicMock(return_value=None)
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = mock_storage_root
        mock_config_loader_instance.get_lock_timeout.return_value = 10
        mock_config_loader_instance.get_backup_enabled.return_value = False
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 执行归档
        with patch('builtins.print') as mock_print:
            cmd_archive(self.mock_args)
        
        # 验证
        mock_shutil.move.assert_called_once()
        mock_meta_store_instance.save.assert_called_once()
        
        # 验证状态更新
        saved_data = mock_meta_store_instance.save.call_args[0][0]
        archived_entry = saved_data["requirements"]["archive/tool/2026-07-23-测试需求"]
        assert archived_entry["status"] == ARCHIVE_STATUS
        assert archived_entry["archived_at"] == "2026-07-23 15:00:00"
        assert archived_entry["archive_reason"] == "测试归档"
    
    @patch('requirement_mgr.commands.archive.find_children')
    @patch('requirement_mgr.commands.archive.find_rev_deps')
    @patch('requirement_mgr.commands.archive.find_req')
    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_already_archived_blocked(self, mock_config_loader, mock_meta_store, 
                                     mock_find_req, mock_find_rev_deps, mock_find_children):
        """测试已归档需求无法再次归档。"""
        # 设置已归档状态
        self.mock_requirements["tool/2026-07-23-测试需求"]["status"] = ARCHIVE_STATUS
        mock_find_req.return_value = ("tool/2026-07-23-测试需求", self.mock_requirements["tool/2026-07-23-测试需求"])
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = MagicMock()
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 验证退出
        with pytest.raises(SystemExit) as exc_info:
            cmd_archive(self.mock_args)
        assert exc_info.value.code == 1
    
    @patch('requirement_mgr.commands.archive.find_children')
    @patch('requirement_mgr.commands.archive.find_rev_deps')
    @patch('requirement_mgr.commands.archive.find_req')
    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_nonexistent_req_blocked(self, mock_config_loader, mock_meta_store, 
                                    mock_find_req, mock_find_rev_deps, mock_find_children):
        """测试不存在的需求无法归档。"""
        mock_find_req.return_value = (None, None)
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = MagicMock()
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 验证退出
        with pytest.raises(SystemExit) as exc_info:
            cmd_archive(self.mock_args)
        assert exc_info.value.code == 1
    
    @patch('requirement_mgr.commands.archive.find_children')
    @patch('requirement_mgr.commands.archive.find_rev_deps')
    @patch('requirement_mgr.commands.archive.find_req')
    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_dry_run_mode(self, mock_config_loader, mock_meta_store, 
                         mock_find_req, mock_find_rev_deps, mock_find_children):
        """测试 dry-run 模式不执行实际操作。"""
        # 设置 dry-run 模式
        self.mock_args.dry_run = True
        
        # 设置有活跃子需求
        mock_find_req.return_value = ("tool/2026-07-23-测试需求", self.mock_requirements["tool/2026-07-23-测试需求"])
        mock_find_children.return_value = [{"id": "REQ-20260723-002", "status": "草案"}]
        mock_find_rev_deps.return_value = []
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = MagicMock()
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 执行 dry-run
        with patch('builtins.print') as mock_print:
            cmd_archive(self.mock_args)
        
        # 验证没有实际操作
        mock_meta_store_instance.save.assert_not_called()
    
    @patch('requirement_mgr.commands.archive.now_cst_str')
    @patch('requirement_mgr.commands.archive.find_children')
    @patch('requirement_mgr.commands.archive.find_rev_deps')
    @patch('requirement_mgr.commands.archive.find_req')
    @patch('requirement_mgr.commands.archive.FileLock')
    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    @patch('requirement_mgr.commands.archive.shutil')
    def test_force_flag_skips_confirmation(self, mock_shutil, mock_config_loader, mock_meta_store, 
                                         mock_file_lock, mock_find_req, mock_find_rev_deps, 
                                         mock_find_children, mock_now_cst_str):
        """测试 --force 标志跳过交互确认。"""
        # 设置有活跃子需求
        mock_find_req.return_value = ("tool/2026-07-23-测试需求", self.mock_requirements["tool/2026-07-23-测试需求"])
        mock_find_children.return_value = [{"id": "REQ-20260723-002", "status": "草案"}]
        mock_find_rev_deps.return_value = []
        
        # 设置 --force
        self.mock_args.force = True
        mock_now_cst_str.return_value = "2026-07-23 15:00:00"
        
        # 模拟目录
        src_path = MagicMock(spec=Path)
        src_path.exists.return_value = True
        dst_path = MagicMock(spec=Path)
        dst_path.exists.return_value = False
        
        # 模拟存储根目录
        mock_storage_root = MagicMock(spec=Path)
        
        # 模拟多次除法操作
        archive_base = MagicMock(spec=Path)
        archive_base.__truediv__ = lambda self, key: dst_path
        mock_storage_root.__truediv__ = lambda self, key: src_path if key == "tool/2026-07-23-测试需求" else archive_base
        
        # 模拟 FileLock 上下文管理器
        mock_file_lock_instance = MagicMock()
        mock_file_lock.return_value.__enter__ = MagicMock(return_value=mock_file_lock_instance)
        mock_file_lock.return_value.__exit__ = MagicMock(return_value=None)
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = mock_storage_root
        mock_config_loader_instance.get_lock_timeout.return_value = 10
        mock_config_loader_instance.get_backup_enabled.return_value = False
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 应该不会调用 input()
        with patch('builtins.input', side_effect=Exception("不应该调用 input")):
            # 执行归档
            with patch('builtins.print') as mock_print:
                cmd_archive(self.mock_args)
            
            # 验证归档成功
            mock_shutil.move.assert_called_once()
    
    @patch('requirement_mgr.commands.archive.find_children')
    @patch('requirement_mgr.commands.archive.find_rev_deps')
    @patch('requirement_mgr.commands.archive.find_req')
    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_conflict_dir_blocked(self, mock_config_loader, mock_meta_store, 
                                 mock_find_req, mock_find_rev_deps, mock_find_children):
        """测试目标目录冲突时无法归档。"""
        # 设置目录冲突
        mock_find_req.return_value = ("tool/2026-07-23-测试需求", self.mock_requirements["tool/2026-07-23-测试需求"])
        mock_find_children.return_value = []
        mock_find_rev_deps.return_value = []
        
        # 模拟源目录存在，目标目录也存在
        src_path = MagicMock(spec=Path)
        src_path.exists.return_value = True
        dst_path = MagicMock(spec=Path)
        dst_path.exists.return_value = True
        
        # 模拟存储根目录
        mock_storage_root = MagicMock(spec=Path)
        mock_storage_root.__truediv__ = lambda self, key: src_path if key == "tool/2026-07-23-测试需求" else dst_path
        
        # 模拟 MetaStore
        mock_meta_store_instance = MagicMock()
        mock_meta_store_instance.load.return_value = self.mock_data
        mock_meta_store.return_value = mock_meta_store_instance
        
        # 模拟 ConfigLoader
        mock_config_loader_instance = MagicMock()
        mock_config_loader_instance.read.return_value = mock_storage_root
        mock_config_loader.return_value = mock_config_loader_instance
        
        # 验证退出
        with pytest.raises(SystemExit) as exc_info:
            cmd_archive(self.mock_args)
        assert exc_info.value.code == 1


class TestArchiveStatus:
    """测试归档状态常量。"""
    
    def test_archive_status_value(self):
        """测试归档状态值是否正确。"""
        assert ARCHIVE_STATUS == "已归档"