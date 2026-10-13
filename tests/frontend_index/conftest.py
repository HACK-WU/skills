# -*- coding: utf-8 -*-
"""frontend-index 专属夹具：加载待测模块、绑定 CLI 运行器。

被测对象：skills/frontend-index/scripts/scan_frontend.py
通用夹具（make_project / git_repo / run_script）见 tests/conftest.py。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_PATH = REPO_ROOT / "skills" / "frontend-index" / "scripts" / "scan_frontend.py"


@pytest.fixture(scope="session")
def sf():
    """待测脚本（作为模块加载，用于单元级断言）。"""
    spec = importlib.util.spec_from_file_location("scan_frontend_under_test", SCAN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def scan_of(sf):
    """调用 scan()：scan_of(root, include=[...], routes=[...], apiDirs=[...]) → ScanResult。"""

    def _scan(root, **opts):
        return sf.scan(str(root), opts)

    return _scan


@pytest.fixture
def run_cli(run_script):
    """跑扫描脚本 CLI：run_cli(root, *args) → CompletedProcess（自动补 --root）。"""

    def _run(root, *args, cwd=None):
        return run_script("frontend-index/scripts/scan_frontend.py", "--root", str(root),
                          *args, cwd=cwd)

    return _run
