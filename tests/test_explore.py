"""
Tests for commands/explore.py's location guardrails and quest-completion
rewards.

/explore deliberately accepts ANY typed location, not just real
Pokemon places (see claude/design-decisions.md) - but whatever a
player types goes straight into an AI prompt, so two basic checks
happen first: reject anything blank/too long, and reject anything
caught by a profanity filter. See _rejection_reason_for()'s own
docstring in commands/explore.py for why this logic lives in its own
plain function rather than inline inside the command.
"""

import pytest

import database.db as db
from commands.explore import _apply_rewards_and_describe, _rejection_reason_for, MAX_LOCATION_LENGTH
from database.player import get_player_profile


def test_a_normal_location_is_accepted():
    assert _rejection_reason_for("Viridian Forest") is None


def test_an_unusual_but_harmless_location_is_still_accepted():
    # This project deliberately allows locations far outside the
    # Pokemon universe (see claude/design-decisions.md) - the
    # guardrails are only meant to catch blank/too-long/inappropriate
    # input, not to enforce a Pokemon-only theme.
    assert _rejection_reason_for("Boon Lay MRT Station") is None


def test_a_blank_location_is_rejected():
    assert _rejection_reason_for("") is not None


def test_a_location_that_is_only_whitespace_is_rejected():
    # explore() itself calls .strip() before this function ever sees
    # the location, but this function is tested on its own too, in
    # case that changes later.
    assert _rejection_reason_for("   ") is not None


def test_a_location_right_at_the_length_limit_is_accepted():
    exactly_the_limit = "a" * MAX_LOCATION_LENGTH
    assert _rejection_reason_for(exactly_the_limit) is None


def test_a_location_one_character_over_the_limit_is_rejected():
    one_too_long = "a" * (MAX_LOCATION_LENGTH + 1)
    assert _rejection_reason_for(one_too_long) is not None


def test_a_location_containing_profanity_is_rejected():
    assert _rejection_reason_for("fuck this place") is not None


# --- Quest-completion rewards -----------------------------------------

@pytest.fixture
def _use_temporary_database(tmp_path, monkeypatch):
    """
    Point database/db.py at a disposable temporary file for one test,
    same technique as tests/test_db_migration.py and
    tests/test_bot_registration.py - never touches the real
    data/pokerealm.db.
    """
    monkeypatch.setattr(db, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test_only.db"))
    db.init_db()


def test_finishing_a_quest_awards_coins_as_well_as_exp_and_friendship(_use_temporary_database):
    # A real gap between the draft report (which says quest completion
    # should "reward coins on completion") and the code as it stood -
    # this pins down the fix: _apply_rewards_and_describe() should now
    # increase the player's coin balance, not just their lead Pokemon's
    # EXP/friendship.
    discord_user_id = 12345
    profile_before = get_player_profile(discord_user_id)
    assert profile_before["coins"] == 0  # brand new player, nothing earned yet

    summary_text = _apply_rewards_and_describe(discord_user_id)

    assert summary_text is not None
    assert "coins" in summary_text.lower()

    profile_after = get_player_profile(discord_user_id)
    assert profile_after["coins"] > 0
