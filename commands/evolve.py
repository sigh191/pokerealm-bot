"""
The ;evolve command - evolve your LEAD Pokémon once it's met its
evolution requirement.

See pokemon/evolution.py for exactly how eligibility is decided (every
evolution in this project is either a level requirement or a friendship
requirement - see that file's module docstring for why). This file is
only responsible for checking the player's ACTUAL lead Pokémon against
that data and presenting the result - the same "engine decides the
rules, command module presents them" split used throughout the project.
"""

from discord.ext import commands
import discord

from database.player import get_player_profile, evolve_species
from pokemon.data import SHINY_NAME_PREFIX, split_stored_name, stored_name_sprite_url
from pokemon.evolution import get_evolution_info, is_eligible_for, evolution_requirement_text

# How long the "Evolve to X!" button stays clickable before the
# opportunity is treated as passed up - same idea, and the same default
# length, as commands/catch.py's ENCOUNTER_TIMEOUT_SECONDS.
EVOLVE_TIMEOUT_SECONDS = 60

EVOLVE_COLOUR = discord.Colour.gold()
ERROR_COLOUR = discord.Colour.red()


class EvolveView(discord.ui.View):
    """
    One "Evolve to X!" button per possible evolution target. Almost
    every species only has one target, so this is almost always a
    single button - Eevee (Vaporeon/Jolteon/Flareon) is the only
    species in this project with more than one, so a button is added
    per target dynamically here rather than the fixed
    @discord.ui.button decorator (same dynamic-button technique as
    commands/catch.py's Master Ball button).
    """

    def __init__(self, *, player_id: int, from_species: str, targets: list[str]):
        super().__init__(timeout=EVOLVE_TIMEOUT_SECONDS)
        self.player_id = player_id
        self.from_species = from_species
        self.resolved = False
        self.message: discord.Message | None = None

        for target in targets:
            self.add_item(self._make_evolve_button(target))

    def _make_evolve_button(self, target: str) -> discord.ui.Button:
        button = discord.ui.Button(
            label=f"Evolve to {target}!",
            style=discord.ButtonStyle.success,
            emoji="✨",
        )

        async def callback(interaction: discord.Interaction):
            await self._resolve(interaction, target)

        button.callback = callback
        return button

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only the player who ran ;evolve may press a button - without
        # this, anyone in the channel could evolve someone else's team.
        if interaction.user.id != self.player_id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="This isn't your evolution to decide! Run /evolve or ;evolve yourself.",
                    colour=ERROR_COLOUR,
                ),
                ephemeral=True,
            )
            return False
        return True

    async def _resolve(self, interaction: discord.Interaction, target: str):
        self.resolved = True
        self.stop()
        for child in self.children:
            child.disabled = True

        result = evolve_species(interaction.user.id, self.from_species, target)

        if result["evolved_count"] > 1:
            subject = f"All {result['evolved_count']} of your {self.from_species}"
            verb = "evolved"
        else:
            subject = f"Your {self.from_species}"
            verb = "evolved"

        embed = discord.Embed(
            title=f"🎉 {subject} {verb} into {target}!",
            colour=EVOLVE_COLOUR,
        )
        # target is already the fully-stored name (e.g. "Shiny
        # Charmeleon" for a shiny lead - see the evolve() command
        # below, which builds this list of stored target names before
        # constructing this view), so stored_name_sprite_url() -
        # rather than sprite_url() - is what correctly resolves it to
        # the shiny palette when needed.
        embed.set_image(url=stored_name_sprite_url(target))

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.resolved:
            return

        for child in self.children:
            child.disabled = True

        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


def setup(bot: commands.Bot):

    @bot.hybrid_command(
        name="evolve",
        description="Evolve your lead Pokémon, if it's ready.",
    )
    async def evolve(ctx: commands.Context):
        player = get_player_profile(ctx.author.id)

        if not player["team"]:
            await ctx.send(embed=discord.Embed(
                description="Your team is empty - there's nothing to evolve yet.",
                colour=ERROR_COLOUR,
            ))
            return

        lead = player["team"][0]
        species_name = lead["name"]
        # Shown on every branch below (even "no evolution"/"not ready
        # yet") so the embed always has a face to it - stored_name_
        # sprite_url() also handles a "Shiny <name>" lead correctly.
        lead_sprite = stored_name_sprite_url(species_name)

        # EVOLUTION_DATA is keyed by real species names only ("Charmander",
        # never "Shiny Charmander") - species_name is the RAW stored name,
        # which for a shiny lead has the "Shiny " prefix still on it, so it
        # has to be split off before looking anything up here. Previously
        # this wasn't done, which meant a shiny lead's evolution entry was
        # never found at all (see claude/design-decisions.md) - every shiny
        # Pokémon looked permanently fully-evolved, whether it actually was
        # or not.
        base_species, is_shiny = split_stored_name(species_name)

        evolution_info = get_evolution_info(base_species)
        if evolution_info is None:
            embed = discord.Embed(
                description=f"**{species_name}** doesn't have any further evolution.",
                colour=EVOLVE_COLOUR,
            )
            if lead_sprite is not None:
                embed.set_thumbnail(url=lead_sprite)
            await ctx.send(embed=embed)
            return

        if not is_eligible_for(evolution_info, lead):
            requirement = evolution_requirement_text(evolution_info)
            embed = discord.Embed(
                description=(
                    f"**{species_name}** (Level {lead['level']}) isn't ready to evolve yet - "
                    f"it needs to {requirement}."
                ),
                colour=EVOLVE_COLOUR,
            )
            if lead_sprite is not None:
                embed.set_thumbnail(url=lead_sprite)
            await ctx.send(embed=embed)
            return

        # evolves_to always lists real (never shiny-prefixed) species
        # names, since EVOLUTION_DATA itself only ever deals in real
        # species. A shiny lead has to evolve into a SHINY target - the
        # real games never turn a shiny Pokémon back into a normal one -
        # so the "Shiny " prefix is re-applied here to whichever targets
        # get shown, stored, and evolved into below.
        targets = evolution_info["evolves_to"]
        stored_targets = [
            f"{SHINY_NAME_PREFIX}{target}" if is_shiny else target
            for target in targets
        ]

        embed = discord.Embed(
            title="✨ Your Pokémon is ready to evolve!",
            colour=EVOLVE_COLOUR,
        )

        if len(stored_targets) == 1:
            stored_target = stored_targets[0]
            embed.description = f"Your **{species_name}** is ready to evolve into **{stored_target}**!"
            embed.set_image(url=stored_name_sprite_url(stored_target))
        else:
            # Eevee's 3-way branch - there's no single "the" evolution
            # to show a picture of, so the embed shows Eevee's own
            # sprite instead and lets each button speak for itself.
            # stored_name_sprite_url() (not sprite_url()) is required
            # here too - species_name may be "Shiny Eevee", which
            # sprite_url() would otherwise treat as one unrecognised
            # slug rather than the shiny sprite of "Eevee".
            options = ", ".join(stored_targets)
            embed.description = (
                f"Your **{species_name}** is ready to evolve! Choose one: {options}."
            )
            embed.set_image(url=stored_name_sprite_url(species_name))

        view = EvolveView(player_id=ctx.author.id, from_species=species_name, targets=stored_targets)
        view.message = await ctx.send(embed=embed, view=view)
