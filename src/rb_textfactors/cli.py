"""The root Typer app: global options, the command groups and the optional commands a generated package has, wired
together, and the console-script entry point.
"""

from __future__ import annotations

import typer

from . import output
from .commands import auth, compare, doctor, keywords, measure
from .core.version import DEV_VERSION, cli_name, installed_version, optional_module, package_summary

_PACKAGE_NAME = __name__.split(".")[0]
# Optional parts (copier questions, dropped by _exclude): each one ships a module that registers its
# commands and global options. Probed at runtime, so this file needs no template logic.
PARTS = ("project", "skill", "describe", "db")

# A bare `<cli>` is the discovery entry point for humans and agents alike:
# name + version + description, then every command with the first line of
# its docstring. No `no_args_is_help` (that exits 2) — main_options() below
# prints this and exits 0. Shell completion stays enabled.
app = typer.Typer(
    cls=output.RootGroup,  # a usage error under --json is the error envelope
    help=f"{cli_name()} {installed_version() or DEV_VERSION} — {package_summary() or 'project-aware automation CLI'}",
)

app.add_typer(auth.app, name="auth")  # `auth status` in every CLI; login/logout only with credentials
app.command(name="doctor")(doctor.doctor)
app.command(name="measure-text")(measure.text_command)
app.command(name="measure-html")(measure.html_command)
app.command(name="average")(compare.average_command)
app.command(name="compare")(compare.compare_command)
app.command(name="compare-set")(compare.compare_set_command)
app.command(name="check-keywords")(keywords.check_keywords_command)
app.command(name="check-html-keywords")(keywords.check_html_keywords_command)
app.command(name="keyword-targets")(keywords.keyword_targets_command)
for part in PARTS:
    if module := optional_module(f"{_PACKAGE_NAME}.commands.{part}"):
        module.register(app)


def _version_callback(value: bool) -> None:
    if not value:
        return
    typer.echo(installed_version() or DEV_VERSION)
    raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_options(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress non-essential output."),
    verbose: bool = typer.Option(False, "--verbose", help="Emit extra diagnostic output."),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Never prompt; fail instead."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen without making changes."),
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show the version and exit."
    ),
) -> None:
    ctx.ensure_object(dict)  # a part's global option (--project) may have put its value here already
    ctx.obj["json"] = json_output
    ctx.obj["quiet"] = quiet
    ctx.obj["verbose"] = verbose
    ctx.obj["non_interactive"] = non_interactive
    ctx.obj["dry_run"] = dry_run
    output.configure_logging(verbose)
    output.help_if_no_command(ctx)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
