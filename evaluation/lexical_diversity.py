"""
Pure, dependency-light functions for measuring how much a set of
generated texts vary from each other.

This backs up the claim made throughout the report (see Chapter 2.1's
comparison table and Chapter 5.7) that PokeRealm's AI-generated quest
text is more varied than the static, always-identical text used by the
Discord bots reviewed in Chapter 2 - Section 2.5 says this needs to be
"measured rather than only observed", citing Shaib et al. (2025), who
review and standardise metrics for measuring the lexical diversity of
generated text.

Distinct-n (implemented below) is one of the most established and
widely cited of those metrics, originally introduced by Li et al.
(2016) - the fraction of all n-word sequences across a whole SET of
generated texts that are unique. It directly answers the question this
project actually needs answered: "if you ask for a quest in the same
location many times, does the model keep saying almost the same
thing?" A low score means yes (repetitive); a high score means the
wording genuinely varies each time.

Kept completely separate from anything AI/network-related - no Ollama
call happens anywhere in this file - so these functions are pure,
deterministic, and can be unit tested directly and instantly (see
tests/test_lexical_diversity.py). The part that actually needs a real,
running Ollama server - calling generate_quest() repeatedly and
measuring its output with these functions - lives in
measure_quest_diversity.py instead, since that can't be part of the
normal automated test suite (a test run shouldn't depend on an
external service being up).
"""

import re


def _tokenize(text: str) -> list[str]:
    """
    Split text into lowercase word tokens, ignoring punctuation - e.g.
    "The Gyarados attacks!" -> ["the", "gyarados", "attacks"].

    Deliberately simple (no external NLP library needed) - good enough
    for comparing word/n-gram overlap between short AI-generated quest
    descriptions, which is all this project needs it for.
    """
    return re.findall(r"[a-z0-9']+", text.lower())


def distinct_n(texts: list[str], n: int) -> float:
    """
    Distinct-n (Li et al., 2016): the fraction of all n-word sequences
    across EVERY text in `texts`, pooled together, that are unique.

    distinct_n(texts, n=1) close to 1.0 means the generated texts, as a
    whole, barely repeat any individual words; close to 0.0 means the
    same words are being reused constantly. distinct_n(texts, n=2)
    does the same thing for consecutive WORD PAIRS instead of single
    words, which is generally a stronger signal of genuine variety -
    two texts can share lots of common single words (like "the" or
    "Pokemon") while still describing completely different scenes, but
    sharing whole word PAIRS repeatedly is a stronger sign of the model
    reusing the same phrasing.

    Returns 0.0 for empty input rather than dividing by zero.
    """
    all_ngrams = []
    for text in texts:
        tokens = _tokenize(text)
        ngrams = list(zip(*(tokens[i:] for i in range(n))))
        all_ngrams.extend(ngrams)

    if not all_ngrams:
        return 0.0

    return len(set(all_ngrams)) / len(all_ngrams)


def average_type_token_ratio(texts: list[str]) -> float:
    """
    Average Type-Token Ratio (TTR) across `texts`.

    For ONE text on its own, TTR is (number of unique words) / (total
    words) - this returns the average of that across every text.
    Unlike distinct_n() above (which measures variety ACROSS the whole
    set of texts), this measures how repetitive each INDIVIDUAL piece
    of generated text is internally (e.g. does one quest scene keep
    reusing the same few words over and over within itself).

    Returns 0.0 if `texts` is empty or every text is empty.
    """
    ratios = []
    for text in texts:
        tokens = _tokenize(text)
        if tokens:
            ratios.append(len(set(tokens)) / len(tokens))

    return sum(ratios) / len(ratios) if ratios else 0.0


def count_exact_duplicates(texts: list[str]) -> int:
    """
    How many texts in `texts` are EXACT duplicates of an earlier one in
    the list (ignoring case and extra whitespace) - a blunt but very
    easy to explain check, separate from the diversity scores above:
    if generate_quest() were somehow producing the identical scene text
    twice, this catches that directly, in a way an aggregate diversity
    score alone could obscure.
    """
    seen = set()
    duplicate_count = 0
    for text in texts:
        normalised = " ".join(text.lower().split())
        if normalised in seen:
            duplicate_count += 1
        else:
            seen.add(normalised)
    return duplicate_count
