# -*- coding: utf-8 -*-
"""元数据存储，封装 meta.json 的原子读写。"""

import json
import os
import tempfile
from pathlib import Path


class MetaStore:
    """管理 meta.json 的加载与原子写入。

    原子写入策略: 先写临时文件，再 os.replace 原子替换。
    调用方需自行获取 FileLock 后再调用 save()。
    """

    def __init__(self, storage_root: Path):
        self._meta_path = storage_root / "meta.json"

    def load(self) -> dict:
        """读取 meta.json，返回完整字典。

        Returns:
            dict: {"requirements": {...}}
            若文件不存在返回 {"requirements": {}}

        Raises:
            json.JSONDecodeError: JSON 格式损坏
        """
        if not self._meta_path.exists():
            return {"requirements": {}}

        with open(self._meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "requirements" not in data:
            data["requirements"] = {}
        return data

    def save(self, data: dict) -> None:
        """原子写入 meta.json。

        注意：调用方需先获取 FileLock。

        Raises:
            OSError: 磁盘写入失败
        """
        meta_dir = self._meta_path.parent
        meta_dir.mkdir(parents=True, exist_ok=True)

        # 在同一目录下创建临时文件，保证 os.replace 在同一文件系统
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tmp",
            dir=meta_dir,
            delete=False,
        ) as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            tmp_path = f.name

        # os.replace 是原子操作
        os.replace(tmp_path, self._meta_path)
