"""
Unit tests for pokemon/growth.py - the level/EXP/friendship maths.

This is the easiest part of the project to unit test properly: every
function here is a PURE function (same input always gives the same
output, nothing saved to a database, no randomness involved except the
two "roll a random reward" functions, which are tested by checking
their result stays inside the range they promise rather than one exact
number).

Run all tests in this project with: pytest
(from the project's root folder - pytest automatically finds every
tests/test_*.py file and every test_*() function inside them).
"""

from pokemon.growth import (
    MAX_LEVEL,
    MAX_FRIENDSHIP,
    EXP_REWARD_RANGE,
    FRIENDSHIP_REWARD_RANGE,
    CATCH_EXP_REWARD_RANGE,
    exp_required_for_level,
    roll_exp_reward,
    roll_friendship_reward,
    roll_catch_exp_reward,
    apply_exp,
    apply_friendship,
)


def test_exp_required_for_level_1_is_zero():
    # A freshly caught Pokemon starts at level 1 with 0 EXP - see
    # growth.py's docstring for exp_required_for_level().
    assert exp_required_for_level(1) == 0


def test_exp_required_for_level_matches_formula():
    # exp_required_for_level() is documented as EXP_BASE * (level **
    # EXP_EXPONENT) for any level above 1 - checking it against a
    # couple of hand-calculated values catches a typo in the formula
    # (e.g. using + instead of ** by accident) that would otherwise
    # only show up much later as "levelling feels wrong".
    assert exp_required_for_level(2) == 20 * (2 ** 2)   # 80
    assert exp_required_for_level(10) == 20 * (10 ** 2)  # 2000


def test_apply_exp_gives_exp_without_levelling_up():
    # A small EXP gain that doesn't cross the next level's threshold
    # should just add up, not trigger a level-up.
    pokemon = {"level": 1, "exp": 0, "friendship": 0}
    result = apply_exp(pokemon, exp_gained=5)

    assert result["exp"] == 5
    assert result["level"] == 1


def test_apply_exp_levels_up_exactly_at_the_threshold():
    # Levelling from 1 to 2 needs exp_required_for_level(2) = 80 EXP
    # (see test above). Landing EXACTLY on that number should level up
    # - this checks the ">=" in growth.py's while loop, not "]>".
    pokemon = {"level": 1, "exp": 0, "friendship": 0}
    result = apply_exp(pokemon, exp_gained=exp_required_for_level(2))

    assert result["level"] == 2


def test_apply_exp_can_cross_more_than_one_level_at_once():
    # A single big EXP reward (e.g. from a legendary catch) should be
    # able to jump more than one level in one go, not just cap out at
    # +1 level per call.
    pokemon = {"level": 1, "exp": 0, "friendship": 0}
    result = apply_exp(pokemon, exp_gained=exp_required_for_level(5))

    assert result["level"] >= 5


def test_apply_exp_does_not_go_past_max_level():
    # A Pokemon already at (or very near) MAX_LEVEL should never level
    # past it, and its EXP should be capped rather than climbing
    # forever with nowhere useful to go.
    pokemon = {"level": MAX_LEVEL, "exp": exp_required_for_level(MAX_LEVEL), "friendship": 0}
    result = apply_exp(pokemon, exp_gained=999_999)

    assert result["level"] == MAX_LEVEL
    assert result["exp"] == exp_required_for_level(MAX_LEVEL)


def test_apply_exp_does_not_mutate_the_original_dict():
    # apply_exp()'s docstring promises it returns a NEW dict rather
    # than changing the one it was given - this matters because the
    # caller (database/player.py) relies on comparing the before/after
    # dicts to detect a level-up.
    pokemon = {"level": 1, "exp": 0, "friendship": 0}
    apply_exp(pokemon, exp_gained=50)

    assert pokemon == {"level": 1, "exp": 0, "friendship": 0}


def test_apply_friendship_adds_up_normally():
    pokemon = {"level": 1, "exp": 0, "friendship": 10}
    result = apply_friendship(pokemon, friendship_gained=5)

    assert result["friendship"] == 15


def test_apply_friendship_does_not_go_past_max_friendship():
    pokemon = {"level": 1, "exp": 0, "friendship": MAX_FRIENDSHIP - 2}
    result = apply_friendship(pokemon, friendship_gained=50)

    assert result["friendship"] == MAX_FRIENDSHIP


def test_roll_exp_reward_stays_within_its_declared_range():
    # roll_exp_reward() is random, so there's no one "correct" answer
    # to check against - instead, this calls it a lot of times and
    # checks EVERY result lands inside EXP_REWARD_RANGE. 200 calls is
    # enough to be confident a bug (e.g. an off-by-one in the range,
    # or the wrong variable used) would get caught, without making the
    # test slow or flaky.
    low, high = EXP_REWARD_RANGE
    for _ in range(200):
        assert low <= roll_exp_reward() <= high


def test_roll_friendship_reward_stays_within_its_declared_range():
    low, high = FRIENDSHIP_REWARD_RANGE
    for _ in range(200):
        assert low <= roll_friendship_reward() <= high


def test_roll_catch_exp_reward_stays_within_range_for_every_rarity():
    # Every rarity tier has its own (low, high) range in
    # CATCH_EXP_REWARD_RANGE - this checks all four, not just one, so
    # a mistake in e.g. the "legendary" entry specifically would still
    # get caught.
    for rarity, (low, high) in CATCH_EXP_REWARD_RANGE.items():
        for _ in range(200):
            assert low <= roll_catch_exp_reward(rarity) <= high
