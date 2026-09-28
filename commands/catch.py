"""
The catch command - the player's core "gameplay loop": run into a wild
Pokémon, then decide how to try to catch it.

There are two ways to throw at a wild Pokémon:
  - Poké Ball - always available. The normal rarity-based % roll.
  - Master Ball - only shows up as a button at all if the player owns
    at least one (bought from /shop, see commands/shop.py). Always
    succeeds, no roll, but is consumed the moment it's used.

Both buttons share the same "resolve the encounter" logic underneath
(award the Pokémon, credit coins, edit the message) - only how the
catch attempt itself is decided differs, which is why there's a single
shared _resolve() method instead of two separate copies of that logic.
"""

from discord.ext import commands
import discord

from pokemon.data import sprite_url
from pokemon.encounters import generate_wild_encounter, attempt_catch
from pokemon.growth import roll_catch_exp_reward
from database.player import (
    get_player_profile,
    add_caught_pokemon,
    add_coins,
    get_item_count,
    use_item,
    apply_lead_rewards,
)

# Discord embed colours used per rarity tier, just to make rarer
# Pokémon feel more exciting when they show up.
RARITY_COLOUR = {
    "common": discord.Colour.green(),
    "uncommon": discord.Colour.blue(),
    "rare": discord.Colour.orange(),
    "legendary": discord.Colour.purple(),
}

# How long (in seconds) the catch buttons stay active before the wild
# Pokémon is treated as having wandered off. Discord Buttons need an
# explicit timeout - without one, the default is 180 seconds.
ENCOUNTER_TIMEOUT_SECONDS = 60

# How long a player has to wait between uses of ;catch/ /catch, so they
# can't just spam it back-to-back. Enforced by discord.py's built-in
# @commands.cooldown below - see catch()'s decorator.
CATCH_COOLDOWN_SECONDS = 4


def _encounter_embed(pokemon: dict) -> discord.Embed:
    """
    Build the embed shown the moment a wild Pokémon appears, before any
    catch attempt.

    This used to also show "Spotted near {location}", but that location
    was just whatever the player last typed into /explore - /catch has
    no location of its own, so it was really just stale, unrelated
    leftover state rather than anything describing this encounter.
    """
    embed = discord.Embed(
        title=f"A wild {pokemon['name']} appeared!",
        description=f"Rarity: **{pokemon['rarity'].capitalize()}**",
        colour=RARITY_COLOUR[pokemon["rarity"]],
    )
    embed.set_image(url=sprite_url(pokemon))
    return embed


class CatchView(discord.ui.View):
    """
    The catch button(s) attached under a wild Pokémon encounter.

    Catching is a View (a message with clickable buttons) rather than
    something that resolves instantly, because - like throwing a Poké
    Ball in the real games - it should be a deliberate action the
    player takes, not something that just happens the moment the
    Pokémon appears.
    """

    def __init__(self, *, pokemon: dict, player_id: int, master_ball_count: int = 0):
        super().__init__(timeout=ENCOUNTER_TIMEOUT_SECONDS)
        self.pokemon = pokemon
        self.player_id = player_id
        self.resolved = False  # True once a button has been used (or the view has timed out)
        self.message = None  # set right after sending, so on_timeout() can edit it

        # The Master Ball button only exists at all if the player owns
        # at least one. It's added dynamically here (rather than with
        # the @discord.ui.button decorator used for the Poké Ball
        # button below, which always creates a fixed button) because
        # whether it should exist depends on data only known at the
        # moment the view is built - see commands/shop.py for the same
        # dynamic-button technique.
        if master_ball_count > 0:
            self.add_item(self._make_master_ball_button())

    def _make_master_ball_button(self) -> discord.ui.Button:
        button = discord.ui.Button(
            label="Master Ball",
            style=discord.ButtonStyle.primary,
            emoji="🟣",
        )

        async def callback(interaction: discord.Interaction):
            await self._resolve(interaction, want_master_ball=True)

        button.callback = callback
        return button

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Only the player who ran /catch may press either button -
        without this check, anyone in the channel could catch (or
        waste) someone else's encounter.
        """
        if interaction.user.id != self.player_id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="This isn't your encounter! Run /catch (or ;catch) to start your own.",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Poké Ball", style=discord.ButtonStyle.success, emoji="🔴")
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, want_master_ball=False)

    async def _resolve(self, interaction: discord.Interaction, *, want_master_ball: bool):
        """
        Shared logic for both buttons: figure out whether the catch is
        guaranteed (Master Ball) or a normal roll (Poké Ball), then
        run the attempt and update the message the same way either
        time.
        """
        guaranteed = False

        if want_master_ball:
            # Consume the Master Ball right here, atomically - if it
            # turns out they don't actually have one anymore (e.g. it
            # somehow got used a split second earlier), this fails
            # safely instead of granting a free guaranteed catch. The
            # encounter is left untouched so they can still use the
            # Poké Ball button instead.
            guaranteed = use_item(interaction.user.id, "master_ball", 1)
            if not guaranteed:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        description="You don't have a Master Ball anymore! Try the Poké Ball instead.",
                        colour=discord.Colour.red(),
                    ),
                    ephemeral=True
                )
                return

        self.resolved = True
        self.stop()  # this view no longer needs to listen for interactions
        for child in self.children:
            child.disabled = True  # one throw per encounter, for now

        attempt = attempt_catch(self.pokemon, guaranteed=guaranteed)
        colour = RARITY_COLOUR[self.pokemon["rarity"]]

        embed = discord.Embed(colour=colour)
        embed.set_image(url=sprite_url(self.pokemon))

        if attempt["guaranteed"]:
            roll_text = "🟣 Master Ball used - guaranteed catch, no roll needed!"
        else:
            # Shown on every normal attempt, caught or not - e.g.
            # "Catch rate: 80% | Roll: 42 (needed 80 or lower)" - so
            # the player can see how close/lucky the throw was, not
            # just a plain yes/no result.
            roll_text = (
                f"🎲 Catch rate: **{attempt['catch_rate']}%** "
                f"| Roll: **{attempt['roll']}** (needed {attempt['catch_rate']} or lower)"
            )

        if attempt["caught"]:
            result = add_caught_pokemon(interaction.user.id, self.pokemon["name"])
            embed.title = f"✅ Gotcha! {self.pokemon['name']} was caught!"

            # Re-check the player's profile here (rather than reusing
            # one fetched earlier) so an Amulet Coin bought moments ago
            # in /shop still gets picked up correctly.
            player = get_player_profile(interaction.user.id)
            coins_earned = attempt["base_coins"] * 2 if player["has_amulet_coin"] else attempt["base_coins"]
            new_balance = add_coins(interaction.user.id, coins_earned)

            coin_text = f"🪙 +{coins_earned:,} coins"
            if player["has_amulet_coin"]:
                coin_text += f" (base {attempt['base_coins']:,} x2 from your Amulet Coin)"
            coin_text += f" - balance: {new_balance:,}"

            # The player's LEAD Pokémon gets a small EXP reward for
            # every successful catch, scaled by the rarity of what was
            # just caught (see pokemon/growth.py's
            # CATCH_EXP_REWARD_RANGE) - not the Pokémon that was just
            # caught itself, the same "lead earns rewards" rule
            # /explore uses (see apply_lead_rewards()'s docstring).
            # Deliberately small next to a full quest's EXP reward, so
            # catching alone can't rush the level 1-100 grind.
            exp_gained = roll_catch_exp_reward(self.pokemon["rarity"])
            lead_result = apply_lead_rewards(interaction.user.id, exp_gained)

            exp_text = ""
            if lead_result is not None:
                exp_text = f"\n⭐ {lead_result['name']} (your lead) gained {exp_gained} EXP"
                if lead_result["leveled_up"]:
                    exp_text += f" - levelled up to **Level {lead_result['level']}**! 🎉"
                else:
                    exp_text += f" (now Level {lead_result['level']})"
                exp_text += "."

            if result["went_to"] == "team":
                embed.description = (
                    f"**{self.pokemon['name']}** ({self.pokemon['rarity']}) joined your team!\n\n"
                    f"{roll_text}\n{coin_text}{exp_text}"
                )
            else:
                embed.description = (
                    f"**{self.pokemon['name']}** ({self.pokemon['rarity']}) was caught, "
                    f"but your team is full (6/6) - it was sent to your box instead.\n\n"
                    f"{roll_text}\n{coin_text}{exp_text}"
                )
        else:
            # A Master Ball throw always sets attempt["caught"] = True,
            # so this branch is only ever reached from a Poké Ball miss.
            embed.title = f"💨 {self.pokemon['name']} broke free!"
            embed.description = (
                f"**{self.pokemon['name']}** ({self.pokemon['rarity']}) escaped. "
                f"Run /catch or ;catch again to look for another one!\n\n"
                f"{roll_text}"
            )

        # edit_message() updates the SAME message the button is on,
        # rather than sending a new one, and also submits the disabled
        # button state set above.
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        """Called automatically by discord.py once ENCOUNTER_TIMEOUT_SECONDS passes with no click."""
        if self.resolved:
            return  # a button was already pressed - nothing to do

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title=f"The wild {self.pokemon['name']} wandered off...",
            description="You didn't throw a Poké Ball in time. Run /catch or ;catch to try again!",
            colour=discord.Colour.dark_grey()
        )
        embed.set_image(url=sprite_url(self.pokemon))

        if self.message is not None:
            await self.message.edit(embed=embed, view=self)


def setup(bot: commands.Bot):

    @bot.hybrid_command(
        name="catch",
        description="Look for a wild Pokémon to catch."
    )
    # commands.cooldown(rate, per, type) - here, 1 use per
    # CATCH_COOLDOWN_SECONDS, tracked PER PLAYER (BucketType.user)
    # rather than one shared cooldown for the whole bot. discord.py
    # handles the timer itself; if someone runs the command again
    # before it's up, it raises CommandOnCooldown instead of running
    # the function body at all - handled in bot.py's on_command_error.
    @commands.cooldown(1, CATCH_COOLDOWN_SECONDS, commands.BucketType.user)
    async def catch(ctx: commands.Context):

        # Not using the returned profile for anything here anymore, but
        # this call still matters: it's what creates this player's row
        # in the database the very first time they're seen. Without it,
        # a brand new player's first-ever /catch would fail silently -
        # add_caught_pokemon() below only UPDATEs an existing row, it
        # doesn't create one.
        get_player_profile(ctx.author.id)
        pokemon = generate_wild_encounter()

        # Checked once here, up front, so the view knows whether to
        # show the Master Ball button at all - see CatchView.__init__.
        master_ball_count = get_item_count(ctx.author.id, "master_ball")

        embed = _encounter_embed(pokemon)
        view = CatchView(
            pokemon=pokemon,
            player_id=ctx.author.id,
            master_ball_count=master_ball_count,
        )

        # ctx.send() returns the actual Message it sent either way
        # (slash or prefix), so - unlike raw Interaction responses -
        # there's no extra step needed to fetch it for on_timeout() to
        # edit later.
        view.message = await ctx.send(embed=embed, view=view)
