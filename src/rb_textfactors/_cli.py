"""Translate local CLI calls into calls to the public Python API."""

import inspect
import json
import sys
from collections.abc import Iterator
from importlib.metadata import version
from types import FunctionType
from typing import Any, get_type_hints

from interfacy import CommandGroup, Interfacy, UsageError
from pydantic import BaseModel, TypeAdapter, ValidationError

import rb_textfactors as api

from . import _cli_docs, _cli_input, operations
from ._cli_docs import DIST_NAME, EXIT_CODES, FLAGS, HELP_FLAGS, MAX_OUTPUT_BYTES, NAME
from .core.errors import InvalidArguments

_JSON = TypeAdapter(Any)
_JSON_OBJECT = TypeAdapter(dict)


class _DoctorFailure(Exception):
    """A diagnostic failed; the exception message is only the check name."""


def _discover_operations() -> Iterator[tuple[str, FunctionType]]:
    for name in api.__all__:
        member = getattr(api, name)
        if inspect.isfunction(member) and member.__module__ == operations.__name__:
            yield name, member


def _build_app(functions: dict[str, FunctionType]) -> Interfacy:
    examples = f"Examples: {NAME} run --help; {NAME} doctor; {NAME} --json schema."
    flag_help = " ".join(f"{flag}: {text}" for flag, text in FLAGS.items())
    app = Interfacy(
        description="Call library operations. " + examples,
        epilog="Global flags (before the command): " + flag_help,
        allow_args_from_file=False,
        expand_model_params=False,
        help_flags=HELP_FLAGS,
    )
    # A measured result is one JSON object. Interfacy handles lists as one token per item.
    app.add_type_parser(dict, _JSON_OBJECT.validate_json)
    group = CommandGroup("run", description="Run a read-only library operation.")
    for name, operation in functions.items():
        for parameter, annotation in get_type_hints(operation).items():
            if parameter != "return" and isinstance(annotation, type):
                if issubclass(annotation, BaseModel):
                    app.add_type_parser(annotation, annotation.model_validate_json)
        content = {"measure-text": "text", "measure-html": "html"}.get(name)
        if content is None:
            group.add_command(operation, name=name)
        else:
            group.add_command(
                _cli_input.with_file_argument(operation, content),
                name=name,
                params={
                    content: {"kind": "positional"},
                    "file": {
                        "metavar": "PATH",
                        "help": f"Read UTF-8 from PATH or use '-' for raw stdin instead of {content}.",
                    },
                },
            )
    app.add_group(group)

    def agent() -> str:
        """Print an offline usage guide that can be saved as SKILL.md."""
        return _cli_docs.skill(app.build_parser_schema())

    def schema() -> dict[str, object]:
        """Describe the command tree, data schemas, exit codes, and safety as JSON."""
        return _cli_docs.describe(app.build_parser_schema(), functions)

    def help() -> None:
        """Show the main help and exit."""
        app.invoke(args=["--help"])

    def doctor() -> dict[str, object]:
        """Check the installed CLI without calling operations or using the network."""
        checks: dict[str, str] = {}
        check = "command_tree"
        try:
            parser = app.build_parser_schema()
            checks[check] = "ok"
            check = "schema"
            _JSON.dump_json(_cli_docs.describe(parser, functions))
            checks[check] = "ok"
            check = "agent_guide"
            _cli_docs.skill(parser)
            checks[check] = "ok"
        except Exception:
            raise _DoctorFailure(check) from None
        return {
            "ok": True,
            "tool": NAME,
            "package": DIST_NAME,
            "version": version(DIST_NAME),
            "python": sys.version.split()[0],
            "checks": checks,
        }

    app.add_command(help)
    app.add_command(doctor)
    app.add_command(agent)
    app.add_command(schema)
    return app


def _fail(code: str, message: str, remediation: str, *, check: str | None = None) -> int:
    error = {"code": code, "message": message, "remediation": remediation}
    if check is not None:
        error["check"] = check
    print(json.dumps({"error": error}), file=sys.stderr)
    return EXIT_CODES[code]


def _doctor_error(check: str) -> int:
    return _fail(
        "DOCTOR_FAILED",
        "An installed CLI check failed.",
        "Reinstall the package; if it still fails, report the failed check and version.",
        check=check,
    )


def _write_result(result: object, *, is_operation: bool) -> int:
    payload = _JSON.dump_json(result)
    if is_operation and len(payload) > MAX_OUTPUT_BYTES:
        return _fail(
            "OUTPUT_LIMIT",
            "Result exceeds 64 KiB.",
            "Narrow the operation input or set top_n when measuring (--top-n on the CLI).",
        )
    print(payload.decode("utf-8"), flush=True)
    return 0


def _run_json_stdin(operation: FunctionType) -> int:
    model = _cli_input.request_model(operation)
    for number, record in _cli_input.json_records():
        try:
            request = model.model_validate(record)
            result = operation(**dict(request))
        except ValidationError:
            raise InvalidArguments(f"Invalid operation fields at stdin line {number}.") from None
        except InvalidArguments as error:
            raise InvalidArguments(f"stdin line {number}: {error}") from None
        status = _write_result(result, is_operation=True)
        if status:
            return status
    return 0


def main(args: list[str] | None = None) -> int:
    """Run a local command and return its process exit code."""
    argv = sys.argv[1:] if args is None else args
    flags: set[str] = set()
    while argv and argv[0] in FLAGS:
        flags.add(argv[0])
        argv = argv[1:]
    json_mode = "--json" in flags
    help_hint = f"Check '{NAME} run --help' for arguments or '{NAME} schema' for stdin fields."

    try:
        if "--version" in flags:
            if argv:
                return _fail("INVALID_ARGUMENTS", "--version takes no command.", help_hint)
            installed = version(DIST_NAME)
            print(json.dumps({"version": installed}) if json_mode else installed)
            return 0
        if not argv or argv == ["run"]:
            argv = [*argv, "--help"]
        functions = {name.replace("_", "-"): fn for name, fn in _discover_operations()}
        if json_mode and len(argv) == 2 and argv[0] == "run" and argv[1] in functions:
            return _run_json_stdin(functions[argv[1]])
        result = _build_app(functions).invoke(args=argv)
        # Interfacy returns None after rendering help. Do not append JSON to it.
        options = argv[: argv.index("--")] if "--" in argv else argv
        if result is None and (argv[0] == "help" or any(flag in options for flag in HELP_FLAGS)):
            return 0
        if argv[0] == "agent" and not json_mode and isinstance(result, str):
            print(result.rstrip())
            return 0
        return _write_result(result, is_operation=argv[0] == "run")
    except InvalidArguments as error:
        return _fail("INVALID_ARGUMENTS", str(error), help_hint)
    except (UsageError, ValidationError):
        # Parser and validation messages can include raw input. Never echo it here.
        return _fail("INVALID_ARGUMENTS", "The arguments are invalid.", help_hint)
    except KeyboardInterrupt:
        return _fail("INTERRUPTED", "The operation was interrupted.", "Retry if still needed.")
    except _DoctorFailure as failure:
        return _doctor_error(str(failure))
    except Exception:
        if argv == ["doctor"]:
            return _doctor_error("command_tree")
        return _fail(
            "OPERATION_FAILED",
            "The operation failed.",
            "Check inputs and report a reproducible bug.",
        )
