"""Compare shared numeric metrics of two measured results."""

from typing import Literal, TypedDict

from .corridors import BLOCKS, ROUND_TO, MeasureBlocks, measured_blocks, numbers, select_blocks

MINIMUM = 0.08
Q75_FACTOR = 1.3
MEDIAN_FACTOR = 1.8
NO_VERDICT = ("water_percent", "nausea_classic", "nausea_academic", "zipf_quality", "ttr", "mtld")
Verdict = Literal["grow", "trim", "ok", "info"]
VERDICTS: tuple[Verdict, ...] = ("grow", "trim", "ok", "info")


class PairMetric(TypedDict):
    a: float
    b: float
    delta: float
    ratio: float
    verdict: Verdict


def verdict(metric: str, own: float, *, q25: float, q75: float, median: float) -> Verdict:
    """Judge against the reference corridor; six metrics always carry information only."""
    if metric in NO_VERDICT:
        return "info"
    if own < max(MINIMUM, q25):
        return "grow"
    if own > max(q75 * Q75_FACTOR, median * MEDIAN_FACTOR):
        return "trim"
    return "ok"


def _carried(a: MeasureBlocks, b: MeasureBlocks) -> list[str]:
    names = dict.fromkeys((*a, *b))
    return [name for name in BLOCKS if name in names] + [name for name in names if name not in BLOCKS]


def _pair(metric: str, a: float, b: float) -> PairMetric:
    return {
        "a": a,
        "b": b,
        "delta": round(a - b, ROUND_TO),
        "ratio": round(a / b, ROUND_TO) if b > 0 else 0.0,
        "verdict": verdict(metric, a, q25=b, q75=b, median=b),
    }


def _block(a: dict | None, b: dict | None) -> dict[str, PairMetric]:
    left, right = numbers(a), numbers(b)
    return {metric: _pair(metric, value, right[metric]) for metric, value in left.items() if metric in right}


def compare(a: dict, b: dict, *, blocks: list[str] | None) -> dict:
    """Compare blocks carried by both sides and skip those missing on either side."""
    left, right = measured_blocks(a, "a"), measured_blocks(b, "b")
    names = _carried(left, right) if blocks is None else select_blocks(blocks)
    return {
        "blocks": {name: _block(left[name], right[name]) for name in names if name in left and name in right},
        "skipped": [name for name in names if name not in left or name not in right],
    }
