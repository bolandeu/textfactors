"""The error envelope, the credential report and the external-program checks."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from rb_textfactors.cli import app
from rb_textfactors.core import deps
from rb_textfactors.core.errors import DependencyTooOld, InvalidArguments

RUNNER = CliRunner()


def test_auth_status_answers_without_credentials() -> None:
    result = RUNNER.invoke(app, ["--json", "auth", "status"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert isinstance(payload["credentials"], list)


def test_doctor_reports_the_external_programs() -> None:
    checks = deps.doctor_checks()
    assert isinstance(checks, list)
    assert all({"name", "ok"} <= set(check) for check in checks)


def test_a_missing_program_is_dependency_too_old() -> None:
    with pytest.raises(DependencyTooOld) as excinfo:
        deps.require_cli("definitely-not-installed-xyz", "1.0", install_url="https://example.invalid/tool")
    assert excinfo.value.code
    assert excinfo.value.action


def test_invalid_arguments_carry_a_code() -> None:
    with pytest.raises(InvalidArguments) as excinfo:
        raise InvalidArguments("bad input")
    assert excinfo.value.code == "INVALID_ARGUMENTS"


def test_the_envelope_of_a_failed_check_has_action_and_code() -> None:
    result = RUNNER.invoke(app, ["--json", "compare", "{", "{}"])
    assert result.exit_code == 2
    error = json.loads(result.output)["error"]
    assert error["code"] == "INVALID_ARGUMENTS"


def test_an_empty_set_is_a_usage_error() -> None:
    result = RUNNER.invoke(app, ["--json", "average"])
    assert result.exit_code == 2
    assert json.loads(result.output)["error"]["code"] == "INVALID_ARGUMENTS"


def test_an_installed_program_passes_the_dependency_check() -> None:
    path = deps.require_cli("sh")
    assert path


def test_a_too_old_program_is_refused() -> None:
    with pytest.raises(DependencyTooOld):
        deps.require_cli("sh", "999.0")


def test_measure_refuses_a_negative_top_n() -> None:
    from rb_textfactors.operations import measure_text

    with pytest.raises(ValueError):
        measure_text("текст", top_n=-1)


def test_check_keywords_refuses_a_target_count_that_does_not_match() -> None:
    from rb_textfactors.operations import check_keywords

    with pytest.raises(ValueError):
        check_keywords("текст", ["слово"], targets=[1, 2])


def test_auth_status_refuses_an_unknown_provider() -> None:
    result = RUNNER.invoke(app, ["--json", "auth", "status", "--provider", "nope"])
    assert result.exit_code == 2
    assert json.loads(result.output)["error"]["code"] == "INVALID_ARGUMENTS"


def test_auth_status_in_the_human_mode() -> None:
    result = RUNNER.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert "credentials" in result.output.lower()


def test_a_json_array_is_not_an_object() -> None:
    from rb_textfactors.commands._input import load

    with pytest.raises(InvalidArguments):
        load("[1, 2]", "--item")


def test_the_human_renderer_skips_absent_fields() -> None:
    from rb_textfactors.commands._input import human

    human("title", ("absent",))({"other": 1})
