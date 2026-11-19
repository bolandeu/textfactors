"""Check a text for given keyword phrases: exact, lemma, diluted and reverse matches."""

from __future__ import annotations

from typing import Literal, TypedDict

import rb_semkit as sk

from .errors import InvalidArguments
from .metrics import TOKEN, _fold

DEFAULT_WINDOW = 3
Matcher = Literal["exact", "lemma", "diluted", "reverse", "any"]


class KeywordResult(TypedDict):
    keyword: str
    find: int
    density: float
    target: int | None
    met: bool | None


def _check_options(
    text: object,
    keywords: object,
    targets: object,
    exact: object,
    lemma: object,
    diluted: object,
    reverse: object,
    any_word: object,
    window: object,
) -> None:
    if not isinstance(text, str):
        raise InvalidArguments("text must be a string.")
    if not isinstance(keywords, list) or not all(isinstance(keyword, str) and keyword.strip() for keyword in keywords):
        raise InvalidArguments("keywords must be a list of non-blank strings.")
    if targets is not None:
        if not isinstance(targets, list) or len(targets) != len(keywords):
            raise InvalidArguments("targets must be a list with one value per keyword.")
        if not all(isinstance(target, int) and not isinstance(target, bool) and target >= 0 for target in targets):
            raise InvalidArguments("targets must be whole numbers of 0 or more.")
    if not all(isinstance(flag, bool) for flag in (exact, lemma, diluted, reverse, any_word)):
        raise InvalidArguments("exact, lemma, diluted, reverse and any_word must be true or false.")
    if not (exact or lemma or diluted or reverse or any_word):
        raise InvalidArguments("Enable at least one match type.")
    if isinstance(window, bool) or not isinstance(window, int) or window < 0:
        raise InvalidArguments("window must be a whole number of 0 or more.")


def _tokens(text: str) -> tuple[list[str], list[str]]:
    forms = [_fold(form) for form in TOKEN.findall(text)]
    lemmatizer = sk.SemtoolsLemmatizer()
    lemmas = [_fold(lemmatizer.lemma(form)) for form in forms]
    return forms, lemmas


def _phrase(keyword: str) -> tuple[list[str], list[str]]:
    forms, lemmas = _tokens(keyword)
    if not forms:
        raise InvalidArguments(f"Keyword {keyword!r} has no letters.")
    return forms, lemmas


def _span(lemmas: list[str], pattern: list[str], start: int, window: int) -> int | None:
    """Return the last index of an in-order match from start, allowing gaps of window words."""
    position = start
    for expected in pattern[1:]:
        limit = min(len(lemmas), position + window + 2)
        position += 1
        while position < limit and lemmas[position] != expected:
            position += 1
        if position >= limit:
            return None
    return position


def _count(
    forms: list[str],
    lemmas: list[str],
    phrase_forms: list[str],
    phrase_lemmas: list[str],
    *,
    exact: bool,
    lemma: bool,
    diluted: bool,
    reverse: bool,
    any_word: bool,
    window: int,
) -> int:
    size = len(phrase_lemmas)
    found = 0
    index = 0
    while index < len(lemmas):
        end: int | None = None
        if (exact and forms[index : index + size] == phrase_forms) or (
            lemma and lemmas[index : index + size] == phrase_lemmas
        ):
            end = index + size - 1
        elif diluted and lemmas[index] == phrase_lemmas[0]:
            end = _span(lemmas, phrase_lemmas, index, window)
        elif reverse and lemmas[index] == phrase_lemmas[-1]:
            end = _span(lemmas, phrase_lemmas[::-1], index, window)
        elif any_word and lemmas[index] in phrase_lemmas:
            end = index
        if end is None:
            index += 1
            continue
        found += 1
        index = end + 1
    return found


def check_keywords(
    text: str,
    keywords: list[str],
    *,
    targets: list[int] | None,
    exact: bool,
    lemma: bool,
    diluted: bool,
    reverse: bool,
    any_word: bool,
    window: int,
) -> dict:
    """Count each keyword phrase in the text and compare it with an optional target."""
    _check_options(text, keywords, targets, exact, lemma, diluted, reverse, any_word, window)
    forms, lemmas = _tokens(text)
    total = len(forms)
    rows: list[KeywordResult] = []
    for position, keyword in enumerate(keywords):
        phrase_forms, phrase_lemmas = _phrase(keyword)
        found = _count(
            forms,
            lemmas,
            phrase_forms,
            phrase_lemmas,
            exact=exact,
            lemma=lemma,
            diluted=diluted,
            reverse=reverse,
            any_word=any_word,
            window=window,
        )
        target = targets[position] if targets is not None else None
        rows.append(
            {
                "keyword": keyword,
                "find": found,
                "density": round(found / total * 100, 3) if total else 0.0,
                "target": target,
                "met": None if target is None else found >= target,
            }
        )
    return {
        "words_total": total,
        "keywords": rows,
        "found": sum(row["find"] > 0 for row in rows),
        "missing": sum(row["find"] == 0 for row in rows),
        "met": sum(row["met"] is True for row in rows),
        "unmet": sum(row["met"] is False for row in rows),
    }
