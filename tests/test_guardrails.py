import pytest

from rag import guardrails as g


def test_cited_numbers_order_and_grouping():
    assert g.cited_numbers("A [2]. B [1, 3][2].") == [2, 1, 3]


def test_drop_invalid_citations():
    assert g.drop_invalid_citations("Fact [1][7]. Other [7].", {1, 2}) == "Fact [1]. Other."


def test_limit_length_cuts_at_sentence():
    text = "First sentence here [1]. Second sentence is longer and goes on [2]. Third."
    out = g.limit_length(text, 60)
    assert out == "First sentence here [1]."
    assert g.limit_length("short", 60) == "short"


def test_clean_question():
    assert g.clean_question("  hi\x00 there ", 100) == "hi there"
    for bad in ("", "   ", None, 5, "x" * 101):
        with pytest.raises(g.InvalidQuestion):
            g.clean_question(bad, 100)


def test_refusal_detection():
    assert g.is_refusal(g.REFUSAL)
    assert not g.is_refusal("You get 20 days [1].")


def test_normalize_model_citation_brackets():
    from rag.llm import normalize_output

    out = normalize_output("Use them by March 31 【1】【2†L5】, carried‑over days.")
    assert out == "Use them by March 31 [1][2], carried-over days."


def test_normalize_strips_markdown_bold_and_percent_spacing():
    from rag.llm import normalize_output

    out = normalize_output("PTO is **not** deducted; match is 100 % of 4 % [1].")
    assert out == "PTO is not deducted; match is 100% of 4% [1]."
