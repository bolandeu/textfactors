"""Extract and measure the blocks, structure and quality of supplied HTML."""

from __future__ import annotations

import re
import warnings
from collections import Counter
from typing import TypedDict

import pandas as pd
from selectolax.lexbor import LexborHTMLParser

from . import metrics
from .corridors import BLOCKS
from .errors import InvalidArguments

# Semkit imports Trafilatura's downloader even when parsing supplied HTML offline.
with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="SOCKS support in urllib3 requires the installation of optional dependencies",
        module=r"urllib3\.contrib\.socks$",
    )
    from rb_semkit import headings as extract_headings
    from rb_semkit import parse_html

NOISE = (
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "nav",
    "footer",
    "aside",
    "form",
    "button",
    "select",
    "option",
    "dialog",
    ".rb-reviews-widget",
    ".rb-reviews",
    ".ti-widget",
    ".wp-gr",
    ".wp-google-review",
    "[class*='reviews-widget']",
    "[class*='review-widget']",
    ".cookie-notification",
    "#cookie-notice",
    "#cookie-law-info-bar",
    "#onetrust-banner-sdk",
    "[class*='cookie-consent']",
    "[class*='cookies-consent']",
    ".ct-related-posts",
    ".ct-share-box",
    ".post-navigation",
    ".ct-breadcrumbs",
    ".ct-header",
    ".rb-sitemap",
    "[role='navigation']",
    "[role='contentinfo']",
    "[hidden]",
    "[aria-hidden='true']",
)
NOINDEX_COMMENT = re.compile(
    r"<!--\s*noindex\s*-->.*?<!--\s*/noindex\s*-->", re.DOTALL | re.IGNORECASE
)
TOKEN = re.compile(r"[а-яёa-z]+(?:-[а-яёa-z]+)*")
VISIBLE = re.compile(r"[^\W_]")
ANTIBOT = (
    "cf-chl",
    "challenge-platform",
    "cf-turnstile",
    "g-recaptcha",
    "h-captcha",
    "data-sitekey",
    "checking your browser",
    "anti-bot",
)
STUB = (
    "just a moment",
    "enable javascript",
    "access denied",
    "site under construction",
    "domain for sale",
    "verify you are human",
    "идет загрузка",
    "идёт загрузка",
    "antibot cloud",
)
FLAG_REASON = {
    "antibot": "антибот-проверка",
    "stub": "заглушка вместо текста",
    "script_dominated": "текст подменён скриптами",
    "repeated_blocks": "повторяющиеся блоки",
}
SCRIPT_SHARE = 0.72
MIN_CHARS = 240
MIN_WORDS = 35
MIN_UNIQUE_WORDS = 18
MIN_SCORE = 42


class Heading(TypedDict):
    level: int
    text: str
    children: list[Heading]


def _noise_cut(html: str, *, noindex: bool) -> str:
    source = NOINDEX_COMMENT.sub(" ", html) if noindex else html
    tree = LexborHTMLParser(source)
    # Remove standalone contact panels, never a service section merely containing a form.
    contact_titles = {"свяжитесь с нами", "обратная связь", "заказать звонок", "contact us"}
    for node in reversed(tree.css("article, section")):
        headings = node.css("h1, h2, h3, h4, h5, h6")
        if (
            node.css_first("form") is not None
            and headings
            and any(
                heading.tag != "h1" and heading.text().strip().lower() in contact_titles
                for heading in headings
            )
        ):
            node.decompose()
    selector = ", ".join((*NOISE, "noindex") if noindex else NOISE)
    # Remove descendants first so recursive decomposition never invalidates a later node.
    for node in reversed(tree.css(selector)):
        node.decompose()
    return tree.html or ""


def _headings(clean: str) -> list[tuple[int, str]]:
    rows = extract_headings(pd.Series([clean]))
    return [(int(level[1:]), text) for level, text in zip(rows["level"], rows["text"], strict=True)]


def _without_headings(text: str, headings: list[tuple[int, str]]) -> str:
    for _, heading in headings:
        if heading:
            text = text.replace(heading, " ", 1)
    return " ".join(text.split())


def _page_text(html: str) -> str:
    """All visible page text: menu, footer and widgets included, scripts excluded."""
    tree = LexborHTMLParser(html)
    for node in reversed(tree.css("script, style, noscript, template, svg, canvas")):
        node.decompose()
    body = tree.body
    return " ".join((body.text(separator=" ") or "").split()) if body is not None else ""


def _blocks(html: str, clean: str, headings: list[tuple[int, str]]) -> dict[str, str]:
    if "<" not in html:
        plain = " ".join(html.split())
        blocks = {name: plain if name in ("text", "text_links") else "" for name in BLOCKS}
        blocks["page"] = plain
        return blocks
    page = parse_html(pd.Series([clean]), drop_noindex=True).iloc[0]
    return {
        "text": _without_headings(page["text"], headings),
        "headings": " ".join(text for level, text in headings if level != 1),
        "links": page["links"],
        "text_links": page["all"],
        "title": page["title"],
        "h1": page["h1"],
        "meta_description": page["description"],
        "page": _page_text(html),
    }


def page_texts(html: str) -> dict[str, str]:
    """Return the seven cleaned block texts that measure_html counts."""
    if not isinstance(html, str) or not html.strip():
        raise InvalidArguments("html must be a non-blank string.")
    clean = _noise_cut(html, noindex=True)
    return _blocks(html, clean, _headings(clean))


def _heading_tree(headings: list[tuple[int, str]]) -> list[Heading]:
    tree: list[Heading] = []
    stack: list[Heading] = []
    for level, text in headings:
        node: Heading = {"level": level, "text": text, "children": []}
        while stack and stack[-1]["level"] >= level:
            stack.pop()
        (stack[-1]["children"] if stack else tree).append(node)
        stack.append(node)
    return tree


def _structure(clean: str, headings: list[tuple[int, str]]) -> dict:
    tree = LexborHTMLParser(clean)
    levels = Counter(level for level, _ in headings)
    structure: dict[str, object] = {f"h{level}_count": levels[level] for level in range(1, 7)}
    structure["li_count"] = len(tree.css("li"))
    structure["table_count"] = len(tree.css("table"))
    structure["heading_tree"] = _heading_tree(headings)
    return structure


def _flags(html: str, text: str, words: int, unique_words: int) -> list[str]:
    found: list[str] = []
    raw = html.lower()
    # A widget inside JS is not a wall: a marker counts only when visible text is a stub.
    lowered = text.lower()
    stub_text = any(marker in lowered for marker in STUB)
    if any(marker in raw for marker in ANTIBOT) and stub_text:
        found.append("antibot")
    if stub_text:
        found.append("stub")
    script_chars = sum(len(node.text() or "") for node in LexborHTMLParser(html).css("script"))
    if script_chars > SCRIPT_SHARE * len(html) and words < 120:
        found.append("script_dominated")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 4 and unique_words < MIN_UNIQUE_WORDS:
        _, count = Counter(lines).most_common(1)[0]
        if count > len(lines) / 2:
            found.append("repeated_blocks")
    return found


def _score(visible_chars: int, words: int, unique_words: int, headings: int) -> int:
    score = (
        40
        if visible_chars >= 1200
        else 28
        if visible_chars >= 500
        else 14
        if visible_chars >= 240
        else 0
    )
    score += 30 if words >= 140 else 22 if words >= 70 else 12 if words >= 35 else 0
    score += (
        20 if unique_words >= 80 else 14 if unique_words >= 35 else 8 if unique_words >= 18 else 0
    )
    return score + (5 if headings else 0)


def _quality(html: str) -> dict:
    # The reference assesses the raw page (including noindex) minus noise tags.
    tree = LexborHTMLParser(_noise_cut(html, noindex=False))
    text = tree.text(separator="\n") or ""
    headings = len(tree.css("h1, h2, h3"))
    visible_chars = len(VISIBLE.findall(text))
    tokens = TOKEN.findall(text.lower())
    words, unique_words = len(tokens), len(set(tokens))
    flags = _flags(html, text, words, unique_words)
    score = _score(visible_chars, words, unique_words, headings)
    score -= 70 if "antibot" in flags else 0
    score -= 55 if "stub" in flags and words < MIN_WORDS else 0
    score -= 25 if "script_dominated" in flags else 0
    score -= 30 if "repeated_blocks" in flags else 0
    score = max(0, min(100, score))
    reasons = [FLAG_REASON[flag] for flag in flags]
    if visible_chars < MIN_CHARS:
        reasons.append(f"знаков {visible_chars} < {MIN_CHARS}")
    if words < MIN_WORDS:
        reasons.append(f"слов {words} < {MIN_WORDS}")
    if unique_words < MIN_UNIQUE_WORDS:
        reasons.append(f"разных слов {unique_words} < {MIN_UNIQUE_WORDS}")
    if not reasons and score < MIN_SCORE:
        reasons.append(f"оценка {score} < {MIN_SCORE}")
    return {
        "accepted": not reasons,
        "score": score,
        "reason": "; ".join(reasons) if reasons else None,
        "visible_chars": visible_chars,
        "words": words,
        "unique_words": unique_words,
        "flags": flags,
    }


def measure_html(
    html: str,
    *,
    ignore_words: list[str] | None,
    stop_phrases: list[str] | None,
    top_n: int,
) -> dict:
    """Measure seven blocks, plus page structure and content quality."""
    if not isinstance(html, str) or not html.strip():
        raise InvalidArguments("html must be a non-blank string.")
    clean = _noise_cut(html, noindex=True)
    headings = _headings(clean)
    return {
        "blocks": {
            name: metrics.measure_text(
                text, ignore_words=ignore_words, stop_phrases=stop_phrases, top_n=top_n
            )
            for name, text in _blocks(html, clean, headings).items()
        },
        "structure": _structure(clean, headings),
        "quality": _quality(html),
    }
