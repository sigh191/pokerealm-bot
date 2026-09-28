"""
Developer-only utility commands.

These aren't part of normal gameplay - they exist purely so the
developer can test and manage the economy (e.g. seeding coins to check
the shop works) without having to grind for them through /catch.

The permission check here is deliberately simple: a single hard-coded
Discord user ID, checked at the top of the command. Discord does have
a more "proper" way to restrict a slash command's visibility (per-guild
command permissions), but that's overkill for a solo student project
with exactly one developer - this ID check is enough to stop anyone
else from using it, even though the command still technically shows up
in the / menu for everyone.
"""

import discord
from discord.ext import commands

from database.player import get_player_profile, add_coins, add_pokemon_to_box, set_pokemon_level
from pokemon.data import WILD_POKEMON, sprite_url, shiny_sprite_url
from pokemon.growth import MAX_LEVEL

DEV_COLOUR = discord.Colour.dark_grey()
ERROR_COLOUR = discord.Colour.red()

# Keith's Discord user ID. If more developers ever needed access, this
# would be a good candidate to move into a list read from .env instead
# of being hard-coded here.
DEVELOPER_DISCORD_ID = 222268882679889921

# ;spawn accepts an optional "Shiny " prefix (case-insensitive) in
# front of a real species name - e.g. "Shiny Vaporeon" - matching the
# same "Shiny <name>" display-name convention commands/promo.py already
# uses for its own shiny giveaway, rather than inventing a second way
# to represent a shiny Pokémon.
SHINY_PREFIX = "shiny "


def _find_species(name: str) -> str | None:
    """
    Case-insensitive lookup of a species name against
    pokemon.data.WILD_POKEMON, returning it in its CANONICAL
    capitalisation (e.g. "dragonite" -> "Dragonite") or None if it
    isn't a real species. Case-insensitive so the command owner doesn't
    have to type exact capitalisation (or the ♀/♂ symbols correctly, in
    every OTHER respect) to get a match.
    """
    lowered = name.lower()
    for pokemon in WILD_POKEMON:
        if pokemon["name"].lower() == lowered:
            return pokemon["name"]
    return None


def setup(bot: commands.Bot):

    @bot.hybrid_command(
        name="givecoins",
        description="[Developer only] Give coins to a player."
    )
    async def givecoins(ctx: commands.Context, user_id: str, amount: int):
        if ctx.author.id != DEVELOPER_DISCORD_ID:
            await ctx.send(embed=discord.Embed(
                description="You don't have permission to use this command.",
                colour=ERROR_COLOUR,
            ), ephemeral=True)
            return

        try:
            target_id = int(user_id)
        except ValueError:
            await ctx.send(embed=discord.Embed(
                description=f"`{user_id}` isn't a valid Discord user ID.",
                colour=ERROR_COLOUR,
            ), ephemeral=True)
            return

        if amount <= 0:
            await ctx.send(embed=discord.Embed(
                description="Amount must be a positive number.",
                colour=ERROR_COLOUR,
            ), ephemeral=True)
            return

        # add_coins() assumes the player already has a row - calling
        # get_player_profile() first guarantees that even if the
        # target has never used the bot before.
        get_player_profile(target_id)
        new_balance = add_coins(target_id, amount)

        embed = discord.Embed(
            description=(
                f"✅ Gave **{amount:,}** coins to <@{target_id}>. "
                f"Their new balance is **{new_balance:,}** coins."
            ),
            colour=DEV_COLOUR,
        )
        await ctx.send(embed=embed)

    @bot.hybrid_command(
        name="spawn",
        description="[Developer only] Spawn a Pokémon directly into a player's box."
    )
    async def spawn(
        ctx: commands.Context,
        user_id: str,
        *,  # everything typed after user_id is the species name, so a
            # multi-word one (e.g. "Mr. Mime", or "Shiny Vaporeon")
            # doesn't need quotes in the ;spawn prefix form - same
            # technique commands/explore.py uses for its location.
        pokemon: str
    ):
        if ctx.author.id != DEVELOPER_DISCORD_ID:
            await ctx.send(embed=discord.Embed(
                description="You don't have permission to use this command.",
                colour=ERROR_COLOUR,
            ), ephemeral=True)
            return

        try:
            target_id = int(user_id)
        except ValueError:
            await ctx.send(embed=discord.Embed(
                description=f"`{user_id}` isn't a valid Discord user ID.",
                colour=ERROR_COLOUR,
            ), ephemeral=True)
            return

        pokemon = pokemon.strip()
        is_shiny = pokemon.lower().startswith(SHINY_PREFIX)
        species_part = pokemon[len(SHINY_PREFIX):].strip() if is_shiny else pokemon

        matched_species = _find_species(species_part)
        if matched_species is None:
            await ctx.send(embed=discord.Embed(
                description=(
                    f"❌ `{species_part}` isn't a recognised species name. "
                    "Check the spelling (e.g. `Dragonite`, `Mr. Mime`, `Nidoran♀`)."
                ),
                colour=ERROR_COLOUR,
            ))
            return

        # Storing it as "Shiny <name>" (a plain string, not a real
        # separate shiny flag) matches the same "Shiny <name>" display
        # convention commands/promo.py's own giveaway already uses -
        # pokemon/data.py's stored_name_sprite_url() (used by
        # commands/move.py and commands/evolve.py) knows how to turn
        # this back into the correct shiny/normal sprite, which is why
        # this embed can just look the species up directly below rather
        # than needing its own special case.
        display_name = f"Shiny {matched_species}" if is_shiny else matched_species

        # add_pokemon_to_box() assumes the player already has a row -
        # calling get_player_profile() first guarantees that even if
        # the target has never used the bot before.
        get_player_profile(target_id)
        add_pokemon_to_box(target_id, display_name)

        species_data = next(p for p in WILD_POKEMON if p["name"] == matched_species)
        embed = discord.Embed(
            title=f"✨ Spawned {display_name}!" if is_shiny else f"Spawned {display_name}!",
            description=f"**{display_name}** was added to <@{target_id}>'s box.",
            colour=DEV_COLOUR,
        )
        embed.set_image(url=shiny_sprite_url(species_data) if is_shiny else sprite_url(species_data))
        await ctx.send(embed=embed)

    @bot.hybrid_command(
        name="setlevel",
        description="[Developer only] Set one of a player's Pokémon to an exact level."
    )
    async def setlevel(
        ctx: commands.Context,
        user_id: str,
        pokemon: str,
        level: int,
    ):
        if ctx.author.id != DEVELOPER_DISCORD_ID:
            await ctx.send(embed=discord.Embed(
                description="You don't have permission to use this command.",
                colour=ERROR_COLOUR,
            ), ephemeral=True)
            return

        try:
            target_id = int(user_id)
        except ValueError:
            await ctx.send(embed=discord.Embed(
                description=f"`{user_id}` isn't a valid Discord user ID.",
                colour=ERROR_COLOUR,
            ), ephemeral=True)
            return

        if level < 1 or level > MAX_LEVEL:
            await ctx.send(embed=discord.Embed(
                description=f"Level must be between 1 and {MAX_LEVEL}.",
                colour=ERROR_COLOUR,
            ), ephemeral=True)
            return

        # Same "Shiny <name>" prefix handling as ;spawn above - a shiny
        # Pokémon is stored (and therefore looked up here) under its own
        # separate "Shiny <name>" key, distinct from the plain species.
        pokemon = pokemon.strip()
        is_shiny = pokemon.lower().startswith(SHINY_PREFIX)
        species_part = pokemon[len(SHINY_PREFIX):].strip() if is_shiny else pokemon

        matched_species = _find_species(species_part)
        if matched_species is None:
            await ctx.send(embed=discord.Embed(
                description=(
                    f"❌ `{species_part}` isn't a recognised species name. "
                    "Check the spelling (e.g. `Dragonite`, `Mr. Mime`, `Nidoran♀`)."
                ),
                colour=ERROR_COLOUR,
            ))
            return

        display_name = f"Shiny {matched_species}" if is_shiny else matched_species

        # set_pokemon_level() itself checks the target actually owns
        # this exact Pokémon (in their team OR box) before changing
        # anything, and returns None if not - it never creates a new
        # species entry the way ;spawn deliberately does, since this
        # command is for adjusting something that already exists, not
        # for granting a new Pokémon.
        new_stats = set_pokemon_level(target_id, display_name, level)
        if new_stats is None:
            await ctx.send(embed=discord.Embed(
                description=(
                    f"❌ <@{target_id}> doesn't have **{display_name}** "
                    "in their team or box. Use ;spawn first if they need one."
                ),
                colour=ERROR_COLOUR,
            ))
            return

        species_data = next(p for p in WILD_POKEMON if p["name"] == matched_species)
        embed = discord.Embed(
            title="Level set!",
            description=(
                f"<@{target_id}>'s **{display_name}** is now **Level {level}** "
                f"({new_stats['exp']:,} EXP)."
            ),
            colour=DEV_COLOUR,
        )
        embed.set_thumbnail(url=shiny_sprite_url(species_data) if is_shiny else sprite_url(species_data))
        await ctx.send(embed=embed)
