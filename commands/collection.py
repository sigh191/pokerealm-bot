"""
The /team and /box commands - let a player check what they've caught.

/team shows one embed per team Pokémon (see _build_team_embeds()) -
Discord embeds only support ONE image each (via set_image, big) or ONE
small corner icon (via set_thumbnail), so sending several small embeds
in one message - Discord allows up to 10 per message - is what makes
"icon next to name" possible for more than one Pokémon at a time. A
team is capped at 6, so it always fits comfortably under that limit.

/box used to work the same way, but a box has no size limit - a long
session of catching can easily end up with more than 10 DIFFERENT
species, which silently cut off the rest under the old embeds-per-
message approach. /box is instead a single embed with one plain text
line per species (see _build_box_text()), sorted by National Pokédex
number - no per-species icon, but no limit on how many species can be
shown either.
"""

from collections import Counter

import discord
from discord.ext import commands

from pokemon.data import WILD_POKEMON, DEX_NUMBER, stored_name_sprite_url, split_stored_name
from pokemon.growth import exp_required_for_level, MAX_LEVEL, MAX_FRIENDSHIP
from database.player import get_player_profile

# A hard limit set by Discord itself (not a design choice) - a single
# message can contain at most 10 embeds. Only /team's per-Pokémon
# embeds run into this (see the module docstring above), and a team
# tops out at 6, so this is really just a safety net.
MAX_EMBEDS_PER_MESSAGE = 10


def _progress_bar(current: int, total: int, length: int = 10) -> str:
    """A simple text progress bar, e.g. '▰▰▰▰▱▱▱▱▱▱' - shared by the EXP and friendship bars below."""
    if total <= 0:
        filled = length
    else:
        filled = max(0, min(length, round(length * current / total)))
    return "▰" * filled + "▱" * (length - filled)


def _build_team_embeds(team: list, colour: discord.Colour) -> list:
    """
    One embed per team SLOT, never grouped by species - unlike
    _build_box_text() below (used for /box), which does group
    duplicates together.

    Note that under the shared-stats-per-species design (see database/
    player.py's module docstring), two Pikachu in the same team will
    always show the exact same level/EXP/friendship, since they share
    one stats entry - this just shows each team slot/position
    separately (so you can still see WHICH slot everyone's in, for
    ;move), not because their progress could differ.
    """
    if not team:
        return [discord.Embed(
            description="Your team is empty! Go catch something with /catch or ;catch.",
            colour=colour,
        )]

    embeds = []
    for pokemon in team:
        level = pokemon["level"]
        exp = pokemon.get("exp", 0)
        friendship = pokemon.get("friendship", 0)

        embed = discord.Embed(title=f"{pokemon['name']} - Level {level}", colour=colour)

        icon_url = stored_name_sprite_url(pokemon["name"])
        if icon_url:
            embed.set_thumbnail(url=icon_url)

        if level >= MAX_LEVEL:
            exp_text = "⭐ MAX LEVEL"
        else:
            # exp/level are both stored as running totals (see
            # pokemon/growth.py), so what's shown here is just the
            # progress WITHIN the current level - the amount already
            # banked before reaching this level doesn't count towards
            # "how close to levelling up" the bar is meant to show.
            exp_into_level = exp - exp_required_for_level(level)
            exp_for_next = exp_required_for_level(level + 1) - exp_required_for_level(level)
            exp_text = (
                f"{_progress_bar(exp_into_level, exp_for_next)} "
                f"{exp_into_level}/{exp_for_next} EXP to Level {level + 1}"
            )
        embed.add_field(name="⭐ Experience", value=exp_text, inline=False)

        embed.add_field(
            name="💗 Friendship",
            value=f"{_progress_bar(friendship, MAX_FRIENDSHIP)} {friendship}/{MAX_FRIENDSHIP}",
            inline=False,
        )

        embeds.append(embed)

    return embeds


def _dex_number(pokemon_name: str) -> int:
    """
    Look up a stored name's National Pokédex number, for sorting the
    box by dex order (e.g. Charmander #4 before Pikachu #25 before
    Mewtwo #150).

    Handles the "Shiny <species>" naming promo.py/dev.py's ;spawn use
    (see pokemon/data.py's split_stored_name()) by looking up the real
    species underneath - "Shiny Charmander" itself isn't in DEX_NUMBER,
    but "Charmander" is. Anything that still can't be matched sorts to
    the very end (instead of crashing), so an unexpected name never
    breaks the whole command.
    """
    species_name, _is_shiny = split_stored_name(pokemon_name)
    return DEX_NUMBER.get(species_name, len(WILD_POKEMON) + 1)


def _build_box_text(pokemon_names: list, empty_message: str) -> str:
    """
    Turn a flat list of stored box names (e.g. ["Pikachu", "Pikachu",
    "Mewtwo"]) into one compact line per species, counted and sorted
    by National Pokédex number, e.g.:
        4x Charmander
        25x Pikachu
        150x Mewtwo

    A single block of text like this - rather than the old one-embed-
    per-species layout - has no limit on how many different species it
    can show: a Discord embed description can hold up to 4096
    characters, comfortably more than the ~151 species x ~15
    characters a completely full box would ever need, whereas the old
    layout silently cut off anything past Discord's 10-embeds-per-
    message limit.
    """
    if not pokemon_names:
        return empty_message

    # Counter groups the duplicate names together and counts them;
    # sorted() then orders the species themselves by dex number.
    counts = Counter(pokemon_names)
    sorted_names = sorted(counts, key=_dex_number)

    return "\n".join(f"{counts[name]}x {name}" for name in sorted_names)


def setup(bot: commands.Bot):

    @bot.hybrid_command(
        name="team",
        description="View your current party of up to 6 Pokémon."
    )
    async def team(ctx: commands.Context):
        player = get_player_profile(ctx.author.id)

        embeds = _build_team_embeds(player["team"], colour=discord.Colour.blurple())

        await ctx.send(
            content=f"**{ctx.author.display_name}'s Team** ({len(player['team'])}/6)",
            embeds=embeds[:MAX_EMBEDS_PER_MESSAGE]
        )

    @bot.hybrid_command(
        name="box",
        description="View the Pokémon stored in your box."
    )
    async def box(ctx: commands.Context):
        player = get_player_profile(ctx.author.id)

        box_text = _build_box_text(
            player["box"],
            empty_message="Your box is empty! It fills up once your team reaches 6/6.",
        )

        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Box ({len(player['box'])} total)",
            description=box_text,
            colour=discord.Colour.dark_teal(),
        )

        await ctx.send(embed=embed)
