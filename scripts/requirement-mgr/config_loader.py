# -*- coding: utf-8 -*-
"""配置加载器，读取 .requirements/config 提供 storage_path。"""

from pathlib import Path


class ConfigLoader:
    """读取并缓存 .requirements/config 中的配置。

    支持两种格式:
        key=value          ← 推荐
        key: value         ← 兼容 YAML 风格
    """

    def __init__(self, config_path: str = ".requirements/config"):
        self._config_path = Path(config_path)
        self._storage_path: Path | None = None
        self._feature_categories: list[str] | None = None
        self._requirement_tags: list[str] | None = None
        self._config_loaded: bool = False

    def read(self) -> Path:
        """读取 config 并返回 storage_path。

        Returns:
            Path: 存储根目录路径

        Raises:
            FileNotFoundError: config 文件不存在
            ValueError: storage_path 为空或未配置
        """
        if not self._config_loaded:
            self._load_config()
        return self._storage_path

    def get_feature_categories(self) -> list[str]:
        """获取功能分类标签列表。

        Returns:
            list[str]: 功能分类标签列表，为空表示不进行功能分类
        """
        if not self._config_loaded:
            self._load_config()
        return self._feature_categories

    def get_requirement_tags(self) -> list[str]:
        """获取需求标签配置列表。

        Returns:
            list[str]: 需求标签配置列表
        """
        if not self._config_loaded:
            self._load_config()
        return self._requirement_tags

    def _load_config(self) -> None:
        """加载配置文件，解析所有配置项。"""
        if self._config_loaded:
            return

        if not self._config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {self._config_path}\n"
                f"请先创建 .requirements/config，内容示例:\n"
                f"  storage_path=.requirements"
            )

        storage_path_found = False
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
                storage_path_found = True
            elif key == "feature_categories":
                # 解析功能分类标签，为空表示不进行功能分类
                self._feature_categories = [t.strip() for t in value.split(",") if t.strip()]
            elif key == "requirement_tags":
                # 解析需求标签配置
                self._requirement_tags = [t.strip() for t in value.split(",") if t.strip()]

        if not storage_path_found:
            raise ValueError(
                f"未在 {self._config_path} 中找到 storage_path 配置"
            )
        
        # 设置默认值
        if self._feature_categories is None:
            self._feature_categories = []
        if self._requirement_tags is None:
            self._requirement_tags = []
        
        self._config_loaded = True
