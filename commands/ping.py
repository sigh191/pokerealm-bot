import discord
from discord.ext import commands


def setup(bot: commands.Bot):

    @bot.hybrid_command(
        name="ping",
        description="Check if PokeRealm is online."
    )
    async def ping(ctx: commands.Context):
        # Every command's output is an embed (rather than a plain
        # text message) for a consistent look across the whole bot -
        # even one this simple, with no Pokémon to show a sprite of.
        embed = discord.Embed(
            description="🏓 PokeRealm is online! ☁️",
            colour=discord.Colour.green(),
        )
        # ctx.send() works the same way whether this was triggered by
        # /ping (a slash command) or ;ping (a prefix command) - that's
        # the whole point of hybrid commands.
        await ctx.send(embed=embed)
