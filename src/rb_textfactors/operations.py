"""Read-only operations shared by the Python API and the generated CLI."""

from __future__ import annotations


def measure_text(
    text: str,
    *,
    ignore_words: list[str] | None = None,
    stop_phrases: list[str] | None = None,
    top_n: int = 0,
) -> dict:
    """Measure plain text: twelve metrics, three norms and three repeat tables.

    Args:
        text: Plain text as a single argument. Empty text gives zero counts.
        ignore_words: Exact word forms without weight; omit to use default units and abbreviations.
        stop_phrases: Phrases to remove before counting, matched case-insensitively.
        top_n: Maximum rows per repeat table, or 0 for all. Density uses the full count.

    Returns:
        A plain dictionary containing metrics, norms and repeat tables for one block.

    Raises:
        ValueError: An option is invalid.
    """
    from .core.metrics import measure_text as measure

    return measure(text, ignore_words=ignore_words, stop_phrases=stop_phrases, top_n=top_n)


def measure_html(
    html: str,
    *,
    ignore_words: list[str] | None = None,
    stop_phrases: list[str] | None = None,
    top_n: int = 0,
) -> dict:
    """Measure the seven blocks, structure and content quality of an HTML page.

    Args:
        html: Page content as a single argument, not a URL or a filename.
        ignore_words: Exact word forms without weight; omit to use default units and abbreviations.
        stop_phrases: Phrases to remove before counting, matched case-insensitively.
        top_n: Maximum rows per repeat table in each block, or 0 for all.

    Returns:
        A plain dictionary with blocks, structure and quality. Rejected pages still have blocks.

    Raises:
        ValueError: The page is blank or an option is invalid.
    """
    from .core.pages import measure_html as measure

    return measure(html, ignore_words=ignore_words, stop_phrases=stop_phrases, top_n=top_n)


def average(items: list[dict], *, blocks: list[str] | None = None) -> dict:
    """Compute the mean, median, quartiles, minimum and maximum of each metric.

    Args:
        items: Measure results with a blocks mapping. On the CLI, pass one JSON object per item.
        blocks: Block names to include; omit to use the seven standard page blocks.

    Returns:
        The item count, the corridor of each numeric metric by block, and skipped block names.

    Raises:
        ValueError: The set is empty or an argument is invalid.
    """
    from .core import corridors

    return corridors.average(items, blocks=blocks)


def compare(a: dict, b: dict, *, blocks: list[str] | None = None) -> dict:
    """Compare two measured results by delta, ratio and verdict.

    Args:
        a: The result to judge, with a blocks mapping. On the CLI, pass one JSON object.
        b: The reference result, with a blocks mapping. On the CLI, pass one JSON object.
        blocks: Block names to compare; omit to consider blocks carried by either result.

    Returns:
        Comparisons for shared numeric metrics by block, and skipped block names.

    Raises:
        ValueError: An argument is invalid.
    """
    from .core import compare_pair

    return compare_pair.compare(a, b, blocks=blocks)


def compare_with_set(
    own: dict,
    items: list[dict],
    *,
    share: float = 0.6,
    blocks: list[str] | None = None,
    min_key_count: int = 2,
) -> dict:
    """Compare one measured result against a set and report missing keys.

    Args:
        own: The result to judge, with a blocks mapping. On the CLI, pass one JSON object.
        items: Reference results with blocks mappings. On the CLI, pass one JSON object per item.
        share: Minimum share of reference items carrying a key, greater than 0 and at most 1.
        blocks: Block names to compare numerically; omit to use the seven standard page blocks.
        min_key_count: Minimum occurrences of a key in one reference item to count toward its share.

    Returns:
        Per-block corridor comparisons, verdict counts, missing keys, and skipped block names.
        Missing keys come from the text and text_links repeat tables regardless of blocks.

    Raises:
        ValueError: The set is empty or an argument is invalid.
    """
    from .core import compare_set

    return compare_set.compare_with_set(
        own, items, share=share, blocks=blocks, min_key_count=min_key_count
    )


def check_keywords(
    text: str,
    keywords: list[str],
    *,
    targets: list[int] | None = None,
    exact: bool = True,
    lemma: bool = True,
    diluted: bool = False,
    reverse: bool = False,
    window: int = 3,
) -> dict:
    """Count given keyword phrases in a text and check them against occurrence targets.

    Args:
        text: Plain text as a single argument. Pass the measured ``blocks.text`` content,
            not raw HTML: markup and page chrome would add false matches.
        keywords: Phrases to look for, in the order they should be reported.
        targets: Required occurrences per keyword, one value per phrase. Omit to skip
            the pass/fail check and report counts only.
        exact: Count the phrase as written, ignoring case.
        lemma: Count the phrase in any grammatical form with words kept together.
        diluted: Count the phrase with up to ``window`` other words between its words.
        reverse: Count the phrase with its words in reverse order, gaps allowed.
        window: Maximum number of extra words between phrase words for diluted and reverse.

    Returns:
        Word count, one row per keyword with found count, density, target and result,
        plus totals for found, missing, met and unmet keywords.

    Raises:
        ValueError: The text, keyword list, target list or an option is invalid.
    """
    from .core.keywords import check_keywords as check

    return check(
        text,
        keywords,
        targets=targets,
        exact=exact,
        lemma=lemma,
        diluted=diluted,
        reverse=reverse,
        window=window,
    )
