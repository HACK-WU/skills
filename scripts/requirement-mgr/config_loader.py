# -*- coding: utf-8 -*-
"""配置加载器，读取 .requirements/config 提供 storage_path。"""

from pathlib import Path


class ConfigLoader:
    """读取并缓存 .requirements/config 中的 storage_path。

    支持两种格式:
        key=value          ← 推荐
        key: value         ← 兼容 YAML 风格
    """

    def __init__(self, config_path: str = ".requirements/config"):
        self._config_path = Path(config_path)
        self._storage_path: Path | None = None

    def read(self) -> Path:
        """读取 config 并返回 storage_path。

        Returns:
            Path: 存储根目录路径

        Raises:
            FileNotFoundError: config 文件不存在
            ValueError: storage_path 为空或未配置
        """
        if self._storage_path is not None:
            return self._storage_path

        if not self._config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {self._config_path}\n"
                f"请先创建 .requirements/config，内容示例:\n"
                f"  storage_path=.requirements"
            )

        for line in self._config_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 支持 key=value 和 key: value 两种格式
            if "=" in line:
                key, _, value = line.partition("=")
            elif ":" in line:
                key, _, value = line.partition(":")
            else:
                continue
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key == "storage_path":
                if not value:
                    raise ValueError("storage_path 不能为空")
                self._storage_path = Path(value)
                return self._storage_path

        raise ValueError(
            f"未在 {self._config_path} 中找到 storage_path 配置"
        )
