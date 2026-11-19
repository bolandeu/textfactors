"""Human-readable output (messages, key-value lists, the doctor report), kept apart from the JSON output."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

# Data goes to stdout; errors and diagnostics go to stderr, so
# `<cli> status > out.txt` never captures an "Error: ..." line as data.
console = Console()
err_console = Console(stderr=True)


def echo(message: str) -> None:
    """Print plain text. Escaped: rich would otherwise treat `[...]` in data as markup and drop it."""
    console.print(escape(message))


def echo_markup(message: str) -> None:
    """Print rich markup (`[green]✓[/green]`); escape() any data you put inside it."""
    console.print(message)


def key_values(title: str, pairs: dict) -> None:
    console.print(f"[bold]{escape(title)}[/bold]")
    for key, value in pairs.items():
        console.print(f"  {escape(str(key))}: {escape(str(value))}")


def render_doctor(checks: list[dict]) -> None:
    for check in checks:
        mark = "[green]✓[/green]" if check["ok"] else "[red]✗[/red]"
        detail = f" ({check['detail']})" if check.get("detail") else ""
        console.print(f"{mark} {escape(check['name'] + detail)}")
