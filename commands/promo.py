"""
The promo command - a free, guaranteed promotional Pokémon.

Like every other command in this project, this is a hybrid command:
one definition, usable as both /promo and ;promo (see bot.py for how
that's wired up). Unlike /catch, there's no wild encounter and no
catch roll here - promo Pokémon are a straightforward giveaway, so
whoever runs it just receives it directly (still following the same
team/box capacity rule as a normal catch - see database/player.py).
"""

import discord
from discord.ext import commands

from pokemon.data import WILD_POKEMON, shiny_sprite_url
from database.player import add_caught_pokemon

# The species currently being given away by /promo (or ;promo). To
# switch to a different promo Pokémon later, just change this name -
# everything else below adapts automatically. It must be a name that
# already exists in pokemon.data.WILD_POKEMON.
CURRENT_PROMO_SPECIES = "Charmander"

PROMO_COLOUR = discord.Colour.gold()


def _get_promo_pokemon() -> dict:
    """Look up the current promo species' normal data, and mark it as shiny."""
    base = next(p for p in WILD_POKEMON if p["name"] == CURRENT_PROMO_SPECIES)
    return {**base, "shiny": True}


def setup(bot: commands.Bot):

    @bot.hybrid_command(
        name="promo",
        description="Claim the current free promotional Pokémon."
    )
    async def promo(ctx: commands.Context):
        pokemon = _get_promo_pokemon()

        # NOTE: the team/box just stores plain name strings for now
        # (e.g. "Pikachu"), so we store this as "Shiny Charmander" to
        # make it visually distinct in a future /team or /box command.
        # That name won't resolve to a real sprite through
        # sprite_url() (it isn't a real species name) - that's fine
        # for now since nothing currently tries to render sprites from
        # stored team/box data, but will need a proper fix (storing
        # shiny status separately from the name) once a command that
        # DOES display box/team sprites gets built.
        display_name = f"Shiny {pokemon['name']}"
        result = add_caught_pokemon(ctx.author.id, display_name)

        embed = discord.Embed(
            title=f"✨ You received a Shiny {pokemon['name']}!",
            colour=PROMO_COLOUR
        )
        embed.set_image(url=shiny_sprite_url(pokemon))

        if result["went_to"] == "team":
            embed.description = f"**{display_name}** joined your team!"
        else:
            embed.description = (
                f"**{display_name}** was added, but your team is full (6/6) "
                "- it was sent to your box instead."
            )

        await ctx.send(embed=embed)
