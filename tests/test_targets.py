"""Check occurrence targets computed from peer keyword densities."""

import pytest

from rb_textfactors import keyword_targets


def page(words: int, rows: list[tuple[str, int, float]]) -> dict:
    return {
        "blocks": {
            "text": {
                "words_total": words,
                "repeat_words_1": [
                    {"key": key, "count": count, "density": density} for key, count, density in rows
                ],
            }
        }
    }


def test_target_is_median_density_applied_to_own_length() -> None:
    own = page(200, [("груз", 1, 0.5)])
    items = [page(100, [("груз", 2, 2.0)]), page(100, [("груз", 4, 4.0)])]
    result = keyword_targets(own, items)
    assert result["block"] == "text"
    assert result["words_total"] == 200
    assert result["items"] == 2
    assert result["keywords"][0] == {
        "keyword": "груз",
        "own": 1,
        "target": 6,
        "add": 5,
        "peers": 2,
        "share": 1.0,
        "density": 3.0,
    }


def test_share_min_length_and_min_count_filter_rows() -> None:
    own = page(100, [])
    items = [
        page(100, [("груз", 2, 2.0), ("к", 5, 5.0), ("склад", 1, 1.0)]),
        page(100, [("груз", 2, 4.0), ("к", 5, 5.0)]),
        page(100, [("другое", 2, 5.0)]),
    ]
    result = keyword_targets(own, items)
    assert [row["keyword"] for row in result["keywords"]] == ["груз"]
    loose = keyword_targets(own, items, share=0.3, min_length=1, min_key_count=1)
    assert [row["keyword"] for row in loose["keywords"]] == ["к", "другое", "груз", "склад"]


def test_rows_with_nothing_to_add_stay_with_zero() -> None:
    own = page(100, [("груз", 9, 9.0)])
    items = [page(100, [("груз", 2, 2.0)])]
    row = keyword_targets(own, items)["keywords"][0]
    assert (row["target"], row["add"]) == (2, 0)


def test_pages_without_the_block_are_skipped_for_coverage() -> None:
    own = page(100, [])
    items = [page(100, [("груз", 2, 2.0)]), {"blocks": {"title": {}}}, {"blocks": None}]
    result = keyword_targets(own, items)
    assert result["items"] == 1
    assert result["keywords"][0]["share"] == 1.0


@pytest.mark.parametrize(
    "arguments",
    [
        {"own": {"blocks": {"title": {}}}, "items": [page(100, [])]},
        {"own": page(100, []), "items": []},
        {"own": page(100, []), "items": [{"blocks": {"text": {}}}], "share": 0},
        {"own": page(100, []), "items": [{"blocks": {"text": {}}}], "min_length": -1},
        {"own": page(100, []), "items": [{"blocks": {"text": {}}}], "block": ""},
    ],
)
def test_invalid_input_raises_value_error(arguments: dict) -> None:
    with pytest.raises(ValueError):
        keyword_targets(**arguments)


def test_min_sites_includes_a_keyword_below_the_share() -> None:
    own = page(100, [])
    items = [
        page(100, [("склад", 2, 2.0)]),
        page(100, [("склад", 2, 4.0)]),
        page(100, [("другое", 2, 5.0)]),
    ]
    assert keyword_targets(own, items, share=0.9)["keywords"] == []
    rows = keyword_targets(own, items, share=0.9, min_sites=2)["keywords"]
    assert [row["keyword"] for row in rows] == ["склад"]
