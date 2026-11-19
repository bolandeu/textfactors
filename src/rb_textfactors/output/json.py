"""Machine-readable output: the one function that prints a JSON document to stdout."""

from __future__ import annotations

import json

import typer


def emit(data: dict) -> None:
    typer.echo(json.dumps(data))
