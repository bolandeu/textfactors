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
    any_word: bool = False,
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
        any_word: Count every occurrence of a single phrase word, whatever its form.
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
        any_word=any_word,
        window=window,
    )


def check_html_keywords(
    html: str,
    keywords: list[str] | None = None,
    *,
    block: str = "text",
    targets: list[int] | None = None,
    exact: bool = True,
    lemma: bool = True,
    diluted: bool = False,
    reverse: bool = False,
    any_word: bool = False,
    window: int = 3,
) -> dict:
    """Check keyword phrases in HTML after the same cleanup used for measurement.

    Args:
        html: Page content as a single argument. Scripts, menu, footer, reviews
            widgets, cookie banners and related-post blocks are removed first.
        keywords: Phrases to look for, in the order they should be reported.
        block: Zone to check: ``text``, ``headings``, ``links``, ``text_links``,
            ``title``, ``h1`` or ``meta_description``. Headings are separate zones,
            so ``text`` does not contain the H1 or H2 wording.
        targets: Required occurrences per keyword, one value per phrase. Omit to skip
            the pass/fail check and report counts only.
        exact: Count the phrase as written, ignoring case.
        lemma: Count the phrase in any grammatical form with words kept together.
        diluted: Count the phrase with up to ``window`` other words between its words.
        reverse: Count the phrase with its words in reverse order, gaps allowed.
        any_word: Count every occurrence of a single phrase word, whatever its form.
        window: Maximum number of extra words between phrase words for diluted and reverse.

    Returns:
        The checked block name, the per-keyword result from ``check_keywords``,
        and the page quality verdict.

    Raises:
        ValueError: The page is blank, the block or keyword options are invalid.
    """
    from .core import keywords as checks
    from .core.corridors import BLOCKS
    from .core.errors import InvalidArguments
    from .core.pages import page_texts

    if block not in BLOCKS:
        raise InvalidArguments("block must be one of: " + ", ".join(BLOCKS) + ".")
    if keywords is None:
        raise InvalidArguments("keywords are required.")
    texts = page_texts(html)
    result = checks.check_keywords(
        texts[block],
        keywords,
        targets=targets,
        exact=exact,
        lemma=lemma,
        diluted=diluted,
        reverse=reverse,
        any_word=any_word,
        window=window,
    )
    from .core.pages import _quality

    quality = _quality(html)
    return {
        "block": block,
        "words_total": result["words_total"],
        "keywords": result["keywords"],
        "found": result["found"],
        "missing": result["missing"],
        "met": result["met"],
        "unmet": result["unmet"],
        "quality": {"accepted": quality["accepted"], "score": quality["score"]},
    }


def keyword_targets(
    own: dict,
    items: list[dict],
    *,
    block: str = "text",
    share: float = 0.6,
    min_key_count: int = 1,
    min_length: int = 3,
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
        One row per keyword: own count, target count from the median peer density,
        the difference, peer coverage and that median density, plus block metadata.

    Raises:
        ValueError: The own result, the set, or an option is invalid.
    """
    from .core import targets

    return targets.keyword_targets(
        own,
        items,
        block=block,
        share=share,
        min_key_count=min_key_count,
        min_length=min_length,
        min_sites=min_sites,
    )
