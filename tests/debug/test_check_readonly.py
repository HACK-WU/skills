from __future__ import annotations

import json
import subprocess
import sys

import pytest


def assert_block(proc, data, rule: str | None = None):
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert data.get("ok") is False
    assert data.get("summary", {}).get("block", 0) >= 1
    if rule:
        assert any(item.get("rule") == rule for item in data.get("findings", [])), data


def assert_pass(proc, data):
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert data.get("ok") is True
    assert data.get("summary", {}).get("block", 0) == 0


# ---------- Python ----------


def test_python_allows_read_query(run_cli):
    proc, data = run_cli(
        """
        from app.models import Order
        qs = Order.objects.filter(id=123).values("id", "status", "updated_at")[:1]
        print(list(qs))
        """,
        lang="python",
    )
    assert_pass(proc, data)
    assert data["language"] == "python"


def test_python_false_positive_words(run_cli):
    proc, data = run_cli(
        """
        # delete is only a word in this comment
        from app.models import Order
        qs = Order.objects.filter(id=1).values("id", "updated_at")[:1]
        print("delete is a label", list(qs))
        """,
        lang="python",
    )
    assert_pass(proc, data)


def test_python_allows_open_read(run_cli):
    proc, data = run_cli(
        """
        with open("data.txt") as fh:
            print(fh.read())
        """,
        lang="python",
    )
    assert_pass(proc, data)


def test_python_blocks_local_dict_update(run_cli):
    proc, data = run_cli(
        """
        result = {"a": 1}
        result.update({"b": 2})
        print(result)
        """,
        lang="python",
    )
    assert_block(proc, data)


@pytest.mark.parametrize(
    "code",
    [
        'from app.models import Order\nOrder.objects.filter(id=1).update(status="paid")',
        'from app.models import Order\nOrder.objects.create(id=1)',
        'from app.models import Order\nOrder.objects.bulk_create([])',
        'from app.models import Order\nOrder.objects.get_or_create(id=1)',
        'from app.models import Order\nOrder.objects.update_or_create(id=1)',
        'from app.models import Order\norder = Order()\norder.save()',
        'from app.models import Order\norder = Order()\norder.delete()',
        'from app.models import Order\nOrder.objects.filter(id=1).delete()',
    ],
)
def test_python_blocks_orm_writes(run_cli, code):
    proc, data = run_cli(code, lang="python")
    assert_block(proc, data)


@pytest.mark.parametrize(
    "code",
    [
        'from django.core.cache import cache\ncache.set("k", "v")',
        'from django.core.cache import cache\ncache.get_or_set("k", lambda: 1)',
        'from app.tasks import send_email\nsend_email.delay(1)',
        'import requests\nrequests.post("http://example.test/orders", json={})',
        'import requests\nrequests.request("POST", "http://example.test/orders")',
        'import subprocess\nsubprocess.run(["ls"])',
        'open("out.txt", "w").write("x")',
        'from app.models import Order\ngetattr(Order, "save")()',
        'from app.models import Order\nOrder.objects.filter(id=1).select_for_update()',
        'import os\nos.environ["TOKEN"] = "x"',
        'import os\nos.system("ls")',
        'from pathlib import Path\nPath("x.txt").write_text("x")',
        'import urllib.request\nurllib.request.urlopen("http://example.test", data=b"x")',
        'import urllib.request\nurllib.request.Request("http://example.test", data=b"x")',
    ],
)
def test_python_blocks_side_effects(run_cli, code):
    proc, data = run_cli(code, lang="python")
    assert_block(proc, data)


def test_python_allows_http_get_variants(run_cli):
    proc, data = run_cli(
        'import requests\nrequests.get("http://example.test/orders/1")',
        lang="python",
    )
    assert_pass(proc, data)


def test_python_blocks_write_method_alias(run_cli):
    proc, data = run_cli(
        """
        from app.models import Order
        fn = Order.objects.filter(id=1).update
        fn(status="paid")
        """,
        lang="python",
    )
    assert_block(proc, data)


def test_python_blocks_imported_write_alias(run_cli):
    proc, data = run_cli(
        'from requests import post as p\np("http://example.test/orders/1")',
        lang="python",
    )
    assert_block(proc, data)


def test_python_blocks_imported_request_alias(run_cli):
    proc, data = run_cli(
        'from requests import request as r\nr("GET", "http://example.test/orders/1")',
        lang="python",
    )
    assert_block(proc, data)


def test_python_blocks_local_set_mutation(run_cli):
    proc, data = run_cli(
        "values = {1, 2}\nvalues.add(3)\nprint(values)",
        lang="python",
    )
    assert_block(proc, data)


def test_python_allows_set_constructor(run_cli):
    proc, data = run_cli("values = set([1, 2])\nprint(values)", lang="python")
    assert_pass(proc, data)


def test_python_allows_urlopen_without_data(run_cli):
    proc, data = run_cli(
        'import urllib.request\nurllib.request.urlopen("http://example.test/orders/1")',
        lang="python",
    )
    assert_pass(proc, data)


def test_python_blocks_urlopen_alias_with_data(run_cli):
    proc, data = run_cli(
        'from urllib.request import urlopen as u\nu("http://example.test/orders/1", data=b"x")',
        lang="python",
    )
    assert_block(proc, data, "http-write")


def test_python_blocks_request_alias_with_data(run_cli):
    proc, data = run_cli(
        'from urllib.request import Request as R\nR("http://example.test/orders/1", data=b"x")',
        lang="python",
    )
    assert_block(proc, data, "http-write")


def test_python_blocks_contextual_write_alias(run_cli):
    proc, data = run_cli(
        'import shutil\nfn = shutil.copy\nfn("a", "b")',
        lang="python",
    )
    assert_block(proc, data, "write-attribute")


def test_python_blocks_os_write_alias(run_cli):
    proc, data = run_cli(
        'import os\nfn = os.rename\nfn("a", "b")',
        lang="python",
    )
    assert_block(proc, data, "write-attribute")


def test_python_blocks_subprocess_alias(run_cli):
    proc, data = run_cli(
        'import subprocess\nfn = subprocess.run\nfn(["ls"])',
        lang="python",
    )
    assert_block(proc, data, "write-attribute")


def test_python_blocks_urlopen_alias_capture(run_cli):
    proc, data = run_cli(
        'import urllib.request\nfn = urllib.request.urlopen\nfn("http://example.test")',
        lang="python",
    )
    assert_block(proc, data, "write-attribute")


def test_python_allows_read_method_alias(run_cli):
    proc, data = run_cli(
        'import requests\nfn = requests.get\nfn("http://example.test/orders/1")',
        lang="python",
    )
    assert_pass(proc, data)


def test_python_blocks_unsafe_deserialization(run_cli):
    proc, data = run_cli(
        'import pickle\nobj = pickle.loads(payload)\nprint(obj)',
        lang="python",
    )
    assert_block(proc, data, "unsafe-deserialization")


def test_python_blocks_yaml_unsafe_load(run_cli):
    proc, data = run_cli(
        'import yaml\nobj = yaml.load(text)\nprint(obj)',
        lang="python",
    )
    assert_block(proc, data, "unsafe-deserialization")


def test_python_allows_yaml_safe_load(run_cli):
    proc, data = run_cli(
        'import yaml\nobj = yaml.safe_load(text)\nprint(obj)',
        lang="python",
    )
    assert_pass(proc, data)


def test_python_blocks_sqlalchemy_session_writes(run_cli):
    proc, data = run_cli(
        """
        from sqlalchemy.orm import Session
        session = Session()
        session.add(obj)
        session.commit()
        """,
        lang="python",
    )
    assert_block(proc, data)


def test_python_blocks_credential_literal(run_cli):
    proc, data = run_cli(
        'TOKEN = "sk-live-abcdef1234567890"\nprint(TOKEN)',
        lang="python",
    )
    assert_block(proc, data, "credential-literal")
    assert "sk-live" not in proc.stdout
    assert "[REDACTED]" in proc.stdout


def test_python_blocks_introspection_bypass(run_cli):
    proc, data = run_cli(
        'from app.models import Order\nfn = vars(Order.objects)["update"]\nfn()',
        lang="python",
    )
    assert_block(proc, data, "dynamic-dispatch")


def test_python_blocks_dict_introspection_bypass(run_cli):
    proc, data = run_cli(
        'from app.models import Order\nfn = Order.objects.__dict__["update"]\nfn()',
        lang="python",
    )
    assert_block(proc, data, "dynamic-attribute")


def test_python_allows_env_credential(run_cli):
    proc, data = run_cli(
        'import os\nTOKEN = os.environ["TOKEN"]\nprint(TOKEN)',
        lang="python",
    )
    assert_pass(proc, data)


def test_python_allows_placeholder_credential(run_cli):
    proc, data = run_cli(
        'TOKEN = "$TOKEN"\npassword = "***"\nprint(TOKEN, password)',
        lang="python",
    )
    assert_pass(proc, data)


@pytest.mark.parametrize(
    "code",
    [
        'DB_URL = "postgresql://user:secret@db.example.test/app"',
        'headers = {"X-Api-Key": "abcdef1234567890"}',
        'headers = {"Authorization": "Basic dXNlcjpwYXNz"}',
        'TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz"',
        'URL = "https://example.test/orders?token=abc123"',
    ],
)
def test_python_blocks_more_credential_shapes(run_cli, code):
    proc, data = run_cli(code, lang="python")
    assert_block(proc, data)


def test_checker_never_executes_code(run_cli, tmp_path):
    marker = tmp_path / "should_not_exist.txt"
    proc, data = run_cli(
        f'open("{marker}", "w").write("executed")',
        lang="python",
    )
    assert_block(proc, data)
    assert not marker.exists(), "检查器不应执行被检查代码"


# ---------- SQL ----------


def test_sql_allows_select(run_cli):
    proc, data = run_cli(
        "SELECT id, status FROM orders WHERE id = 1 LIMIT 1;",
        lang="sql",
    )
    assert_pass(proc, data)


def test_sql_allows_readonly_transaction_wrapper(run_cli):
    proc, data = run_cli(
        """
        BEGIN READ ONLY;
        SELECT id, status FROM orders WHERE id = 1 LIMIT 1;
        ROLLBACK;
        """,
        lang="sql",
    )
    assert_pass(proc, data)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE orders SET status = 'paid' WHERE id = 1;",
        "DELETE FROM orders WHERE id = 1;",
        "INSERT INTO orders (id) VALUES (1);",
        "DROP TABLE orders;",
        "TRUNCATE TABLE orders;",
        "ALTER TABLE orders ADD COLUMN x int;",
        "CREATE TABLE x (id int);",
    ],
)
def test_sql_blocks_writes(run_cli, sql):
    proc, data = run_cli(sql, lang="sql")
    assert_block(proc, data)


def test_sql_blocks_multi_statement(run_cli):
    proc, data = run_cli("SELECT 1; DROP TABLE orders;", lang="sql")
    assert_block(proc, data, "sql-multi-statement")


def test_sql_blocks_for_update(run_cli):
    proc, data = run_cli(
        "SELECT id FROM orders WHERE id = 1 FOR UPDATE;",
        lang="sql",
    )
    assert_block(proc, data, "sql-lock")


def test_sql_blocks_explain_analyze(run_cli):
    proc, data = run_cli(
        "EXPLAIN ANALYZE SELECT * FROM orders WHERE id = 1;",
        lang="sql",
    )
    assert_block(proc, data, "sql-explain-analyze")


def test_sql_blocks_nextval(run_cli):
    proc, data = run_cli("SELECT nextval('order_seq');", lang="sql")
    assert_block(proc, data, "sql-write-function")


def test_sql_blocks_into_outfile(run_cli):
    proc, data = run_cli(
        "SELECT id INTO OUTFILE '/tmp/orders.txt' FROM orders WHERE id = 1;",
        lang="sql",
    )
    assert_block(proc, data)


def test_sql_warns_without_limit(run_cli):
    proc, data = run_cli("SELECT id FROM orders;", lang="sql")
    assert proc.returncode == 0
    assert data["summary"]["warn"] >= 1

    proc_strict, data_strict = run_cli("SELECT id FROM orders;", lang="sql", strict=True)
    assert proc_strict.returncode == 1
    assert data_strict["strict"] is True


def test_sql_string_and_comment_false_positive(run_cli):
    proc, data = run_cli(
        """
        -- DROP TABLE orders; is only a comment
        SELECT 'delete' AS label
        FROM orders
        WHERE note = 'delete'
        LIMIT 1;
        """,
        lang="sql",
    )
    assert_pass(proc, data)


def test_sql_quoted_identifier_false_positive(run_cli):
    proc, data = run_cli(
        'SELECT "delete" FROM orders WHERE id = 1 LIMIT 1;',
        lang="sql",
    )
    assert_pass(proc, data)


# ---------- Redis ----------


@pytest.mark.parametrize(
    "snippet",
    [
        "GET order:12345:status",
        "HGETALL order:12345",
        "SCAN 0 MATCH order:12345:* COUNT 20",
        "redis-cli -h 127.0.0.1 -p 6379 --no-raw GET order:12345",
        "redis-cli --no-raw HGETALL order:12345",
    ],
)
def test_redis_allows_reads(run_cli, snippet):
    proc, data = run_cli(snippet, lang="redis")
    assert_pass(proc, data)


@pytest.mark.parametrize(
    "snippet",
    [
        "SET order:12345:status paid",
        "DEL order:12345",
        "FLUSHALL",
        'EVAL "return 1" 0',
        "CONFIG SET maxmemory 1mb",
        "AUTH secret",
        "redis-cli --pipe",
        "redis-cli --eval script.lua key1",
    ],
)
def test_redis_blocks_writes(run_cli, snippet):
    proc, data = run_cli(snippet, lang="redis")
    assert_block(proc, data)


def test_redis_blocks_cli_password(run_cli):
    proc, data = run_cli("redis-cli -a secret GET order:12345", lang="redis")
    assert_block(proc, data, "redis-credential")


@pytest.mark.parametrize(
    "snippet",
    [
        "redis-cli -asecret GET order:12345",
        "redis-cli --pass=secret GET order:12345",
        "redis-cli -u redis://user:secret@127.0.0.1:6379 GET order:12345",
    ],
)
def test_redis_blocks_combined_credentials(run_cli, snippet):
    proc, data = run_cli(snippet, lang="redis")
    assert_block(proc, data, "redis-credential")


def test_redis_warns_heavy_command(run_cli):
    proc, data = run_cli("KEYS *", lang="redis")
    assert proc.returncode == 0
    assert data["summary"]["warn"] >= 1


# ---------- HTTP ----------


@pytest.mark.parametrize(
    "snippet",
    [
        "GET /orders/12345",
        "HEAD /orders/12345",
        'curl -sS "$API_BASE/orders/12345"',
        'curl -sS -X GET "$API_BASE/orders/12345" -H "Authorization: Bearer $TOKEN"',
        'wget -q "$API_BASE/orders/12345"',
    ],
)
def test_http_allows_reads(run_cli, snippet):
    proc, data = run_cli(snippet, lang="http")
    assert_pass(proc, data)


@pytest.mark.parametrize(
    "snippet",
    [
        "POST /orders",
        "PUT /orders/1",
        "PATCH /orders/1",
        "DELETE /orders/1",
        'curl -sS -X POST "$API_BASE/orders/1" -d "{}"',
        'curl -sS --data "{}" "$API_BASE/orders/1"',
        'curl -sS -T ./payload.json "$API_BASE/upload"',
        'curl -sS -u user:pass "$API_BASE/orders/1"',
        'curl -sS -o out.txt "$API_BASE/orders/1"',
        'curl -sS -c cookies.txt "$API_BASE/orders/1"',
        'curl -sS -O "$API_BASE/orders/1"',
        'curl -sS -XPOST "$API_BASE/orders/1"',
        'curl -sS -d@payload.json "$API_BASE/orders/1"',
        'curl -sS --json "{}" "$API_BASE/orders/1"',
        'curl -sS -D headers.txt "$API_BASE/orders/1"',
        'curl -sS --oauth2-bearer secret "$API_BASE/orders/1"',
        'curl -sS -K curlrc "$API_BASE/orders/1"',
        'wget --post-data="{}" "$API_BASE/orders/1"',
        'wget --method=DELETE "$API_BASE/orders/1"',
        'wget -O out.html "$API_BASE/orders/1"',
    ],
)
def test_http_blocks_writes(run_cli, snippet):
    proc, data = run_cli(snippet, lang="http")
    assert_block(proc, data)


def test_http_blocks_credential_header(run_cli):
    proc, data = run_cli(
        'curl -sS "$API_BASE/orders/1" -H "Authorization: Bearer sk-live-abcdef1234567890"',
        lang="http",
    )
    assert_block(proc, data)


def test_http_warns_mutation_url(run_cli):
    proc, data = run_cli("GET /orders/12345/delete", lang="http")
    assert proc.returncode == 0
    assert data["summary"]["warn"] >= 1

    proc_strict, _ = run_cli("GET /orders/12345/delete", lang="http", strict=True)
    assert proc_strict.returncode == 1


def test_text_mode_blocks_secret(run_cli):
    proc, data = run_cli(
        "evidence: Authorization: Bearer sk-live-abcdef1234567890",
        lang="text",
    )
    assert_block(proc, data)
    assert "sk-live" not in proc.stdout
    assert "[REDACTED]" in proc.stdout


def test_text_mode_allows_placeholder(run_cli):
    proc, data = run_cli(
        "evidence: Authorization: Bearer $TOKEN",
        lang="text",
    )
    assert_pass(proc, data)


def test_text_mode_blocks_cli_password(run_cli):
    proc, data = run_cli("evidence: wget --password=secret http://example.test", lang="text")
    assert_block(proc, data, "credential-cli")
    assert "secret" not in proc.stdout

    proc2, data2 = run_cli("evidence: wget --password secret http://example.test", lang="text")
    assert_block(proc2, data2, "credential-cli")


def test_text_mode_allows_cli_password_placeholder(run_cli):
    proc, data = run_cli("evidence: wget --password=$PASSWORD http://example.test", lang="text")
    assert_pass(proc, data)


# ---------- Auto detection ----------


def test_auto_detect_languages(run_cli):
    cases = [
        ('print("hello")', "python"),
        ("SELECT id FROM orders WHERE id = 1 LIMIT 1;", "sql"),
        ("GET order:12345", "redis"),
        ("GET /orders/12345", "http"),
    ]
    for snippet, expected in cases:
        proc, data = run_cli(snippet, lang="auto")
        assert proc.returncode == 0, (snippet, proc.stdout, proc.stderr)
        assert data["language"] == expected, (snippet, data)


def test_auto_detect_sql_with_leading_comment(run_cli):
    proc, data = run_cli(
        "/* read only */\nSELECT id FROM orders WHERE id = 1 LIMIT 1;",
        lang="auto",
    )
    assert proc.returncode == 0
    assert data["language"] == "sql"


# ---------- CLI / errors ----------


def test_cli_missing_file(script_path):
    proc = subprocess.run(
        [sys.executable, str(script_path), "--json", "/no/such/file"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert "无法读取文件" in payload["error"]


def test_cli_unknown_input(run_cli):
    proc, data = run_cli("not a known snippet", lang="auto")
    assert proc.returncode == 2
    assert data.get("ok") is False


def test_cli_invalid_python(run_cli):
    proc, data = run_cli("if :", lang="python")
    assert proc.returncode == 2
    assert data.get("ok") is False


def test_cli_stdin(script_path):
    proc = subprocess.run(
        [sys.executable, str(script_path), "--json", "--lang", "sql", "-"],
        input="SELECT id FROM orders WHERE id = 1 LIMIT 1;\n",
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True


def test_json_output_shape(run_cli):
    proc, data = run_cli("SELECT id FROM orders WHERE id = 1 LIMIT 1;", lang="sql")
    assert proc.returncode == 0
    assert set(data) == {"ok", "language", "strict", "summary", "findings"}
    assert set(data["summary"]) == {"block", "warn", "info"}
    assert isinstance(data["findings"], list)
