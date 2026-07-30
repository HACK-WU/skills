# -*- coding: utf-8 -*-
"""FileLock 的单元测试：互斥、释放后重入、锁文件保留策略。"""

from pathlib import Path

from requirement_mgr.core.file_lock import FileLock


class TestFileLock:
    def test_acquire_and_release(self, tmp_path):
        target = tmp_path / "meta.json"
        lock = FileLock(str(target), timeout=1)
        assert lock.acquire() is True
        lock.release()

    def test_lock_file_kept_after_release(self, tmp_path):
        """release 后保留 .lock 文件（避免 unlink 引入的 inode 竞态）。"""
        target = tmp_path / "meta.json"
        lock = FileLock(str(target), timeout=1)
        assert lock.acquire() is True
        lock.release()
        assert (tmp_path / "meta.json.lock").exists()

    def test_second_lock_blocked_until_release(self, tmp_path):
        """同一锁文件的两个实例互斥；释放后可重新获取。"""
        target = tmp_path / "meta.json"
        lock1 = FileLock(str(target), timeout=1)
        lock2 = FileLock(str(target), timeout=1)

        assert lock1.acquire() is True
        # lock1 持有期间 lock2 超时失败
        assert lock2.acquire() is False

        lock1.release()
        # 释放后 lock2 可获取（锁文件保留不影响功能）
        assert lock2.acquire() is True
        lock2.release()

    def test_context_manager_timeout_raises(self, tmp_path):
        target = tmp_path / "meta.json"
        lock1 = FileLock(str(target), timeout=1)
        assert lock1.acquire() is True
        try:
            raised = False
            try:
                with FileLock(str(target), timeout=1):
                    pass
            except TimeoutError:
                raised = True
            assert raised
        finally:
            lock1.release()

    def test_env_var_timeout_fallback(self, tmp_path, monkeypatch):
        """timeout=None 时读取 REQ_LOCK_TIMEOUT 环境变量。"""
        monkeypatch.setenv("REQ_LOCK_TIMEOUT", "7")
        lock = FileLock(str(tmp_path / "meta.json"))
        assert lock._timeout == 7
