# -*- coding: utf-8 -*-
"""跨脚本共享的测试夹具（放在 tests/ 根，所有子目录可见）。

约定：`tests/{script_dir}/` 对应 `skills/{skill}/scripts/`，一个脚本一个子目录 ——
具体见 tests/README.md。本文件只放**与具体脚本无关**的夹具：
- `make_project`：按 {相对路径: 内容} 生成假项目
- `git_repo`：已提交一次的临时 git 仓库（无 git 时自动 skip）
- `run_script`：以子进程跑任意 skills/ 下脚本

运行：cd <repo root> && python3 -m pytest tests -q
"""
import itertools
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"


@pytest.fixture
def make_project(tmp_path):
    """按 {相对路径: 内容} 生成假项目目录，返回其根 Path。内容自动 dedent。"""
    counter = itertools.count(1)

    def _make(files, name=None):
        base = tmp_path / (name or "proj%d" % next(counter))
        base.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
        return base

    return _make


@pytest.fixture
def run_script():
    """跑 skills/ 下的脚本：run_script("<skill>/scripts/<name>.py", *args) → CompletedProcess。

    不注入任何业务参数（各脚本参数不同），需要固定参数时在子目录 conftest 里再包一层。
    """

    def _run(script_rel, *args, cwd=None, timeout=60):
        cmd = [sys.executable, str(SKILLS_DIR / script_rel)] + [str(a) for a in args]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)

    return _run


class GitRepo(object):
    """轻量 git 仓库句柄：path / git(*args) / head() / write(rel, text)。"""

    def __init__(self, path, env):
        self.path = path
        self.env = env

    def git(self, *args):
        # -c commit.gpgsign=false：本机若全局开启提交签名，夹具仓库会因缺 gpg 而失败
        return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=str(self.path),
                              env=self.env, capture_output=True, text=True, check=True)

    def head(self):
        return self.git("rev-parse", "HEAD").stdout.strip()

    def write(self, rel, text):
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def __str__(self):
        return str(self.path)


@pytest.fixture
def git_repo(tmp_path):
    """一个已提交一次的临时 git 仓库（用于 `--check` 类新鲜度测试）。"""
    if not shutil.which("git"):
        pytest.skip("本机无 git，跳过新鲜度测试")
    repo = GitRepo(tmp_path / "gitrepo", dict(
        os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e",
        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e"))
    repo.path.mkdir()
    repo.git("init", "-q")
    repo.write("src/page.ts", "export const page = 1\n")
    repo.git("add", ".")
    repo.git("commit", "-qm", "init")
    return repo
