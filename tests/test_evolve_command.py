"""
Tests for commands/evolve.py - specifically the shiny-species evolution
matching fix.

Previously, `;evolve` looked a lead Pokémon up in EVOLUTION_DATA by its
RAW stored name (e.g. "Shiny Charmander"), but EVOLUTION_DATA is keyed
by real species names only ("Charmander"). That lookup always missed
for a shiny lead, so every shiny Pokémon appeared permanently
fully-evolved (the "doesn't have any further evolution" message),
whether it actually was or not. Fixed by splitting the shiny prefix
off (pokemon/data.py's split_stored_name()) before any EVOLUTION_DATA
lookup, and re-applying it to whichever target species is
shown/stored/evolved into, since a shiny Pokémon evolves into a shiny
of its next stage, never a normal one.

These tests register the real command on a throwaway, disconnected
discord.py Bot (same technique as tests/test_dev.py) so the actual
registered callback is exercised, not a reimplementation of its logic.
"""

import asyncio

import discord
import pytest
from discord.ext import commands

import database.db as db
import commands.evolve as evolve_module
from database.db import get_connection
from database.player import get_player_profile
from pokemon.growth import exp_required_for_level


class FakeContext:
    """Minimal ctx.send()-recording stand-in - same idea as test_dev.py's FakeContext."""

    def __init__(self, author_id: int):
        self.author = type("Author", (), {"id": author_id})()
        self.sent_messages = []

    async def send(self, *args, **kwargs):
        self.sent_messages.append((args, kwargs))
        return None


class FakeInteractionResponse:
    """Records the single edit_message() call EvolveView._resolve() makes."""

    def __init__(self):
        self.edited = None

    async def edit_message(self, **kwargs):
        self.edited = kwargs


class FakeInteraction:
    """Just enough of a discord.Interaction for EvolveView._resolve()."""

    def __init__(self, user_id: int):
        self.user = type("User", (), {"id": user_id})()
        self.response = FakeInteractionResponse()


@pytest.fixture
def _use_temporary_database(tmp_path, monkeypatch):
    """Same disposable-database technique as the other test files - never touches data/pokerealm.db."""
    monkeypatch.setattr(db, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test_only.db"))
    db.init_db()


@pytest.fixture
def evolve_command():
    """Register commands/evolve.py's command on a throwaway Bot and hand back the real /evolve command object."""
    bot = commands.Bot(command_prefix=";", intents=discord.Intents.default())
    evolve_module.setup(bot)
    return bot.get_command("evolve")


def _set_lead(discord_user_id: int, stored_name: str, level: int) -> None:
    """
    Test-only helper: force a player's TEAM lead to be exactly
    `stored_name` (e.g. "Shiny Charmander") at `level`, bypassing the
    normal catch/spawn/move flow, which has no way to put a shiny
    Pokémon directly into the team slot 1 needed to exercise ;evolve's
    lead-reading logic.

    get_player_profile() is called first so the player's row exists,
    matching the pattern every other command's tests use.
    """
    get_player_profile(discord_user_id)
    import json

    with get_connection() as connection:
        connection.execute(
            "UPDATE players SET team = ?, pokemon_stats = ? WHERE discord_user_id = ?",
            (
                json.dumps([stored_name]),
                json.dumps({stored_name: {"level": level, "exp": exp_required_for_level(level), "friendship": 0}}),
                discord_user_id,
            ),
        )


# --- the core reported bug: a shiny lead ready to evolve ---------------

def test_shiny_lead_ready_to_evolve_is_offered_evolution_not_falsely_reported_as_final_form(
    _use_temporary_database, evolve_command
):
    discord_user_id = 111111
    # Charmander -> Charmeleon requires level 16 (pokemon/evolution.py).
    _set_lead(discord_user_id, "Shiny Charmander", level=16)
    ctx = FakeContext(discord_user_id)

    asyncio.run(evolve_command.callback(ctx))

    assert len(ctx.sent_messages) == 1
    embed = ctx.sent_messages[0][1]["embed"]
    # Before the fix, this would incorrectly be "Shiny Charmander
    # doesn't have any further evolution."
    assert "doesn't have any further evolution" not in (embed.description or "")
    assert "ready to evolve" in embed.title.lower()
    assert "Shiny Charmeleon" in embed.description


def test_shiny_lead_not_ready_yet_still_correctly_reports_the_real_requirement(
    _use_temporary_database, evolve_command
):
    discord_user_id = 222222
    _set_lead(discord_user_id, "Shiny Charmander", level=1)
    ctx = FakeContext(discord_user_id)

    asyncio.run(evolve_command.callback(ctx))

    embed = ctx.sent_messages[0][1]["embed"]
    assert "doesn't have any further evolution" not in (embed.description or "")
    assert "isn't ready to evolve yet" in embed.description
    assert "level 16" in embed.description


def test_shiny_eevee_offers_all_three_targets_shiny_prefixed(
    _use_temporary_database, evolve_command
):
    discord_user_id = 333333
    _set_lead(discord_user_id, "Shiny Eevee", level=40)
    ctx = FakeContext(discord_user_id)

    asyncio.run(evolve_command.callback(ctx))

    embed = ctx.sent_messages[0][1]["embed"]
    for target in ("Shiny Vaporeon", "Shiny Jolteon", "Shiny Flareon"):
        assert target in embed.description
    # And never the non-shiny forms, which would mean the shiny prefix
    # was dropped rather than carried through to the targets.
    assert "Choose one: Vaporeon" not in embed.description


def test_a_non_shiny_lead_is_unaffected_by_the_fix(_use_temporary_database, evolve_command):
    discord_user_id = 444444
    _set_lead(discord_user_id, "Charmander", level=16)
    ctx = FakeContext(discord_user_id)

    asyncio.run(evolve_command.callback(ctx))

    embed = ctx.sent_messages[0][1]["embed"]
    assert "Charmeleon" in embed.description
    assert "Shiny" not in embed.description


# --- actually evolving a shiny lead produces a shiny evolved form ------

def test_evolving_a_shiny_lead_results_in_the_shiny_evolved_form(
    _use_temporary_database,
):
    discord_user_id = 555555
    _set_lead(discord_user_id, "Shiny Charmander", level=16)

    view = evolve_module.EvolveView(
        player_id=discord_user_id,
        from_species="Shiny Charmander",
        targets=["Shiny Charmeleon"],
    )
    interaction = FakeInteraction(discord_user_id)

    asyncio.run(view._resolve(interaction, "Shiny Charmeleon"))

    assert interaction.response.edited is not None
    embed = interaction.response.edited["embed"]
    assert "Shiny Charmeleon" in embed.title

    profile = get_player_profile(discord_user_id)
    assert profile["team"][0]["name"] == "Shiny Charmeleon"
    # It must NOT have silently lost its shininess by evolving into the
    # plain form instead.
    assert "Charmander" not in profile["pokemon_stats"]
