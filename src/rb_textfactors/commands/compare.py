"""The `average`, `compare` and `compare-set` commands: a corridor of a set and one page against it."""

from __future__ import annotations

import typer

from .. import output
from ..operations import average, compare, compare_with_set
from . import _input

ItemOption = typer.Option(..., "--item", help="One measure result as a JSON object; repeat for a set.")
BlockOption = typer.Option(None, "--block", help="Block name to use; repeat for several. Omit for the standard seven.")
ShareOption = typer.Option(0.6, "--share", help="Minimum share of the set carrying a key, 0 < share <= 1.")
MinKeyCountOption = typer.Option(
    2, "--min-key-count", help="Occurrences of a key in one item to count toward its share."
)


@output.guard
def average_command(
    ctx: typer.Context,
    item: list[str] = ItemOption,
    block: list[str] = BlockOption,
    json_output: bool = output.JsonOption,
    quiet: bool = output.QuietOption,
) -> None:
    """Compute the mean, median, quartiles, minimum and maximum of each metric over a set.

    Example: {cli} average --item @a.json --item @b.json
    """
    del json_output, quiet  # read by output.guard through the context
    result = average(_input.load_items(item), blocks=list(block) if block else None)
    output.emit_success(ctx, result, _input.human("averages", ("items",)))


@output.guard
def compare_command(
    ctx: typer.Context,
    own: str = typer.Argument(..., help="The result to judge, as a JSON object."),
    reference: str = typer.Argument(..., help="The reference result, as a JSON object."),
    block: list[str] = BlockOption,
    json_output: bool = output.JsonOption,
    quiet: bool = output.QuietOption,
) -> None:
    """Compare two measured results by delta, ratio and verdict.

    Example: {cli} compare @own.json @reference.json
    """
    del json_output, quiet  # read by output.guard through the context
    result = compare(
        _input.load(own, "own"), _input.load(reference, "reference"), blocks=list(block) if block else None
    )
    output.emit_success(ctx, result, _input.human("comparison", ("blocks",)))


@output.guard
def compare_set_command(
    ctx: typer.Context,
    own: str = typer.Argument(..., help="The result to judge, as a JSON object."),
    item: list[str] = ItemOption,
    block: list[str] = BlockOption,
    share: float = ShareOption,
    min_key_count: int = MinKeyCountOption,
    json_output: bool = output.JsonOption,
    quiet: bool = output.QuietOption,
) -> None:
    """Compare one measured result against a set and report the keys it misses.

    Example: {cli} compare-set @own.json --item @a.json --item @b.json
    """
    del json_output, quiet  # read by output.guard through the context
    result = compare_with_set(
        _input.load(own, "own"),
        _input.load_items(item),
        share=share,
        blocks=list(block) if block else None,
        min_key_count=min_key_count,
    )
    output.emit_success(ctx, result, _input.human("missing keys", ("items", "missing")))
