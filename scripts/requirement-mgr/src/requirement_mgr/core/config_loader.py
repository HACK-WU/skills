# -*- coding: utf-8 -*-
"""配置加载器，读取 .requirements/config 提供存储路径和各项配置。"""

from pathlib import Path


class ConfigLoader:
    """读取并缓存 .requirements/config 中的配置。

    支持两种格式:
        key=value          <- 推荐
        key: value         <- 兼容 YAML 风格
    """

    def __init__(self, config_path: str = ".requirements/config"):
        self._config_path = Path(config_path)
        self._storage_path: Path | None = None
        self._feature_categories: list[str] | None = None
        self._requirement_tags: list[str] | None = None
        self._requirement_statuses: list[str] | None = None
        self._requirement_roles: list[str] | None = None
        self._id_prefix: str = "REQ"
        self._id_digits: int = 3
        self._lock_timeout: int = 5
        self._backup_enabled: bool = False
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
        """获取功能分类标签列表。"""
        if not self._config_loaded:
            self._load_config()
        return self._feature_categories

    def get_requirement_tags(self) -> list[str]:
        """获取需求标签配置列表。"""
        if not self._config_loaded:
            self._load_config()
        return self._requirement_tags

    def get_requirement_statuses(self) -> list[str]:
        """获取需求状态列表。"""
        if not self._config_loaded:
            self._load_config()
        return self._requirement_statuses

    def get_requirement_roles(self) -> list[str]:
        """获取需求角色列表。"""
        if not self._config_loaded:
            self._load_config()
        return self._requirement_roles

    def get_id_prefix(self) -> str:
        """获取 ID 前缀。"""
        if not self._config_loaded:
            self._load_config()
        return self._id_prefix

    def get_id_digits(self) -> int:
        """获取 ID 日期后序号位数。"""
        if not self._config_loaded:
            self._load_config()
        return self._id_digits

    def get_lock_timeout(self) -> int:
        """获取文件锁超时秒数。"""
        if not self._config_loaded:
            self._load_config()
        return self._lock_timeout

    def get_backup_enabled(self) -> bool:
        """获取是否启用写入前备份。"""
        if not self._config_loaded:
            self._load_config()
        return self._backup_enabled

    def get_default_status(self) -> str:
        """返回第一个状态值作为默认状态。"""
        statuses = self.get_requirement_statuses()
        return statuses[0] if statuses else "草案"

    def get_default_role(self) -> str:
        """返回第一个角色值作为默认角色。"""
        roles = self.get_requirement_roles()
        return roles[0] if roles else "standalone"

    def _load_config(self) -> None:
        """加载配置文件，解析所有配置项。"""
        if self._config_loaded:
            return

        if not self._config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {self._config_path}\n"
                f"请先运行 req init 初始化项目配置"
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
                self._feature_categories = [t.strip() for t in value.split(",") if t.strip()]
            elif key == "requirement_tags":
                self._requirement_tags = [t.strip() for t in value.split(",") if t.strip()]
            elif key == "requirement_statuses":
                self._requirement_statuses = [s.strip() for s in value.split(",") if s.strip()]
            elif key == "requirement_roles":
                self._requirement_roles = [r.strip() for r in value.split(",") if r.strip()]
            elif key == "id_prefix":
                self._id_prefix = value if value else "REQ"
            elif key == "id_digits":
                try:
                    self._id_digits = int(value) if value else 3
                except ValueError:
                    self._id_digits = 3
            elif key == "lock_timeout":
                try:
                    self._lock_timeout = int(value) if value else 5
                except ValueError:
                    self._lock_timeout = 5
            elif key == "backup_enabled":
                self._backup_enabled = value.lower() in ("true", "1", "yes")

        if not storage_path_found:
            raise ValueError(
                f"未在 {self._config_path} 中找到 storage_path 配置"
            )

        # 空值防护：关键配置项不能为空列表
        if self._requirement_statuses is not None and len(self._requirement_statuses) == 0:
            raise ValueError(
                "requirement_statuses 不能为空。请在 .requirements/config 中配置状态列表，"
                "或删除该行使用默认值（草案,已确认,设计中,实施中,已完成,已取消）"
            )
        if self._requirement_roles is not None and len(self._requirement_roles) == 0:
            raise ValueError(
                "requirement_roles 不能为空。请在 .requirements/config 中配置角色列表，"
                "或删除该行使用默认值（standalone,parent,child）"
            )

        # 设置默认值（仅当字段完全未定义时）
        if self._feature_categories is None:
            self._feature_categories = []
        if self._requirement_tags is None:
            self._requirement_tags = []
        if self._requirement_statuses is None:
            self._requirement_statuses = ["草案", "已确认", "设计中", "实施中", "已完成", "已取消"]
        if self._requirement_roles is None:
            self._requirement_roles = ["standalone", "parent", "child"]

        self._config_loaded = True
