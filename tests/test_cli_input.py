"""Check JSON stdin and raw file input through the installed CLI contract."""

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from rb_textfactors import average, compare, compare_with_set, measure_html, measure_text

A = {"blocks": {"text": {"words_count": 5}}}
B = {"blocks": {"text": {"words_count": 800}}}


def cli(*args: str, data: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "rb_textfactors", *args],
        input=data,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )


@pytest.mark.parametrize(
    ("name", "operation", "arguments"),
    [
        ("measure-text", measure_text, {"text": "Доставка грузов из Китая", "top_n": 1}),
        ("measure-html", measure_html, {"html": "<h1>Доставка</h1><p>Грузы из Китая.</p>"}),
        ("average", average, {"items": [A, B], "blocks": ["text"]}),
        ("compare", compare, {"a": A, "b": B}),
        ("compare-with-set", compare_with_set, {"own": A, "items": [B], "share": 1}),
    ],
)
def test_stdin_accepts_one_json_object_for_each_operation(
    name: str, operation: Callable[..., dict], arguments: dict
) -> None:
    result = cli("--json", "--no-input", "run", name, data=json.dumps(arguments, indent=2))
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    assert json.loads(result.stdout) == operation(**arguments)


def test_html_accepts_jsonl_from_spider() -> None:
    pages = ["<h1>Доставка</h1><p>Доставка грузов из Китая.</p>", "<p>Цена перевозки.</p>"]
    requests = [
        {"html": html, "url": f"https://example.test/{index}", "status": 200, "top_n": 1}
        for index, html in enumerate(pages)
    ]
    stream = "\n\n".join(json.dumps(item, ensure_ascii=False) for item in requests)
    result = cli("--json", "--no-input", "run", "measure-html", data=stream + "\n")
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    assert [json.loads(line) for line in result.stdout.splitlines()] == [
        measure_html(html, top_n=1) for html in pages
    ]


@pytest.mark.parametrize(
    "payload",
    [
        "",
        '{not-json: "do-not-echo-me"}',
        '[{"text":"do-not-echo-me"}]',
        '{"text":"do-not-echo-me","top_n":true}',
        '{"text":"do-not-echo-me","top_nn":1}',
    ],
)
def test_invalid_json_input_does_not_echo_untrusted_data(payload: str) -> None:
    result = cli("--json", "--no-input", "run", "measure-text", data=payload)
    assert result.returncode == 2
    assert not result.stdout
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "INVALID_ARGUMENTS"
    assert error["remediation"]
    assert "do-not-echo-me" not in result.stderr


def test_jsonl_stops_after_first_error_and_leaves_only_completed_records() -> None:
    stream = '{"text":"first"}\n{"text":42}\n{"text":"third"}\n'
    result = cli("--json", "run", "measure-text", data=stream)
    assert result.returncode == 2
    assert json.loads(result.stdout) == measure_text("first")
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "INVALID_ARGUMENTS"
    assert "2" in error["message"]


def test_json_stdin_respects_the_output_limit() -> None:
    item = {"blocks": {"text": {"x" * 65536: 1}}}
    result = cli("--json", "run", "average", data=json.dumps({"items": [item]}))
    assert result.returncode == 9
    assert not result.stdout
    assert json.loads(result.stderr)["error"]["code"] == "OUTPUT_LIMIT"


def test_file_input_handles_large_html_without_an_argv_limit(tmp_path: Path) -> None:
    html = "<!--" + "x" * 450_000 + "--><h1>Доставка</h1><p>Доставка грузов из Китая.</p>"
    page = tmp_path / "page with spaces.html"
    page.write_text(html, encoding="utf-8")
    result = cli("--json", "run", "measure-html", "--file", str(page), "--top-n", "1")
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    assert json.loads(result.stdout) == measure_html(html, top_n=1)


def test_file_input_preserves_the_utf8_text(tmp_path: Path) -> None:
    text = "Доставка груза\r\nДешевле морем.\r\n"
    path = tmp_path / "example.txt"
    path.write_bytes(text.encode())
    result = cli("run", "measure-text", "--file", str(path))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == measure_text(text)


def test_dash_file_reads_raw_stdin_even_in_json_output_mode() -> None:
    text = "Доставка груза.\n"
    result = cli("--json", "--no-input", "run", "measure-text", "--file", "-", data=text)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == measure_text(text)


def test_file_errors_are_structured_and_do_not_expose_paths(tmp_path: Path) -> None:
    secret_name = tmp_path / "do-not-echo-me.txt"
    invalid_encoding = tmp_path / "non-utf8.txt"
    invalid_encoding.write_bytes(b"\xff")
    for args in (
        ("--file", str(secret_name)),
        ("--file", str(invalid_encoding)),
        ("also an argument", "--file", str(secret_name)),
    ):
        result = cli("run", "measure-text", *args)
        assert result.returncode == 2
        assert not result.stdout
        assert json.loads(result.stderr)["error"]["code"] == "INVALID_ARGUMENTS"
        assert "do-not-echo-me" not in result.stderr


def test_file_and_json_input_are_discoverable() -> None:
    help_result = cli("run", "measure-html", "--help")
    assert help_result.returncode == 0, help_result.stderr
    assert "--file" in help_result.stdout
    schema = json.loads(cli("schema").stdout)["commands"]["run"]["commands"]
    html = schema["measure-html"]
    assert html["stdin_schema"]["required"] == ["html"]
    assert "file" not in html["stdin_schema"]["properties"]
    assert any("--file" in arg["flags"] for arg in html["arguments"])
    assert schema["compare"]["stdin_schema"]["required"] == ["a", "b"]
    guide = cli("agent")
    assert guide.returncode == 0, guide.stderr
    assert "JSONL" in guide.stdout and "--file" in guide.stdout
