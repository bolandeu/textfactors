"""Bind file and JSON input at the CLI boundary, not in the library API."""

import inspect
import sys
from collections.abc import Iterator
from functools import update_wrapper
from pathlib import Path
from types import FunctionType
from typing import Any, get_type_hints

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, create_model

from . import operations
from .core.errors import InvalidArguments

_JSON_OBJECT = TypeAdapter(dict[str, Any])


def _read_content(content: str | None, path: str | None) -> str:
    if path is None:
        if content is None:
            raise InvalidArguments("Pass content as an argument or use --file PATH or --file -.")
        return content
    if content is not None:
        raise InvalidArguments("Do not combine a content argument with --file.")
    if path == "-" and sys.stdin.isatty():
        raise InvalidArguments("Pipe raw UTF-8 content to --file -.")
    try:
        data = sys.stdin.buffer.read() if path == "-" else Path(path).read_bytes()
        return data.decode("utf-8")
    except (OSError, ValueError):
        raise InvalidArguments("Cannot read the --file input as UTF-8.") from None


def with_file_argument(operation: FunctionType, content_name: str) -> FunctionType:
    """Expose an optional positional and --file to Interfacy without changing the Python API."""
    signature = inspect.signature(operation, eval_str=True)
    parameters = [
        param.replace(default=None) if param.name == content_name else param
        for param in signature.parameters.values()
    ]
    parameters.append(
        inspect.Parameter("file", inspect.Parameter.KEYWORD_ONLY, default=None, annotation=str)
    )
    cli_signature = signature.replace(parameters=parameters)

    def command(*args: Any, **kwargs: Any) -> dict:
        arguments = cli_signature.bind(*args, **kwargs).arguments
        arguments[content_name] = _read_content(
            arguments.get(content_name), arguments.pop("file", None)
        )
        return operation(**arguments)

    update_wrapper(command, operation)
    vars(command)["__signature__"] = cli_signature
    return command


def request_model(operation: FunctionType) -> type[BaseModel]:
    """Describe and validate a JSON request using the public operation signature."""
    hints = get_type_hints(operation)
    fields: dict[str, Any] = {
        name: (hints[name], ... if param.default is inspect.Parameter.empty else param.default)
        for name, param in inspect.signature(operation).parameters.items()
    }
    # HTML input also accepts a Spider row and ignores its fetch metadata.
    extra = "ignore" if operation is operations.measure_html else "forbid"
    return create_model(
        f"{operation.__name__}_request", __config__=ConfigDict(strict=True, extra=extra), **fields
    )


def _parse_record(data: bytes, number: int) -> dict[str, Any]:
    try:
        return _JSON_OBJECT.validate_json(data)
    except ValidationError:
        raise InvalidArguments(f"Expected a UTF-8 JSON object at stdin line {number}.") from None


def json_records() -> Iterator[tuple[int, dict[str, Any]]]:
    """Read one possibly multiline JSON object or stream one object per nonblank line."""
    if sys.stdin.isatty():
        raise InvalidArguments("Pipe a JSON object or JSONL to stdin.")
    try:
        stream = sys.stdin.buffer
        lines = ((number, line) for number, line in enumerate(stream, 1) if line.strip())
        first = next(lines, None)
        if first is None:
            raise InvalidArguments("Expected JSON input on stdin; received no records.")
        number, line = first
        try:
            record = _JSON_OBJECT.validate_json(line)
        except ValidationError:
            # A pretty-printed object may span lines. JSONL records never do.
            yield number, _parse_record(line + stream.read(), number)
            return
        yield number, record
        for number, line in lines:
            yield number, _parse_record(line, number)
    except OSError:
        raise InvalidArguments("Cannot read JSON input from stdin.") from None
