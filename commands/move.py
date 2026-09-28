"""
The /move command - reorder your team, to choose which Pokémon is
your LEAD.

The lead (whichever Pokémon sits in position 1) matters a lot more in
this project than it does in the mainline games: it's the one whose
sprite gets classified for quest "vibe" (see ai/image_classifier.py),
the one every /explore quest's story is written around, and the one
that gets the EXP/friendship reward when a quest completes (see
apply_lead_rewards() in database/player.py). This command is how a
player actively chooses who they're "upgrading" that way, instead of
it being permanently fixed to whatever order they happened to catch
things in.

Moving a Pokémon SWAPS it with whoever is currently in the target
position - see move_team_pokemon()'s docstring in database/player.py
for why a swap, rather than shifting the rest of the team along.
"""

import discord
from discord.ext import commands

from database.player import get_player_profile, move_team_pokemon
from pokemon.data import stored_name_sprite_url

MOVE_COLOUR = discord.Colour.blue()
ERROR_COLOUR = discord.Colour.red()


def setup(bot: commands.Bot):

    @bot.hybrid_command(
        name="move",
        description="Reorder your team - move a Pokémon to a new position (1 = lead)."
    )
    async def move(ctx: commands.Context, pokemon_name: str, position: int):
        # NOTE: for a species stored with a space in its name (like a
        # Shiny promo Pokémon - see commands/promo.py, e.g. "Shiny
        # Charmander"), the ;move prefix form needs quotes around it
        # (;move "Shiny Charmander" 1) so it's parsed as one argument
        # rather than two. The /move slash-command form doesn't have
        # this issue - Discord always sends each option as one value.
        player = get_player_profile(ctx.author.id)
        team_size = len(player["team"])

        if team_size == 0:
            await ctx.send(embed=discord.Embed(
                description="Your team is empty - there's nothing to reorder yet.",
                colour=ERROR_COLOUR,
            ))
            return

        if position < 1 or position > team_size:
            await ctx.send(embed=discord.Embed(
                description=(
                    f"Position must be between 1 and {team_size} "
                    f"(your team currently has {team_size} Pokémon)."
                ),
                colour=ERROR_COLOUR,
            ))
            return

        # Whoever is CURRENTLY sitting in the destination slot - purely
        # to make the confirmation message clear about what actually
        # happens, since ;move SWAPS two Pokémon rather than shifting
        # the whole team along (see move_team_pokemon()'s docstring).
        current_occupant = player["team"][position - 1]["name"]

        new_team = move_team_pokemon(ctx.author.id, pokemon_name, position)

        if new_team is None:
            await ctx.send(embed=discord.Embed(
                description=(
                    f"Couldn't find **{pokemon_name}** on your team. "
                    "Check /team or ;team for the exact name."
                ),
                colour=ERROR_COLOUR,
            ))
            return

        moved_name = new_team[position - 1]["name"]

        if moved_name.lower() == current_occupant.lower():
            # The player "moved" a Pokémon to the position it was
            # already in - swapping it with itself is a no-op.
            summary = f"✅ **{moved_name}** is already in position {position}."
        else:
            summary = f"✅ Swapped **{moved_name}** and **{current_occupant}** - **{moved_name}** is now in position {position}"
            summary += " (your new lead!)" if position == 1 else "."

        order_text = "\n".join(
            f"{i + 1}. {pokemon['name']} (Lv. {pokemon['level']})"
            for i, pokemon in enumerate(new_team)
        )

        # The moved Pokémon's own sprite is shown on the embed -
        # stored_name_sprite_url() handles a "Shiny <name>" stored name
        # correctly too, the same helper commands/collection.py uses.
        embed = discord.Embed(
            title="Team reordered!",
            description=f"{summary}\n\n**Team order:**\n{order_text}",
            colour=MOVE_COLOUR,
        )
        sprite = stored_name_sprite_url(moved_name)
        if sprite is not None:
            embed.set_thumbnail(url=sprite)

        await ctx.send(embed=embed)
