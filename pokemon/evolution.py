"""
Evolution data and eligibility checks for all 151 Generation 1 species.

Design decision (stated by Keith): a real Pokémon's evolution normally
happens one of four ways - reaching a level, growing fond enough of its
trainer (friendship), being exposed to an evolution stone, or being
traded to another player. This project has no trading and no item-based
stone mechanic, so those two methods can't work as-is. Rather than just
dropping those evolutions from the game entirely, every evolution that
ISN'T friendship-based is converted into a LEVEL requirement instead:
a species that already evolved by levelling up keeps its real level
requirement unchanged, and a species that normally needed a stone or a
trade instead evolves at a flat LEVEL 40.

A fact worth being explicit about (and worth mentioning in the report):
friendship-based evolution didn't exist yet in the actual Generation 1
games - it was only introduced in Generation 2 (e.g. Golbat -> Crobat).
None of the 151 species in this project's roster evolve by friendship
in the real games, so in practice EVERY evolution below ends up being
level-based. The "friendship" method is still fully implemented and
supported here (see is_eligible_for() below) so the system is correct
and extensible if Generation 2 species were ever added later - it just
means nothing in the CURRENT 151-species roster exercises that path.

Levels below match the real Generation 1 games (Bulbasaur -> Ivysaur at
16, Charmander -> Charmeleon at 16, and so on). Species with no entry
here either never evolve (e.g. Tauros, Snorlax) or are already the
final form of their line (e.g. Venusaur).
"""

from pokemon.growth import MAX_FRIENDSHIP

# Every non-level evolution (stone or trade, in the real games) becomes
# this flat level in this project - see the module docstring above.
CONVERTED_EVOLUTION_LEVEL = 40

# How much friendship a species needs before it's eligible for a
# friendship-based evolution. Set to the maximum a Pokémon can reach
# (pokemon/growth.py's MAX_FRIENDSHIP) - "friendship" evolutions in the
# real games require a very high bond, so requiring the max here fits
# that, even though no species in this project's roster currently uses
# this method (see the module docstring above).
FRIENDSHIP_EVOLUTION_THRESHOLD = MAX_FRIENDSHIP

# One entry per species that evolves. Species not listed here either
# never evolve or are already a fully-evolved final form.
#
# Fields:
#   "evolves_to" - list of species names it can evolve into. Almost
#                  always one name; Eevee is the only 3-way branch in
#                  this roster (Vaporeon/Jolteon/Flareon), so it's a
#                  list rather than a single string everywhere, to
#                  handle that one case without a special data shape.
#   "method"     - "level" or "friendship" (see module docstring - only
#                  "level" is ever actually used right now).
#   "level"      - only present when method == "level".
#   "originally" - NOT used by any game logic - purely a record of what
#                  this evolution actually required in the real games,
#                  kept here so the report can cite exactly which
#                  species were converted from stone/trade to level 40.
EVOLUTION_DATA = {
    "Bulbasaur": {"evolves_to": ["Ivysaur"], "method": "level", "level": 16, "originally": "level"},
    "Ivysaur": {"evolves_to": ["Venusaur"], "method": "level", "level": 32, "originally": "level"},
    "Charmander": {"evolves_to": ["Charmeleon"], "method": "level", "level": 16, "originally": "level"},
    "Charmeleon": {"evolves_to": ["Charizard"], "method": "level", "level": 36, "originally": "level"},
    "Squirtle": {"evolves_to": ["Wartortle"], "method": "level", "level": 16, "originally": "level"},
    "Wartortle": {"evolves_to": ["Blastoise"], "method": "level", "level": 36, "originally": "level"},
    "Caterpie": {"evolves_to": ["Metapod"], "method": "level", "level": 7, "originally": "level"},
    "Metapod": {"evolves_to": ["Butterfree"], "method": "level", "level": 10, "originally": "level"},
    "Weedle": {"evolves_to": ["Kakuna"], "method": "level", "level": 7, "originally": "level"},
    "Kakuna": {"evolves_to": ["Beedrill"], "method": "level", "level": 10, "originally": "level"},
    "Pidgey": {"evolves_to": ["Pidgeotto"], "method": "level", "level": 18, "originally": "level"},
    "Pidgeotto": {"evolves_to": ["Pidgeot"], "method": "level", "level": 36, "originally": "level"},
    "Rattata": {"evolves_to": ["Raticate"], "method": "level", "level": 20, "originally": "level"},
    "Spearow": {"evolves_to": ["Fearow"], "method": "level", "level": 20, "originally": "level"},
    "Ekans": {"evolves_to": ["Arbok"], "method": "level", "level": 22, "originally": "level"},
    "Pikachu": {"evolves_to": ["Raichu"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Thunder Stone)"},
    "Sandshrew": {"evolves_to": ["Sandslash"], "method": "level", "level": 22, "originally": "level"},
    "Nidoran♀": {"evolves_to": ["Nidorina"], "method": "level", "level": 16, "originally": "level"},
    "Nidorina": {"evolves_to": ["Nidoqueen"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Moon Stone)"},
    "Nidoran♂": {"evolves_to": ["Nidorino"], "method": "level", "level": 16, "originally": "level"},
    "Nidorino": {"evolves_to": ["Nidoking"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Moon Stone)"},
    "Clefairy": {"evolves_to": ["Clefable"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Moon Stone)"},
    "Vulpix": {"evolves_to": ["Ninetales"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Fire Stone)"},
    "Jigglypuff": {"evolves_to": ["Wigglytuff"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Moon Stone)"},
    "Zubat": {"evolves_to": ["Golbat"], "method": "level", "level": 22, "originally": "level"},
    "Oddish": {"evolves_to": ["Gloom"], "method": "level", "level": 21, "originally": "level"},
    "Gloom": {"evolves_to": ["Vileplume"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Leaf Stone)"},
    "Paras": {"evolves_to": ["Parasect"], "method": "level", "level": 24, "originally": "level"},
    "Venonat": {"evolves_to": ["Venomoth"], "method": "level", "level": 31, "originally": "level"},
    "Diglett": {"evolves_to": ["Dugtrio"], "method": "level", "level": 26, "originally": "level"},
    "Meowth": {"evolves_to": ["Persian"], "method": "level", "level": 28, "originally": "level"},
    "Psyduck": {"evolves_to": ["Golduck"], "method": "level", "level": 33, "originally": "level"},
    "Mankey": {"evolves_to": ["Primeape"], "method": "level", "level": 28, "originally": "level"},
    "Growlithe": {"evolves_to": ["Arcanine"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Fire Stone)"},
    "Poliwag": {"evolves_to": ["Poliwhirl"], "method": "level", "level": 25, "originally": "level"},
    "Poliwhirl": {"evolves_to": ["Poliwrath"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Water Stone)"},
    "Abra": {"evolves_to": ["Kadabra"], "method": "level", "level": 16, "originally": "level"},
    "Kadabra": {"evolves_to": ["Alakazam"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "trade"},
    "Machop": {"evolves_to": ["Machoke"], "method": "level", "level": 28, "originally": "level"},
    "Machoke": {"evolves_to": ["Machamp"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "trade"},
    "Bellsprout": {"evolves_to": ["Weepinbell"], "method": "level", "level": 21, "originally": "level"},
    "Weepinbell": {"evolves_to": ["Victreebel"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Leaf Stone)"},
    "Tentacool": {"evolves_to": ["Tentacruel"], "method": "level", "level": 30, "originally": "level"},
    "Geodude": {"evolves_to": ["Graveler"], "method": "level", "level": 25, "originally": "level"},
    "Graveler": {"evolves_to": ["Golem"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "trade"},
    "Ponyta": {"evolves_to": ["Rapidash"], "method": "level", "level": 40, "originally": "level"},
    "Slowpoke": {"evolves_to": ["Slowbro"], "method": "level", "level": 37, "originally": "level"},
    "Magnemite": {"evolves_to": ["Magneton"], "method": "level", "level": 30, "originally": "level"},
    "Doduo": {"evolves_to": ["Dodrio"], "method": "level", "level": 31, "originally": "level"},
    "Seel": {"evolves_to": ["Dewgong"], "method": "level", "level": 34, "originally": "level"},
    "Grimer": {"evolves_to": ["Muk"], "method": "level", "level": 38, "originally": "level"},
    "Shellder": {"evolves_to": ["Cloyster"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Water Stone)"},
    "Gastly": {"evolves_to": ["Haunter"], "method": "level", "level": 25, "originally": "level"},
    "Haunter": {"evolves_to": ["Gengar"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "trade"},
    "Drowzee": {"evolves_to": ["Hypno"], "method": "level", "level": 26, "originally": "level"},
    "Krabby": {"evolves_to": ["Kingler"], "method": "level", "level": 28, "originally": "level"},
    "Voltorb": {"evolves_to": ["Electrode"], "method": "level", "level": 30, "originally": "level"},
    "Exeggcute": {"evolves_to": ["Exeggutor"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Leaf Stone)"},
    "Cubone": {"evolves_to": ["Marowak"], "method": "level", "level": 28, "originally": "level"},
    "Koffing": {"evolves_to": ["Weezing"], "method": "level", "level": 35, "originally": "level"},
    "Rhyhorn": {"evolves_to": ["Rhydon"], "method": "level", "level": 42, "originally": "level"},
    "Horsea": {"evolves_to": ["Seadra"], "method": "level", "level": 32, "originally": "level"},
    "Goldeen": {"evolves_to": ["Seaking"], "method": "level", "level": 33, "originally": "level"},
    "Staryu": {"evolves_to": ["Starmie"], "method": "level", "level": CONVERTED_EVOLUTION_LEVEL, "originally": "stone (Water Stone)"},
    "Magikarp": {"evolves_to": ["Gyarados"], "method": "level", "level": 20, "originally": "level"},
    "Eevee": {
        "evolves_to": ["Vaporeon", "Jolteon", "Flareon"],
        "method": "level",
        "level": CONVERTED_EVOLUTION_LEVEL,
        "originally": "stone (Water/Thunder/Fire Stone - a 3-way branch, normally the player's choice of stone)",
    },
    "Omanyte": {"evolves_to": ["Omastar"], "method": "level", "level": 40, "originally": "level"},
    "Kabuto": {"evolves_to": ["Kabutops"], "method": "level", "level": 40, "originally": "level"},
    "Dratini": {"evolves_to": ["Dragonair"], "method": "level", "level": 30, "originally": "level"},
    "Dragonair": {"evolves_to": ["Dragonite"], "method": "level", "level": 55, "originally": "level"},
}


def get_evolution_info(species_name: str) -> dict | None:
    """
    Look up a species' evolution entry, or None if it doesn't evolve at
    all (either it never evolves, or it's already a fully-evolved final
    form - both cases are simply absent from EVOLUTION_DATA).
    """
    return EVOLUTION_DATA.get(species_name)


def is_eligible_for(evolution_info: dict, pokemon_stats: dict) -> bool:
    """
    Given one species' evolution entry (from EVOLUTION_DATA) and a
    Pokémon's current stats ({"level", "exp", "friendship"} - see
    database/player.py), decide whether it currently meets the
    requirement to evolve.

    A plain function of its two inputs (no database access), so this
    can be tested directly and instantly - see
    tests/test_evolution.py.
    """
    if evolution_info["method"] == "level":
        return pokemon_stats.get("level", 1) >= evolution_info["level"]

    if evolution_info["method"] == "friendship":
        return pokemon_stats.get("friendship", 0) >= FRIENDSHIP_EVOLUTION_THRESHOLD

    # Not currently reachable with the methods used in EVOLUTION_DATA
    # above, but fails safe (not eligible) rather than crashing if a
    # future entry ever used an unrecognised method by mistake.
    return False


def evolution_requirement_text(evolution_info: dict) -> str:
    """
    A short, player-facing description of what's still needed, for the
    "not ready yet" message in commands/evolve.py - e.g. "reach level
    40" or "reach maximum friendship".
    """
    if evolution_info["method"] == "level":
        return f"reach level {evolution_info['level']}"

    return "reach maximum friendship"
