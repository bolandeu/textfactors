"""Guard the supported public Python and CLI contracts."""

import inspect
import json
import subprocess
import sys
from collections.abc import Callable
from importlib.metadata import distribution
from typing import get_type_hints

import pytest
from pydantic import TypeAdapter

import rb_textfactors as api
from rb_textfactors import _cli_docs, operations
from rb_textfactors._cli import main


def cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", api.__name__, *args],
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=10,
    )


def test_public_exports_and_generated_command_help() -> None:
    exports = {"average", "compare", "compare_with_set", "measure_html", "measure_text"}
    assert len(api.__all__) == len(exports)
    assert set(api.__all__) == exports
    discovered: list[str] = []
    for name in api.__all__:
        member = getattr(api, name)
        assert inspect.isfunction(member) and member.__module__ == operations.__name__
        documentation = inspect.getdoc(member)
        assert documentation
        annotations = get_type_hints(member)
        assert set(inspect.signature(member).parameters) | {"return"} <= annotations.keys()
        assert all(TypeAdapter(annotation).json_schema() for annotation in annotations.values())
        command = name.replace("_", "-")
        discovered.append(command)
        help_result = cli("run", command, "--help")
        assert help_result.returncode == 0, help_result.stderr
        assert documentation.splitlines()[0] in help_result.stdout
    listing = cli("run", "--help")
    assert listing.returncode == 0, listing.stderr
    assert all(name in listing.stdout for name in discovered)
    assert "summarize-orders" not in listing.stdout

    public_schema = cli("schema")
    assert public_schema.returncode == 0, public_schema.stderr
    commands = json.loads(public_schema.stdout)["commands"]["run"]["commands"]
    assert set(commands) == set(discovered)
    skill = cli("agent")
    assert skill.returncode == 0, skill.stderr
    assert skill.stdout.startswith("---\nname: ")
    assert all(f" run {name}`" in skill.stdout for name in discovered)
    assert not skill.stderr


def assert_cli_result(expected: dict, *args: str) -> None:
    result = cli("--json", "--no-input", "run", *args)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
    assert not result.stderr


@pytest.mark.parametrize(
    ("name", "operation", "content"),
    [
        ("measure-text", api.measure_text, "Доставка груза. Доставка груза в офис срочно"),
        ("measure-html", api.measure_html, "<h1>Доставка</h1><p>Доставка груза в офис срочно</p>"),
    ],
)
def test_python_and_cli_measurements_match(
    name: str, operation: Callable[..., dict], content: str
) -> None:
    expected = operation(
        content, top_n=1, stop_phrases=["в офис"], ignore_words=["срочно", "груза"]
    )
    assert_cli_result(
        expected,
        name,
        content,
        "--top-n",
        "1",
        "--stop-phrases",
        "в офис",
        "--ignore-words",
        "срочно",
        "груза",
    )


def test_empty_text_passes_through_the_cli() -> None:
    assert_cli_result(api.measure_text(""), "measure-text", "")


def test_explicit_empty_list_of_ignore_words_matches_python() -> None:
    content = "Цена 500 рублей"
    assert_cli_result(
        api.measure_text(content, ignore_words=[]), "measure-text", content, "--ignore-words"
    )


@pytest.mark.parametrize("name", ["average", "compare", "compare-with-set"])
def test_python_and_cli_comparisons_match(name: str) -> None:
    own = {"blocks": {"text": api.measure_text("Грузы")}}
    a = api.measure_html("<h1>Перевозки</h1><p>Надёжная доставка грузов.</p>")
    b = api.measure_html("<h1>Грузы</h1><p>Мы доставляем грузы в порт.</p>")
    own_json, a_json, b_json = (json.dumps(item, ensure_ascii=False) for item in (own, a, b))
    if name == "average":
        assert_cli_result(
            api.average([a, b], blocks=["text", "title"]),
            name,
            a_json,
            b_json,
            "--blocks",
            "text",
            "title",
        )
    elif name == "compare":
        assert_cli_result(api.compare(own, a), name, own_json, a_json)
    else:
        expected = api.compare_with_set(own, [a, b], share=0.5, blocks=["text"], min_key_count=1)
        assert expected["missing_keys"]
        assert_cli_result(
            expected,
            name,
            own_json,
            a_json,
            b_json,
            "--share",
            "0.5",
            "--blocks",
            "text",
            "--min-key-count",
            "1",
        )


@pytest.mark.parametrize(
    "args",
    [
        ("compare", '["do-not-echo-me"]', "{}"),
        ("compare", '{"blocks":"do-not-echo-me"}', "{}"),
        ("compare", "@do-not-echo-me.json", "{}"),
        ("average",),
        ("compare-with-set", "{}", "{}", "--share", "0"),
        ("measure-html", "  "),
        ("measure-text", "do-not-echo-me", "--top-n", "-1"),
    ],
)
def test_invalid_input_is_machine_readable_and_not_echoed(args: tuple[str, ...]) -> None:
    result = cli("--json", "--no-input", "run", *args)
    assert result.returncode == 2
    assert not result.stdout
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "INVALID_ARGUMENTS"
    assert "--help" in error["remediation"]
    assert "do-not-echo-me" not in result.stderr


def test_schema_includes_data_contract_and_safety() -> None:
    result = cli("--json", "schema")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["schema_version"] == 1
    assert data["tool"] == "textfactors"
    assert data["package"] == "rb-textfactors"
    assert data["read_only"]
    assert data["safety"]["no_input"]
    assert data["exit_codes"]["INVALID_ARGUMENTS"] == 2
    assert data["exit_codes"]["DOCTOR_FAILED"] == 10
    assert {"help", "doctor"} <= data["commands"].keys()
    commands = data["commands"]["run"]["commands"]
    argument = commands["average"]["arguments"][0]
    assert argument["name"] == "items"
    assert argument["required"] is True
    assert argument["json_schema"]["type"] == "array"
    assert argument["json_schema"]["items"]["type"] == "object"
    arguments = {arg["name"]: arg for arg in commands["measure-text"]["arguments"]}
    assert arguments["text"]["json_schema"]["type"] == "string"
    assert arguments["top_n"]["default"] == 0
    assert "--top-n" in arguments["top_n"]["flags"]
    assert all(command["result_schema"]["type"] == "object" for command in commands.values())


def test_oversized_result_has_no_partial_output(capsys: pytest.CaptureFixture[str]) -> None:
    item = {"blocks": {"text": {"x" * 65536: 1}}}
    status = main(["run", "average", json.dumps(item)])
    captured = capsys.readouterr()
    assert status == 9
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "OUTPUT_LIMIT"


def test_bare_cli_and_help_aliases_show_the_same_help() -> None:
    result = cli()
    assert result.returncode == 0
    for name in ("run", "agent", "schema", "doctor", "--json", "--no-input"):
        assert name in result.stdout
    assert not result.stderr
    for alias in ("help", "--help", "-h"):
        alias_result = cli(alias)
        assert alias_result.returncode == 0, alias_result.stderr
        assert not alias_result.stderr
        assert alias_result.stdout == result.stdout


def test_cli_entry_point_and_version_use_the_right_names() -> None:
    package = distribution("rb-textfactors")
    cli_name = "textfactors"
    entry_points = package.entry_points.select(group="console_scripts", name=cli_name)
    assert [entry.value for entry in entry_points] == [f"{api.__name__}._cli:main"]
    result = cli("--version")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == package.version


def test_doctor_checks_the_installed_cli() -> None:
    result = cli("--json", "--no-input", "doctor")
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["tool"] == "textfactors"
    assert data["package"] == "rb-textfactors"
    assert data["version"]
    assert data["checks"] == {"command_tree": "ok", "schema": "ok", "agent_guide": "ok"}


def test_doctor_reports_failed_check_without_raw_error(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_guide(*args: object) -> str:
        raise RuntimeError("do-not-echo-me")

    monkeypatch.setattr(_cli_docs, "skill", broken_guide)
    assert main(["doctor"]) == 10
    captured = capsys.readouterr()
    assert not captured.out
    assert "do-not-echo-me" not in captured.err
    error = json.loads(captured.err)["error"]
    assert error["code"] == "DOCTOR_FAILED"
    assert error["check"] == "agent_guide"
    assert error["remediation"]
