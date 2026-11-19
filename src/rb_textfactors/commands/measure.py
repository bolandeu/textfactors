"""The `measure-text` and `measure-html` commands: the metrics of one text or one page."""

from __future__ import annotations

from collections.abc import Callable

import typer

from .. import output
from ..operations import measure_html, measure_text

IgnoreWordOption = typer.Option(None, "--ignore-word", help="Exact word form without weight.")
StopPhraseOption = typer.Option(None, "--stop-phrase", help="Phrase to drop before counting.")
TopNOption = typer.Option(0, "--top-n", help="Rows per repeat table; 0 is all of them.")


def _ignored(ignore_words: list[str] | None, stop_phrases: list[str] | None) -> dict[str, list[str] | None]:
    return {
        "ignore_words": list(ignore_words or []) or None,
        "stop_phrases": list(stop_phrases or []) or None,
    }


def _human(title: str) -> Callable[[dict], None]:
    def render(payload: dict) -> None:
        blocks = payload.get("blocks") or {}
        block = blocks.get("text") if isinstance(blocks, dict) else None
        pairs: dict[str, object] = {"items": payload.get("items", 1)}
        if isinstance(block, dict):
            for key in ("chars", "words", "sentences", "paragraphs"):
                if key in block:
                    pairs[key] = block[key]
        output.human.key_values(title, pairs)

    return render


@output.guard
def text_command(
    ctx: typer.Context,
    text: str = typer.Argument(..., help="Plain text to measure."),
    ignore_word: list[str] = IgnoreWordOption,
    stop_phrase: list[str] = StopPhraseOption,
    top_n: int = TopNOption,
    json_output: bool = output.JsonOption,
    quiet: bool = output.QuietOption,
) -> None:
    """Measure plain text: twelve metrics, three norms and three repeat tables.

    Example: {cli} measure-text "Купить ёлку в Москве"
    """
    del json_output, quiet  # read by output.guard through the context
    result = measure_text(text, top_n=top_n, **_ignored(ignore_word, stop_phrase))
    output.emit_success(ctx, result, _human("text"))


@output.guard
def html_command(
    ctx: typer.Context,
    html: str = typer.Argument(..., help="HTML of one page."),
    ignore_word: list[str] = IgnoreWordOption,
    stop_phrase: list[str] = StopPhraseOption,
    top_n: int = TopNOption,
    json_output: bool = output.JsonOption,
    quiet: bool = output.QuietOption,
) -> None:
    """Measure an HTML page: seven blocks, structure and content quality.

    Example: {cli} measure-html "<html><body><h1>Ёлка</h1></body></html>"
    """
    del json_output, quiet  # read by output.guard through the context
    result = measure_html(html, top_n=top_n, **_ignored(ignore_word, stop_phrase))
    output.emit_success(ctx, result, _human("page"))
