"""
The shop - lets a player spend coins on upgrades and items.

The shop is built data-driven off pokemon.economy.SHOP_ITEMS rather
than hard-coding each item's behaviour here - adding a third item
later mostly just means adding another entry to that dict. The one
thing every item needs to say about itself is its "kind":
  - "upgrade"    a one-time permanent purchase (e.g. Amulet Coin) -
                 flips a specific flag on the player's row.
  - "consumable" stacks in the player's inventory and gets used up
                 elsewhere (e.g. Master Ball, used in /catch) - just
                 adds one to the player's "items" dict.
Only the "upgrade" branch below needs to know about a *specific* item
(amulet_coin) - the "consumable" branch is fully generic and needs no
changes at all when a new stackable item is added.

/coins is also defined here (rather than its own file) since it's a
tiny, closely-related command - there was otherwise no way for a
player to check their balance outside of a /catch result.
"""

import discord
from discord.ext import commands

from pokemon.economy import SHOP_ITEMS
from database.player import get_player_profile, spend_coins, set_amulet_coin, add_item

SHOP_TIMEOUT_SECONDS = 60


class ShopView(discord.ui.View):
    """One "Buy" button per item in SHOP_ITEMS, built dynamically."""

    def __init__(self, *, player_id: int):
        super().__init__(timeout=SHOP_TIMEOUT_SECONDS)
        self.player_id = player_id
        self.message = None

        for item_key, item in SHOP_ITEMS.items():
            self.add_item(self._make_buy_button(item_key, item))

    def _make_buy_button(self, item_key: str, item: dict) -> discord.ui.Button:
        # Built by hand (rather than the @discord.ui.button decorator
        # used in catch.py) because the NUMBER of buttons depends on
        # how many items are in SHOP_ITEMS - the decorator only works
        # for a fixed button known when the class is written.
        button = discord.ui.Button(
            label=f"Buy {item['name']} - {item['price']:,} coins",
            style=discord.ButtonStyle.success,
            emoji="🛒",
        )

        async def callback(interaction: discord.Interaction):
            await self._handle_purchase(interaction, item_key, item)

        button.callback = callback
        return button

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player_id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="This isn't your shop menu! Run /shop or ;shop to open your own.",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return False
        return True

    async def _handle_purchase(self, interaction: discord.Interaction, item_key: str, item: dict):
        player = get_player_profile(interaction.user.id)

        # Only "upgrade" items can be "already owned" - consumables
        # can always be bought again to stack up more of them.
        if item["kind"] == "upgrade" and item_key == "amulet_coin" and player["has_amulet_coin"]:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="You already own the Amulet Coin!",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return

        # spend_coins() checks the balance AND deducts it in one step,
        # so there's no way for two quick clicks to overspend.
        if not spend_coins(interaction.user.id, item["price"]):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=(
                        f"You don't have enough coins for that - {item['name']} costs "
                        f"{item['price']:,}, and you only have {player['coins']:,}."
                    ),
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return

        if item["kind"] == "upgrade":
            # Still specific to amulet_coin for now - a future upgrade
            # would need its own flag (and its own line here), the
            # same way this one does.
            if item_key == "amulet_coin":
                set_amulet_coin(interaction.user.id, owned=True)

            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"✅ Purchased **{item['name']}** for {item['price']:,} coins!",
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
        else:
            # Generic path for ANY consumable item - no item_key check
            # needed, which is what makes adding future stackable
            # items to SHOP_ITEMS "free" (no code changes here).
            new_count = add_item(interaction.user.id, item_key, 1)
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=(
                        f"✅ Purchased **{item['name']}** for {item['price']:,} coins! "
                        f"You now own {new_count}. Check /inventory or ;inventory anytime."
                    ),
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            await self.message.edit(view=self)


def _shop_embed(player: dict) -> discord.Embed:
    embed = discord.Embed(
        title="🛍️ PokeRealm Shop",
        description=f"Your balance: **{player['coins']:,}** 🪙",
        colour=discord.Colour.gold()
    )

    for item_key, item in SHOP_ITEMS.items():
        value = item["description"]

        if item["kind"] == "upgrade":
            if item_key == "amulet_coin" and player["has_amulet_coin"]:
                value += "\n✅ *You already own this.*"
        else:
            # Consumables show how many the player currently has
            # instead - there's no "already own it" state for these.
            owned_count = player["items"].get(item_key, 0)
            value += f"\n🎒 You own: **{owned_count}**"

        embed.add_field(
            name=f"{item['name']} - {item['price']:,} coins",
            value=value,
            inline=False
        )

    return embed


def setup(bot: commands.Bot):

    @bot.hybrid_command(
        name="shop",
        description="Browse the shop and spend your coins."
    )
    async def shop(ctx: commands.Context):
        player = get_player_profile(ctx.author.id)
        embed = _shop_embed(player)
        view = ShopView(player_id=ctx.author.id)

        view.message = await ctx.send(embed=embed, view=view)

    @bot.hybrid_command(
        name="coins",
        description="Check your current coin balance."
    )
    async def coins(ctx: commands.Context):
        player = get_player_profile(ctx.author.id)
        embed = discord.Embed(
            description=f"🪙 {ctx.author.display_name}, you have **{player['coins']:,}** coins.",
            colour=discord.Colour.gold(),
        )
        await ctx.send(embed=embed)
