# -*- coding: utf-8 -*-
"""元数据存储，封装 meta.json 的原子读写。"""

import json
import os
import shutil
import tempfile
from pathlib import Path


class MetaCorruptedError(Exception):
    """meta.json 损坏（JSON 解析失败）。

    由 cli 入口统一捕获，输出友好提示与恢复指引，避免裸 traceback。
    """

    def __init__(self, meta_path, cause: Exception):
        self.meta_path = meta_path
        self.cause = cause
        super().__init__(f"meta.json 损坏: {cause}")


class MetaStore:
    """管理 meta.json 的加载与原子写入。

    原子写入策略: 先写临时文件，再 os.replace 原子替换。
    调用方需自行获取 FileLock 后再调用 save()。
    """

    def __init__(self, storage_root: Path, backup_enabled: bool = False):
        self._meta_path = storage_root / "meta.json"
        self._backup_enabled = backup_enabled

    @property
    def meta_path(self) -> Path:
        return self._meta_path

    @property
    def backup_path(self) -> Path:
        return Path(str(self._meta_path) + ".bak")

    def load(self) -> dict:
        """读取 meta.json，返回完整字典。

        Returns:
            dict: {"requirements": {...}}
            若文件不存在返回 {"requirements": {}}

        Raises:
            MetaCorruptedError: JSON 格式损坏
        """
        if not self._meta_path.exists():
            return {"requirements": {}}

        try:
            with open(self._meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise MetaCorruptedError(self._meta_path, e) from e

        if "requirements" not in data:
            data["requirements"] = {}
        return data

    def load_backup(self) -> dict:
        """读取 meta.json.bak，供 req restore 使用。

        Raises:
            FileNotFoundError: 备份不存在
            MetaCorruptedError: 备份本身也损坏
        """
        backup_path = self.backup_path
        if not backup_path.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")
        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise MetaCorruptedError(backup_path, e) from e
        if "requirements" not in data:
            data["requirements"] = {}
        return data

    def save(self, data: dict) -> None:
        """原子写入 meta.json。

        注意：调用方需先获取 FileLock。

        Raises:
            OSError: 磁盘写入失败
        """
        # 备份逻辑
        if self._backup_enabled and self._meta_path.exists():
            backup_path = Path(str(self._meta_path) + ".bak")
            shutil.copy2(self._meta_path, backup_path)

        meta_dir = self._meta_path.parent
        meta_dir.mkdir(parents=True, exist_ok=True)

        # 在同一目录下创建临时文件，保证 os.replace 在同一文件系统；
        # 失败时清理临时文件，避免 .tmp 泄漏
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".tmp",
                dir=meta_dir,
                delete=False,
            ) as f:
                tmp_path = f.name
                json.dump(data, f, ensure_ascii=False, indent=2)

            # os.replace 是原子操作
            os.replace(tmp_path, self._meta_path)
        except Exception:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise
