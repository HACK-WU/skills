# -*- coding: utf-8 -*-
"""CLI 行为与退出码的单元测试（对文档化契约的回归保护）。

覆盖：退出码 0/2/3/4/5/6/7、`--dump-config`、`--out`、`--max` 截断留痕、
`--check` 新鲜度闸门四分支（新鲜/过期/缺 meta/commit 不可达）。
"""
import json

MINIMAL = {
    "src/router/index.ts": """
        const P = () => import('../pages/p')
        export default [{ path: '/p', component: P }]
        """,
    "src/pages/p.ts": "export const P = () => fetch('/api/ping')\n",
}


def test_exit_0_success_and_out_file(make_project, run_cli, tmp_path):
    root = make_project(MINIMAL)
    out = tmp_path / "scan.json"
    proc = run_cli(root, "--include", "src/**", "--routes", "src/router/**/*.ts",
                   "--format", "json", "--out", out)
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["stats"]["pages"] == 1
    assert len(data["page_apis"]) == 1


def test_exit_2_when_no_conventions(make_project, run_cli):
    """既无路由也无接口约定 → 2（不得伪装成"成功但空"）。"""
    root = make_project({"src/util.ts": "export const noop = () => 1\n"})
    proc = run_cli(root, "--include", "src/**")
    assert proc.returncode == 2
    assert "未识别到路由与接口约定" in proc.stderr


def test_exit_3_when_root_missing(tmp_path, run_cli):
    proc = run_cli(tmp_path / "not-exist")
    assert proc.returncode == 3
    assert "根目录不存在" in proc.stderr


def test_exit_4_when_routes_but_no_api(make_project, run_cli):
    """有页面但完全提取不到调用 → 4（与"没路由"的 2 区分开）。"""
    root = make_project({
        "src/router/index.ts": """
            const L = () => import('../pages/layout')
            export default [{ path: '/layout', component: L }]
            """,
        "src/pages/layout.ts": "export const Layout = () => null\n",
    })
    proc = run_cli(root, "--include", "src/**", "--routes", "src/router/**/*.ts")
    assert proc.returncode == 4, (proc.returncode, proc.stderr)


def test_exit_5_for_bad_arguments(make_project, run_cli, tmp_path):
    root = make_project(MINIMAL)
    assert run_cli(root, "--max", "6000").returncode == 5, "--max 超硬上限应拒绝"
    assert run_cli(root, "--alias", "no-equals").returncode == 5, "--alias 缺 = 应拒绝"
    assert run_cli(root, "--check").returncode == 5, "--check 缺 --index 应拒绝"
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    proc = run_cli(root, "--config", bad, "--include", "src/**")
    assert proc.returncode == 5 and "声明文件" in proc.stderr


def test_dump_config_shape(make_project, run_cli):
    root = make_project(MINIMAL)
    proc = run_cli(root, "--dump-config", "--include", "src/**")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert "detected" in data and "suggested_config" in data
    app = data["suggested_config"]["apps"][0]
    assert app["root"] == "." and isinstance(app["routes"], list)


def test_max_truncation_leaves_trace(make_project, run_cli, tmp_path):
    """回归：截断必须留痕（stats.truncated + pending），不得静默少列。"""
    files = {
        "src/router/index.ts": """
            const P = () => import('../pages/p')
            export default [{ path: '/p', component: P }]
            """,
    }
    calls = "\n".join("fetch('/api/e%d')" % i for i in range(12))
    files["src/pages/p.ts"] = "export const P = () => {\n%s\n}\n" % calls
    root = make_project(files)
    out = tmp_path / "trunc.json"
    proc = run_cli(root, "--include", "src/**", "--routes", "src/router/**/*.ts",
                   "--max", "5", "--format", "json", "--out", out)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["stats"]["page_api_rows"] == 5
    assert "truncated" in data["stats"], data["stats"]
    assert any(p["type"] == "输出截断" for p in data["pending"])


def _write_meta(index_dir, root, commit, scope="."):
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "meta.json").write_text(json.dumps({
        "slug": "t", "root": str(root), "scope": scope, "commit": commit,
        "generated": "2026-10-13",
    }), encoding="utf-8")


def test_check_fresh_returns_0(git_repo, run_cli, tmp_path):
    index = tmp_path / "idx"
    _write_meta(index, git_repo, git_repo.head())
    proc = run_cli(git_repo, "--check", "--index", index)
    assert proc.returncode == 0, proc.stderr
    assert "新鲜" in proc.stdout


def test_check_stale_returns_6_with_changed_file(git_repo, run_cli, tmp_path):
    index = tmp_path / "idx"
    _write_meta(index, git_repo, git_repo.head())
    git_repo.write("src/page.ts", "export const page = 2\n")
    git_repo.git("add", ".")
    git_repo.git("commit", "-qm", "change page")
    proc = run_cli(git_repo, "--check", "--index", index)
    assert proc.returncode == 6, proc.stdout + proc.stderr
    assert "src/page.ts" in (proc.stdout + proc.stderr), "过期时必须列出范围内变更文件"


def test_check_missing_meta_returns_7(git_repo, run_cli, tmp_path):
    index = tmp_path / "empty-idx"
    index.mkdir()
    proc = run_cli(git_repo, "--check", "--index", index)
    assert proc.returncode == 7, proc.stderr


def test_check_unreachable_commit_returns_3(git_repo, run_cli, tmp_path):
    """回归：记录 commit 不可达时必须报错，不得当作"范围内无变化"放行。"""
    index = tmp_path / "idx"
    _write_meta(index, git_repo, "deadbeef" * 5)
    proc = run_cli(git_repo, "--check", "--index", index)
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "不可达" in proc.stderr
