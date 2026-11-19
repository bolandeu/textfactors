"""Shared CLI helpers: the JSON arguments the report commands read and their human renderer."""

from __future__ import annotations

import json
from collections.abc import Callable

from .. import output
from ..core.errors import InvalidArguments


def load(value: str, what: str) -> dict:
    """One JSON object from a command-line argument."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise InvalidArguments(f"{what} is not valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise InvalidArguments(f"{what} must be a JSON object")
    return parsed


def load_items(values: list[str]) -> list[dict]:
    """One JSON object per `--item`: the items of a set."""
    if not values:
        raise InvalidArguments("Pass at least one --item")
    return [load(value, f"--item {index}") for index, value in enumerate(values, start=1)]


def human(title: str, keys: tuple[str, ...]) -> Callable[[dict], None]:
    """A compact human view: the named top-level fields, then the rest as a table of counts."""

    def render(payload: dict) -> None:
        pairs = {key: payload[key] for key in keys if key in payload}
        output.human.key_values(title, pairs)

    return render
