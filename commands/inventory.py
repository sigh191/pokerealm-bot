"""
The /inventory command - shows how many of each stackable item
(currently just Master Ball) a player owns.

This reads straight from the same "items" dict that every consumable
/shop purchase writes to (see database/player.py and
pokemon/economy.py) - it doesn't need to know item names in advance,
it just lists whatever is in the dict with a count greater than zero.
That means it doesn't need any changes when a new consumable item is
added to the shop later.
"""

import discord
from discord.ext import commands

from pokemon.economy import SHOP_ITEMS
from database.player import get_player_profile


def _item_display_name(item_key: str) -> str:
    """
    Look up the nice display name for an item key (e.g. "master_ball"
    -> "Master Ball"). Falls back to the raw key itself if it's ever
    not found in SHOP_ITEMS, so this never crashes on an odd item.
    """
    item = SHOP_ITEMS.get(item_key)
    return item["name"] if item else item_key


def setup(bot: commands.Bot):

    @bot.hybrid_command(
        name="inventory",
        description="Check how many of each item you own."
    )
    async def inventory(ctx: commands.Context):
        player = get_player_profile(ctx.author.id)
        owned_items = {key: count for key, count in player["items"].items() if count > 0}

        embed = discord.Embed(
            title=f"🎒 {ctx.author.display_name}'s Inventory",
            colour=discord.Colour.dark_gold()
        )

        if not owned_items:
            embed.description = (
                "You don't own any items yet - visit /shop or ;shop to buy some!"
            )
        else:
            for item_key, count in owned_items.items():
                embed.add_field(
                    name=_item_display_name(item_key),
                    value=f"x{count}",
                    inline=True
                )

        await ctx.send(embed=embed)
