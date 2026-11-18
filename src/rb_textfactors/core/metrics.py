"""Measure text volume, variety, water, nausea and repeat frequencies."""

import math
import re
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise
from typing import Protocol, TypedDict

import pandas as pd
import rb_semkit as sk

from .errors import InvalidArguments

TOKEN = re.compile(r"[а-яёa-z]+(?:-[а-яёa-z]+)*", re.IGNORECASE)
SENTENCE = re.compile(r"[.!?…\n]+")
DEFAULT_IGNORE_WORDS = ("рублей", "руб", "стр", "ул", "шт", "см", "мм", "мл", "кг", "кв")


class _StopWords(Protocol):
    def picks(self, words: list[str]) -> list[bool]: ...


class _Lemmatizer(Protocol):
    def lemma(self, word: str) -> str: ...


@dataclass(frozen=True)
class Word:
    form: str
    lemma: str
    stop: bool
    ignore: bool

    @property
    def counts(self) -> bool:
        return not (self.stop or self.ignore)


class RepeatRow(TypedDict):
    key: str
    count: int
    density: float
    example: str


def _fold(word: str) -> str:
    return word.lower().replace("ё", "е")


def _cut(text: str, phrases: list[str]) -> str:
    for phrase in phrases:
        words = phrase.split()
        if words:
            pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, words)) + r"(?!\w)"
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return text


def _words(part: str, ignore: frozenset[str], stops: _StopWords, lemmas: _Lemmatizer) -> list[Word]:
    forms = TOKEN.findall(part)
    is_stop = stops.picks([_fold(form) for form in forms])
    return [
        Word(form, lemmas.lemma(form), stop, _fold(form) in ignore)
        for form, stop in zip(forms, is_stop, strict=True)
    ]


def _grams(clauses: list[list[Word]], n: int) -> Counter[str]:
    """Count runs of n content words, keeping intervening stop or ignore words in the key."""
    found: Counter[str] = Counter()
    for words in clauses:
        places = [index for index, word in enumerate(words) if word.counts]
        for start in range(len(places) - n + 1):
            span = words[places[start] : places[start + n - 1] + 1]
            if any(left.lemma == right.lemma for left, right in pairwise(span)):
                continue
            found[" ".join(word.lemma for word in span)] += 1
    return found


def _words_table(sentences: list[list[Word]]) -> tuple[Counter[str], dict[str, list[str]]]:
    found: Counter[str] = Counter()
    forms: dict[str, list[str]] = {}
    for words in sentences:
        for word in words:
            if word.counts:
                found[word.lemma] += 1
                seen = forms.setdefault(word.lemma, [])
                if word.form not in seen:
                    seen.append(word.form)
    return found, forms


def _rows(
    found: Counter[str], forms: dict[str, list[str]] | None, words_count: int, top_n: int
) -> list[RepeatRow]:
    rows: list[RepeatRow] = [
        {
            "key": key,
            "count": count,
            "density": round(count / words_count * 100, 3) if words_count else 0.0,
            "example": ", ".join(forms[key]) if forms else key,
        }
        for key, count in found.items()
    ]
    rows.sort(key=lambda row: row["count"], reverse=True)  # Keep first appearance on ties.
    return rows[:top_n] if top_n else rows


def _stop_rows(stops: Counter[str], words_total: int, top_n: int) -> list[dict]:
    rows = [
        {
            "word": word,
            "count": count,
            "density": round(count / words_total * 100, 3) if words_total else 0.0,
        }
        for word, count in stops.items()
    ]
    rows.sort(key=lambda row: row["count"], reverse=True)
    return rows[:top_n] if top_n else rows


def _norms(classic: float, academic: float, water: float) -> dict[str, str]:
    if academic < 3:
        academic_label = "мало повторов"
    elif academic <= 9:
        academic_label = "в норме"
    elif academic <= 12:
        academic_label = "повышенная"
    else:
        academic_label = "переспам"
    return {
        "nausea_classic": "в норме"
        if classic <= 4
        else "повышенная"
        if classic <= 7
        else "переспам",
        "nausea_academic": academic_label,
        "water_percent": "мало воды"
        if water < 10
        else "в норме"
        if water <= 25
        else "многовато воды",
    }


def _check_options(
    ignore_words: list[str] | None, stop_phrases: list[str] | None, top_n: int
) -> None:
    for name, values in (("ignore_words", ignore_words), ("stop_phrases", stop_phrases)):
        if values is not None and (
            not isinstance(values, list) or not all(isinstance(value, str) for value in values)
        ):
            raise InvalidArguments(f"{name} must be a list of strings or None.")
    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 0:
        raise InvalidArguments("top_n must be an integer of 0 or more.")


def measure_text(
    text: str,
    *,
    ignore_words: list[str] | None,
    stop_phrases: list[str] | None,
    top_n: int,
) -> dict:
    """Count one text, retaining the reference's token, lemma and clause rules."""
    if not isinstance(text, str):
        raise InvalidArguments("text must be a string.")
    _check_options(ignore_words, stop_phrases, top_n)
    excluded = DEFAULT_IGNORE_WORDS if ignore_words is None else ignore_words
    ignore = frozenset(_fold(word) for word in excluded)
    cut = _cut(text, stop_phrases or [])
    stop_words, lemmatizer = sk.stopwords(), sk.SemtoolsLemmatizer()
    sentences = [
        words
        for part in SENTENCE.split(cut)
        if (words := _words(part, ignore, stop_words, lemmatizer))
    ]
    series = pd.Series([cut])
    clauses = [_words(phrase, ignore, stop_words, lemmatizer) for phrase in sk.split_text(series)]
    words_total = sum(len(words) for words in sentences)
    stops = sum(word.stop for words in sentences for word in words)
    ignored = sum(word.ignore for words in sentences for word in words)
    found, forms = _words_table(sentences)
    stop_counter = Counter(
        word.lemma for words in sentences for word in words if word.stop and not word.ignore
    )
    words_count = words_total - stops - ignored
    roots = len(found)
    top = max(found.values(), default=0)
    water = round(100 * stops / words_total, 2) if words_total else 0.0
    classic = round(math.sqrt(top), 2)
    academic = round(100 * top / words_total, 2) if words_total else 0.0
    stats = sk.text_stats(series, no_digits=True, exclude=sorted(ignore)).iloc[0]
    mtld = float(stats["mtld"])
    return {
        "length": len(text),
        "length_trim": len("".join(text.split())),
        "sentences": len(sentences),
        "words_total": words_total,
        "words_count": words_count,
        "words_root_count": roots,
        "water_percent": water,
        "nausea_classic": classic,
        "nausea_academic": academic,
        "zipf_quality": float(stats["zipf"]),
        "ttr": round(roots / words_count, 3) if words_count else 0.0,
        "mtld": mtld or (float(roots) if roots > 1 else 0.0),
        "norms": _norms(classic, academic, water),
        "stop_words": _stop_rows(stop_counter, words_total, top_n),
        "repeat_words_1": _rows(found, forms, words_count, top_n),
        "repeat_words_2": _rows(_grams(clauses, 2), None, words_count, top_n),
        "repeat_words_3": _rows(_grams(clauses, 3), None, words_count, top_n),
    }
