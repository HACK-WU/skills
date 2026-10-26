from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "debug"
    / "scripts"
    / "check_readonly.py"
)


@pytest.fixture
def run_cli(tmp_path):
    """把片段写盘后调用 CLI，返回 (CompletedProcess, JSON payload)。"""

    def _run(code: str, lang: str = "auto", strict: bool = False, suffix: str = ".txt"):
        snippet = tmp_path / f"snippet{suffix}"
        snippet.write_text(textwrap.dedent(code).strip() + "\n", encoding="utf-8")
        args = [sys.executable, str(SCRIPT), "--json"]
        if strict:
            args.append("--strict")
        args.extend(["--lang", lang, str(snippet)])
        proc = subprocess.run(args, capture_output=True, text=True, timeout=20)
        try:
            payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError:
            payload = {}
        return proc, payload

    return _run


@pytest.fixture
def script_path() -> Path:
    assert SCRIPT.exists(), f"check_readonly.py 不存在: {SCRIPT}"
    return SCRIPT
