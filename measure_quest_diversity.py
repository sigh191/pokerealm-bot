"""
Generates a quest for the SAME location, player level, and team many
times in a row through the REAL AI pipeline, and measures how much the
resulting text actually varies - the concrete measurement Chapter 2.5
of the report says is needed to back up PokeRealm's claim that its
AI-generated quests are more varied than the always-identical text
used by the Discord bots reviewed in Chapter 2, rather than relying on
manual inspection ("it looked varied when I tried it") alone.

This needs a real, running Ollama server (the same requirement as
actually playing the bot) and makes NUMBER_OF_SAMPLES real calls to
it, so it is NOT part of the automated pytest suite - a normal test
run shouldn't depend on an external service being up, and this is
meant to be run once (or a few times) to get a number for the report,
not on every code change. The actual diversity maths lives in
evaluation/lexical_diversity.py instead, which IS unit tested (see
tests/test_lexical_diversity.py), since that part has no such
dependency.

Run with: python measure_quest_diversity.py
(takes a minute or two, depending on how fast Ollama responds locally)
"""

from ai.quest_generator import generate_quest
from evaluation.lexical_diversity import (
    distinct_n,
    average_type_token_ratio,
    count_exact_duplicates,
)

# Deliberately fixed and unchanged across every call - only the
# WORDING the model chooses is being measured here, since the
# location, player level, and team are identical every single time.
# This isolates exactly the claim this script exists to check: "does
# the SAME input produce varied output", which is a much more
# convincing (and harder to satisfy) thing to measure than "do
# different inputs produce different output".
SAMPLE_LOCATION = "Viridian Forest"
SAMPLE_PLAYER_LEVEL = 12
SAMPLE_TEAM = [{"name": "Charmander", "level": 12, "exp": 0, "friendship": 0}]

# How many quests to generate for the same location. 30 is enough to
# get a stable diversity score without taking too long against a
# locally-hosted model.
NUMBER_OF_SAMPLES = 30


def _print_diversity_report(label: str, texts: list[str]) -> None:
    """
    Print Distinct-1/2, average TTR, and exact-duplicate count for one
    set of texts, under a heading - pulled into its own function so the
    SAME breakdown can be run separately for titles, scenes, and the
    full combined text below, instead of only ever seeing one pooled
    number that can hide a problem in a specific field (see the
    "combined text" heading's own comment for why that matters here).
    """
    print(f"\n--- {label} ---")
    print(f"Distinct-1 (unique single words, pooled across all {len(texts)} quests): {distinct_n(texts, n=1):.3f}")
    print(f"Distinct-2 (unique word pairs, pooled across all {len(texts)} quests):   {distinct_n(texts, n=2):.3f}")
    print(f"Average type-token ratio (unique words / total words, per quest):        {average_type_token_ratio(texts):.3f}")
    print(f"Exact duplicates: {count_exact_duplicates(texts)} out of {len(texts)}")


def main():
    print(
        f"Generating {NUMBER_OF_SAMPLES} quests for '{SAMPLE_LOCATION}' "
        f"(same location, player level, and team every time)...\n"
    )

    titles = []
    scenes = []
    combined_texts = []

    for i in range(NUMBER_OF_SAMPLES):
        quest, _vibe, _sound = generate_quest(SAMPLE_LOCATION, SAMPLE_PLAYER_LEVEL, SAMPLE_TEAM)

        title = quest.get("title", "")
        scene = quest.get("scene", "")

        titles.append(title)
        scenes.append(scene)
        # Combining all four fields gives a fuller sample of text per
        # quest than "scene" alone (the prompt caps "scene" at under
        # 100 words), which is useful for an overall impression - but
        # see the comment on its own heading below for why this number
        # ALONE isn't the full picture.
        combined_texts.append(" ".join([title, scene, quest.get("npc", ""), quest.get("objective", "")]))

        print(f"  [{i + 1}/{NUMBER_OF_SAMPLES}] {title or '(no title)'}")

    # Reported separately per field, not just as one pooled number,
    # because a short field (like "title", usually 2-4 words) can
    # repeat constantly while still barely denting an aggregate score
    # dominated by much longer "scene" text - pooling everything
    # together would hide exactly that kind of problem instead of
    # revealing it. This happened in practice: the same fixed
    # vibe/sound (from always using the same Pokemon and location)
    # made Llama repeatedly reach for near-identical titles, something
    # only visible once titles are measured on their own.
    _print_diversity_report("TITLES only", titles)
    _print_diversity_report("SCENES only", scenes)
    _print_diversity_report("Combined (title + scene + npc + objective)", combined_texts)

    print(
        "\nHigher Distinct-n/TTR values (closer to 1.0) mean more variety; 0 exact "
        "duplicates means nothing was generated identically twice. Check the TITLES "
        "score separately from SCENES - a low title score with a high scene score means "
        "the model varies the story but keeps reusing similar titles, which the combined "
        "score alone would not make obvious."
    )


if __name__ == "__main__":
    main()
