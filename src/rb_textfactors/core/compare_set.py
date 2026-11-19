"""Judge one measured result against a set and find missing repeat keys."""

import math
import statistics
from typing import TypedDict

from .compare_pair import VERDICTS, Verdict, verdict
from .corridors import (
    ROUND_TO,
    MeasureBlocks,
    corridor,
    measured_blocks,
    measured_set,
    numbers,
    numbers_of,
    select_blocks,
)
from .errors import InvalidArguments

KEY_BLOCKS = ("text", "text_links")


class SetMetric(TypedDict):
    own: float
    median: float
    q25: float
    q75: float
    min: float
    max: float
    delta: float
    verdict: Verdict


class MissingKey(TypedDict):
    block: str
    key: str
    share: float
    density: float


def _check_options(share: float, min_key_count: int) -> None:
    if isinstance(share, bool) or not isinstance(share, (int, float)) or not 0 < share <= 1:
        raise InvalidArguments("share must satisfy 0 < share <= 1.")
    if isinstance(min_key_count, bool) or not isinstance(min_key_count, int):
        raise InvalidArguments("min_key_count must be a whole number.")


def _figures(metric: str, own: float, values: list[float]) -> SetMetric:
    figures = corridor(values)
    own = round(own, ROUND_TO)
    median, q25, q75 = figures["median"], figures["q25"], figures["q75"]
    return {
        "own": own,
        "median": median,
        "q25": q25,
        "q75": q75,
        "min": figures["min"],
        "max": figures["max"],
        "delta": round(own - median, ROUND_TO),
        "verdict": verdict(metric, own, q25=q25, q75=q75, median=median),
    }


def _block(own: MeasureBlocks, items: list[MeasureBlocks], name: str) -> dict[str, SetMetric]:
    mine = numbers(own.get(name))
    return {metric: _figures(metric, mine.get(metric, 0), values) for metric, values in numbers_of(items, name).items()}


def _keys(block: dict | None) -> dict[str, dict]:
    table = (block or {}).get("repeat_words_1") or []
    if not isinstance(table, (list, tuple)):
        raise InvalidArguments("repeat_words_1 must be a list of repeat rows.")
    keys: dict[str, dict] = {}
    for row in table:
        if not isinstance(row, dict) or "key" not in row:
            continue
        key = row["key"]
        if not isinstance(key, str):
            raise InvalidArguments("A repeat row's key must be a string.")
        keys[key] = row
    return keys


def _row_number(row: dict, field: str) -> float:
    value = row.get(field, 0)
    if not isinstance(value, (int, float)) or (isinstance(value, float) and not math.isfinite(value)):
        raise InvalidArguments(f"A repeat row's {field} must be a finite number.")
    return value


def _missing(own: MeasureBlocks, items: list[MeasureBlocks], share: float, min_key_count: int) -> list[MissingKey]:
    rows: list[MissingKey] = []
    for name in KEY_BLOCKS:
        mine = _keys(own.get(name))
        found: dict[str, list[float]] = {}
        pages = 0
        for item in items:
            block = item.get(name)
            if block is None:
                continue
            pages += 1
            for key, row in _keys(block).items():
                if _row_number(row, "count") >= min_key_count:
                    found.setdefault(key, []).append(_row_number(row, "density"))
        for key, densities in found.items():
            part = len(densities) / pages
            if part >= share and key not in mine:
                rows.append(
                    {
                        "block": name,
                        "key": key,
                        "share": round(part, ROUND_TO),
                        "density": round(statistics.median(densities), ROUND_TO),
                    }
                )
    return sorted(rows, key=lambda row: (-row["density"], row["key"]))


def compare_with_set(
    own: dict,
    items: list[dict],
    *,
    share: float,
    blocks: list[str] | None,
    min_key_count: int,
) -> dict:
    """Return corridor comparisons, verdict counts, and keys missing from own."""
    measured = measured_set(items)
    names = select_blocks(blocks)
    mine = measured_blocks(own, "own")
    _check_options(share, min_key_count)
    compared = [name for name in names if name in mine and any(name in item for item in measured)]
    figures = {name: _block(mine, measured, name) for name in compared}
    verdicts = dict.fromkeys(VERDICTS, 0)
    for block in figures.values():
        for metric in block.values():
            verdicts[metric["verdict"]] += 1
    return {
        "items": sum(any(name in item for name in compared) for item in measured),
        "blocks": figures,
        "verdicts": verdicts,
        "missing_keys": _missing(mine, measured, share, min_key_count),
        "skipped": [name for name in names if name not in compared],
    }
