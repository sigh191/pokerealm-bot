"""
Per-Pokémon experience, levelling, and friendship.

This is kept separate from pokemon/economy.py (which is about the
PLAYER's coin economy) because this file is about progression that
belongs to an individual Pokémon on a player's team, not the player's
account as a whole.

Like pokemon/encounters.py, everything in this file is deterministic,
plain Python - no AI involved. Quest completions (see
commands/explore.py) decide WHEN a Pokémon earns EXP/friendship, but
the actual maths of how much EXP a level needs, and what counts as a
level-up, lives here and only here - the same "engine controls
mechanics" split used throughout this project.
"""

import random

MAX_LEVEL = 100
MAX_FRIENDSHIP = 100

# How much EXP a Pokémon needs, in total, to have REACHED a given
# level (counting from level 1, which always needs 0). Quadratic
# growth means the amount needed per level keeps climbing the whole
# way, so - combined with EXP_REWARD_RANGE below - getting from level
# 1 to level 100 is a genuine, multi-session grind rather than
# something a single afternoon of quests could finish. That's a
# deliberate scope decision, not an accident: see the project report's
# discussion of this feature for the reasoning.
EXP_BASE = 20
EXP_EXPONENT = 2


def exp_required_for_level(level: int) -> int:
    """
    Total cumulative EXP needed to have REACHED `level`, starting from
    level 1 (which always needs 0 - a freshly caught Pokémon starts
    there). This is a pure function of `level` alone, not of any
    specific Pokémon, so it can be tested and reasoned about on its
    own - the same approach the project's evaluation chapter already
    takes with pokemon/encounters.py's probabilities.
    """
    if level <= 1:
        return 0
    return EXP_BASE * (level ** EXP_EXPONENT)


# The random amount of EXP one completed quest awards. A random RANGE,
# not a fixed number, for the same reason pokemon/economy.py's
# COIN_REWARD_RANGE is a range - it keeps repeated grinding from
# feeling perfectly predictable.
EXP_REWARD_RANGE = (15, 40)

# The random amount of friendship one completed quest awards.
FRIENDSHIP_REWARD_RANGE = (1, 5)


def roll_exp_reward() -> int:
    """Pick a random EXP amount to award for completing one quest."""
    low, high = EXP_REWARD_RANGE
    return random.randint(low, high)


def roll_friendship_reward() -> int:
    """Pick a random friendship amount to award for completing one quest."""
    low, high = FRIENDSHIP_REWARD_RANGE
    return random.randint(low, high)


# EXP awarded to the player's LEAD Pokémon for a successful /catch,
# per rarity tier of whatever was just caught (see
# pokemon/encounters.py) - same tiered-range idea as
# pokemon/economy.py's COIN_REWARD_RANGE.
#
# Deliberately kept well below EXP_REWARD_RANGE (15-40 for a full,
# multi-step quest): catching is a single click with no waiting, so if
# it paid similar EXP to a quest, there'd be no reason to ever bother
# with /explore. Common catches (by far the most frequent encounter -
# see RARITY_WEIGHTS in pokemon/data.py) only trickle a few EXP at a
# time on purpose, to keep the level 1-100 climb a genuine grind
# rather than something a single catching session could rush through.
# Legendary catches are the one exception - rare enough that paying
# out roughly quest-level EXP still doesn't meaningfully speed up the
# overall grind, and makes landing one feel appropriately special.
CATCH_EXP_REWARD_RANGE = {
    "common": (3, 8),
    "uncommon": (6, 15),
    "rare": (12, 25),
    "legendary": (25, 50),
}


def roll_catch_exp_reward(rarity: str) -> int:
    """Pick a random EXP amount to award the lead Pokémon for catching one of `rarity`."""
    low, high = CATCH_EXP_REWARD_RANGE[rarity]
    return random.randint(low, high)


def apply_exp(pokemon: dict, exp_gained: int) -> dict:
    """
    Add `exp_gained` to a single Pokémon's stats (a {"level", "exp",
    "friendship"} dict - see database/player.py's shared-per-species
    pokemon_stats), levelling it up as many times as the new total EXP
    supports (in case one big reward crosses more than one level's
    threshold at once).

    Returns a NEW dict rather than mutating `pokemon` in place - this
    function is pure game logic, not a database write. The caller
    (database/player.py) decides when to actually save the result.
    """
    pokemon = dict(pokemon)
    pokemon["exp"] = pokemon.get("exp", 0) + exp_gained

    while (
        pokemon["level"] < MAX_LEVEL
        and pokemon["exp"] >= exp_required_for_level(pokemon["level"] + 1)
    ):
        pokemon["level"] += 1

    if pokemon["level"] >= MAX_LEVEL:
        # Levels never go past MAX_LEVEL, and EXP is capped at exactly
        # what level 100 needed, so a level-100 Pokémon doesn't keep
        # silently accumulating EXP it can never use forever.
        pokemon["level"] = MAX_LEVEL
        pokemon["exp"] = min(pokemon["exp"], exp_required_for_level(MAX_LEVEL))

    return pokemon


def apply_friendship(pokemon: dict, friendship_gained: int) -> dict:
    """Add `friendship_gained` to a Pokémon's friendship, capped at MAX_FRIENDSHIP."""
    pokemon = dict(pokemon)
    pokemon["friendship"] = min(
        MAX_FRIENDSHIP, pokemon.get("friendship", 0) + friendship_gained
    )
    return pokemon
