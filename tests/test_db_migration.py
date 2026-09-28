"""
Tests for database/db.py's migration logic - specifically, that
running init_db() against an OLD-format database file safely upgrades
it without losing or corrupting any existing player data.

A database file is built to match an earlier version of the schema,
the real migration function is run against it, and the result is
checked column by column - this used to be verified by hand and is
now a real, repeatable automated test instead.

IMPORTANT: these tests never touch the real data/pokerealm.db file.
Every test below uses pytest's tmp_path fixture (a fresh, empty
temporary folder pytest creates and deletes automatically for each
test) and monkeypatch to point database.db at THAT folder instead -
see the _use_temporary_database fixture below. Without this, running
the test suite could overwrite real player data.
"""

import json
import sqlite3

import pytest

import database.db as db


@pytest.fixture
def _use_temporary_database(tmp_path, monkeypatch):
    """
    Point database/db.py's DB_PATH and DATA_DIR at a throwaway folder
    for the lifetime of one test, instead of the project's real
    data/pokerealm.db.

    Any test that takes `_use_temporary_database` as an argument gets
    this automatically undone by pytest afterwards (monkeypatch always
    reverts its changes at the end of each test), so tests can't leak
    into each other or into the real database file.
    """
    temp_db_path = tmp_path / "legacy_test.db"
    monkeypatch.setattr(db, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(temp_db_path))
    return temp_db_path


def _build_legacy_database(db_path):
    """
    Hand-build a database file in the shape an EARLY version of this
    project's schema would have produced: only the original four
    columns (no box, coins, has_amulet_coin, items, or pokemon_stats
    at all), and "team" stored as a list of old-style per-slot dicts
    (before the shared-stats-per-species migration) rather than plain
    species-name strings.

    """
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE players (
            discord_user_id INTEGER PRIMARY KEY,
            level INTEGER NOT NULL DEFAULT 1,
            team TEXT NOT NULL,
            current_location TEXT NOT NULL DEFAULT 'Pallet Town'
        )
        """
    )
    old_style_team = [
        {"name": "Pikachu", "level": 12, "exp": 340, "friendship": 8},
        {"name": "Charmander", "level": 5, "exp": 20, "friendship": 2},
    ]
    connection.execute(
        "INSERT INTO players (discord_user_id, level, team, current_location) VALUES (?, ?, ?, ?)",
        (12345, 7, json.dumps(old_style_team), "Pallet Town"),
    )
    connection.commit()
    connection.close()


def _read_player_row(db_path, discord_user_id):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT * FROM players WHERE discord_user_id = ?", (discord_user_id,)
    ).fetchone()
    connection.close()
    return row


def test_migration_preserves_existing_player_data(_use_temporary_database):
    legacy_db_path = _use_temporary_database
    _build_legacy_database(legacy_db_path)

    db.init_db()

    row = _read_player_row(legacy_db_path, 12345)
    assert row is not None, "the pre-existing player row should still exist after migrating"
    assert row["level"] == 7
    assert row["current_location"] == "Pallet Town"


def test_migration_adds_missing_columns_with_safe_defaults(_use_temporary_database):
    legacy_db_path = _use_temporary_database
    _build_legacy_database(legacy_db_path)

    db.init_db()

    row = _read_player_row(legacy_db_path, 12345)
    assert json.loads(row["box"]) == []
    assert row["coins"] == 0
    assert row["has_amulet_coin"] == 0
    assert json.loads(row["items"]) == {}


def test_migration_converts_old_team_format_to_shared_species_stats(_use_temporary_database):
    legacy_db_path = _use_temporary_database
    _build_legacy_database(legacy_db_path)

    db.init_db()

    row = _read_player_row(legacy_db_path, 12345)

    # "team" should now be a plain list of species-name strings...
    assert json.loads(row["team"]) == ["Pikachu", "Charmander"]

    # ...and each one's old level/exp/friendship should have been
    # copied into the new shared pokemon_stats column, keyed by name.
    pokemon_stats = json.loads(row["pokemon_stats"])
    assert pokemon_stats["Pikachu"] == {"level": 12, "exp": 340, "friendship": 8}
    assert pokemon_stats["Charmander"] == {"level": 5, "exp": 20, "friendship": 2}


def test_running_init_db_a_second_time_is_a_safe_no_op(_use_temporary_database):
    # init_db() has to be safe to call every time the bot starts up
    # (see its own docstring) - this checks that migrating an
    # ALREADY-migrated database a second time doesn't change anything
    # or crash, since a normal player will have init_db() run against
    # their save file every single time they start the bot.
    legacy_db_path = _use_temporary_database
    _build_legacy_database(legacy_db_path)

    db.init_db()
    row_after_first_migration = dict(_read_player_row(legacy_db_path, 12345))

    db.init_db()
    row_after_second_migration = dict(_read_player_row(legacy_db_path, 12345))

    assert row_after_first_migration == row_after_second_migration
