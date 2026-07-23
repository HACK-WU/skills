#!/usr/bin/env python3
"""运行 requirement-mgr 的单元测试。"""

import subprocess
import sys
from pathlib import Path


def main():
    """运行测试。"""
    project_root = Path(__file__).parent
    tests_dir = project_root / "tests"
    
    # 检查 pytest 是否安装
    try:
        import pytest
    except ImportError:
        print("错误: pytest 未安装。请运行: pip install pytest")
        sys.exit(1)
    
    # 运行测试
    cmd = [sys.executable, "-m", "pytest", str(tests_dir), "-v"]
    print(f"运行测试: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, cwd=project_root)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()