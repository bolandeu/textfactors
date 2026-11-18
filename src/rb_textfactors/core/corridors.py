"""Summarize the numeric metrics of a set of measured results by block."""

import math
import statistics

from .errors import InvalidArguments

BLOCKS = (
    "text",
    "headings",
    "links",
    "text_links",
    "title",
    "h1",
    "meta_description",
    "page",
)
ROUND_TO = 3
MeasureBlocks = dict[str, dict | None]


def select_blocks(blocks: list[str] | None) -> list[str]:
    """Use the standard page blocks when no explicit list was supplied."""
    if blocks is None:
        return list(BLOCKS)
    if not isinstance(blocks, list) or not all(isinstance(name, str) for name in blocks):
        raise InvalidArguments("blocks must be a list of block names or None.")
    return blocks


def measured_blocks(item: object, field: str) -> MeasureBlocks:
    """Extract a result's blocks, treating a missing or null map as absent."""
    if not isinstance(item, dict):
        raise InvalidArguments(f"{field} must contain a measure result object.")
    blocks = item.get("blocks")
    if blocks is None:
        return {}
    if not isinstance(blocks, dict) or not all(
        isinstance(name, str) and (block is None or isinstance(block, dict))
        for name, block in blocks.items()
    ):
        raise InvalidArguments(f"{field}.blocks must map block names to objects or null.")
    return blocks


def measured_set(items: list[dict]) -> list[MeasureBlocks]:
    """Extract the block maps from a non-empty set of results."""
    try:
        blocks = [measured_blocks(item, "items") for item in items]
    except TypeError as error:
        raise InvalidArguments("items must be a list of measure results.") from error
    if not blocks:
        raise InvalidArguments("items must contain at least one measure result.")
    return blocks


def numbers(block: dict | None) -> dict[str, float]:
    """Read numeric metrics, excluding boolean values and non-numeric metadata."""
    values: dict[str, float] = {}
    for name, value in (block or {}).items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if isinstance(value, float) and not math.isfinite(value):
                raise InvalidArguments("Metric values must be finite.")
            values[name] = value
    return values


def numbers_of(items: list[MeasureBlocks], block: str) -> dict[str, list[float]]:
    """Collect the values of each metric in first-appearance order."""
    values: dict[str, list[float]] = {}
    for item in items:
        for metric, value in numbers(item.get(block)).items():
            values.setdefault(metric, []).append(value)
    return values


def corridor(values: list[float]) -> dict[str, float]:
    """Compute six figures to three decimals, using nearest-rank quartiles."""
    ordered = sorted(values)
    size = len(ordered)
    figures = {
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "q25": ordered[math.ceil(0.25 * size) - 1],
        "q75": ordered[math.ceil(0.75 * size) - 1],
        "min": ordered[0],
        "max": ordered[-1],
    }
    return {name: round(figure, ROUND_TO) for name, figure in figures.items()}


def average(items: list[dict], *, blocks: list[str] | None) -> dict:
    """Build each block's corridor and report blocks carried by no item."""
    measured = measured_set(items)
    names = select_blocks(blocks)
    carried = {name: [item for item in measured if name in item] for name in names}
    return {
        "items": len(measured),
        "blocks": {
            name: {
                "count": len(carried[name]),
                "metrics": {
                    metric: corridor(values)
                    for metric, values in numbers_of(carried[name], name).items()
                },
            }
            for name in names
            if carried[name]
        },
        "skipped": [name for name in names if not carried[name]],
    }
