"""
Tests for pokemon/evolution.py's eligibility rules, and
database/player.py's evolve_species().

See pokemon/evolution.py's own module docstring for the design
decision being tested here: every evolution that isn't friendship-based
becomes a LEVEL requirement instead - either the real Generation 1
level (if it already levelled up), or a flat level 40 (if it normally
needed a stone or a trade).
"""

import pytest

import database.db as db
from database.player import evolve_species, get_player_profile
from pokemon.data import WILD_POKEMON
from pokemon.evolution import (
    CONVERTED_EVOLUTION_LEVEL,
    EVOLUTION_DATA,
    evolution_requirement_text,
    get_evolution_info,
    is_eligible_for,
)

KNOWN_SPECIES_NAMES = {pokemon["name"] for pokemon in WILD_POKEMON}


# --- Data integrity (EVOLUTION_DATA is a big, hand-written table -----------
# these two tests exist to catch a typo'd species name immediately,
# rather than it only being noticed the next time someone happens to
# try to evolve into it).

def test_every_evolution_target_is_a_real_species():
    for species, info in EVOLUTION_DATA.items():
        for target in info["evolves_to"]:
            assert target in KNOWN_SPECIES_NAMES, f"{species} evolves into unknown species {target!r}"


def test_every_species_key_is_a_real_species():
    for species in EVOLUTION_DATA:
        assert species in KNOWN_SPECIES_NAMES, f"{species!r} is not a real species name"


def test_every_converted_stone_or_trade_evolution_uses_the_flat_level():
    # The whole point of the design decision (see pokemon/evolution.py's
    # docstring) is that stone/trade evolutions all become the SAME
    # flat level - if one of them drifted to a different number, that
    # would defeat the point of having one shared, easy-to-explain rule.
    for species, info in EVOLUTION_DATA.items():
        if info["originally"] != "level":
            assert info["method"] == "level"
            assert info["level"] == CONVERTED_EVOLUTION_LEVEL, species


# --- get_evolution_info() ---------------------------------------------------

def test_get_evolution_info_returns_none_for_a_species_with_no_further_evolution():
    # Venusaur is fully evolved - no entry in EVOLUTION_DATA at all.
    assert get_evolution_info("Venusaur") is None


def test_get_evolution_info_returns_none_for_an_unrecognised_name():
    # e.g. a promo Pokémon stored as "Shiny Charmander" (see
    # commands/promo.py) - shouldn't crash, just report no evolution.
    assert get_evolution_info("Shiny Charmander") is None


def test_get_evolution_info_finds_a_real_evolving_species():
    info = get_evolution_info("Charmander")
    assert info["evolves_to"] == ["Charmeleon"]
    assert info["level"] == 16


# --- is_eligible_for() ------------------------------------------------------

def test_is_eligible_for_level_method_below_the_required_level():
    info = get_evolution_info("Charmander")  # requires level 16
    assert is_eligible_for(info, {"level": 15, "exp": 0, "friendship": 0}) is False


def test_is_eligible_for_level_method_at_the_required_level():
    info = get_evolution_info("Charmander")
    assert is_eligible_for(info, {"level": 16, "exp": 0, "friendship": 0}) is True


def test_is_eligible_for_level_method_above_the_required_level():
    info = get_evolution_info("Charmander")
    assert is_eligible_for(info, {"level": 50, "exp": 0, "friendship": 0}) is True


def test_stone_converted_evolution_requires_the_flat_level_not_the_original_level():
    # Nidorina would normally need a Moon Stone, not a level - it should
    # now require CONVERTED_EVOLUTION_LEVEL (40), not anything lower.
    info = get_evolution_info("Nidorina")
    assert info["level"] == CONVERTED_EVOLUTION_LEVEL
    assert is_eligible_for(info, {"level": CONVERTED_EVOLUTION_LEVEL - 1, "exp": 0, "friendship": 0}) is False
    assert is_eligible_for(info, {"level": CONVERTED_EVOLUTION_LEVEL, "exp": 0, "friendship": 0}) is True


def test_is_eligible_for_friendship_method():
    # No species in this project's roster actually uses "friendship"
    # (see pokemon/evolution.py's module docstring for why - it wasn't
    # a Generation 1 mechanic), but the method itself still needs to
    # work correctly for the system to be genuinely extensible, so it's
    # tested directly here with a hand-built entry rather than a real
    # species.
    info = {"evolves_to": ["Something"], "method": "friendship"}
    assert is_eligible_for(info, {"level": 100, "exp": 0, "friendship": 99}) is False
    assert is_eligible_for(info, {"level": 100, "exp": 0, "friendship": 100}) is True


def test_eevees_three_way_branch_has_three_targets():
    info = get_evolution_info("Eevee")
    assert set(info["evolves_to"]) == {"Vaporeon", "Jolteon", "Flareon"}
    assert info["level"] == CONVERTED_EVOLUTION_LEVEL


# --- evolution_requirement_text() ------------------------------------------

def test_evolution_requirement_text_for_level_method():
    info = get_evolution_info("Charmander")
    assert evolution_requirement_text(info) == "reach level 16"


def test_evolution_requirement_text_for_friendship_method():
    info = {"evolves_to": ["Something"], "method": "friendship"}
    assert "friendship" in evolution_requirement_text(info)


# --- database/player.py's evolve_species() ----------------------------------

@pytest.fixture
def _use_temporary_database(tmp_path, monkeypatch):
    """Same disposable-database technique as the other test files - never touches data/pokerealm.db."""
    monkeypatch.setattr(db, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test_only.db"))
    db.init_db()


def test_evolve_species_renames_every_matching_team_and_box_slot(_use_temporary_database):
    discord_user_id = 111

    # Seed a player who owns three Charmander in total: two in the team
    # (the default starting team plus a second one appended) and one in
    # the box - evolving should affect all three, since they all share
    # ONE pokemon_stats entry (see the project's shared-stats design).
    get_player_profile(discord_user_id)  # creates the row, default team = ["Pikachu"]

    with db.get_connection() as connection:
        connection.execute(
            "UPDATE players SET team = ?, box = ?, pokemon_stats = ? WHERE discord_user_id = ?",
            (
                '["Charmander", "Charmander"]',
                '["Charmander"]',
                '{"Charmander": {"level": 20, "exp": 100, "friendship": 5}}',
                discord_user_id,
            ),
        )

    result = evolve_species(discord_user_id, "Charmander", "Charmeleon")
    assert result["evolved_count"] == 3

    profile = get_player_profile(discord_user_id)
    assert [pokemon["name"] for pokemon in profile["team"]] == ["Charmeleon", "Charmeleon"]
    assert profile["box"] == ["Charmeleon"]
    assert "Charmander" not in profile["pokemon_stats"]

    # Level, EXP, and friendship carry over UNCHANGED - evolving isn't a
    # reward in itself, it's the same Pokémon in a new form.
    assert profile["pokemon_stats"]["Charmeleon"] == {"level": 20, "exp": 100, "friendship": 5}


def test_evolve_species_keeps_the_higher_level_if_the_target_species_is_already_owned(_use_temporary_database):
    discord_user_id = 222
    get_player_profile(discord_user_id)

    with db.get_connection() as connection:
        connection.execute(
            "UPDATE players SET team = ?, pokemon_stats = ? WHERE discord_user_id = ?",
            (
                '["Charmander"]',
                (
                    '{"Charmander": {"level": 16, "exp": 0, "friendship": 0}, '
                    '"Charmeleon": {"level": 40, "exp": 500, "friendship": 20}}'
                ),
                discord_user_id,
            ),
        )

    evolve_species(discord_user_id, "Charmander", "Charmeleon")

    profile = get_player_profile(discord_user_id)
    # The player's existing, more-progressed Charmeleon should NOT be
    # overwritten by the freshly-evolved, lower-level one.
    assert profile["pokemon_stats"]["Charmeleon"] == {"level": 40, "exp": 500, "friendship": 20}
