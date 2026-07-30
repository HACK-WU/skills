# -*- coding: utf-8 -*-
"""跨平台排他文件锁，基于 fcntl（Unix）/ msvcrt（Windows）。"""

import os
import time

_LOCK_RETRY_INTERVAL = 0.1


class FileLock:
    """跨平台排他文件锁，支持上下文管理器和超时重试。

    用法:
        with FileLock("path/to/meta.json", timeout=10):
            # 临界区操作
            ...
    """

    def __init__(self, filepath: str, timeout: int | None = None):
        """初始化文件锁。

        Args:
            filepath: 被锁文件路径（实际锁的是 filepath.lock）
            timeout: 超时秒数。None 时依次检查环境变量 REQ_LOCK_TIMEOUT，再兜底 5
        """
        if timeout is None:
            env_timeout = os.environ.get("REQ_LOCK_TIMEOUT")
            if env_timeout:
                try:
                    timeout = int(env_timeout)
                except ValueError:
                    timeout = 5
            else:
                timeout = 5
        self._timeout = timeout
        self._lockfile = filepath + ".lock"
        self._fd = None

    def acquire(self) -> bool:
        """获取排他锁，超时内未获取返回 False。"""
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            try:
                self._fd = open(self._lockfile, "w")
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self._fd.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (IOError, OSError):
                if self._fd:
                    self._fd.close()
                    self._fd = None
                time.sleep(_LOCK_RETRY_INTERVAL)
        return False

    def release(self) -> None:
        """释放锁。

        注意：故意不删除 .lock 文件。unlink 会引入 inode 竞态
        （A 删文件后 B 重建新 inode，C 锁旧 inode → B/C 双持锁）。
        保留 0 字节锁文件是 flock 的标准用法，进程退出时内核会自动释放锁。
        """
        if self._fd:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self._fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                self._fd.close()
            except (IOError, OSError):
                pass
            finally:
                self._fd = None

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(
                f"无法在 {self._timeout}s 内获取文件锁: {self._lockfile}"
            )
        return self

    def __exit__(self, *args):
        self.release()
        return False
