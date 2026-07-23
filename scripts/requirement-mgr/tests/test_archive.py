"""archive 命令的单元测试。"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from argparse import Namespace

# 将项目根目录添加到 sys.path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from requirement_mgr.commands.archive import cmd_archive, _archive_doc, ARCHIVE_STATUS


class TestArchiveCommand:
    """测试归档命令。"""
    
    def setup_method(self):
        """每个测试前的设置。"""
        self.mock_args = Namespace(
            req_id="REQ-20260723-001",
            reason="测试归档",
            dry_run=False,
            force=False,
            doc=None,
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


class TestArchiveDoc:
    """测试文档级归档（--doc）。

    使用临时目录 + 真实文件系统，路径穿越防护的 resolve() 难以 mock。
    """

    def setup_method(self):
        """每个测试前创建临时需求目录结构和 mock meta.json。"""
        self.tmp_root = Path(__file__).parent / "_tmp_archive_doc_test"
        # 需求目录：tmp_root/tool/2026-07-23-测试需求/
        self.req_dirname = "tool/2026-07-23-测试需求"
        self.req_dir = self.tmp_root / self.req_dirname
        # 清理可能的残留
        if self.req_dir.exists():
            import shutil as _sh
            _sh.rmtree(self.req_dir)
        self.req_dir.mkdir(parents=True, exist_ok=True)

        # 创建几个测试文档
        (self.req_dir / "design").mkdir(exist_ok=True)
        (self.req_dir / "design" / "old-design.md").write_text("# 旧设计", encoding="utf-8")
        (self.req_dir / "legacy-notes.md").write_text("旧笔记", encoding="utf-8")

        # mock 数据
        self.req_entry = {
            "id": "REQ-20260723-001",
            "feature": "测试需求",
            "status": "草案",
            "created": "2026-07-23 10:00:00",
            "updated": "2026-07-23 10:00:00",
            "version": 1,
            "tags": ["feat", "tool"],
            "changelog": ["初始创建"],
            "docs": [
                {"path": "design/old-design.md", "type": "design"},
                {"path": "requirement.md", "type": "requirement"},
            ],
        }
        self.mock_data = {"requirements": {self.req_dirname: self.req_entry.copy()}}

    def teardown_method(self):
        """每个测试后清理临时目录。"""
        import shutil as _sh
        if self.tmp_root.exists():
            _sh.rmtree(self.tmp_root)

    def _make_args(self, doc, **kwargs):
        """构造 Namespace 参数对象。"""
        return Namespace(
            req_id="REQ-20260723-001",
            reason=kwargs.get("reason"),
            dry_run=kwargs.get("dry_run", False),
            force=kwargs.get("force", False),
            doc=doc,
        )

    def _make_mocks(self):
        """构造 ConfigLoader / MetaStore 的 mock。"""
        ms = MagicMock()
        ms.load.return_value = {"requirements": {self.req_dirname: dict(self.req_entry)}}
        cl = MagicMock()
        cl.read.return_value = self.tmp_root
        cl.get_lock_timeout.return_value = 10
        cl.get_backup_enabled.return_value = False
        return cl, ms

    @patch('requirement_mgr.commands.archive.now_cst_str')
    @patch('requirement_mgr.commands.archive.find_req')
    @patch('requirement_mgr.commands.archive.FileLock')
    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_doc_archive_success(self, mock_cl, mock_ms, mock_lock, mock_find_req, mock_now):
        """测试文档级归档成功：文件移动、状态不变、docs 移除、changelog 追加。"""
        cl, ms = self._make_mocks()
        mock_cl.return_value = cl
        mock_ms.return_value = ms
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=None)
        # 锁内重读返回带 docs 的数据
        locked_req = dict(self.req_entry)
        ms.load.return_value = {"requirements": {self.req_dirname: locked_req}}
        mock_find_req.return_value = (self.req_dirname, locked_req)
        mock_now.return_value = "2026-07-23 15:00:00"

        args = self._make_args("design/old-design.md", reason="设计已废弃")
        with patch('builtins.print'):
            _archive_doc(args, self.tmp_root, self.req_dirname, self.req_entry.copy(), ms, 10)

        # 验证文件移动
        assert not (self.req_dir / "design" / "old-design.md").exists()
        dst = self.req_dir / "archive" / "design" / "old-design.md"
        assert dst.exists()
        assert dst.read_text(encoding="utf-8") == "# 旧设计"

        # 验证 meta.json 更新
        saved = ms.save.call_args[0][0]
        req = saved["requirements"][self.req_dirname]
        assert req["status"] == "草案"  # 状态不变
        assert req["version"] == 2  # 版本自增
        assert req["updated"] == "2026-07-23 15:00:00"
        # docs 中已移除归档文档
        doc_paths = [d["path"] for d in req["docs"]]
        assert "design/old-design.md" not in doc_paths
        assert "requirement.md" in doc_paths
        # changelog 追加
        assert any("归档文档" in c for c in req["changelog"])
        assert any("design/old-design.md" in c for c in req["changelog"])

    @patch('requirement_mgr.commands.archive.find_req')
    @patch('requirement_mgr.commands.archive.FileLock')
    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_doc_archive_dry_run(self, mock_cl, mock_ms, mock_lock, mock_find_req):
        """测试文档级归档 dry-run 不执行实际操作。"""
        cl, ms = self._make_mocks()
        mock_cl.return_value = cl
        mock_ms.return_value = ms
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=None)
        mock_find_req.return_value = (self.req_dirname, dict(self.req_entry))

        args = self._make_args("design/old-design.md", reason="废弃", dry_run=True)
        with patch('builtins.print'):
            _archive_doc(args, self.tmp_root, self.req_dirname, dict(self.req_entry), ms, 10)

        # 验证文件未移动
        assert (self.req_dir / "design" / "old-design.md").exists()
        assert not (self.req_dir / "archive").exists()
        # 验证未保存 meta.json
        ms.save.assert_not_called()

    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_doc_archive_path_traversal(self, mock_cl, mock_ms):
        """测试路径穿越防护：--doc ../../etc/passwd 应被拦截。"""
        cl, ms = self._make_mocks()
        mock_cl.return_value = cl
        mock_ms.return_value = ms

        args = self._make_args("../../etc/passwd")
        with patch('builtins.print'):
            with pytest.raises(SystemExit) as exc_info:
                _archive_doc(args, self.tmp_root, self.req_dirname, dict(self.req_entry), ms, 10)
        assert exc_info.value.code == 1
        # 验证未移动任何文件
        ms.save.assert_not_called()

    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_doc_archive_empty_path(self, mock_cl, mock_ms):
        """测试空 --doc 路径被拦截。"""
        cl, ms = self._make_mocks()
        mock_cl.return_value = cl
        mock_ms.return_value = ms

        args = self._make_args("./")
        with patch('builtins.print'):
            with pytest.raises(SystemExit) as exc_info:
                _archive_doc(args, self.tmp_root, self.req_dirname, dict(self.req_entry), ms, 10)
        assert exc_info.value.code == 1

    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_doc_archive_already_archived_req(self, mock_cl, mock_ms):
        """测试已整体归档的需求不支持文档级归档。"""
        cl, ms = self._make_mocks()
        mock_cl.return_value = cl
        mock_ms.return_value = ms

        archived_entry = dict(self.req_entry)
        archived_entry["status"] = ARCHIVE_STATUS
        args = self._make_args("design/old-design.md")
        with patch('builtins.print'):
            with pytest.raises(SystemExit) as exc_info:
                _archive_doc(args, self.tmp_root, self.req_dirname, archived_entry, ms, 10)
        assert exc_info.value.code == 1
        ms.save.assert_not_called()

    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_doc_archive_nonexistent_doc(self, mock_cl, mock_ms):
        """测试归档不存在的文档被拦截。"""
        cl, ms = self._make_mocks()
        mock_cl.return_value = cl
        mock_ms.return_value = ms

        args = self._make_args("not-exist.md")
        with patch('builtins.print'):
            with pytest.raises(SystemExit) as exc_info:
                _archive_doc(args, self.tmp_root, self.req_dirname, dict(self.req_entry), ms, 10)
        assert exc_info.value.code == 1
        ms.save.assert_not_called()

    @patch('requirement_mgr.commands.archive.find_req')
    @patch('requirement_mgr.commands.archive.FileLock')
    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_doc_archive_dst_conflict(self, mock_cl, mock_ms, mock_lock, mock_find_req):
        """测试目标已存在时被拦截。"""
        cl, ms = self._make_mocks()
        mock_cl.return_value = cl
        mock_ms.return_value = ms
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=None)
        mock_find_req.return_value = (self.req_dirname, dict(self.req_entry))

        # 预先创建目标文件
        (self.req_dir / "archive" / "design").mkdir(parents=True, exist_ok=True)
        (self.req_dir / "archive" / "design" / "old-design.md").write_text("已存在", encoding="utf-8")

        args = self._make_args("design/old-design.md")
        with patch('builtins.print'):
            with pytest.raises(SystemExit) as exc_info:
                _archive_doc(args, self.tmp_root, self.req_dirname, dict(self.req_entry), ms, 10)
        assert exc_info.value.code == 1
        ms.save.assert_not_called()

    @patch('requirement_mgr.commands.archive.now_cst_str')
    @patch('requirement_mgr.commands.archive.find_req')
    @patch('requirement_mgr.commands.archive.FileLock')
    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_doc_archive_no_reason(self, mock_cl, mock_ms, mock_lock, mock_find_req, mock_now):
        """测试不带 --reason 的文档级归档仍可成功。"""
        cl, ms = self._make_mocks()
        mock_cl.return_value = cl
        mock_ms.return_value = ms
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=None)
        locked_req = dict(self.req_entry)
        ms.load.return_value = {"requirements": {self.req_dirname: locked_req}}
        mock_find_req.return_value = (self.req_dirname, locked_req)
        mock_now.return_value = "2026-07-23 15:00:00"

        args = self._make_args("legacy-notes.md", reason=None)
        with patch('builtins.print'):
            _archive_doc(args, self.tmp_root, self.req_dirname, self.req_entry.copy(), ms, 10)

        # 验证文件移动
        assert not (self.req_dir / "legacy-notes.md").exists()
        assert (self.req_dir / "archive" / "legacy-notes.md").exists()

        saved = ms.save.call_args[0][0]
        req = saved["requirements"][self.req_dirname]
        # changelog 不含原因
        last_log = req["changelog"][-1]
        assert "归档文档: legacy-notes.md" in last_log
        assert "（" not in last_log  # 无 reason 拼接

    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_doc_archive_dot_slash_prefix(self, mock_cl, mock_ms):
        """测试 ./ 前缀被正确规范化（不破坏路径，不误判为穿越）。"""
        cl, ms = self._make_mocks()
        mock_cl.return_value = cl
        mock_ms.return_value = ms

        # ./design/old-design.md 应被规范化为 design/old-design.md，不触发路径穿越拦截
        args = self._make_args("./design/old-design.md", dry_run=True)
        with patch('builtins.print'):
            _archive_doc(args, self.tmp_root, self.req_dirname, dict(self.req_entry), ms, 10)
        # dry-run 正常返回，不抛异常，说明 ./ 前缀未触发路径穿越拦截

    @patch('requirement_mgr.commands.archive.find_req')
    @patch('requirement_mgr.commands.archive.FileLock')
    @patch('requirement_mgr.commands.archive.MetaStore')
    @patch('requirement_mgr.commands.archive.ConfigLoader')
    def test_doc_archive_concurrent_archived(self, mock_cl, mock_ms, mock_lock, mock_find_req):
        """测试锁内二次检查发现需求已被整体归档时被拦截。"""
        cl, ms = self._make_mocks()
        mock_cl.return_value = cl
        mock_ms.return_value = ms
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=None)
        # 锁内重读时需求已被归档
        archived_req = dict(self.req_entry)
        archived_req["status"] = ARCHIVE_STATUS
        mock_find_req.return_value = (self.req_dirname, archived_req)

        args = self._make_args("design/old-design.md")
        with patch('builtins.print'):
            with pytest.raises(SystemExit) as exc_info:
                _archive_doc(args, self.tmp_root, self.req_dirname, dict(self.req_entry), ms, 10)
        assert exc_info.value.code == 1
        ms.save.assert_not_called()