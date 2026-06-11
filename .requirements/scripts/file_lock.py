# -*- coding: utf-8 -*-
"""跨平台排他文件锁，基于 fcntl（Unix）/ msvcrt（Windows）。"""

import os
import time

_LOCK_TIMEOUT = int(os.environ.get("REQ_LOCK_TIMEOUT", "5"))
_LOCK_RETRY_INTERVAL = 0.1


class FileLock:
    """跨平台排他文件锁，支持上下文管理器和超时重试。

    用法:
        with FileLock("path/to/meta.json"):
            # 临界区操作
            ...
    """

    def __init__(self, filepath: str):
        self._lockfile = filepath + ".lock"
        self._fd = None

    def acquire(self) -> bool:
        """获取排他锁，5s 内未获取返回 False。"""
        deadline = time.time() + _LOCK_TIMEOUT
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
        """释放锁并删除 .lock 文件。"""
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
            try:
                os.unlink(self._lockfile)
            except OSError:
                pass

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(
                f"无法在 {_LOCK_TIMEOUT}s 内获取文件锁: {self._lockfile}"
            )
        return self

    def __exit__(self, *args):
        self.release()
        return False
