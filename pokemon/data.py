"""
Static data about every Pokémon PokeRealm knows about: all 151
original (Generation 1) Pokémon, catchable through /catch and /explore
alike, plus two quest-exclusive Generation 2 legendaries (Ho-Oh and
Lugia - see the "quest_exclusive" flag near the end of WILD_POKEMON,
and pokemon/legendary_quest.py) that can only be obtained by finishing
a /explore quest. Every entry records its rarity tier and where to
find its sprite image.

This is deliberately just plain Python data (no database, no AI) - it
does not need to change at runtime, so a database table would be
overkill. If the list grows a lot later, this could move into its own
table, but a plain list is simpler to read and edit for now.

How rarity is decided
----------------------
Rarity is based on each Pokémon's position in its evolution line:
  - Still evolves further (a "basic" or "middle" form)      -> common,
    unless it ALSO evolved from something else (a true middle
    form, e.g. Ivysaur) -> uncommon
  - Fully evolved (the last form of a multi-stage line)      -> rare
  - Never evolves at all (no earlier or later form, e.g.
    Tauros, Ditto, Snorlax)                                  -> uncommon
  - The five Legendary/Mythical Pokémon (Articuno, Zapdos,
    Moltres, Mewtwo, Mew) are hard-coded as "legendary",
    overriding all of the above.

Sprites
-------
Sprite images are loaded directly from Pokémon Showdown
(https://play.pokemonshowdown.com/sprites/ani/), which hosts free,
publicly-served animated Pokémon sprites. We don't download or store
the images ourselves - Discord fetches them straight from that URL
when it renders the embed. The filename Showdown expects is the
Pokémon's name, lowercased, with every character that isn't a-z/0-9
removed (this is Showdown's own "toID" convention) - see
_to_showdown_id() below. Two Pokémon (the Nidoran forms) can't be
derived this way because their names use ♀/♂ symbols, so they get an
explicit "slug" override instead.
"""

import re

SHOWDOWN_SPRITE_BASE = "https://play.pokemonshowdown.com/sprites/ani/"
SHOWDOWN_SHINY_SPRITE_BASE = "https://play.pokemonshowdown.com/sprites/ani-shiny/"


def _to_showdown_id(name: str) -> str:
    """
    Convert a Pokémon's display name into the ID format Pokémon
    Showdown uses for its sprite filenames, e.g. "Mr. Mime" -> "mrmime",
    "Farfetch'd" -> "farfetchd".
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


def sprite_url(pokemon: dict) -> str:
    """Build the full (normal) sprite image URL for a Pokémon dict."""
    slug = pokemon.get("slug") or _to_showdown_id(pokemon["name"])
    return f"{SHOWDOWN_SPRITE_BASE}{slug}.gif"


def shiny_sprite_url(pokemon: dict) -> str:
    """Same as sprite_url(), but points at Showdown's shiny sprite set instead."""
    slug = pokemon.get("slug") or _to_showdown_id(pokemon["name"])
    return f"{SHOWDOWN_SHINY_SPRITE_BASE}{slug}.gif"


# All 151 Generation 1 Pokémon, in National Pokédex order.
WILD_POKEMON = [
    {"name": "Bulbasaur", "rarity": "common"},
    {"name": "Ivysaur", "rarity": "uncommon"},
    {"name": "Venusaur", "rarity": "rare"},
    {"name": "Charmander", "rarity": "common"},
    {"name": "Charmeleon", "rarity": "uncommon"},
    {"name": "Charizard", "rarity": "rare"},
    {"name": "Squirtle", "rarity": "common"},
    {"name": "Wartortle", "rarity": "uncommon"},
    {"name": "Blastoise", "rarity": "rare"},
    {"name": "Caterpie", "rarity": "common"},
    {"name": "Metapod", "rarity": "uncommon"},
    {"name": "Butterfree", "rarity": "rare"},
    {"name": "Weedle", "rarity": "common"},
    {"name": "Kakuna", "rarity": "uncommon"},
    {"name": "Beedrill", "rarity": "rare"},
    {"name": "Pidgey", "rarity": "common"},
    {"name": "Pidgeotto", "rarity": "uncommon"},
    {"name": "Pidgeot", "rarity": "rare"},
    {"name": "Rattata", "rarity": "common"},
    {"name": "Raticate", "rarity": "rare"},
    {"name": "Spearow", "rarity": "common"},
    {"name": "Fearow", "rarity": "rare"},
    {"name": "Ekans", "rarity": "common"},
    {"name": "Arbok", "rarity": "rare"},
    {"name": "Pikachu", "rarity": "common"},
    {"name": "Raichu", "rarity": "rare"},
    {"name": "Sandshrew", "rarity": "common"},
    {"name": "Sandslash", "rarity": "rare"},
    {"name": "Nidoran♀", "rarity": "common", "slug": "nidoranf"},
    {"name": "Nidorina", "rarity": "uncommon"},
    {"name": "Nidoqueen", "rarity": "rare"},
    {"name": "Nidoran♂", "rarity": "common", "slug": "nidoranm"},
    {"name": "Nidorino", "rarity": "uncommon"},
    {"name": "Nidoking", "rarity": "rare"},
    {"name": "Clefairy", "rarity": "common"},
    {"name": "Clefable", "rarity": "rare"},
    {"name": "Vulpix", "rarity": "common"},
    {"name": "Ninetales", "rarity": "rare"},
    {"name": "Jigglypuff", "rarity": "common"},
    {"name": "Wigglytuff", "rarity": "rare"},
    {"name": "Zubat", "rarity": "common"},
    {"name": "Golbat", "rarity": "rare"},
    {"name": "Oddish", "rarity": "common"},
    {"name": "Gloom", "rarity": "uncommon"},
    {"name": "Vileplume", "rarity": "rare"},
    {"name": "Paras", "rarity": "common"},
    {"name": "Parasect", "rarity": "rare"},
    {"name": "Venonat", "rarity": "common"},
    {"name": "Venomoth", "rarity": "rare"},
    {"name": "Diglett", "rarity": "common"},
    {"name": "Dugtrio", "rarity": "rare"},
    {"name": "Meowth", "rarity": "common"},
    {"name": "Persian", "rarity": "rare"},
    {"name": "Psyduck", "rarity": "common"},
    {"name": "Golduck", "rarity": "rare"},
    {"name": "Mankey", "rarity": "common"},
    {"name": "Primeape", "rarity": "rare"},
    {"name": "Growlithe", "rarity": "common"},
    {"name": "Arcanine", "rarity": "rare"},
    {"name": "Poliwag", "rarity": "common"},
    {"name": "Poliwhirl", "rarity": "uncommon"},
    {"name": "Poliwrath", "rarity": "rare"},
    {"name": "Abra", "rarity": "common"},
    {"name": "Kadabra", "rarity": "uncommon"},
    {"name": "Alakazam", "rarity": "rare"},
    {"name": "Machop", "rarity": "common"},
    {"name": "Machoke", "rarity": "uncommon"},
    {"name": "Machamp", "rarity": "rare"},
    {"name": "Bellsprout", "rarity": "common"},
    {"name": "Weepinbell", "rarity": "uncommon"},
    {"name": "Victreebel", "rarity": "rare"},
    {"name": "Tentacool", "rarity": "common"},
    {"name": "Tentacruel", "rarity": "rare"},
    {"name": "Geodude", "rarity": "common"},
    {"name": "Graveler", "rarity": "uncommon"},
    {"name": "Golem", "rarity": "rare"},
    {"name": "Ponyta", "rarity": "common"},
    {"name": "Rapidash", "rarity": "rare"},
    {"name": "Slowpoke", "rarity": "common"},
    {"name": "Slowbro", "rarity": "rare"},
    {"name": "Magnemite", "rarity": "common"},
    {"name": "Magneton", "rarity": "rare"},
    {"name": "Farfetch'd", "rarity": "uncommon"},
    {"name": "Doduo", "rarity": "common"},
    {"name": "Dodrio", "rarity": "rare"},
    {"name": "Seel", "rarity": "common"},
    {"name": "Dewgong", "rarity": "rare"},
    {"name": "Grimer", "rarity": "common"},
    {"name": "Muk", "rarity": "rare"},
    {"name": "Shellder", "rarity": "common"},
    {"name": "Cloyster", "rarity": "rare"},
    {"name": "Gastly", "rarity": "common"},
    {"name": "Haunter", "rarity": "uncommon"},
    {"name": "Gengar", "rarity": "rare"},
    {"name": "Onix", "rarity": "uncommon"},
    {"name": "Drowzee", "rarity": "common"},
    {"name": "Hypno", "rarity": "rare"},
    {"name": "Krabby", "rarity": "common"},
    {"name": "Kingler", "rarity": "rare"},
    {"name": "Voltorb", "rarity": "common"},
    {"name": "Electrode", "rarity": "rare"},
    {"name": "Exeggcute", "rarity": "common"},
    {"name": "Exeggutor", "rarity": "rare"},
    {"name": "Cubone", "rarity": "common"},
    {"name": "Marowak", "rarity": "rare"},
    {"name": "Hitmonlee", "rarity": "uncommon"},
    {"name": "Hitmonchan", "rarity": "uncommon"},
    {"name": "Lickitung", "rarity": "uncommon"},
    {"name": "Koffing", "rarity": "common"},
    {"name": "Weezing", "rarity": "rare"},
    {"name": "Rhyhorn", "rarity": "common"},
    {"name": "Rhydon", "rarity": "rare"},
    {"name": "Chansey", "rarity": "uncommon"},
    {"name": "Tangela", "rarity": "uncommon"},
    {"name": "Kangaskhan", "rarity": "uncommon"},
    {"name": "Horsea", "rarity": "common"},
    {"name": "Seadra", "rarity": "rare"},
    {"name": "Goldeen", "rarity": "common"},
    {"name": "Seaking", "rarity": "rare"},
    {"name": "Staryu", "rarity": "common"},
    {"name": "Starmie", "rarity": "rare"},
    {"name": "Mr. Mime", "rarity": "uncommon"},
    {"name": "Scyther", "rarity": "uncommon"},
    {"name": "Jynx", "rarity": "uncommon"},
    {"name": "Electabuzz", "rarity": "uncommon"},
    {"name": "Magmar", "rarity": "uncommon"},
    {"name": "Pinsir", "rarity": "uncommon"},
    {"name": "Tauros", "rarity": "uncommon"},
    {"name": "Magikarp", "rarity": "common"},
    {"name": "Gyarados", "rarity": "rare"},
    {"name": "Lapras", "rarity": "uncommon"},
    {"name": "Ditto", "rarity": "uncommon"},
    {"name": "Eevee", "rarity": "common"},
    {"name": "Vaporeon", "rarity": "rare"},
    {"name": "Jolteon", "rarity": "rare"},
    {"name": "Flareon", "rarity": "rare"},
    {"name": "Porygon", "rarity": "uncommon"},
    {"name": "Omanyte", "rarity": "common"},
    {"name": "Omastar", "rarity": "rare"},
    {"name": "Kabuto", "rarity": "common"},
    {"name": "Kabutops", "rarity": "rare"},
    {"name": "Aerodactyl", "rarity": "uncommon"},
    {"name": "Snorlax", "rarity": "uncommon"},
    {"name": "Articuno", "rarity": "legendary"},
    {"name": "Zapdos", "rarity": "legendary"},
    {"name": "Moltres", "rarity": "legendary"},
    {"name": "Dratini", "rarity": "common"},
    {"name": "Dragonair", "rarity": "uncommon"},
    {"name": "Dragonite", "rarity": "rare"},
    {"name": "Mewtwo", "rarity": "legendary"},
    {"name": "Mew", "rarity": "legendary"},

    # Ho-Oh and Lugia are Generation 2 legendaries - outside the
    # original 151 (Generation 1) roster this file's docstring
    # describes above. They were added specifically as a QUEST-ONLY
    # reward (see pokemon/legendary_quest.py), in response to real
    # tester feedback that /explore didn't feel like it affected
    # gameplay enough.
    # "quest_exclusive": True is what keeps them out of the normal
    # /catch pool - see the filter in pokemon/encounters.py's
    # generate_wild_encounter(). They still live in this same list
    # (rather than a separate one) so every other piece of shared
    # species infrastructure - sprites, Pokédex numbers, /team and
    # /box display, the owner-only ;spawn lookup - already works for
    # them automatically, without needing its own special case.
    {"name": "Ho-Oh", "rarity": "legendary", "quest_exclusive": True},
    {"name": "Lugia", "rarity": "legendary", "quest_exclusive": True},
]

# How likely each rarity TIER is to show up at all (relative weights,
# not percentages - see pokemon/encounters.py). Because "rare" and
# "common" now contain very different numbers of species (56 vs 54,
# roughly even) but very different tier-level odds (9% vs 60%), an
# individual rare species is still much harder to run into than an
# individual common one, even though the two tiers are similar in size.
RARITY_WEIGHTS = {
    "common": 60,
    "uncommon": 30,
    "rare": 9,
    "legendary": 1,
}

# The chance, as a whole number out of 100, of successfully catching a
# Pokémon of each rarity tier on a single throw - e.g. 80 means an
# 80% chance. Using 1-100 instead of 0.0-1.0 makes it easy to show the
# player a "roll" that matches this same scale (see attempt_catch() in
# pokemon/encounters.py). Catch-rate boosts and Poké Ball types (e.g.
# a Master Ball) are planned as later, separate additions on top of
# these base numbers.
BASE_CATCH_RATE = {
    "common": 80,
    "uncommon": 65,
    "rare": 50,
    "legendary": 30,
}

# Each species' National Pokédex number, e.g. DEX_NUMBER["Pikachu"] ==
# 25. Built automatically from WILD_POKEMON's own order (see its
# comment above: "in National Pokédex order") rather than typing out
# all 151 numbers by hand a second time, which would be easy to get
# out of sync with the list above if it's ever edited. Used by
# commands/collection.py to sort the box by dex order.
DEX_NUMBER = {pokemon["name"]: index + 1 for index, pokemon in enumerate(WILD_POKEMON)}

# Ho-Oh and Lugia are appended to the END of WILD_POKEMON above (so
# their position in the list doesn't disturb the original 151's own
# order), which means the auto-numbering line above would give them
# the wrong Pokédex numbers (152 and 153 - their position in this
# list, not their real one). Overridden here with their real National
# Pokédex numbers, so ai/audio_classifier.py can still find the
# correct cry clip for them if one is ever set as a player's lead
# Pokémon.
DEX_NUMBER["Ho-Oh"] = 250
DEX_NUMBER["Lugia"] = 249

# The prefix commands/promo.py stores in front of a promo Pokémon's
# species name (e.g. "Shiny Charmander") - see that file's own comment
# for why the shiny status is folded into the stored NAME itself,
# rather than a separate column. Every place that needs to turn a
# stored team/box name back into a sprite (see
# stored_name_sprite_url() below) needs to know about this same
# prefix, so it's kept here as one shared constant rather than a
# string literal copy-pasted into every one of those places.
SHINY_NAME_PREFIX = "Shiny "


def split_stored_name(pokemon_name: str) -> tuple[str, bool]:
    """
    Split a name as STORED in a player's team/box back into
    (real_species_name, is_shiny) - e.g. "Shiny Charmander" ->
    ("Charmander", True), "Pikachu" -> ("Pikachu", False).

    Every stored team/box name is either a real species name, or that
    real species name with SHINY_NAME_PREFIX in front of it (see
    commands/promo.py and commands/dev.py's ;spawn) - there's no third
    format, so this one function is enough to undo it anywhere that
    needs the real species back (an evolution lookup, a Pokédex number,
    or a sprite - see stored_name_sprite_url() below).
    """
    if pokemon_name.startswith(SHINY_NAME_PREFIX):
        return pokemon_name[len(SHINY_NAME_PREFIX):], True
    return pokemon_name, False


def stored_name_sprite_url(pokemon_name: str) -> str | None:
    """
    Resolve the sprite/GIF URL for a name exactly as it's stored in a
    player's team/box - which might be a real species name ("Pikachu")
    or a shiny promo/spawned one ("Shiny Charmander" - see
    commands/promo.py and commands/dev.py's ;spawn).

    This is the one shared place that turns a stored name into the
    CORRECT sprite (the shiny palette for a shiny entry, the normal one
    otherwise) - used by every command that shows a Pokémon's sprite
    for something already in a player's team/box (commands/move.py,
    commands/evolve.py, commands/collection.py), so the shiny handling
    only has to be written once.

    Returns None if the name can't be matched to any known species (for
    example, a display name typed some other way in the past), so a
    caller can fall back to no image instead of crashing.
    """
    species_name, is_shiny = split_stored_name(pokemon_name)
    species = next((p for p in WILD_POKEMON if p["name"] == species_name), None)
    if species is None:
        return None
    return shiny_sprite_url(species) if is_shiny else sprite_url(species)
