from srt_gen.text_cleanup import collapse_repeated_word_loops


def test_preserves_normal_double_words() -> None:
    text = "This is very very good."
    assert collapse_repeated_word_loops(text) == "This is very very good."


def test_collapses_three_or_more_repeated_words() -> None:
    text = "the the the the plan is ready"
    assert collapse_repeated_word_loops(text) == "the plan is ready"


def test_collapses_case_and_punctuation_variants() -> None:
    text = "No no, NO no no we should stop."
    assert collapse_repeated_word_loops(text) == "No we should stop."


def test_trims_and_normalizes_whitespace() -> None:
    text = "  test   test   test   value  "
    assert collapse_repeated_word_loops(text) == "test value"
