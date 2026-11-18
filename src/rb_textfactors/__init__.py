"""Public Python API for rb-textfactors: measure, compare and check keywords."""

from .operations import (
    average,
    check_html_keywords,
    check_keywords,
    compare,
    compare_with_set,
    keyword_targets,
    measure_html,
    measure_text,
)

__all__ = [
    "average",
    "check_html_keywords",
    "check_keywords",
    "compare",
    "compare_with_set",
    "keyword_targets",
    "measure_html",
    "measure_text",
]
