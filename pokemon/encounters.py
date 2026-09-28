"""
Deterministic, rule-based logic for wild Pokémon encounters.

Nothing in this file talks to the AI/Ollama module. That's on purpose:
this is the "game engine" side of the hybrid design - whether a catch
succeeds has to be predictable and fair (a fixed formula plus Python's
random number generator), not something an AI decides.
"""

import random

from pokemon.data import WILD_POKEMON, RARITY_WEIGHTS, BASE_CATCH_RATE
from pokemon.economy import roll_coin_reward


def generate_wild_encounter() -> dict:
    """
    Pick a random wild Pokémon for the player to run into.

    This is a weighted random choice: rarer tiers (see RARITY_WEIGHTS)
    are much less likely to be picked than common ones, which is what
    makes rare/legendary Pokémon feel special.
    """
    rarity = random.choices(
        population=list(RARITY_WEIGHTS.keys()),
        weights=list(RARITY_WEIGHTS.values()),
        k=1,
    )[0]

    # "quest_exclusive" species (currently Ho-Oh and Lugia - see
    # pokemon/data.py and pokemon/legendary_quest.py) are deliberately
    # excluded from ordinary wild encounters: they're a rare bonus
    # reward for finishing a /explore quest, not something /catch
    # should ever be able to stumble into on its own.
    candidates = [
        p for p in WILD_POKEMON
        if p["rarity"] == rarity and not p.get("quest_exclusive")
    ]
    return random.choice(candidates)


def attempt_catch(pokemon: dict, guaranteed: bool = False) -> dict:
    """
    Attempt to catch the given Pokémon, and report back exactly how
    the roll went (not just whether it succeeded), so the player can
    see how close/lucky the attempt was - a lot more interesting than
    a plain yes/no.

    This "rolls a d100": pick a random whole number from 1 to 100, and
    the catch succeeds if that roll lands at or under the Pokémon's
    catch rate (see BASE_CATCH_RATE in pokemon/data.py). E.g. an 80%
    catch rate succeeds on a roll of 80 or lower.

    If `guaranteed` is True - thrown with a Master Ball instead of a
    normal Poké Ball - no roll happens at all, and the catch always
    succeeds, the same way Master Balls work in the real games. The
    caller (commands/catch.py) is responsible for checking the player
    actually owns a Master Ball and consuming it BEFORE calling this
    with guaranteed=True - this function just trusts whatever it's
    told and doesn't touch the database itself.

    A successful catch also rolls a coin reward (see
    pokemon/economy.py) - this is the BASE amount, before any
    multiplier from upgrades like the Amulet Coin, since this file
    doesn't know anything about a specific player's purchases. The
    caller is responsible for applying that multiplier and actually
    crediting the coins.

    Returns a dict:
        {"caught": bool, "roll": int or None, "catch_rate": int,
         "base_coins": int, "guaranteed": bool}
    "roll" is None when guaranteed=True, since no roll was made.
    """
    catch_rate = BASE_CATCH_RATE[pokemon["rarity"]]

    if guaranteed:
        base_coins = roll_coin_reward(pokemon["rarity"])
        return {
            "caught": True,
            "roll": None,
            "catch_rate": catch_rate,
            "base_coins": base_coins,
            "guaranteed": True,
        }

    roll = random.randint(1, 100)
    caught = roll <= catch_rate
    base_coins = roll_coin_reward(pokemon["rarity"]) if caught else 0

    return {
        "caught": caught,
        "roll": roll,
        "catch_rate": catch_rate,
        "base_coins": base_coins,
        "guaranteed": False,
    }
