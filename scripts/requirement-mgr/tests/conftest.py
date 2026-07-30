# -*- coding: utf-8 -*-
"""共享测试夹具：真实临时工作区（config + 存储目录），用于集成风格测试。"""

import sys
from pathlib import Path

# 将 src 目录添加到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

# 带功能分类的标准配置
CONFIG_WITH_CATEGORIES = """storage_path=.requirements
feature_categories=tool,web
requirement_tags=tool,web,feat,fix,p1
lock_timeout=3
"""

# 无分类约束的宽松配置
CONFIG_NO_CATEGORIES = """storage_path=.requirements
lock_timeout=3
"""


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """带功能分类约束的临时工作区，chdir 到其中。"""
    (tmp_path / ".requirements").mkdir()
    (tmp_path / ".requirements" / "config").write_text(
        CONFIG_WITH_CATEGORIES, encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def workspace_no_categories(tmp_path, monkeypatch):
    """无分类/标签约束的临时工作区，chdir 到其中。"""
    (tmp_path / ".requirements").mkdir()
    (tmp_path / ".requirements" / "config").write_text(
        CONFIG_NO_CATEGORIES, encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path
