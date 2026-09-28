"""
A quick, throwaway script for peeking inside data/pokerealm.db from the
terminal, without needing a SQLite viewer installed.

Run it with:
    python view_players.py
"""

from database.db import get_connection

with get_connection() as connection:
    rows = connection.execute("SELECT * FROM players").fetchall()

if not rows:
    print("No players in the database yet - try running /explore once first.")
else:
    print(f"{len(rows)} player row(s):\n")
    for row in rows:
        print(dict(row))
