"""Reference examples and edge cases for the public text and comparison API."""

from copy import deepcopy
from inspect import signature

import pytest

from rb_textfactors import average, compare, compare_with_set, measure_html, measure_text

BLOCKS = ("text", "headings", "links", "text_links", "title", "h1", "meta_description")
NUMBERS = (
    "length",
    "length_trim",
    "sentences",
    "words_total",
    "words_count",
    "words_root_count",
    "water_percent",
    "nausea_classic",
    "nausea_academic",
    "zipf_quality",
    "ttr",
    "mtld",
)
WORKED = "Растаможка авто в Москве: цена от 120 000 рублей"


def test_reference_signatures() -> None:
    options = "*, ignore_words: list[str] | None = None, stop_phrases: list[str] | None = None, top_n: int = 0"
    blocks = "blocks: list[str] | None = None"
    signatures = {
        measure_text: f"(text: str, {options}) -> dict",
        measure_html: f"(html: str, {options}) -> dict",
        average: f"(items: list[dict], *, {blocks}) -> dict",
        compare: f"(a: dict, b: dict, *, {blocks}) -> dict",
        compare_with_set: f"(own: dict, items: list[dict], *, share: float = 0.6, {blocks}, min_key_count: int = 2) -> dict",
    }
    for function, expected in signatures.items():
        assert str(signature(function, eval_str=True)) == expected


def test_worked_text_from_reference() -> None:
    result = measure_text(WORKED)
    assert tuple(result) == (
        *NUMBERS,
        "norms",
        "stop_words",
        "repeat_words_1",
        "repeat_words_2",
        "repeat_words_3",
    )
    assert tuple(result[name] for name in NUMBERS) == (48, 40, 1, 7, 4, 4, 28.57, 1, 14.29, 0, 1, 4)
    assert result["norms"] == {
        "nausea_classic": "в норме",
        "nausea_academic": "переспам",
        "water_percent": "многовато воды",
    }
    assert result["repeat_words_1"] == [
        {"key": "растаможка", "count": 1, "density": 25.0, "example": "Растаможка"},
        {"key": "авто", "count": 1, "density": 25.0, "example": "авто"},
        {"key": "москва", "count": 1, "density": 25.0, "example": "Москве"},
        {"key": "цена", "count": 1, "density": 25.0, "example": "цена"},
    ]
    assert [row["key"] for row in result["repeat_words_2"]] == ["растаможка авто", "авто в москва"]
    assert [row["key"] for row in result["repeat_words_3"]] == ["растаможка авто в москва"]


@pytest.mark.parametrize("text", ["", " \t\n", "123 !!!"])
def test_text_without_letters_has_zero_counts(text: str) -> None:
    result = measure_text(text)
    assert result["length"] == len(text)
    assert [result[name] for name in NUMBERS[2:]] == [0] * 10
    assert [result[f"repeat_words_{n}"] for n in (1, 2, 3)] == [[], [], []]
    assert result["norms"] == {
        "nausea_classic": "в норме",
        "nausea_academic": "мало повторов",
        "water_percent": "мало воды",
    }


def test_measure_text_options_and_same_lemma() -> None:
    text = "автомобилей автомобиля в интернет-магазине. Доставка срочно"
    result = measure_text(
        text, stop_phrases=["В Интернет-магазине"], ignore_words=["СРОЧНО"], top_n=1
    )
    assert (
        result["length"],
        result["sentences"],
        result["words_total"],
        result["words_count"],
    ) == (len(text), 2, 4, 3)
    assert result["repeat_words_1"] == [
        {"key": "автомобиль", "count": 2, "density": 66.667, "example": "автомобилей, автомобиля"},
    ]
    assert result["repeat_words_2"] == result["repeat_words_3"] == []
    assert measure_text(WORKED, ignore_words=[])["words_count"] == 5


def test_measure_text_rejects_negative_top_n() -> None:
    with pytest.raises(ValueError, match="top_n"):
        measure_text(WORKED, top_n=-1)


def test_average_uses_nearest_rank_and_only_items_carrying_the_block() -> None:
    items = [
        {"blocks": {"text": {"words_count": n, "boolean": True, "repeat_words_1": []}}}
        for n in range(1, 11)
    ]
    items.append({"blocks": {"h1": {"length": 3}}})
    original = deepcopy(items)
    result = average(items)
    assert result == {
        "items": 11,
        "blocks": {
            "text": {
                "count": 10,
                "metrics": {
                    "words_count": {
                        "mean": 5.5,
                        "median": 5.5,
                        "q25": 3,
                        "q75": 8,
                        "min": 1,
                        "max": 10,
                    }
                },
            },
            "h1": {
                "count": 1,
                "metrics": {
                    "length": {"mean": 3, "median": 3, "q25": 3, "q75": 3, "min": 3, "max": 3}
                },
            },
        },
        "skipped": ["headings", "links", "text_links", "title", "meta_description"],
    }
    assert items == original
    assert average(items, blocks=[]) == {"items": 11, "blocks": {}, "skipped": []}


def test_average_rounds_every_figure() -> None:
    result = average([{"blocks": {"text": {"ttr": 0.1111}}}, {"blocks": {"text": {"ttr": 0.2222}}}])
    assert result["blocks"]["text"]["metrics"]["ttr"] == {
        "mean": 0.167,
        "median": 0.167,
        "q25": 0.111,
        "q75": 0.222,
        "min": 0.111,
        "max": 0.222,
    }


def test_comparison_deltas_ratios_and_verdicts() -> None:
    a = {
        "blocks": {
            "text": {"words_count": 5, "length": 5000, "ttr": 0.5, "only_a": 1},
            "custom": {"n": 2},
        }
    }
    b = {
        "blocks": {
            "text": {"words_count": 800, "length": 1000, "ttr": 0.6, "only_b": 1},
            "title": {},
        }
    }
    assert compare(a, b) == {
        "blocks": {
            "text": {
                "words_count": {"a": 5, "b": 800, "delta": -795, "ratio": 0.006, "verdict": "grow"},
                "length": {"a": 5000, "b": 1000, "delta": 4000, "ratio": 5, "verdict": "trim"},
                "ttr": {"a": 0.5, "b": 0.6, "delta": -0.1, "ratio": 0.833, "verdict": "info"},
            },
        },
        "skipped": ["title", "custom"],
    }
    assert compare(a, b, blocks=["unknown"]) == {"blocks": {}, "skipped": ["unknown"]}


@pytest.mark.parametrize(
    ("a", "b", "ratio", "verdict"),
    [
        (10, 0, 0, "trim"),
        (0, -5, 0, "grow"),
        (0.079, 0.01, 7.9, "grow"),
        (10, 10, 1, "ok"),
        (18, 10, 1.8, "ok"),
    ],
)
def test_pair_verdict_boundaries(a: float, b: float, ratio: float, verdict: str) -> None:
    result = compare({"blocks": {"text": {"n": a}}}, {"blocks": {"text": {"n": b}}})
    assert result["blocks"]["text"]["n"]["ratio"] == ratio
    assert result["blocks"]["text"]["n"]["verdict"] == verdict


def test_set_figures_exclude_own_and_use_zero_for_missing_metric() -> None:
    own = {"blocks": {"text": {"words_count": 5, "ttr": 0.5}}}
    items = [
        {"blocks": {"text": {"words_count": n, "ttr": 0.2222, "length": 100}}}
        for n in (800, 700, 900)
    ]
    result = compare_with_set(own, [*items, {"blocks": {"headings": {}}}])
    assert result["items"] == 3
    assert result["skipped"] == list(BLOCKS[1:])
    assert result["blocks"]["text"]["words_count"] == {
        "own": 5,
        "median": 800,
        "q25": 700,
        "q75": 900,
        "min": 700,
        "max": 900,
        "delta": -795,
        "verdict": "grow",
    }
    assert result["blocks"]["text"]["length"]["own"] == 0
    assert result["blocks"]["text"]["ttr"]["delta"] == 0.278
    assert result["verdicts"] == {"grow": 2, "trim": 0, "ok": 0, "info": 1}


def test_missing_keys_use_only_pages_with_the_block_and_sort_by_median_density() -> None:
    own = {"blocks": {"text": {"repeat_words_1": [{"key": "kept"}]}}}
    items = [
        {
            "blocks": {
                "text": {
                    "repeat_words_1": [
                        {"key": key, "count": count, "density": density}
                        for key, count, density in [
                            ("beta", 2, 3),
                            ("alpha", 2, 3),
                            ("gamma", 2, 5 if index % 2 else 7),
                            ("kept", 2, 5),
                            ("once", 1, 1),
                            ("rare", 2, 2),
                        ]
                        if index < (5 if key == "rare" else 6)
                    ]
                }
            }
        }
        for index in range(10)
    ]
    items.extend(
        [
            {},
            {"blocks": {"title": {}}},
            {
                "blocks": {
                    "text_links": {
                        "repeat_words_1": [
                            {"key": "link", "count": 2, "density": 1},
                        ]
                    }
                }
            },
        ]
    )
    assert compare_with_set(own, items)["missing_keys"] == [
        {"block": "text", "key": "gamma", "share": 0.6, "density": 6.0},
        {"block": "text", "key": "alpha", "share": 0.6, "density": 3.0},
        {"block": "text", "key": "beta", "share": 0.6, "density": 3.0},
        {"block": "text_links", "key": "link", "share": 1.0, "density": 1.0},
    ]
    result = compare_with_set(own, items, share=0.5, min_key_count=1, blocks=["title"])
    assert result["blocks"] == {}
    assert [row["key"] for row in result["missing_keys"]] == [
        "gamma",
        "alpha",
        "beta",
        "rare",
        "link",
        "once",
    ]


def test_null_blocks_are_treated_as_absent_in_a_mixed_set() -> None:
    own = {"blocks": {"text": {"words_count": 2}}}
    result = compare_with_set(own, [own, {"blocks": None}], blocks=["text"])
    assert result["items"] == 1
    assert result["blocks"]["text"]["words_count"]["verdict"] == "ok"


@pytest.mark.parametrize("share", [-1.0, 0.0, 1.01, float("nan")])
def test_set_rejects_shares_outside_range(share: float) -> None:
    with pytest.raises(ValueError, match="share"):
        compare_with_set({}, [{}], share=share)


def test_rejects_empty_sets_and_malformed_blocks() -> None:
    with pytest.raises(ValueError, match="items"):
        average([])
    with pytest.raises(ValueError, match="items"):
        compare_with_set({}, [])
    with pytest.raises(ValueError, match="blocks"):
        compare({"blocks": ["text"]}, {})
    with pytest.raises(ValueError, match="finite"):
        average([{"blocks": {"text": {"length": float("inf")}}}])


@pytest.mark.parametrize(
    ("row", "field"),
    [
        ({"key": ["cargo"], "count": 2}, "key"),
        ({"key": "cargo", "count": "two"}, "count"),
        ({"key": "cargo", "count": 2, "density": float("nan")}, "density"),
    ],
)
def test_set_rejects_malformed_repeat_values(row: dict, field: str) -> None:
    reference = {"blocks": {"text": {"repeat_words_1": [row]}}}
    with pytest.raises(ValueError, match=field):
        compare_with_set({}, [reference])


def test_measurements_compose_without_modifying_inputs() -> None:
    own = {"blocks": {"text": measure_text("доставка груза")}}
    competitor = measure_html("<p>Доставка грузов. Доставка грузов. Документы.</p>")
    original_own, original_competitor = deepcopy(own), deepcopy(competitor)
    assert compare(own, competitor)["blocks"]["text"]["words_count"]["verdict"] == "grow"
    assert average([own, competitor])["blocks"]["text"]["count"] == 2
    assert compare_with_set(own, [competitor])["missing_keys"] == [
        {"block": "text_links", "key": "груз", "share": 1, "density": 40},
        {"block": "text_links", "key": "доставка", "share": 1, "density": 40},
    ]
    assert (own, competitor) == (original_own, original_competitor)


def test_stop_words_list_shows_what_makes_water() -> None:
    text = "Это и как, это нужно."
    result = measure_text(text)
    rows = {row["word"]: row for row in result["stop_words"]}
    assert rows["это"]["count"] == 2
    assert rows["и"]["count"] == 1
    assert all(
        row["density"] == round(row["count"] / result["words_total"] * 100, 3)
        for row in result["stop_words"]
    )
    assert measure_text(text, top_n=1)["stop_words"] == result["stop_words"][:1]
    assert measure_text("Доставка грузов")["stop_words"] == []
