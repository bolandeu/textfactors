"""Measure the reference HTML fixtures and exercise boundary cases through the API."""

import json
from pathlib import Path

import pytest

from rb_textfactors import measure_html, measure_text

FIXTURES = Path(__file__).parent / "fixtures"
PAGES = sorted((FIXTURES / "pages").glob("*.html"))
BLOCKS = ("text", "headings", "links", "text_links", "title", "h1", "meta_description")


def test_each_fixture_has_a_reference_capture() -> None:
    assert len(PAGES) == 6
    assert {page.stem for page in PAGES} == {
        path.stem for path in (FIXTURES / "reference").glob("*.json")
    }


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.stem)
def test_page_matches_reference_capture(page: Path) -> None:
    capture = json.loads((FIXTURES / "reference" / f"{page.stem}.json").read_text(encoding="utf-8"))
    expected = {
        "blocks": {**capture["zones"], **capture["meta"]},
        "structure": capture["structure"],
        "quality": capture["quality"],
    }
    result = measure_html(page.read_text(encoding="utf-8"))
    assert tuple(result["blocks"]) == BLOCKS
    assert result == expected


def test_html_drops_noindex_and_nested_noise_but_retains_links_and_structure() -> None:
    start = (
        "<html><head><title>Доставка воды</title>"
        '<meta name="description" content="Вода в офис"></head><body>'
    )
    body = (
        "<h1>Доставка</h1><h2>Цены</h2><h3>Тарифы</h3><h2></h2>"
        '<p>Текст <a href="/cena">цена</a> авто</p><ul><li>Один</li><li>Два</li></ul>'
        "<table><tr><td><table><tr><td>Вложенная</td></tr></table></td></tr></table>"
    )
    clean = measure_html(f"{start}{body}</body></html>")
    noisy = measure_html(
        f'{start}<nav><aside><a href="/">Исключить</a><h1>Исключить</h1></aside></nav>'
        f"<form><button>Исключить</button></form>{body}"
        "<noindex><p>Исключить</p><ul><li>Исключить</li></ul></noindex>"
        '<!--noindex--><a href="/">Исключить</a><!--/noindex--></body></html>'
    )
    assert noisy["blocks"] == clean["blocks"]
    assert (
        noisy["structure"]
        == clean["structure"]
        == {
            "h1_count": 1,
            "h2_count": 1,
            "h3_count": 1,
            "li_count": 2,
            "table_count": 2,
            "heading_tree": [
                {
                    "level": 1,
                    "text": "Доставка",
                    "children": [
                        {
                            "level": 2,
                            "text": "Цены",
                            "children": [{"level": 3, "text": "Тарифы", "children": []}],
                        }
                    ],
                }
            ],
        }
    )
    blocks = clean["blocks"]
    assert blocks["headings"] == measure_text("Цены Тарифы")
    assert blocks["links"] == measure_text("цена")
    assert blocks["title"] == measure_text("Доставка воды")
    assert blocks["meta_description"] == measure_text("Вода в офис")
    assert "цена" not in {row["key"] for row in blocks["text"]["repeat_words_1"]}
    assert "цена" in {row["key"] for row in blocks["text_links"]["repeat_words_1"]}


def test_script_dominated_page_is_rejected_without_losing_its_blocks() -> None:
    result = measure_html(f"<script>{'x' * 4096}</script><h1>Заголовок</h1><p>Абзац</p>")
    assert result["quality"]["flags"] == ["script_dominated"]
    assert result["quality"]["accepted"] is False
    assert result["blocks"]["text"] == measure_text("Абзац")


def test_plain_page_and_empty_html() -> None:
    result = measure_html("  Только  текст \n без  тегов ")
    assert (
        result["blocks"]["text"]
        == result["blocks"]["text_links"]
        == measure_text("Только текст без тегов")
    )
    assert result["blocks"]["h1"] == result["blocks"]["meta_description"] == measure_text("")
    assert result["structure"]["heading_tree"] == []
    with pytest.raises(ValueError, match="html"):
        measure_html(" \n ")
