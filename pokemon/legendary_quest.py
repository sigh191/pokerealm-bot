"""
The "mystical legendary" quest bonus: a small chance, after a player
finishes a /explore quest chain, that Ho-Oh or Lugia reveals itself
and joins them.

This exists as a direct answer to real tester feedback (esprit98, see
claude/design-decisions.md and the report's evaluation chapter) that
/explore's quest choices didn't feel like they affected gameplay
beyond flavour text. Quest completion already rewards EXP, friendship,
and coins (see commands/explore.py's _apply_rewards_and_describe()) -
friendship specifically is quest-exclusive, since a successful /catch
never grants it (see database/player.py's apply_lead_rewards()) - but
this adds something bigger and rarer on top: a real, permanent
Pokémon that can ONLY be obtained by questing, never by catching (see
pokemon/data.py's "quest_exclusive" flag and the filter in
pokemon/encounters.py).

Deliberately built as a plain dice-roll plus fixed flavour text, NOT
something the AI model decides. This keeps the same "AI writes
narrative, the deterministic engine controls every outcome that needs
to be fair" split used everywhere else in this project (see the
report's Design chapter): whether a player actually receives a real,
permanent Pokémon has to be a fair, predictable roll that can be
tested and reasoned about, not something a language model could be
prompted into granting or refusing.
"""

import random

# The real, launched chance - deliberately rare, since landing a
# legendary is supposed to feel like a special moment, not a routine
# quest reward. Set once manual end-to-end testing (at a much higher
# value, to actually observe it firing) confirmed the feature worked
# correctly; see claude/design-decisions.md for that testing note.
# 1/150 rather than a round percentage so the exact intended odds are
# unambiguous from the source rather than rounded off (1/150 ≈ 0.67%).
LEGENDARY_QUEST_CHANCE = 1 / 150

# The two quest-exclusive legendaries (see pokemon/data.py). Kept as
# its own short list here, rather than searching WILD_POKEMON for
# every species flagged "quest_exclusive", so it's obvious at a glance
# exactly which two species this specific bonus can hand out - the
# ordinary Generation 1 legendaries (Articuno, Zapdos, Moltres,
# Mewtwo, Mew) stay catchable normally through /catch and are never
# awarded this way.
QUEST_LEGENDARIES = ["Ho-Oh", "Lugia"]

# Short "mystical" flavour text shown when a legendary reveals itself,
# one per species, filled in with the player's display name. Written
# by hand (not AI-generated) on purpose - a rare, exciting moment like
# this benefits from a guaranteed, consistently well-written result
# every single time, rather than depending on Ollama being available
# and returning something sensible. A future version could ask Llama
# to write a fresh variant each time, the same way quest scenes are
# generated, but that's left as a documented possibility rather than
# built now (see the report's Further Work section).
MYSTICAL_JOIN_TEXT = {
    "Ho-Oh": (
        "As the quest draws to a close, the sky above blazes with impossible colour - "
        "a rainbow trailing behind wings of fire. **Ho-Oh** descends from the clouds, "
        "watching {player} in silence for a long moment... then lands, as if it has "
        "been waiting for someone like {player} all along. **It wants to join your journey!**"
    ),
    "Lugia": (
        "The quest ends, but the sea itself seems to hold its breath. Deep beneath the "
        "waves, something ancient stirs - and **Lugia** rises, silver and immense, its "
        "eyes fixed on {player}. No words are needed. **It wants to join your journey!**"
    ),
}


def roll_for_legendary_encounter() -> str | None:
    """
    Roll for the quest-ending legendary bonus.

    Returns the species name that revealed itself ("Ho-Oh" or "Lugia",
    picked with equal probability between the two), or None if nothing
    happened this time. Called at most once per finished quest chain -
    see commands/explore.py's _roll_legendary_bonus().
    """
    if random.random() >= LEGENDARY_QUEST_CHANCE:
        return None
    return random.choice(QUEST_LEGENDARIES)


def legendary_join_text(species_name: str, player_display_name: str) -> str:
    """
    Build the ready-to-display flavour text for whichever legendary
    just revealed itself, with the player's own display name filled
    into the template.
    """
    template = MYSTICAL_JOIN_TEXT[species_name]
    return template.format(player=player_display_name)
