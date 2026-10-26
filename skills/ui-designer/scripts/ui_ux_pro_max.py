#!/usr/bin/env python3
"""ui-ux-pro-max 调用桥。

只做三件事：
  1. 定位项目内安装的 ui-ux-pro-max（不联网、不改外部依赖）；
  2. 以 JSON 调用其 search.py；
  3. 把结果归一化为 ui-designer 可消费的结构，并在失败时给出可降级信号。

使用：
  python3 ui_ux_pro_max.py probe --project-root .
  python3 ui_ux_pro_max.py generate "beauty spa wellness" --project "Serena" --project-root .
  python3 ui_ux_pro_max.py domain --domain ux --query "error summary validation" --project-root .
  python3 ui_ux_pro_max.py stack --stack react --query "form validation" --project-root .
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

CANDIDATE_SEARCH_PATHS = (
    "ui-tools/vendor/skills/ui-ux-pro-max/scripts/search.py",
    "ui-tools/vendor/ui-ux-pro-max/scripts/search.py",
)
DEFAULT_TIMEOUT = 30


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() or (candidate / "ui-tools").is_dir():
            return candidate
    return current


def find_search_script(project_root: Path) -> Path | None:
    for relative in CANDIDATE_SEARCH_PATHS:
        candidate = project_root / relative
        if candidate.is_file():
            return candidate
    return None


def read_version(search_script: Path) -> str | None:
    skill_dir = search_script.parent.parent
    for filename in ("skill.json", "package.json"):
        candidate = skill_dir / filename
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        version = data.get("version")
        if isinstance(version, str) and version:
            return version
    return None


def emit(payload: dict[str, Any], exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def resolve_search(args: argparse.Namespace) -> tuple[Path | None, Path, dict[str, Any]]:
    project_root = (
        Path(args.project_root).expanduser()
        if args.project_root
        else find_project_root(Path.cwd())
    )
    search_script = find_search_script(project_root)
    if search_script is None:
        return None, project_root, {
            "ok": False,
            "code": "not_installed",
            "error": "ui-ux-pro-max 未安装到项目内",
            "projectRoot": str(project_root),
            "expected": [
                str(project_root / relative) for relative in CANDIDATE_SEARCH_PATHS
            ],
        }
    return search_script, project_root, {
        "ok": True,
        "search": str(search_script),
        "vendor": str(search_script.parent.parent),
        "version": read_version(search_script),
        "python": sys.version.split()[0],
        "projectRoot": str(project_root),
    }


def run_search(
    search_script: Path, args: list[str], timeout: int
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        completed = subprocess.run(
            [sys.executable, str(search_script), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, {
            "ok": False,
            "code": "timeout",
            "error": f"ui-ux-pro-max 调用超时（{timeout}s）",
        }
    except OSError as exc:
        return None, {
            "ok": False,
            "code": "spawn_error",
            "error": f"无法执行 search.py：{exc}",
        }

    if completed.returncode != 0:
        return None, {
            "ok": False,
            "code": "upstream_error",
            "error": (completed.stderr or completed.stdout or "").strip()
            or f"search.py 退出码 {completed.returncode}",
        }

    try:
        return json.loads(completed.stdout), None
    except json.JSONDecodeError as exc:
        return None, {
            "ok": False,
            "code": "bad_json",
            "error": f"search.py 输出不是合法 JSON：{exc}",
        }


def command_probe(args: argparse.Namespace) -> int:
    _, _, probe = resolve_search(args)
    return emit(probe, 0 if probe["ok"] else 1)


def command_generate(args: argparse.Namespace) -> int:
    search_script, _, probe = resolve_search(args)
    if search_script is None:
        return emit(probe, 1)

    search_args = [args.query, "--design-system", "--json"]
    if args.project:
        search_args.extend(["-p", args.project])

    payload, error = run_search(search_script, search_args, args.timeout)
    if error is not None:
        error.update({"projectRoot": probe["projectRoot"], "version": probe["version"]})
        return emit(error, 2)

    design_system = (payload or {}).get("design_system")
    if not isinstance(design_system, dict):
        return emit(
            {
                "ok": False,
                "code": "empty_result",
                "error": "search.py 未返回 design_system",
                "projectRoot": probe["projectRoot"],
                "version": probe["version"],
            },
            2,
        )

    required = ("pattern", "style", "colors", "typography")
    missing = [key for key in required if not design_system.get(key)]
    if missing:
        return emit(
            {
                "ok": False,
                "code": "incomplete_result",
                "error": "design_system 缺少必要字段",
                "missing": missing,
                "projectRoot": probe["projectRoot"],
                "version": probe["version"],
            },
            2,
        )

    return emit(
        {
            "ok": True,
            "designSystem": design_system,
            "persistence": (payload or {}).get("persistence"),
            "source": {
                "vendor": probe["vendor"],
                "version": probe["version"],
                "query": args.query,
            },
        }
    )


def command_passthrough(args: argparse.Namespace, mode: str) -> int:
    search_script, _, probe = resolve_search(args)
    if search_script is None:
        return emit(probe, 1)

    search_args = [args.query, f"--{mode}", getattr(args, mode), "--json"]
    search_args.extend(["-n", str(args.max_results)])

    payload, error = run_search(search_script, search_args, args.timeout)
    if error is not None:
        error.update({"projectRoot": probe["projectRoot"], "version": probe["version"]})
        return emit(error, 2)

    return emit(
        {
            "ok": True,
            "result": payload,
            "source": {
                "vendor": probe["vendor"],
                "version": probe["version"],
                "query": args.query,
                "mode": mode,
            },
        }
    )


def command_domain(args: argparse.Namespace) -> int:
    return command_passthrough(args, "domain")


def command_stack(args: argparse.Namespace) -> int:
    return command_passthrough(args, "stack")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ui-ux-pro-max bridge for ui-designer"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--project-root",
            default=None,
            help="项目根目录（默认从 cwd 向上查找 .git 或 ui-tools）",
        )
        sub.add_argument(
            "--timeout",
            type=int,
            default=DEFAULT_TIMEOUT,
            help=f"search.py 超时秒数（默认 {DEFAULT_TIMEOUT}）",
        )

    probe = subparsers.add_parser("probe", help="检测 ui-ux-pro-max 是否可用")
    add_common(probe)
    probe.set_defaults(func=command_probe)

    generate = subparsers.add_parser("generate", help="生成设计系统建议")
    generate.add_argument("query")
    generate.add_argument("--project", default=None)
    add_common(generate)
    generate.set_defaults(func=command_generate)

    domain = subparsers.add_parser("domain", help="按 domain 查询")
    domain.add_argument("--domain", required=True)
    domain.add_argument("--query", required=True)
    domain.add_argument("--max-results", type=int, default=3)
    add_common(domain)
    domain.set_defaults(func=command_domain)

    stack = subparsers.add_parser("stack", help="按技术栈查询")
    stack.add_argument("--stack", required=True)
    stack.add_argument("--query", required=True)
    stack.add_argument("--max-results", type=int, default=3)
    add_common(stack)
    stack.set_defaults(func=command_stack)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
