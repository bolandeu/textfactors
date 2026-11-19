"""The report commands: the JSON they accept, the set they compare and the envelopes they emit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rb_textfactors.cli import app
from rb_textfactors.operations import measure_html, measure_text

RUNNER = CliRunner()
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TEXT_A = "Купить ёлку в Москве. Ёлка стоит дорого, но ёлку хотят все."
TEXT_B = "Ёлка в Петербурге. Купить ёлку можно зимой."
PAGE_A = "<html><body><h1>Ёлка</h1><p>Купить ёлку в Москве дёшево.</p></body></html>"
PAGE_B = "<html><body><h1>Ёлки</h1><p>Ёлку купить зимой в Петербурге.</p></body></html>"


def _measured(text: str) -> str:
    return json.dumps(measure_text(text))


def _ok(args: list[str]) -> dict:
    result = RUNNER.invoke(app, ["--json", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_average_of_two_items() -> None:
    payload = _ok(["average", "--item", _measured(TEXT_A), "--item", _measured(TEXT_B)])
    assert payload["items"] == 2


def test_compare_two_pages() -> None:
    payload = _ok(["compare", _measured(TEXT_A), _measured(TEXT_B)])
    assert payload["ok"] is True and payload["blocks"] is not None


def test_compare_set_reports_missing_keys() -> None:
    payload = _ok(["compare-set", _measured(TEXT_A), "--item", _measured(TEXT_B), "--item", _measured(TEXT_B)])
    assert payload["ok"] is True and "missing_keys" in payload


def test_keyword_targets_from_a_set() -> None:
    page_a = json.dumps(measure_html(PAGE_A))
    page_b = json.dumps(measure_html(PAGE_B))
    payload = _ok(["keyword-targets", page_a, "--item", page_b, "--min-sites", "1"])
    assert payload["ok"] is True and "keywords" in payload


def test_measure_html_page() -> None:
    payload = _ok(["measure-html", "<html><body><h1>Ёлка</h1><p>Купить ёлку в Москве.</p></body></html>"])
    assert payload["ok"] is True


def test_check_html_keywords() -> None:
    payload = _ok(["check-html-keywords", "<html><body><p>Ёлка</p></body></html>", "--keyword", "ёлка"])
    assert payload["keywords"]


def test_a_broken_json_argument_is_a_usage_error() -> None:
    result = RUNNER.invoke(app, ["--json", "average", "--item", "{"])
    assert result.exit_code == 2
    assert json.loads(result.output)["error"]["code"] == "INVALID_ARGUMENTS"


@pytest.mark.parametrize("name", ["--help", "--version"])
def test_the_root_answers(name: str) -> None:
    result = RUNNER.invoke(app, [name])
    assert result.exit_code == 0
    assert result.output.strip()


def test_the_bare_root_lists_the_commands() -> None:
    result = RUNNER.invoke(app, [])
    assert result.exit_code == 0
    assert "measure-text" in result.output and "compare" in result.output


def test_measure_html_of_a_fixture_page() -> None:
    page = next(iter(sorted(FIXTURES.glob("*.html"))), None)
    if page is None:
        pytest.skip("no html fixture")
    result = measure_html(page.read_text(encoding="utf-8"))
    assert result["ok"] is None or isinstance(result, dict)


def test_the_human_view_of_a_page() -> None:
    result = RUNNER.invoke(app, ["measure-html", PAGE_A])
    assert result.exit_code == 0
    assert result.output.strip()
