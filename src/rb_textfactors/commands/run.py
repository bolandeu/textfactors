"""The `run` command: the example action of the template, where a package puts its own work."""

from __future__ import annotations

import typer

from .. import output


@output.guard
def run(
    ctx: typer.Context,
    json_output: bool = output.JsonOption,
    quiet: bool = output.QuietOption,
    dry_run: bool = output.DryRunOption,
) -> None:
    """Execute the project's main operation.

    Extension point: replace this body with a call into core.services (or a
    provider) for this CLI's actual business logic.

    If the real implementation changes external state, keep this shape:
    check `output.is_dry_run(ctx)` first and return a preview instead of
    acting, and — if the action is destructive/irreversible — call
    `output.require_confirmation(ctx, "...", confirm)` right before the
    change itself (never before the dry-run preview).

    Example: {cli} run --dry-run
    """
    if output.is_dry_run(ctx):
        output.emit_success(
            ctx,
            {"result": "dry-run", "would_do": "nothing implemented yet — this is a placeholder"},
            render_human=lambda d: output.human.echo("Dry run: no changes made (placeholder operation)."),
        )
        return

    output.emit_success(
        ctx, {"result": "not implemented"}, render_human=lambda d: output.human.echo("run: not implemented yet")
    )
