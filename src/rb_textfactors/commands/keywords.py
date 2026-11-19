"""The keyword commands: occurrences in a text or a page, and the targets a set of pages implies."""

from __future__ import annotations

import typer

from .. import output
from ..operations import check_html_keywords, check_keywords, keyword_targets
from . import _input

KeywordOption = typer.Option(..., "--keyword", help="Phrase to count; repeat for several.")
TargetOption = typer.Option(None, "--target", help="Required occurrences per keyword, in the same order.")
BlockOption = typer.Option("text", "--block", help="Zone to check: text, headings, links, title, h1, meta_description.")
ItemOption = typer.Option(..., "--item", help="One measure result as a JSON object; repeat for a set.")
ExactOption = typer.Option(True, "--exact/--no-exact", help="Count the phrase as written, ignoring case.")
LemmaOption = typer.Option(True, "--lemma/--no-lemma", help="Count the phrase in any grammatical form.")
DilutedOption = typer.Option(False, "--diluted/--no-diluted", help="Allow other words between the phrase's words.")
ReverseOption = typer.Option(False, "--reverse/--no-reverse", help="Allow the words in reverse order.")
AnyWordOption = typer.Option(False, "--any-word/--no-any-word", help="Count every occurrence of a single word.")
WindowOption = typer.Option(3, "--window", help="Words allowed between the phrase's words with --diluted.")
ShareOption = typer.Option(0.6, "--share", help="Minimum share of the set carrying a keyword, 0 < share <= 1.")
MinKeyCountOption = typer.Option(1, "--min-key-count", help="Occurrences of a keyword in one page to count.")
MinLengthOption = typer.Option(3, "--min-length", help="Minimum keyword length in characters.")
MinSitesOption = typer.Option(0, "--min-sites", help="Include a keyword carried by at least this many pages.")


def _counts(
    keywords: list[str],
    targets: list[int] | None,
    exact: bool,
    lemma: bool,
    diluted: bool,
    reverse: bool,
    any_word: bool,
    window: int,
) -> dict:
    return {
        "keywords": list(keywords),
        "targets": list(targets) if targets else None,
        "exact": exact,
        "lemma": lemma,
        "diluted": diluted,
        "reverse": reverse,
        "any_word": any_word,
        "window": window,
    }


@output.guard
def check_keywords_command(
    ctx: typer.Context,
    text: str = typer.Argument(..., help="Plain text, the measured blocks.text content rather than HTML."),
    keyword: list[str] = KeywordOption,
    target: list[int] | None = TargetOption,
    exact: bool = ExactOption,
    lemma: bool = LemmaOption,
    diluted: bool = DilutedOption,
    reverse: bool = ReverseOption,
    any_word: bool = AnyWordOption,
    window: int = WindowOption,
    json_output: bool = output.JsonOption,
    quiet: bool = output.QuietOption,
) -> None:
    """Count keyword phrases in a text and check them against occurrence targets.

    Example: {cli} check-keywords "Купить ёлку" --keyword "ёлку" --target 2
    """
    del json_output, quiet  # read by output.guard through the context
    result = check_keywords(text, **_counts(keyword, target, exact, lemma, diluted, reverse, any_word, window))  # type: ignore[arg-type]
    output.emit_success(ctx, result, _input.human("keywords", ("passed", "failed")))


@output.guard
def check_html_keywords_command(
    ctx: typer.Context,
    html: str = typer.Argument(..., help="HTML of one page."),
    keyword: list[str] = KeywordOption,
    block: str = BlockOption,
    target: list[int] | None = TargetOption,
    exact: bool = ExactOption,
    lemma: bool = LemmaOption,
    diluted: bool = DilutedOption,
    reverse: bool = ReverseOption,
    any_word: bool = AnyWordOption,
    window: int = WindowOption,
    json_output: bool = output.JsonOption,
    quiet: bool = output.QuietOption,
) -> None:
    """Check keyword phrases in HTML after the same cleanup used for measurement.

    Example: {cli} check-html-keywords page.html --keyword "ёлку" --block headings
    """
    del json_output, quiet  # read by output.guard through the context
    counts = _counts(keyword, target, exact, lemma, diluted, reverse, any_word, window)
    result = check_html_keywords(html, block=block, **counts)  # type: ignore[arg-type]
    output.emit_success(ctx, result, _input.human("keywords", ("passed", "failed")))


@output.guard
def keyword_targets_command(
    ctx: typer.Context,
    own: str = typer.Argument(..., help="The measured result to improve, as a JSON object."),
    item: list[str] = ItemOption,
    block: str = BlockOption,
    share: float = ShareOption,
    min_key_count: int = MinKeyCountOption,
    min_length: int = MinLengthOption,
    min_sites: int = MinSitesOption,
    json_output: bool = output.JsonOption,
    quiet: bool = output.QuietOption,
) -> None:
    """Compute how many occurrences each peer keyword needs on the own page.

    Example: {cli} keyword-targets @own.json --item @a.json --item @b.json
    """
    del json_output, quiet  # read by output.guard through the context
    result = keyword_targets(
        _input.load(own, "own"),
        _input.load_items(item),
        block=block,
        share=share,
        min_key_count=min_key_count,
        min_length=min_length,
        min_sites=min_sites,
    )
    output.emit_success(ctx, result, _input.human("targets", ("items",)))
