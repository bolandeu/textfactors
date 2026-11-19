"""The `auth` command group: `status` reports the health of the credentials of every provider, or an empty report when
the package has none.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime

import typer

from .. import output
from ..core.errors import InvalidArguments
from ..core.version import DEV_VERSION, cli_name, installed_version, module_exists, optional_module

# `auth status` exists in every CLI (the Standard, Health); a CLI
# generated without credentials (no credentials/ package, no commands/login.py)
# reports an empty `credentials` list and exits 0. Detected at runtime so this
# file needs no template logic — same approach as doctor.py.
_PACKAGE_NAME = __name__.split(".")[0]
_HAS_CREDENTIALS = module_exists(f"{_PACKAGE_NAME}.credentials.manager")

app = output.group("Credentials: report their health (and store them, if this CLI has any).")


@app.command("status")
@output.guard
def auth_status(
    ctx: typer.Context,
    check: bool = typer.Option(
        False, "--check", help="Also make one cheap read-only call per provider (10 s timeout) to prove each works."
    ),
    provider: str | None = typer.Option(
        None, "--provider", help="Report only this provider, or one target as <kind>:<target> (default: all)."
    ),
    json_output: bool = output.JsonOption,
    quiet: bool = output.QuietOption,
) -> None:
    """Report every provider's credential: where it comes from and whether it works. Never prints values.

    Without --check only presence is reported (status `unchecked` or `missing`).
    Exits 0 when every required provider is ok/unchecked (an optional one may be
    missing), 3 when any required provider has a problem or any credential is
    invalid/expired, 2 on a usage error. A per-target provider (one credential per
    site/host/account) gets one entry per stored target, named `<kind>:<target>`. The --json shape is a cross-tool contract:
    `tool`, `version`, `checked_at`, `credentials[]` with `provider`, `required`,
    `fields`, `source`, `source_ref`, `status`, `expires_at`, `quota`, `message`.

    Example: {cli} auth status --check --json
    """
    tool, version = cli_name(), installed_version() or DEV_VERSION
    if not _HAS_CREDENTIALS:
        if provider is not None:
            raise InvalidArguments(f"Unknown provider '{provider}' ({tool} stores no credentials).")
        checked_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        payload = {"tool": tool, "version": version, "checked_at": checked_at, "credentials": []}
        output.emit_report(ctx, payload, lambda _: output.human.echo(f"{tool} stores no credentials."), None)
        return
    health = importlib.import_module(f"{_PACKAGE_NAME}.credentials.health")
    payload, problem = health.status(tool, version, check=check, only=provider)
    output.emit_report(ctx, payload, health.render, problem)


if _login := optional_module(f"{_PACKAGE_NAME}.commands.login"):
    app.command("login")(_login.login)
    app.command("logout")(_login.logout)
