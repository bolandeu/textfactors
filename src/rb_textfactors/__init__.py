"""Public Python API for rb-textfactors: measure, compare and check keywords."""

from .operations import (
    average,
    check_keywords,
    compare,
    compare_with_set,
    measure_html,
    measure_text,
)

__all__ = [
    "average",
    "check_keywords",
    "compare",
    "compare_with_set",
    "measure_html",
    "measure_text",
]
