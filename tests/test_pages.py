"""Measure the reference HTML fixtures and exercise boundary cases through the API."""

import json
from pathlib import Path

import pytest

from rb_textfactors import measure_html, measure_text


def contains(expected: object, actual: object) -> bool:
    """Reference captures predate our extra keys: lists exact, dicts as a subset."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and contains(value, actual[key]) for key, value in expected.items()
        )
    return expected == actual


FIXTURES = Path(__file__).parent / "fixtures"
PAGES = sorted((FIXTURES / "pages").glob("*.html"))
BLOCKS = (
    "text",
    "headings",
    "links",
    "text_links",
    "title",
    "h1",
    "meta_description",
    "page",
)


def test_each_fixture_has_a_reference_capture() -> None:
    assert len(PAGES) == 6
    assert {page.stem for page in PAGES} == {path.stem for path in (FIXTURES / "reference").glob("*.json")}


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
    assert contains(expected, result)


def test_html_drops_noindex_and_nested_noise_but_retains_links_and_structure() -> None:
    start = '<html><head><title>Доставка воды</title><meta name="description" content="Вода в офис"></head><body>'
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
    assert {k: v for k, v in noisy["blocks"].items() if k != "page"} == {
        k: v for k, v in clean["blocks"].items() if k != "page"
    }
    assert noisy["blocks"]["page"]["words_total"] > clean["blocks"]["page"]["words_total"]
    assert (
        noisy["structure"]
        == clean["structure"]
        == {
            "h1_count": 1,
            "h2_count": 1,
            "h3_count": 1,
            "h4_count": 0,
            "h5_count": 0,
            "h6_count": 0,
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


def test_captcha_widget_does_not_reject_a_full_page() -> None:
    text = (
        "Таможенный представитель оформляет импортные документы для внешнеэкономической деятельности. "
        "Специалисты рассчитывают платежи, проверяют декларации, сопровождают транзит и "
        "консультируют клиентов по классификации товаров, срокам выпуска, рискам и стоимости. "
        "Компания готовит документы, взаимодействует с таможенными органами и помогает "
        "снизить задержки при выпуске грузов."
    )
    result = measure_html(
        f"<h1>Таможенный представитель</h1><p>{text}</p>"
        '<div class="g-recaptcha" data-sitekey="public-widget-key"></div>'
    )
    assert result["quality"]["accepted"] is True
    assert result["quality"]["flags"] == []
    assert result["quality"]["score"] >= 40


def test_challenge_text_rejects_a_short_captcha_page() -> None:
    result = measure_html(
        '<div id="cf-turnstile"><p>Checking your browser before accessing the site.</p>'
        "<p>Verify you are human.</p></div>"
    )
    assert result["quality"]["accepted"] is False
    assert result["quality"]["flags"] == ["antibot", "stub"]


def test_page_chrome_is_not_measured_as_content() -> None:
    body = (
        "<h1>Таможенный представитель</h1>"
        "<p>Оформляем импортные грузы и консультируем по внешнеэкономической деятельности.</p>"
        '<div class="rb-reviews-widget"><h2>Отзывы</h2><p>Яндекс 5, Google 5</p></div>'
        '<div class="cookie-notification"><p>Мы используем куки.</p></div>'
        '<div class="ct-related-posts"><h2>Похожие услуги</h2><p>Таможенный склад</p></div>'
        '<article><h2>Свяжитесь с нами</h2><form><input name="phone"></form></article>'
    )
    result = measure_html(f"<html><body>{body}</body></html>")
    assert result["structure"]["h2_count"] == 0
    assert result["structure"]["heading_tree"] == [{"level": 1, "text": "Таможенный представитель", "children": []}]
    assert result["blocks"]["text"] == measure_text(
        "Оформляем импортные грузы и консультируем по внешнеэкономической деятельности."
    )
    assert "Яндекс" not in result["blocks"]["text_links"]["repeat_words_1"][0]["example"]


def test_plain_page_and_empty_html() -> None:
    result = measure_html("  Только  текст \n без  тегов ")
    assert result["blocks"]["text"] == result["blocks"]["text_links"] == measure_text("Только текст без тегов")
    assert result["blocks"]["h1"] == result["blocks"]["meta_description"] == measure_text("")
    assert result["structure"]["heading_tree"] == []
    with pytest.raises(ValueError, match="html"):
        measure_html(" \n ")


def test_structure_counts_headings_up_to_h6() -> None:
    html = "<h1>А</h1><h2>Б</h2><h3>В</h3><h4>Г</h4><h5>Д</h5><h6>Е</h6><h4>Ж</h4><p>Текст статьи.</p>"
    structure = measure_html(html)["structure"]
    assert [structure[f"h{level}_count"] for level in range(1, 7)] == [1, 1, 1, 2, 1, 1]
    assert structure["heading_tree"][0]["children"][0]["children"][0]["children"][0]["text"] == "Г"


def test_page_block_keeps_chrome_for_volume_comparison() -> None:
    html = "<nav><a href='/'>Меню сайта</a></nav><h1>Услуга</h1><p>Текст услуги.</p><footer>Подвал и контакты</footer>"
    result = measure_html(html)
    assert result["blocks"]["text"]["words_total"] == 2
    assert result["blocks"]["page"]["words_total"] == 8
    assert result["blocks"]["text_links"]["words_total"] == 3
