"""
This file is the only place in the project that talks to the actual
database file on disk. Everything else (like player.py) should go
through the functions in this file instead of writing raw SQL itself.

Why SQLite?
-----------
SQLite stores the whole database as a single file (data/pokerealm.db)
and needs no separate server to install or run, which makes it a good
fit for a solo/small student project. Python has a built-in "sqlite3"
module, so there is nothing extra to install.
"""

import json
import os
import sqlite3

# Path to the database file. Using os.path.dirname/join like this means
# the path always resolves correctly no matter which folder you run the
# bot from.
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "pokerealm.db")


def get_connection() -> sqlite3.Connection:
    """
    Open (and if needed, create) the database file, and return a
    connection to it. Call .close() on the connection when you're done
    with it, or use it inside a "with" block.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)

    # Row factory lets us access columns by name (row["level"]) instead
    # of only by position (row[0]), which is much easier to read.
    connection.row_factory = sqlite3.Row

    return connection


def init_db() -> None:
    """
    Create the players table if it does not already exist yet, and
    bring an already-existing table up to date if it's missing any
    columns that a newer version of this file expects (see
    _migrate_add_missing_columns below). This is safe to call every
    time the bot starts up - it will not wipe or duplicate existing
    data.
    """
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                discord_user_id INTEGER PRIMARY KEY,
                level INTEGER NOT NULL DEFAULT 1,
                team TEXT NOT NULL,
                box TEXT NOT NULL DEFAULT '[]',
                current_location TEXT NOT NULL DEFAULT 'Pallet Town',
                coins INTEGER NOT NULL DEFAULT 0,
                has_amulet_coin INTEGER NOT NULL DEFAULT 0,
                items TEXT NOT NULL DEFAULT '{}',
                pokemon_stats TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        _migrate_add_missing_columns(connection)
        _migrate_shared_pokemon_stats(connection)
    print(f"Database ready at {DB_PATH}")


def _migrate_add_missing_columns(connection: sqlite3.Connection) -> None:
    """
    A small, manual database migration.

    CREATE TABLE IF NOT EXISTS only helps the very first time the
    database file is created - it does nothing to a table that already
    exists from an older version of this project. If someone already
    has a data/pokerealm.db file from before the "box" column existed,
    this adds that column to their existing table (defaulting every
    existing row's box to an empty list) instead of the table just
    silently not having it. Their existing players, teams, and
    progress are left completely untouched.
    """
    existing_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(players)")
    }

    if "box" not in existing_columns:
        connection.execute("ALTER TABLE players ADD COLUMN box TEXT NOT NULL DEFAULT '[]'")
        print("Migrated database: added 'box' column to the players table.")

    if "coins" not in existing_columns:
        connection.execute("ALTER TABLE players ADD COLUMN coins INTEGER NOT NULL DEFAULT 0")
        print("Migrated database: added 'coins' column to the players table.")

    if "has_amulet_coin" not in existing_columns:
        connection.execute("ALTER TABLE players ADD COLUMN has_amulet_coin INTEGER NOT NULL DEFAULT 0")
        print("Migrated database: added 'has_amulet_coin' column to the players table.")

    if "items" not in existing_columns:
        connection.execute("ALTER TABLE players ADD COLUMN items TEXT NOT NULL DEFAULT '{}'")
        print("Migrated database: added 'items' column to the players table.")

    if "pokemon_stats" not in existing_columns:
        connection.execute("ALTER TABLE players ADD COLUMN pokemon_stats TEXT NOT NULL DEFAULT '{}'")
        print("Migrated database: added 'pokemon_stats' column to the players table.")


def _migrate_shared_pokemon_stats(connection: sqlite3.Connection) -> None:
    """
    A one-time DATA migration (not just a schema one) that only needs
    to run because of a design change: every Pokémon of the same
    species a player owns now shares ONE set of stats (level, EXP,
    friendship) - see database/player.py's module docstring - instead
    of each team slot tracking its own progress independently.

    Before this change, a player's "team" column stored a list of
    individual {"name", "level", "exp", "friendship"} dicts, one per
    team slot. This converts any such row into the new shape: "team"
    becomes a plain list of species-name strings (matching how "box"
    already worked), and whatever stats each dict had are copied into
    the new "pokemon_stats" column, keyed by species name, so nobody's
    existing progress is lost in the switch.

    Safe to run on every startup: a row already in the new format (a
    team of plain strings) is detected and skipped immediately, so this
    only ever does real work once per player, the first time they're
    loaded after this migration was added.
    """
    rows = connection.execute("SELECT discord_user_id, team, pokemon_stats FROM players").fetchall()

    migrated_count = 0
    for row in rows:
        team = json.loads(row["team"])

        # Already the new format (plain species-name strings) - most
        # rows, most of the time, and always true for a player created
        # after this migration existed - nothing to do.
        if all(isinstance(entry, str) for entry in team):
            continue

        pokemon_stats = json.loads(row["pokemon_stats"])
        new_team = []

        for entry in team:
            if isinstance(entry, str):
                new_team.append(entry)
                continue

            # An old per-slot dict, e.g. {"name": "Pikachu", "level":
            # 12, "exp": 340, "friendship": 8}.
            name = entry["name"]
            new_team.append(name)

            # Only set this species' shared stats from this entry if
            # nothing has claimed them yet - if the player happened to
            # have two Pikachu at DIFFERENT levels under the old
            # per-slot system, the first one encountered wins, since
            # the whole point of this migration is that they can no
            # longer differ.
            if name not in pokemon_stats:
                pokemon_stats[name] = {
                    "level": entry.get("level", 1),
                    "exp": entry.get("exp", 0),
                    "friendship": entry.get("friendship", 0),
                }

        connection.execute(
            "UPDATE players SET team = ?, pokemon_stats = ? WHERE discord_user_id = ?",
            (json.dumps(new_team), json.dumps(pokemon_stats), row["discord_user_id"]),
        )
        migrated_count += 1

    if migrated_count:
        print(f"Migrated database: converted {migrated_count} player(s) from per-slot team stats to shared per-species stats.")
