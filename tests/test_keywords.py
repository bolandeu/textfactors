"""Check keyword occurrence counting, targets and CLI parity."""

import json

import pytest

from rb_textfactors import check_html_keywords, check_keywords

TEXT = (
    "Таможенный представитель оформляет импортные грузы. "
    "Опытный таможенный и надёжный представитель работает в Москве. "
    "Представитель таможенный выезжает на склад."
)


def test_exact_lemma_and_diluted_matches_are_counted_separately() -> None:
    exact = check_keywords(TEXT, ["таможенный представитель"])
    lemma = check_keywords(TEXT, ["таможенный представитель"], exact=False)
    diluted = check_keywords(TEXT, ["таможенный представитель"], exact=False, diluted=True)
    assert exact["keywords"][0]["find"] == 1
    assert lemma["keywords"][0]["find"] == 1
    assert diluted["keywords"][0]["find"] == 2
    assert diluted["keywords"][0]["density"] == round(2 / diluted["words_total"] * 100, 3)


def test_reverse_order_matches_only_when_enabled() -> None:
    text = "Представитель таможенный оформляет грузы."
    assert check_keywords(text, ["таможенный представитель"])["keywords"][0]["find"] == 0
    result = check_keywords(text, ["таможенный представитель"], reverse=True)
    assert result["keywords"][0]["find"] == 1


def test_window_limits_the_gap_between_phrase_words() -> None:
    text = "Таможенный очень опытный и надёжный представитель"
    assert check_keywords(text, ["таможенный представитель"], exact=False)["keywords"][0]["find"] == 0
    wide = check_keywords(text, ["таможенный представитель"], exact=False, diluted=True, window=4)
    narrow = check_keywords(text, ["таможенный представитель"], exact=False, diluted=True, window=3)
    assert wide["keywords"][0]["find"] == 1
    assert narrow["keywords"][0]["find"] == 0


def test_targets_report_met_and_unmet_keywords() -> None:
    result = check_keywords(TEXT, ["таможенный", "брокер", "представитель"], targets=[2, 1, 3])
    assert [row["met"] for row in result["keywords"]] == [True, False, True]
    assert (result["found"], result["missing"]) == (2, 1)
    assert (result["met"], result["unmet"]) == (2, 1)
    assert result["keywords"][0]["target"] == 2
    assert result["keywords"][0]["density"] == round(3 / result["words_total"] * 100, 3)


def test_without_targets_counts_only_and_keeps_text_order() -> None:
    result = check_keywords(TEXT, ["брокер", "таможенный"])
    assert [row["keyword"] for row in result["keywords"]] == ["брокер", "таможенный"]
    assert [row["met"] for row in result["keywords"]] == [None, None]
    assert result["met"] == result["unmet"] == 0


def test_empty_text_and_empty_keyword_list() -> None:
    empty = check_keywords("", ["брокер"], targets=[0])
    assert empty["words_total"] == 0
    assert empty["keywords"][0] == {
        "keyword": "брокер",
        "find": 0,
        "density": 0.0,
        "target": 0,
        "met": True,
    }
    assert check_keywords(TEXT, [])["keywords"] == []


@pytest.mark.parametrize(
    "arguments",
    [
        {"text": 1, "keywords": ["брокер"]},
        {"text": TEXT, "keywords": "брокер"},
        {"text": TEXT, "keywords": ["  "]},
        {"text": TEXT, "keywords": ["123"]},
        {"text": TEXT, "keywords": ["брокер"], "targets": [1, 2]},
        {"text": TEXT, "keywords": ["брокер"], "targets": [-1]},
        {"text": TEXT, "keywords": ["брокер"], "targets": [True]},
        {"text": TEXT, "keywords": ["брокер"], "exact": False, "lemma": False},
        {"text": TEXT, "keywords": ["брокер"], "window": -1},
    ],
)
def test_invalid_input_raises_value_error(arguments: dict) -> None:
    with pytest.raises(ValueError):
        check_keywords(**arguments)


def test_cli_call_matches_the_python_api() -> None:
    from typer.testing import CliRunner

    from rb_textfactors.cli import app

    args = [
        "--json",
        "check-keywords",
        TEXT,
        "--keyword",
        "таможенный",
        "--keyword",
        "брокер",
        "--target",
        "2",
        "--target",
        "1",
    ]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    expected = check_keywords(TEXT, ["таможенный", "брокер"], targets=[2, 1])
    assert json.loads(result.stdout)["keywords"] == expected["keywords"]


def test_any_word_counts_each_phrase_word_separately() -> None:
    text = "Таможенный представитель оформляет грузы и платежи. Брокер помогает."
    result = check_keywords(text, ["таможенный представитель"], exact=False, lemma=False, any_word=True)
    row = result["keywords"][0]
    assert row["find"] == 2
    assert row["density"] == round(2 / result["words_total"] * 100, 3)


def test_any_word_does_not_double_count_an_exact_phrase() -> None:
    text = "Таможенный представитель оформляет грузы."
    with_exact = check_keywords(text, ["таможенный представитель"], any_word=True)
    without_exact = check_keywords(text, ["таможенный представитель"], exact=False, lemma=False, any_word=True)
    assert with_exact["keywords"][0]["find"] == 1
    assert without_exact["keywords"][0]["find"] == 2


def test_html_zone_selection_and_page_cleanup() -> None:
    html = (
        "<title>Таможенный представитель в Москве</title>"
        "<h1>Таможенный представитель</h1>"
        "<p>Оформляем импортные грузы.</p>"
        '<div class="rb-reviews-widget"><p>Брокер брокер брокер</p></div>'
    )
    text = check_html_keywords(html, ["таможенный", "брокер"], targets=[1, 0])
    title = check_html_keywords(html, ["москва"], block="title")
    h1 = check_html_keywords(html, ["таможенный"], block="h1")
    assert text["block"] == "text"
    assert [row["find"] for row in text["keywords"]] == [0, 0]
    assert text["keywords"][1]["met"] is True
    assert title["keywords"][0]["find"] == 1
    assert h1["keywords"][0]["find"] == 1
    assert text["quality"] == {"accepted": False, "score": 5}


def test_html_keywords_reject_unknown_block_and_blank_page() -> None:
    with pytest.raises(ValueError, match="block"):
        check_html_keywords("<p>Текст</p>", ["текст"], block="body")
    with pytest.raises(ValueError, match="html"):
        check_html_keywords("  ", ["текст"])
