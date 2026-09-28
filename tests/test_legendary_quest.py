"""
Tests for pokemon/legendary_quest.py - the rare "a legendary reveals
itself" quest bonus (Ho-Oh/Lugia), and its integration points in
pokemon/data.py and pokemon/encounters.py.

Added following real tester feedback that quest choices didn't feel
like they affected gameplay - this is the mechanic built in direct
response to that.
"""

import random

import pytest

import database.db as db
import pokemon.legendary_quest as legendary_quest
from pokemon.data import WILD_POKEMON, DEX_NUMBER
from pokemon.encounters import generate_wild_encounter
from pokemon.legendary_quest import (
    QUEST_LEGENDARIES,
    MYSTICAL_JOIN_TEXT,
    roll_for_legendary_encounter,
    legendary_join_text,
)


# --- pokemon/data.py integration ---------------------------------------

def test_hooh_and_lugia_are_in_wild_pokemon_and_flagged_quest_exclusive():
    for name in QUEST_LEGENDARIES:
        entry = next((p for p in WILD_POKEMON if p["name"] == name), None)
        assert entry is not None, f"{name} should be a real entry in WILD_POKEMON"
        assert entry["rarity"] == "legendary"
        assert entry.get("quest_exclusive") is True


def test_hooh_and_lugia_have_their_real_national_dex_numbers():
    # Overridden explicitly in pokemon/data.py, since the auto-numbering
    # from WILD_POKEMON's order would otherwise give them the wrong
    # numbers (their position in the list, not their real Pokédex
    # number) - see that file's comment for why this matters for the
    # audio cry classifier.
    assert DEX_NUMBER["Ho-Oh"] == 250
    assert DEX_NUMBER["Lugia"] == 249


# --- pokemon/encounters.py: quest-exclusive species never appear in /catch --

def test_quest_exclusive_species_never_appear_as_a_normal_wild_encounter():
    # Not a statistical check with tolerance - this must be EXACTLY
    # zero, every single time, since Ho-Oh/Lugia are supposed to be
    # completely unobtainable through /catch, not just rare there.
    trials = 3000
    seen_names = {generate_wild_encounter()["name"] for _ in range(trials)}

    for name in QUEST_LEGENDARIES:
        assert name not in seen_names, (
            f"{name} is quest-exclusive and should never come from "
            f"generate_wild_encounter(), but appeared within {trials} trials"
        )


# --- pokemon/legendary_quest.py: the roll itself ------------------------

def test_roll_for_legendary_encounter_returns_none_when_the_roll_misses(monkeypatch):
    # random.random() returning exactly LEGENDARY_QUEST_CHANCE should
    # miss - the docstring's rule is "< chance succeeds", so landing
    # exactly on the boundary should NOT trigger the bonus.
    monkeypatch.setattr(random, "random", lambda: legendary_quest.LEGENDARY_QUEST_CHANCE)
    assert roll_for_legendary_encounter() is None


def test_roll_for_legendary_encounter_returns_a_quest_legendary_when_the_roll_hits(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    result = roll_for_legendary_encounter()
    assert result in QUEST_LEGENDARIES


def test_roll_for_legendary_encounter_can_return_either_species_over_many_rolls(monkeypatch):
    # Guaranteed to hit every time (roll always 0.0), so this is purely
    # checking random.choice() actually varies between the two
    # species rather than always picking the first one in the list.
    monkeypatch.setattr(random, "random", lambda: 0.0)
    results = {roll_for_legendary_encounter() for _ in range(200)}
    assert results == set(QUEST_LEGENDARIES)


# --- pokemon/legendary_quest.py: flavour text ---------------------------

def test_legendary_join_text_exists_for_every_quest_legendary():
    for name in QUEST_LEGENDARIES:
        assert name in MYSTICAL_JOIN_TEXT


def test_legendary_join_text_mentions_the_species_and_the_players_name():
    text = legendary_join_text("Ho-Oh", "TestPlayer")
    assert "Ho-Oh" in text
    assert "TestPlayer" in text

    text = legendary_join_text("Lugia", "AnotherPlayer")
    assert "Lugia" in text
    assert "AnotherPlayer" in text


# --- commands/explore.py integration ------------------------------------

@pytest.fixture
def _use_temporary_database(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test_only.db"))
    db.init_db()


def test_roll_legendary_bonus_adds_the_species_to_the_players_box_when_it_hits(
    _use_temporary_database, monkeypatch
):
    from commands.explore import _roll_legendary_bonus
    from database.player import get_player_profile

    monkeypatch.setattr(random, "random", lambda: 0.0)  # guaranteed hit
    monkeypatch.setattr(random, "choice", lambda seq: "Lugia")

    discord_user_id = 42424242
    get_player_profile(discord_user_id)  # create the player's row first

    result = _roll_legendary_bonus(discord_user_id, "TestPlayer")

    assert result is not None
    assert result["species"] == "Lugia"
    assert "Lugia" in result["text"]
    assert result["sprite_url"] is not None

    profile = get_player_profile(discord_user_id)
    assert "Lugia" in profile["box"]


def test_roll_legendary_bonus_does_nothing_when_the_roll_misses(
    _use_temporary_database, monkeypatch
):
    from commands.explore import _roll_legendary_bonus
    from database.player import get_player_profile

    monkeypatch.setattr(random, "random", lambda: 0.999)  # guaranteed miss

    discord_user_id = 13131313
    get_player_profile(discord_user_id)

    assert _roll_legendary_bonus(discord_user_id, "TestPlayer") is None

    profile = get_player_profile(discord_user_id)
    assert profile["box"] == []


# --- commands/explore.py: the legendary's own embed ---------------------

def test_build_legendary_embed_uses_a_big_image_not_a_thumbnail():
    # The whole point of giving the legendary its own embed (rather
    # than a field + thumbnail on the quest's embed) is so its sprite
    # renders big - set_image(), not set_thumbnail(). Asserting this
    # directly guards against someone "simplifying" it back to a
    # thumbnail later and quietly undoing the point of this change.
    from commands.explore import _build_legendary_embed

    legendary = {
        "species": "Ho-Oh",
        "text": "Ho-Oh wants to join your journey!",
        "sprite_url": "https://example.com/ho-oh.png",
    }
    embed = _build_legendary_embed(legendary)

    assert embed.image.url == "https://example.com/ho-oh.png"
    assert embed.thumbnail.url is None
    assert "Ho-Oh wants to join your journey!" in embed.description


def test_build_legendary_embed_handles_a_missing_sprite_url_gracefully():
    from commands.explore import _build_legendary_embed

    legendary = {
        "species": "Lugia",
        "text": "Lugia wants to join your journey!",
        "sprite_url": None,
    }
    embed = _build_legendary_embed(legendary)

    # Shouldn't crash, and shouldn't set an image with no URL to show.
    assert embed.image.url is None
