"""
Tests for commands/dev.py - the owner-only ;spawn and ;setlevel
commands (and the shared species-name lookup helper they both use).

Both commands are deliberately restricted to a single hard-coded
Discord user ID (Keith's own, DEVELOPER_DISCORD_ID) - see dev.py's own
module docstring for why a full permissions system would be overkill
here. These tests register the command on a real (but disconnected)
discord.py Bot, the same technique tests/test_bot_registration.py uses
for bot.py itself, so the actual registered command's callback is what
gets exercised - not a reimplementation of its logic.

Every command response is an embed, so these tests read the message
text from `kwargs["embed"].description` rather than a plain
positional string argument.
"""

import asyncio

import discord
import pytest
from discord.ext import commands

import database.db as db
import commands.dev as dev_module
from database.player import get_player_profile
from pokemon.data import WILD_POKEMON
from pokemon.growth import MAX_LEVEL, exp_required_for_level

DEVELOPER_ID = dev_module.DEVELOPER_DISCORD_ID
NOT_THE_DEVELOPER_ID = DEVELOPER_ID + 1  # any other ID


class FakeContext:
    """Minimal ctx.send()-recording stand-in - same idea as test_bot_registration.py's FakeContext."""

    def __init__(self, author_id: int):
        self.author = type("Author", (), {"id": author_id})()
        self.sent_messages = []

    async def send(self, *args, **kwargs):
        self.sent_messages.append((args, kwargs))


@pytest.fixture
def _use_temporary_database(tmp_path, monkeypatch):
    """Same disposable-database technique as the other test files - never touches data/pokerealm.db."""
    monkeypatch.setattr(db, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test_only.db"))
    db.init_db()


@pytest.fixture
def spawn_command():
    """Register commands/dev.py's commands on a throwaway Bot and hand back the real /spawn command object."""
    bot = commands.Bot(command_prefix=";", intents=discord.Intents.default())
    dev_module.setup(bot)
    return bot.get_command("spawn")


@pytest.fixture
def setlevel_command():
    """Same idea as spawn_command, but hands back /setlevel instead."""
    bot = commands.Bot(command_prefix=";", intents=discord.Intents.default())
    dev_module.setup(bot)
    return bot.get_command("setlevel")


# --- _find_species() --------------------------------------------------------

def test_find_species_matches_case_insensitively():
    assert dev_module._find_species("dragonite") == "Dragonite"
    assert dev_module._find_species("DRAGONITE") == "Dragonite"
    assert dev_module._find_species("Dragonite") == "Dragonite"


def test_find_species_matches_every_real_species_name_exactly():
    # Round-trips every one of the 151 real names through the
    # lower-cased lookup, catching any accidental typo in _find_species
    # itself rather than just spot-checking a couple of names.
    for pokemon in WILD_POKEMON:
        assert dev_module._find_species(pokemon["name"].lower()) == pokemon["name"]


def test_find_species_returns_none_for_an_unrecognised_name():
    assert dev_module._find_species("Not A Real Pokemon") is None


# --- ;spawn ------------------------------------------------------------------

def test_spawn_rejects_a_non_developer(spawn_command, _use_temporary_database):
    ctx = FakeContext(author_id=NOT_THE_DEVELOPER_ID)
    asyncio.run(spawn_command.callback(ctx, "123", pokemon="Dragonite"))

    assert "permission" in ctx.sent_messages[0][1]["embed"].description.lower()

    # Nothing should have been spawned - the target's box (if a row was
    # even created) must stay empty.
    profile = get_player_profile(123)
    assert profile["box"] == []


def test_spawn_adds_a_normal_species_to_the_targets_box(spawn_command, _use_temporary_database):
    target_id = 456
    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(spawn_command.callback(ctx, str(target_id), pokemon="Dragonite"))

    profile = get_player_profile(target_id)
    assert profile["box"] == ["Dragonite"]
    # A spawned Pokémon should NOT touch the target's existing team.
    assert [p["name"] for p in profile["team"]] == ["Pikachu"]


def test_spawn_stores_a_shiny_prefixed_species_correctly(spawn_command, _use_temporary_database):
    target_id = 789
    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(spawn_command.callback(ctx, str(target_id), pokemon="Shiny Vaporeon"))

    profile = get_player_profile(target_id)
    assert profile["box"] == ["Shiny Vaporeon"]


def test_spawn_matches_species_names_case_insensitively(spawn_command, _use_temporary_database):
    target_id = 999
    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(spawn_command.callback(ctx, str(target_id), pokemon="dragonite"))

    profile = get_player_profile(target_id)
    # Stored using the CANONICAL capitalisation, not whatever case the
    # developer happened to type.
    assert profile["box"] == ["Dragonite"]


def test_spawn_rejects_an_unrecognised_species_name(spawn_command, _use_temporary_database):
    target_id = 111
    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(spawn_command.callback(ctx, str(target_id), pokemon="Not A Real Pokemon"))

    assert "recognised" in ctx.sent_messages[0][1]["embed"].description.lower()
    profile = get_player_profile(target_id)
    assert profile["box"] == []


def test_spawn_rejects_an_invalid_discord_id(spawn_command, _use_temporary_database):
    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(spawn_command.callback(ctx, "not-a-real-id", pokemon="Dragonite"))

    assert "valid discord user id" in ctx.sent_messages[0][1]["embed"].description.lower()


# --- ;setlevel -----------------------------------------------------------

def test_setlevel_rejects_a_non_developer(setlevel_command, _use_temporary_database):
    target_id = 222
    ctx = FakeContext(author_id=NOT_THE_DEVELOPER_ID)
    # The target already owns a Pikachu (DEFAULT_TEAM) - make sure it's
    # genuinely the permission check stopping this, not "no such Pokémon".
    get_player_profile(target_id)
    asyncio.run(setlevel_command.callback(ctx, str(target_id), "Pikachu", 50))

    assert "permission" in ctx.sent_messages[0][1]["embed"].description.lower()

    # Nothing should have changed - still level 1.
    profile = get_player_profile(target_id)
    assert profile["team"][0]["level"] == 1


def test_setlevel_rejects_an_invalid_discord_id(setlevel_command, _use_temporary_database):
    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(setlevel_command.callback(ctx, "not-a-real-id", "Pikachu", 50))

    assert "valid discord user id" in ctx.sent_messages[0][1]["embed"].description.lower()


@pytest.mark.parametrize("bad_level", [0, -5, MAX_LEVEL + 1])
def test_setlevel_rejects_a_level_outside_1_to_max(setlevel_command, _use_temporary_database, bad_level):
    target_id = 333
    get_player_profile(target_id)  # owns the default Pikachu
    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(setlevel_command.callback(ctx, str(target_id), "Pikachu", bad_level))

    assert f"between 1 and {MAX_LEVEL}" in ctx.sent_messages[0][1]["embed"].description

    profile = get_player_profile(target_id)
    assert profile["team"][0]["level"] == 1


def test_setlevel_rejects_an_unrecognised_species_name(setlevel_command, _use_temporary_database):
    target_id = 444
    get_player_profile(target_id)
    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(setlevel_command.callback(ctx, str(target_id), "Not A Real Pokemon", 50))

    assert "recognised" in ctx.sent_messages[0][1]["embed"].description.lower()


def test_setlevel_rejects_a_species_the_player_doesnt_own(setlevel_command, _use_temporary_database):
    target_id = 555
    # Owns only the default Pikachu - never caught a Dragonite.
    get_player_profile(target_id)
    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(setlevel_command.callback(ctx, str(target_id), "Dragonite", 50))

    description = ctx.sent_messages[0][1]["embed"].description.lower()
    assert "doesn't have" in description


def test_setlevel_sets_level_and_matching_exp_for_a_team_pokemon(setlevel_command, _use_temporary_database):
    target_id = 666
    get_player_profile(target_id)  # owns the default Pikachu, in their team
    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(setlevel_command.callback(ctx, str(target_id), "Pikachu", 50))

    profile = get_player_profile(target_id)
    pikachu = profile["team"][0]
    assert pikachu["level"] == 50
    # EXP must match exactly what pokemon/growth.py says Level 50 needs -
    # not just the level number changing on its own, which would leave a
    # tiny reward able to bump the level again immediately.
    assert pikachu["exp"] == exp_required_for_level(50)


def test_setlevel_works_for_a_boxed_species(setlevel_command, _use_temporary_database):
    from database.player import add_pokemon_to_box

    target_id = 777
    get_player_profile(target_id)
    add_pokemon_to_box(target_id, "Dragonite")

    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(setlevel_command.callback(ctx, str(target_id), "Dragonite", 80))

    profile = get_player_profile(target_id)
    assert profile["pokemon_stats"]["Dragonite"]["level"] == 80
    assert profile["pokemon_stats"]["Dragonite"]["exp"] == exp_required_for_level(80)


def test_setlevel_works_for_a_shiny_prefixed_species(setlevel_command, _use_temporary_database):
    from database.player import add_pokemon_to_box

    target_id = 888
    get_player_profile(target_id)
    add_pokemon_to_box(target_id, "Shiny Vaporeon")

    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(setlevel_command.callback(ctx, str(target_id), "Shiny Vaporeon", 30))

    profile = get_player_profile(target_id)
    assert profile["pokemon_stats"]["Shiny Vaporeon"]["level"] == 30
    # The plain (non-shiny) Vaporeon stats entry must not exist or be
    # touched - "Shiny Vaporeon" is its own separate stats key.
    assert "Vaporeon" not in profile["pokemon_stats"]


def test_setlevel_leaves_friendship_untouched(setlevel_command, _use_temporary_database):
    from database.player import apply_lead_rewards

    target_id = 999
    get_player_profile(target_id)
    # Build up some friendship on the default lead (Pikachu) first.
    apply_lead_rewards(target_id, exp_gained=0, friendship_gained=7)

    ctx = FakeContext(author_id=DEVELOPER_ID)
    asyncio.run(setlevel_command.callback(ctx, str(target_id), "Pikachu", 40))

    profile = get_player_profile(target_id)
    pikachu = profile["team"][0]
    assert pikachu["level"] == 40
    assert pikachu["friendship"] == 7  # unchanged by ;setlevel

    assert "pikachu" in ctx.sent_messages[0][1]["embed"].description.lower()
    assert "level 40" in ctx.sent_messages[0][1]["embed"].description.lower()
