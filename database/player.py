"""
Player-related database queries.

Anything that needs player data (like commands/explore.py) should call
the functions in this file, and should not need to know that the data
is actually stored in SQLite underneath. That way, if we ever swap the
database technology later, only this file has to change.

Design decision: stats are shared PER SPECIES, not per individual
Pokémon
--------------------------------------------------------------------
Every Pokémon of the same species a player owns - whether it's in
their team or sitting in their box - shares ONE set of stats (level,
EXP, friendship). If a player has a level 45 Charmander, every
Charmander they own is level 45; there's no such thing as "two
Charmander at different levels" in this project. This is simpler than
the real games (where each individual Pokémon levels up separately),
which is a deliberate scope decision - see the project's design notes.

Concretely, this means:
  - The "team" column is just a list of species-name strings, in
    order (team[0] is the LEAD - see apply_lead_rewards() below) -
    the same shape "box" already used.
  - The new "pokemon_stats" column is a dict keyed by species name,
    e.g. {"Charmander": {"level": 45, "exp": 9800, "friendship": 12}},
    holding the ONE shared stats entry for that species. A species
    only appears here once a player has owned at least one of it.
  - Nothing else in the codebase (commands/explore.py, commands/
    collection.py, commands/move.py, ai/quest_generator.py, ...) needs
    to know about this split: get_player_profile() still hands back
    "team" as a list of {"name", "level", "exp", "friendship"} dicts,
    built fresh each time by joining the name list against
    pokemon_stats (see _team_with_stats() below) - it's just no longer
    where that data is actually STORED.
"""

import json

from database.db import get_connection
from pokemon.growth import apply_exp, apply_friendship, exp_required_for_level

# Defaults used the very first time a player is seen.
DEFAULT_LEVEL = 1
DEFAULT_LOCATION = "Pallet Town"
DEFAULT_COINS = 0
DEFAULT_TEAM = ["Pikachu"]

# The party (active team) can only hold this many Pokémon at once,
# same as the real games - anything caught beyond this goes into the
# player's box instead.
MAX_TEAM_SIZE = 6


def _default_stats() -> dict:
    """
    The stats a species starts at the moment a player owns their first
    one of it: level 1, no EXP, no friendship yet (see
    pokemon/growth.py for how those change over time). A plain
    function rather than a shared constant dict, so every caller gets
    its own fresh copy instead of accidentally sharing (and mutating)
    the same one.
    """
    return {"level": 1, "exp": 0, "friendship": 0}


def _default_pokemon_stats() -> dict:
    """The starting pokemon_stats dict for a brand new player, matching DEFAULT_TEAM."""
    return {name: _default_stats() for name in DEFAULT_TEAM}


def _stats_for(pokemon_stats: dict, name: str) -> dict:
    """
    Look up one species' shared stats. Falls back to a fresh level-1
    entry if pokemon_stats doesn't have this species yet - shouldn't
    normally happen, since add_caught_pokemon() always creates the
    entry the moment a species is first owned, but staying defensive
    here means a missing entry just shows as "Level 1" instead of
    crashing a command.
    """
    return dict(pokemon_stats.get(name, _default_stats()))


def _team_with_stats(team_names: list, pokemon_stats: dict) -> list:
    """
    Build the "team" shape the rest of the codebase expects: one dict
    per team slot, with that species' CURRENT shared stats joined in.

    This is deliberately regenerated fresh from (team_names,
    pokemon_stats) every time, rather than being what's actually
    stored - pokemon_stats is the only place a species' progress lives
    (see the module docstring above), so there's nowhere for the two
    copies to drift apart.
    """
    return [{"name": name, **_stats_for(pokemon_stats, name)} for name in team_names]


def _row_to_profile(row) -> dict:
    """
    Convert one row from the database into the same dictionary shape
    the rest of the codebase already expects (see the old, hard-coded
    version of get_player_profile that this replaces).
    """
    pokemon_stats = json.loads(row["pokemon_stats"])

    return {
        "level": row["level"],
        "team": _team_with_stats(json.loads(row["team"]), pokemon_stats),
        # Box entries stay plain species-name strings, same as team
        # names do now - see the module docstring above for why a
        # species' actual stats live in pokemon_stats instead, shared
        # by every Pokémon of that species regardless of whether it's
        # in the team or the box.
        "box": json.loads(row["box"]),
        "pokemon_stats": pokemon_stats,
        "current_location": row["current_location"],
        "coins": row["coins"],
        # SQLite has no real boolean type - it's stored as 0/1 in an
        # INTEGER column, so it's converted back to True/False here.
        "has_amulet_coin": bool(row["has_amulet_coin"]),
        # Stackable items, e.g. {"master_ball": 3} - a plain dict
        # rather than a column-per-item, so new items (see
        # pokemon/economy.py) never need a database migration.
        "items": json.loads(row["items"]),
    }


def get_player_profile(discord_user_id: int) -> dict:
    """
    Look up a player's profile by their Discord user ID.

    If this is the first time we have seen this player, a new row is
    created for them with the default level/team/box/location, so that
    every player always gets a valid profile back - the caller never
    has to check for "no profile yet" as a special case.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT level, team, box, current_location, coins, has_amulet_coin, items, pokemon_stats "
            "FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()

        if row is not None:
            return _row_to_profile(row)

        # No row for this player yet - create one with the defaults.
        connection.execute(
            "INSERT INTO players (discord_user_id, level, team, box, current_location, coins, has_amulet_coin, items, pokemon_stats) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (discord_user_id, DEFAULT_LEVEL, json.dumps(DEFAULT_TEAM), json.dumps([]), DEFAULT_LOCATION,
             DEFAULT_COINS, 0, json.dumps({}), json.dumps(_default_pokemon_stats())),
        )

    default_stats = _default_pokemon_stats()
    return {
        "level": DEFAULT_LEVEL,
        "team": _team_with_stats(DEFAULT_TEAM, default_stats),
        "box": [],
        "pokemon_stats": default_stats,
        "current_location": DEFAULT_LOCATION,
        "coins": DEFAULT_COINS,
        "has_amulet_coin": False,
        "items": {},
    }


def update_player_location(discord_user_id: int, location: str) -> None:
    """
    Update the location stored for a player, for example after they
    successfully run /explore somewhere new.

    This assumes the player already exists in the database - calling
    get_player_profile() first (which explore.py already does)
    guarantees that.
    """
    with get_connection() as connection:
        connection.execute(
            "UPDATE players SET current_location = ? WHERE discord_user_id = ?",
            (location, discord_user_id),
        )


def add_caught_pokemon(discord_user_id: int, pokemon_name: str) -> dict:
    """
    Record a newly-caught Pokémon against a player.

    If their team (party) has room - fewer than MAX_TEAM_SIZE Pokémon
    - the new Pokémon joins the team. Otherwise, it's sent to their box
    instead, the same way a full party sends new catches to PC storage
    in the real games, so a full team never stops the player from
    catching more Pokémon. Team and box entries are both just the
    species name - see the module docstring above for why the actual
    stats live elsewhere (pokemon_stats), shared by species.

    If this is the player's first time ever owning this species, it
    starts a fresh level-1 pokemon_stats entry. If they already own
    one (in their team OR their box), this catch just joins the
    EXISTING shared stats untouched - that's the whole point of the
    shared-stats design: a second Charmander doesn't reset or duplicate
    progress, it just becomes another copy of the same level 45
    Charmander.

    Returns a dict describing what happened, so the caller can show an
    appropriate message without needing a second database read:
        {"went_to": "team" or "box", "team": [...], "box": [...]}

    Like update_player_location(), this assumes the player already
    exists - calling get_player_profile() first guarantees that.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT team, box, pokemon_stats FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()

        team = json.loads(row["team"]) if row is not None else list(DEFAULT_TEAM)
        box = json.loads(row["box"]) if row is not None else []
        pokemon_stats = json.loads(row["pokemon_stats"]) if row is not None else _default_pokemon_stats()

        if pokemon_name not in pokemon_stats:
            pokemon_stats[pokemon_name] = _default_stats()

        if len(team) < MAX_TEAM_SIZE:
            team.append(pokemon_name)
            went_to = "team"
        else:
            box.append(pokemon_name)
            went_to = "box"

        connection.execute(
            "UPDATE players SET team = ?, box = ?, pokemon_stats = ? WHERE discord_user_id = ?",
            (json.dumps(team), json.dumps(box), json.dumps(pokemon_stats), discord_user_id),
        )

    return {
        "went_to": went_to,
        "team": _team_with_stats(team, pokemon_stats),
        "box": box,
    }


def add_pokemon_to_box(discord_user_id: int, pokemon_name: str) -> dict:
    """
    Add a Pokémon straight into a player's BOX, skipping the
    team-if-there's-room logic add_caught_pokemon() uses for a normal
    catch. Used by the owner-only ;spawn command (commands/dev.py) -
    unlike a real catch, a spawned Pokémon should never displace a slot
    in the player's active team; it should always land in storage,
    exactly like a full team already sends normal catches to the box.

    Same shared-stats behaviour as add_caught_pokemon(): a fresh level-1
    pokemon_stats entry is created only if the player has never owned
    this species before; otherwise it joins the EXISTING shared stats
    untouched.

    Returns {"box": [...]} - the player's new box (species-name list).

    Like add_caught_pokemon(), this assumes the player already exists -
    commands/dev.py calls get_player_profile() first to guarantee that.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT box, pokemon_stats FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()

        box = json.loads(row["box"]) if row is not None else []
        pokemon_stats = json.loads(row["pokemon_stats"]) if row is not None else _default_pokemon_stats()

        if pokemon_name not in pokemon_stats:
            pokemon_stats[pokemon_name] = _default_stats()

        box.append(pokemon_name)

        connection.execute(
            "UPDATE players SET box = ?, pokemon_stats = ? WHERE discord_user_id = ?",
            (json.dumps(box), json.dumps(pokemon_stats), discord_user_id),
        )

    return {"box": box}


def evolve_species(discord_user_id: int, from_species: str, to_species: str) -> dict:
    """
    Evolve every Pokémon a player owns of `from_species` into
    `to_species` at once (see commands/evolve.py, and
    pokemon/evolution.py for deciding WHETHER a species is eligible -
    this function only performs the change, it doesn't check
    eligibility itself).

    Because stats are shared PER SPECIES, not per individual Pokémon
    (see this module's docstring), there's no such thing as "evolve
    just the one in the team and leave the others as Charmander" - a
    player who owns three Charmander (whether in their team, their box,
    or split across both) only ever has ONE shared Charmander stats
    entry, so evolving it necessarily evolves all three at once, the
    same way apply_lead_rewards() levelling up the lead already levels
    up every other Pokémon of that species too. This matches how the
    project's own shared-stats design decision already behaves - it
    isn't a new limitation introduced by evolution.

    The pokemon_stats entry itself (level/exp/friendship) is renamed
    from `from_species` to `to_species` UNCHANGED - evolving doesn't
    reset or boost progress, exactly like the real games.

    Returns {"evolved_count": <int>}, where evolved_count is how many
    team+box slots were renamed (i.e. how many of that species the
    player owned) - used by commands/evolve.py purely to phrase the
    confirmation message correctly ("your Charmander" vs "your 3
    Charmander").
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT team, box, pokemon_stats FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()

        team = json.loads(row["team"]) if row is not None else []
        box = json.loads(row["box"]) if row is not None else []
        pokemon_stats = json.loads(row["pokemon_stats"]) if row is not None else {}

        evolved_count = sum(1 for name in team if name == from_species)
        evolved_count += sum(1 for name in box if name == from_species)

        team = [to_species if name == from_species else name for name in team]
        box = [to_species if name == from_species else name for name in box]

        if from_species in pokemon_stats:
            stats = pokemon_stats.pop(from_species)
            # Merge rather than overwrite, in the unlikely case the
            # player already separately owns some `to_species` (e.g.
            # they evolve a second Charmander after already catching a
            # wild Charmeleon) - the higher level wins, since "evolving
            # made your Pokémon weaker" would make no sense to a player.
            if to_species in pokemon_stats and pokemon_stats[to_species]["level"] >= stats["level"]:
                pass  # existing to_species entry is already equal or ahead - keep it
            else:
                pokemon_stats[to_species] = stats

        connection.execute(
            "UPDATE players SET team = ?, box = ?, pokemon_stats = ? WHERE discord_user_id = ?",
            (json.dumps(team), json.dumps(box), json.dumps(pokemon_stats), discord_user_id),
        )

    return {"evolved_count": evolved_count}


def set_pokemon_level(discord_user_id: int, pokemon_name: str, level: int) -> dict | None:
    """
    Directly set a species' shared level (see this module's docstring
    on why level/EXP/friendship are shared PER SPECIES, not per
    individual Pokémon) to an exact value, used by the owner-only
    ;setlevel command (commands/dev.py) so higher-level behaviour can
    be tested without grinding there for real.

    EXP is set to exactly what that level requires (see
    pokemon/growth.py's exp_required_for_level()) - not just the
    level number on its own - so the Pokémon isn't left in an
    inconsistent state (e.g. "Level 50" but with only enough EXP for
    Level 3) that would let it level up again from a tiny reward.
    Friendship is left completely untouched.

    Only allowed for a species the player actually owns - `pokemon_name`
    (the exact stored name, e.g. "Charmander" or "Shiny Vaporeon") must
    appear somewhere in their team OR box. Returns None if the player
    has no row yet, or doesn't own that exact Pokémon, so
    commands/dev.py can tell "no such Pokémon" apart from success.

    Returns the species' new stats dict ({"level", "exp", "friendship"})
    on success.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT team, box, pokemon_stats FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()

        if row is None:
            return None

        team = json.loads(row["team"])
        box = json.loads(row["box"])
        pokemon_stats = json.loads(row["pokemon_stats"])

        if pokemon_name not in team and pokemon_name not in box:
            return None

        stats = _stats_for(pokemon_stats, pokemon_name)
        stats["level"] = level
        stats["exp"] = exp_required_for_level(level)
        pokemon_stats[pokemon_name] = stats

        connection.execute(
            "UPDATE players SET pokemon_stats = ? WHERE discord_user_id = ?",
            (json.dumps(pokemon_stats), discord_user_id),
        )

    return stats


def move_team_pokemon(discord_user_id: int, pokemon_name: str, new_position: int):
    """
    Swap the named team Pokémon into `new_position` (1-indexed - so
    position 1 makes it the new LEAD) with whichever Pokémon currently
    sits there. This is how a player chooses which Pokémon gets quest
    vibes/EXP/friendship (see ai/quest_generator.py and
    apply_lead_rewards() below), rather than it being permanently
    fixed to whichever order they happened to catch things in - see
    commands/move.py.

    This is a straight SWAP of exactly the two Pokémon involved, not a
    shift - moving Squirtle from position 3 to position 1 just trades
    places with whoever is currently in position 1; everyone else's
    position is untouched. (An earlier version of this function popped
    the Pokémon out and re-inserted it, which shifted every Pokémon in
    between along by one - more movement than the player actually
    asked for.)

    Matching on `pokemon_name` is case-insensitive, since players
    won't always type a species name with the exact capitalisation
    stored in the database.

    `new_position` is clamped into a valid position automatically
    (rather than failing) if it's out of range - commands/move.py
    already validates it against the player's actual team size before
    calling this, so out-of-range here would only happen from a caller
    that skipped that check.

    Returns the player's new team order (a list of Pokémon dicts), or
    None if no team member's name matched `pokemon_name`.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT team, pokemon_stats FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()

        team = json.loads(row["team"]) if row is not None else []
        pokemon_stats = json.loads(row["pokemon_stats"]) if row is not None else {}

        match_index = next(
            (i for i, name in enumerate(team) if name.lower() == pokemon_name.lower()),
            None,
        )
        if match_index is None:
            return None

        target_index = max(0, min(len(team) - 1, new_position - 1))
        team[match_index], team[target_index] = team[target_index], team[match_index]

        connection.execute(
            "UPDATE players SET team = ? WHERE discord_user_id = ?",
            (json.dumps(team), discord_user_id),
        )

    return _team_with_stats(team, pokemon_stats)


def apply_lead_rewards(discord_user_id: int, exp_gained: int, friendship_gained: int = 0):
    """
    Apply EXP and (optionally) friendship gains to a player's LEAD
    (first) team Pokémon, all in one update. Used whenever something
    rewards progress to "whichever Pokémon the player is currently
    playing as": a completed quest chain (commands/explore.py, with
    both exp_gained and friendship_gained) and a successful /catch
    (commands/catch.py, exp_gained only - friendship_gained left at
    its default of 0, since catching a Pokémon doesn't make your OTHER
    Pokémon fonder of you).

    The lead is the same Pokémon ai/image_classifier.py reads the
    sprite of for quest flavour, and the same one commands/explore.py
    builds a quest chain's narrative around, so it's the natural,
    deterministic choice for who a reward applies to - rather than,
    say, trying to parse AI-generated quest TEXT to guess which
    Pokémon it happened to focus on, which would be fragile and would
    break the project's "AI generates content, engine controls
    mechanics" separation. A player who wants a DIFFERENT Pokémon to
    receive rewards instead can move it into the lead position with
    ;move or /move (see commands/move.py).

    Returns the updated lead Pokémon's dict, with an extra
    "leveled_up" bool added, or None if the player's team is
    currently empty (nothing to reward).

    Because stats are shared per species (see the module docstring
    above), this updates pokemon_stats for the LEAD's SPECIES - not
    just "the Pokémon in team slot 1". If the player owns three
    Charmander and their lead is one of them, all three become the new
    level at once, whether the other two are elsewhere in the team or
    sitting in the box - there's only one Charmander entry in
    pokemon_stats for all of them to share.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT team, pokemon_stats FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()

        team = json.loads(row["team"]) if row is not None else []
        pokemon_stats = json.loads(row["pokemon_stats"]) if row is not None else {}

        if not team:
            return None

        lead_name = team[0]
        lead_stats = _stats_for(pokemon_stats, lead_name)

        before_level = lead_stats["level"]
        lead_stats = apply_exp(lead_stats, exp_gained)
        lead_stats = apply_friendship(lead_stats, friendship_gained)
        pokemon_stats[lead_name] = lead_stats

        connection.execute(
            "UPDATE players SET pokemon_stats = ? WHERE discord_user_id = ?",
            (json.dumps(pokemon_stats), discord_user_id),
        )

    result = dict(lead_stats)
    result["name"] = lead_name
    result["leveled_up"] = result["level"] > before_level
    return result


def add_coins(discord_user_id: int, amount: int) -> int:
    """
    Add coins to a player's balance and return their new total.

    A negative amount subtracts instead - used by spend_coins() below
    rather than duplicating this same read/update logic.

    Like update_player_location(), this assumes the player already
    exists - call get_player_profile() first if that isn't guaranteed
    (see commands/dev.py's ;givecoins, which may target a player who
    has never used the bot before).
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT coins FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()

        current_coins = row["coins"] if row is not None else DEFAULT_COINS
        new_balance = current_coins + amount

        connection.execute(
            "UPDATE players SET coins = ? WHERE discord_user_id = ?",
            (new_balance, discord_user_id),
        )

    return new_balance


def spend_coins(discord_user_id: int, amount: int) -> bool:
    """
    Try to deduct `amount` coins from a player's balance.

    Returns True and deducts the coins if they can afford it. Returns
    False and leaves their balance untouched if they can't - checking
    and deducting happen inside the same database connection so a
    player can't spend coins they don't have.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT coins FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()

        current_coins = row["coins"] if row is not None else DEFAULT_COINS

        if current_coins < amount:
            return False

        connection.execute(
            "UPDATE players SET coins = ? WHERE discord_user_id = ?",
            (current_coins - amount, discord_user_id),
        )

    return True


def set_amulet_coin(discord_user_id: int, owned: bool = True) -> None:
    """Mark whether a player owns the Amulet Coin upgrade (see pokemon/economy.py)."""
    with get_connection() as connection:
        connection.execute(
            "UPDATE players SET has_amulet_coin = ? WHERE discord_user_id = ?",
            (1 if owned else 0, discord_user_id),
        )


def get_item_count(discord_user_id: int, item_key: str) -> int:
    """
    How many of a given item (e.g. "master_ball") a player currently
    owns. Returns 0 for an item they've never owned, rather than
    raising an error - callers never need to special-case "never
    bought one yet".
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT items FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()
        items = json.loads(row["items"]) if row is not None else {}

    return items.get(item_key, 0)


def add_item(discord_user_id: int, item_key: str, quantity: int = 1) -> int:
    """
    Add `quantity` of an item to a player's inventory (e.g. after a
    /shop purchase) and return their new count of that item.

    Like add_coins(), this assumes the player's row already exists.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT items FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()

        items = json.loads(row["items"]) if row is not None else {}
        items[item_key] = items.get(item_key, 0) + quantity

        connection.execute(
            "UPDATE players SET items = ? WHERE discord_user_id = ?",
            (json.dumps(items), discord_user_id),
        )

    return items[item_key]


def use_item(discord_user_id: int, item_key: str, quantity: int = 1) -> bool:
    """
    Try to consume `quantity` of an item (e.g. throwing a Master Ball).

    Returns True and deducts it if the player has enough. Returns
    False and leaves their inventory untouched if they don't - the
    check and the deduction happen inside the same database connection
    (same pattern as spend_coins()), so it's not possible for a player
    to use an item they don't actually have.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT items FROM players WHERE discord_user_id = ?",
            (discord_user_id,),
        ).fetchone()

        items = json.loads(row["items"]) if row is not None else {}
        current_count = items.get(item_key, 0)

        if current_count < quantity:
            return False

        items[item_key] = current_count - quantity

        connection.execute(
            "UPDATE players SET items = ? WHERE discord_user_id = ?",
            (json.dumps(items), discord_user_id),
        )

    return True
