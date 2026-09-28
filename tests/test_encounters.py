"""
Unit tests for pokemon/encounters.py - wild encounters and catch rolls.

Two different testing styles are used in this file on purpose:

1. Most tests below use pytest's `monkeypatch` fixture to control
   exactly what random.randint()/random.choices() return, so the test
   can check an EXACT, predictable outcome (e.g. "a roll of exactly
   the catch rate should succeed") instead of hoping to get lucky with
   real randomness.

2. The one test at the very bottom,
   test_generate_wild_encounter_matches_configured_rarity_weights(),
   deliberately does NOT mock randomness - it runs the real function
   thousands of times and checks the OVERALL distribution roughly
   matches RARITY_WEIGHTS. This is a smaller, automated version of the
   20,000-trial statistical validation described in the report's
   evaluation chapter, which was previously only ever run by hand and
   never saved as a real, repeatable test.
"""

import random

import pytest

from pokemon.data import WILD_POKEMON, RARITY_WEIGHTS, BASE_CATCH_RATE
from pokemon.economy import COIN_REWARD_RANGE
from pokemon.encounters import attempt_catch, generate_wild_encounter


# A fixed, known Pokemon to attempt_catch() against, so every test
# below is testing the exact same input and only varying the random
# roll / guaranteed flag.
SAMPLE_COMMON_POKEMON = {"name": "Rattata", "rarity": "common"}


def test_attempt_catch_guaranteed_always_succeeds_with_no_roll():
    # Thrown with a Master Ball (see commands/catch.py) - should always
    # succeed, and "roll" should be None since no roll was actually
    # made (checking this matters because the caller uses roll=None to
    # decide whether to show a "you rolled X" message).
    result = attempt_catch(SAMPLE_COMMON_POKEMON, guaranteed=True)

    assert result["caught"] is True
    assert result["roll"] is None
    assert result["guaranteed"] is True


def test_attempt_catch_guaranteed_still_pays_out_coins_in_range():
    low, high = COIN_REWARD_RANGE["common"]
    result = attempt_catch(SAMPLE_COMMON_POKEMON, guaranteed=True)

    assert low <= result["base_coins"] <= high


def test_attempt_catch_succeeds_when_roll_lands_exactly_on_the_catch_rate(monkeypatch):
    # attempt_catch()'s docstring says a roll AT OR UNDER the catch
    # rate succeeds - this checks the "at" boundary specifically
    # (roll == catch_rate exactly), which is the case most likely to
    # be broken by an off-by-one mistake (e.g. writing "roll <
    # catch_rate" instead of "roll <= catch_rate").
    catch_rate = BASE_CATCH_RATE["common"]
    monkeypatch.setattr(random, "randint", lambda a, b: catch_rate)

    result = attempt_catch(SAMPLE_COMMON_POKEMON, guaranteed=False)

    assert result["caught"] is True
    assert result["roll"] == catch_rate


def test_attempt_catch_fails_when_roll_lands_just_above_the_catch_rate(monkeypatch):
    catch_rate = BASE_CATCH_RATE["common"]
    monkeypatch.setattr(random, "randint", lambda a, b: catch_rate + 1)

    result = attempt_catch(SAMPLE_COMMON_POKEMON, guaranteed=False)

    assert result["caught"] is False
    assert result["base_coins"] == 0


def test_attempt_catch_reports_the_correct_catch_rate_for_each_rarity():
    # BASE_CATCH_RATE has one entry per rarity tier - looping over all
    # four here (rather than just testing "common") makes sure the
    # rarity is actually being used to look up the rate, not hardcoded.
    for rarity, expected_rate in BASE_CATCH_RATE.items():
        pokemon = {"name": "Test Pokemon", "rarity": rarity}
        result = attempt_catch(pokemon, guaranteed=True)
        assert result["catch_rate"] == expected_rate


def test_generate_wild_encounter_always_returns_a_real_pokemon_with_matching_rarity():
    # Every encounter should be one of the 151 real Pokemon in
    # WILD_POKEMON, and its "rarity" field should be internally
    # consistent (not, say, a Pikachu labelled "legendary").
    encounter = generate_wild_encounter()

    matching_entry = next((p for p in WILD_POKEMON if p["name"] == encounter["name"]), None)
    assert matching_entry is not None
    assert encounter["rarity"] == matching_entry["rarity"]


@pytest.mark.slow
def test_generate_wild_encounter_matches_configured_rarity_weights():
    """
    Statistical sanity check, not a strict unit test (see the module
    docstring above) - runs 5,000 real encounters and checks the
    observed rarity split is in the right ballpark for RARITY_WEIGHTS
    (60/30/9/1). A generous +/-10 percentage point tolerance is used
    deliberately, since this uses real randomness rather than a fixed
    seed - it's checking "roughly the right shape", the same thing the
    report's Chapter 5 already checked by hand with 20,000 trials, not
    verifying an exact percentage.
    """
    trials = 5000
    counts = {rarity: 0 for rarity in RARITY_WEIGHTS}

    for _ in range(trials):
        encounter = generate_wild_encounter()
        counts[encounter["rarity"]] += 1

    total_weight = sum(RARITY_WEIGHTS.values())

    for rarity, weight in RARITY_WEIGHTS.items():
        expected_fraction = weight / total_weight
        observed_fraction = counts[rarity] / trials
        assert abs(observed_fraction - expected_fraction) < 0.10, (
            f"{rarity}: expected roughly {expected_fraction:.1%}, "
            f"observed {observed_fraction:.1%} over {trials} trials"
        )
