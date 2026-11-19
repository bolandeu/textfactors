"""The CLI surface: every command answers --help and the envelope commands answer --json."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from rb_textfactors.cli import app

RUNNER = CliRunner()
COMMANDS = [
    "measure-text",
    "measure-html",
    "average",
    "compare",
    "compare-set",
    "check-keywords",
    "check-html-keywords",
    "keyword-targets",
    "doctor",
]


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_answers_help(command: str) -> None:
    result = RUNNER.invoke(app, [command, "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output or "usage:" in result.output


def test_doctor_reports_its_checks() -> None:
    result = RUNNER.invoke(app, ["--json", "doctor"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["checks"]


def test_measure_text_emits_the_metrics() -> None:
    result = RUNNER.invoke(app, ["--json", "measure-text", "Купить ёлку в Москве"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["words_total"] == 4


def test_an_unknown_option_is_the_error_envelope() -> None:
    result = RUNNER.invoke(app, ["--json", "measure-text", "текст", "--nope"])
    assert result.exit_code == 2
    assert json.loads(result.output)["error"]["code"]


def test_version_prints_the_installed_version() -> None:
    result = RUNNER.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_quiet_suppresses_the_human_output() -> None:
    result = RUNNER.invoke(app, ["--quiet", "measure-text", "Купить ёлку в Москве"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_the_human_view_of_a_measurement() -> None:
    result = RUNNER.invoke(app, ["measure-text", "Купить ёлку в Москве"])
    assert result.exit_code == 0
    assert "words" in result.output or "text" in result.output


def test_doctor_in_the_human_mode() -> None:
    result = RUNNER.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert result.output.strip()


def test_verbose_adds_diagnostics_without_breaking_the_envelope() -> None:
    result = RUNNER.invoke(app, ["--json", "--verbose", "doctor"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["ok"] is True
