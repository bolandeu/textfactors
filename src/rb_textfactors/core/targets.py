"""Turn peer keyword densities into occurrence targets for one page."""

from __future__ import annotations

import statistics
from typing import TypedDict

from .corridors import ROUND_TO, measured_blocks, measured_set
from .errors import InvalidArguments

DEFAULT_SHARE = 0.6
DEFAULT_MIN_LENGTH = 3


class KeywordTarget(TypedDict):
    keyword: str
    own: int
    target: int
    add: int
    peers: int
    share: float
    density: float


def _check_options(block: str, share: float, min_key_count: int, min_length: int) -> None:
    if not isinstance(block, str) or not block:
        raise InvalidArguments("block must be a non-empty block name.")
    if isinstance(share, bool) or not isinstance(share, (int, float)) or not 0 < share <= 1:
        raise InvalidArguments("share must satisfy 0 < share <= 1.")
    for name, value in (("min_key_count", min_key_count), ("min_length", min_length)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise InvalidArguments(f"{name} must be a whole number of 0 or more.")


def _table(block: dict | None) -> dict[str, dict]:
    rows = (block or {}).get("repeat_words_1") or []
    if not isinstance(rows, (list, tuple)):
        raise InvalidArguments("repeat_words_1 must be a list of repeat rows.")
    table: dict[str, dict] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("key"), str):
            table[row["key"]] = row
    return table


def _count(block: dict | None) -> int:
    value = (block or {}).get("words_total", 0)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InvalidArguments("words_total must be a number.")
    return int(value)


def keyword_targets(
    own: dict,
    items: list[dict],
    *,
    block: str = "text",
    share: float = DEFAULT_SHARE,
    min_key_count: int = 1,
    min_length: int = DEFAULT_MIN_LENGTH,
    min_sites: int = 0,
) -> dict:
    """Compute how many occurrences each peer keyword needs on the own page.

    Args:
        own: The measured result to improve, with a blocks mapping.
        items: Reference results with blocks mappings.
        block: Block whose repeat table is used; ``text`` by default.
        share: Minimum share of reference pages that must carry the keyword.
        min_key_count: Minimum occurrences of a keyword in one reference page.
        min_length: Minimum keyword length in characters; drops stray letters.
        min_sites: Include a keyword carried by at least this many pages even below
            ``share``. Zero disables the rule.

    Returns:
        The block, its word count, and one row per keyword with the own count, the
        target count from the median peer density, the difference, peer coverage
        and that median density. Rows with nothing to add are kept with ``add: 0``.

    Raises:
        ValueError: The own result, the set, or an option is invalid.
    """
    _check_options(block, share, min_key_count, min_length)
    if isinstance(min_sites, bool) or not isinstance(min_sites, int) or min_sites < 0:
        raise InvalidArguments("min_sites must be a whole number of 0 or more.")
    mine = measured_blocks(own, "own")
    references = measured_set(items)
    page = mine.get(block)
    if page is None:
        raise InvalidArguments(f"own result has no {block} block.")
    words = _count(page)
    current = {key: row for key, row in _table(page).items()}
    pages = [item[block] for item in references if item.get(block) is not None]
    if not pages:
        raise InvalidArguments(f"no reference result carries the {block} block.")
    found: dict[str, list[float]] = {}
    for reference in pages:
        for key, row in _table(reference).items():
            if not isinstance(row.get("count"), (int, float)):
                continue
            if row["count"] >= min_key_count and len(key) >= min_length:
                density = row.get("density", 0)
                if isinstance(density, (int, float)) and not isinstance(density, bool):
                    found.setdefault(key, []).append(float(density))
    rows: list[KeywordTarget] = []
    for key, densities in found.items():
        coverage = len(densities) / len(pages)
        if coverage < share and not (min_sites and len(densities) >= min_sites):
            continue
        median = statistics.median(densities)
        target = round(median * words / 100)
        have = current.get(key, {}).get("count", 0)
        have = int(have) if isinstance(have, (int, float)) and not isinstance(have, bool) else 0
        rows.append(
            {
                "keyword": key,
                "own": have,
                "target": target,
                "add": max(0, target - have),
                "peers": len(densities),
                "share": round(coverage, ROUND_TO),
                "density": round(median, ROUND_TO),
            }
        )
    rows.sort(key=lambda row: (-row["add"], -row["peers"], row["keyword"]))
    return {"block": block, "words_total": words, "items": len(pages), "keywords": rows}
