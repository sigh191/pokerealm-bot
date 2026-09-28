"""
Unit tests for evaluation/lexical_diversity.py's pure functions.

These use small, hand-picked example sentences with a diversity score
worked out by hand (see each test's comment), rather than real
AI-generated text - the point is to prove the MATHS is correct, not to
measure PokeRealm's actual quests (that's measure_quest_diversity.py's
job, which needs a real Ollama server and isn't part of this suite).
"""

from evaluation.lexical_diversity import (
    distinct_n,
    average_type_token_ratio,
    count_exact_duplicates,
)


def test_distinct_1_is_1_when_every_word_across_all_texts_is_unique():
    texts = ["red blue green", "yellow purple orange"]
    assert distinct_n(texts, n=1) == 1.0


def test_distinct_1_drops_when_words_repeat_across_texts():
    # Unigrams across both texts: the, cat, sat, the, cat, ran
    # -> 4 unique ("the", "cat", "sat", "ran") out of 6 total.
    texts = ["the cat sat", "the cat ran"]
    assert distinct_n(texts, n=1) == 4 / 6


def test_distinct_2_is_stricter_than_distinct_1_for_reordered_text():
    # These two share the exact same 3 words, so distinct-1 would be
    # low - but as consecutive PAIRS, only "the cat" is actually
    # shared: bigrams are (the,cat),(cat,sat) and (sat,the),(the,cat)
    # -> 3 unique out of 4 total.
    texts = ["the cat sat", "sat the cat"]
    assert distinct_n(texts, n=2) == 3 / 4


def test_distinct_n_handles_empty_input_without_crashing():
    assert distinct_n([], n=1) == 0.0
    assert distinct_n([""], n=1) == 0.0


def test_average_ttr_is_1_when_no_text_repeats_a_word():
    texts = ["red blue green", "yellow purple orange"]
    assert average_type_token_ratio(texts) == 1.0


def test_average_ttr_drops_when_a_text_repeats_the_same_word():
    # 1 unique word ("cat") out of 4 total -> TTR of 0.25 for this one text.
    texts = ["cat cat cat cat"]
    assert average_type_token_ratio(texts) == 0.25


def test_average_ttr_handles_empty_input_without_crashing():
    assert average_type_token_ratio([]) == 0.0
    assert average_type_token_ratio([""]) == 0.0


def test_count_exact_duplicates_ignores_case_and_extra_whitespace():
    texts = [
        "A wild Pikachu appears.",
        "a wild pikachu   appears.",  # same text, different case/spacing
        "Something completely different.",
    ]
    assert count_exact_duplicates(texts) == 1


def test_count_exact_duplicates_is_zero_when_everything_is_different():
    texts = ["one thing happens", "a different thing happens", "yet another scene"]
    assert count_exact_duplicates(texts) == 0
