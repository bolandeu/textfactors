"""The output layer every command goes through: global options, the `guard` decorator (JSON envelope, exit codes,
`--dry-run`, confirmation) and the result and error emitters.
"""

from __future__ import annotations

import functools
import logging
import sys
import weakref
from collections.abc import Callable
from typing import ClassVar, NoReturn, cast

import typer
from rich.markup import escape
from typer.core import TyperGroup
from typer.main import get_command

from ..core.errors import Aborted, CliError, InvalidArguments
from ..core.version import cli_name
from . import human
from . import json as json_output

__all__ = [
    "ConfirmOption",
    "DryRunOption",
    "JsonOption",
    "NonInteractiveOption",
    "QuietOption",
    "RootGroup",
    "VerboseOption",
    "configure_logging",
    "emit_error",
    "emit_report",
    "emit_success",
    "group",
    "guard",
    "help_if_no_command",
    "human",
    "is_dry_run",
    "is_guarded",
    "require_confirmation",
    "vecho",
]

from .._distribution import TOOL

_CLI_NAME = cli_name()
_PACKAGE_NAME = __name__.split(".")[0]
# Click's UsageError (unknown option, missing argument, bad value): recent Typer ships its own copy of Click,
# so it is taken from Typer's BadParameter, never imported from the `click` package.
_UsageError = cast("type[Exception]", typer.BadParameter.__bases__[0])
_GUARDED: weakref.WeakSet[Callable] = weakref.WeakSet()

# Reusable local options: attach to any command so `<cli> <command> --json`
# works, on top of the global `<cli> --json <command>` handled by guard().
JsonOption = typer.Option(False, "--json", help="Emit machine-readable JSON output.")
QuietOption = typer.Option(False, "--quiet", help="Suppress non-essential output.")
DryRunOption = typer.Option(False, "--dry-run", help="Show what would happen without making changes.")
ConfirmOption = typer.Option(
    False, "--confirm", help="Confirm a destructive action (required together with --non-interactive)."
)
VerboseOption = typer.Option(False, "--verbose", help="Emit extra diagnostic output.")
NonInteractiveOption = typer.Option(False, "--non-interactive", help="Never prompt; fail instead.")


def configure_logging(verbose: bool) -> None:
    """Route `logging` to stderr: DEBUG under --verbose, WARNING otherwise.

    This is the diagnostics channel that also works under --json (stdout
    stays pure data). Library debug output (httpx request lines, keyring
    backend selection, ...) shows up under --verbose for free.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


def help_if_no_command(ctx: typer.Context) -> None:
    """Print the group's help and exit 0 when it was invoked without a subcommand.

    Click's own no-args handling exits 2 (a usage *error*); a bare
    `<cli>` or `<cli> auth` is a question, not a mistake, so it gets the
    help text and a clean exit instead.
    """
    if ctx.invoked_subcommand is not None:
        return
    # Typer's rich help renders straight to the console and returns "";
    # plain click returns the text — handle both.
    text = ctx.get_help()
    if text:
        typer.echo(text)
    raise typer.Exit()


def group(help_text: str) -> typer.Typer:
    """Create a command group (`<cli> config ...`) with help-on-no-args behavior."""
    app = typer.Typer(help=escape(help_text))  # rich would eat `[...]` in the help text

    @app.callback(invoke_without_command=True)
    def _default(ctx: typer.Context) -> None:
        help_if_no_command(ctx)

    return app


class RootGroup(TyperGroup):
    """The CLI's root group: a usage error (unknown option, missing argument) under --json is the error envelope.

    Click reports a usage error while it parses the arguments, before any
    command runs, so `guard` never sees it. The root's own arguments fail in
    `make_context`, a subcommand's inside `invoke`; both end here.

    An optional part adds its global options (`--project`, `--ai`) to `part_options`
    when it registers; they reach no callback argument (`expose_value=False`).
    """

    # Declaration functions (`def _global_options(x: T = typer.Option(...))`), never parameters: Typer builds a
    # parameter from a callback signature, so the declaration is the only public way to make one.
    part_options: ClassVar[list[Callable[[], None]]] = []

    def __init__(self, *, params=None, **kwargs):
        part_params = [param for decl in self.part_options for param in _root_params(decl)]
        super().__init__(params=[*(params or []), *part_params], **kwargs)

    def make_context(self, info_name, args, parent=None, **extra):
        argv = list(args)  # Click consumes `args` while it parses
        try:
            ctx = super().make_context(info_name, args, parent, **extra)
        except _UsageError as exc:
            _usage_error(exc, argv)
        ctx.meta["argv"] = argv
        return ctx

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except _UsageError as exc:
            _usage_error(exc, ctx.meta["argv"])


def _root_params(decl: Callable[[], None]) -> list:
    """The parameters Typer builds from a declared signature: it is mounted on a throwaway app and read back."""
    spec = typer.Typer(add_completion=False)
    spec.callback()(decl)
    return list(get_command(spec).params)


def _usage_error(exc: Exception, argv: list[str]) -> NoReturn:
    """Under --json: INVALID_ARGUMENTS on stdout, exit 2. Otherwise Click's own usage message."""
    options = argv[: argv.index("--")] if "--" in argv else argv
    if "--json" not in options:
        raise exc
    error = InvalidArguments(str(exc))
    json_output.emit({"ok": False, "error": error.to_dict()})
    raise typer.Exit(code=error.exit_code)


def emit_success(ctx: typer.Context, payload: dict, render_human: Callable[[dict], None]) -> None:
    if ctx.obj.get("json"):
        json_output.emit({"ok": True, **payload})
    elif not ctx.obj.get("quiet"):
        render_human(payload)


def emit_report(
    ctx: typer.Context, payload: dict, render_human: Callable[[dict], None], problem: CliError | None
) -> None:
    """Emit a report that is data whether or not it found a problem (e.g. `auth status`).

    No problem: exactly `emit_success`. A problem: the full payload is still
    emitted, plus `ok: false` and the problem as the standard `error` object,
    and the process exits with the problem's exit code.
    """
    if problem is None:
        emit_success(ctx, payload, render_human)
        return
    if ctx.obj.get("json"):
        json_output.emit({"ok": False, "error": problem.to_dict(), **payload})
    else:
        if not ctx.obj.get("quiet"):
            render_human(payload)
        human.err_console.print(f"[red]Error:[/red] {escape(problem.message)}")
        if problem.action:
            human.err_console.print(f"[dim]{escape(problem.action)}[/dim]")
    raise typer.Exit(code=problem.exit_code)


def emit_error(ctx: typer.Context, error: CliError) -> None:
    if ctx.obj.get("json"):
        json_output.emit({"ok": False, "error": error.to_dict()})
    else:
        human.err_console.print(f"[red]Error:[/red] {escape(error.message)}")
        if error.action:
            human.err_console.print(f"[dim]{escape(error.action)}[/dim]")
    raise typer.Exit(code=error.exit_code)


_LOCAL_FLAG_TO_CTX_KEY = {
    "json_output": "json",
    "quiet": "quiet",
    "verbose": "verbose",
    "non_interactive": "non_interactive",
    "dry_run": "dry_run",
}


def is_dry_run(ctx: typer.Context) -> bool:
    return bool(ctx.obj.get("dry_run"))


def vecho(ctx: typer.Context, message: str) -> None:
    """Print a progress line for a human, only under --verbose and only in human mode.

    For diagnostics that should also reach --json callers (on stderr), use
    `logging.getLogger(__name__).debug(...)` instead — see configure_logging.
    """
    if ctx.obj.get("verbose") and not ctx.obj.get("json") and not ctx.obj.get("quiet"):
        human.err_console.print(f"[dim]{escape(message)}[/dim]")


def require_confirmation(ctx: typer.Context, description: str, confirm: bool) -> None:
    """Gate an irreversible/external-state-changing action behind confirmation.

    Call this immediately before the action itself (never before a
    --dry-run preview — dry-run should short-circuit earlier and skip this
    entirely). `--confirm` skips the prompt for scripts/agents that already
    got human sign-off; `--non-interactive` without `--confirm` fails
    loudly instead of hanging on a prompt an agent can't answer. Declining
    the prompt raises `Aborted`, so it's reported like any other CliError
    (JSON envelope under --json, exit 1).
    """
    if confirm:
        return
    if ctx.obj.get("non_interactive"):
        raise InvalidArguments(f"{description} requires --confirm when --non-interactive is set.")
    if not typer.confirm(f"{description}. Continue?"):
        raise Aborted(description)


def guard(func: Callable) -> Callable:
    """Route any error raised by a command through emit_error.

    Expected failures (`CliError`) are reported with their own code and
    exit status. Anything else — a bug, a library exception nobody mapped
    yet — becomes an `UNEXPECTED` error (exit 1) so a `--json` caller still
    gets a parseable envelope; the traceback goes to stderr under
    --verbose. Also merges any command-local --json/--quiet/--verbose/
    --non-interactive option into ctx.obj, so both `<cli> --json status`
    and `<cli> status --json` work the same way.
    """

    @functools.wraps(func)
    def wrapper(ctx: typer.Context, *args, **kwargs):
        for flag_name, obj_key in _LOCAL_FLAG_TO_CTX_KEY.items():
            if kwargs.get(flag_name):
                ctx.obj[obj_key] = True
        try:
            return func(ctx, *args, **kwargs)
        except CliError as exc:
            emit_error(ctx, exc)
        except (typer.Exit, typer.Abort):
            raise  # already a controlled exit — don't wrap it
        except Exception as exc:
            if ctx.obj.get("verbose"):
                human.err_console.print_exception()
            emit_error(
                ctx,
                CliError(
                    "UNEXPECTED",
                    f"{type(exc).__name__}: {exc}",
                    action="Re-run with --verbose for the traceback; if it persists, report it with that output.",
                ),
            )

    # Docstrings are the --help text; `{cli}` in their `Example:` lines becomes
    # this CLI's name and `{package}` the package's (the project folder's name),
    # so template-born commands need no Jinja rendering.
    # Escaped because Typer renders help as rich markup, which silently drops
    # anything in brackets (`[[tool.rb.external]]`, `[x]`).
    doc = (func.__doc__ or "").replace("{cli}", _CLI_NAME).replace("{package}", TOOL)
    wrapper.__doc__ = escape(doc) or None
    _GUARDED.add(wrapper)
    return wrapper


def is_guarded(func: Callable) -> bool:
    """Whether `func` is an `output.guard` wrapper — tests/test_help.py requires it of every command."""
    return func in _GUARDED
