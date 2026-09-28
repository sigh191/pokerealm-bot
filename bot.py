import math
import os
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Import command files
from commands import ping, explore, catch, promo, collection, shop, dev, inventory, move, evolve
from database.db import init_db

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# Optional: your test server's ID, for fast command syncing while
# developing (see the comment above sync below for why this matters).
# Set TEST_GUILD_ID=your_server_id in .env. If it's not set, the bot
# still works, it just falls back to the slow, global sync.
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")
TEST_GUILD = discord.Object(id=int(TEST_GUILD_ID)) if TEST_GUILD_ID else None

# Create the database file and the players table if they don't exist
# yet. This only needs to run once per bot startup, not per command.
init_db()

intents = discord.Intents.default()

# Needed to read message text - both for prefix commands (;catch) and
# so discord.py can parse arguments typed after them (e.g. the location
# in ";explore Viridian Forest"). This ALSO has to be turned on in the
# Discord Developer Portal, under your application -> Bot -> "Message
# Content Intent" - without doing that, this line alone isn't enough
# and prefix commands will silently never trigger.
intents.message_content = True

# commands.Bot (rather than a plain discord.Client) is what adds
# support for "hybrid commands" - a single command definition that
# discord.py automatically exposes BOTH as a slash command (/catch)
# and as a classic prefix command (;catch), so every command in this
# project only has to be written once. It still does everything
# discord.Client did (it IS one, underneath), including having its own
# bot.tree for slash-command syncing.
bot = commands.Bot(command_prefix=";", intents=intents, case_insensitive=True)

# Each command module registers its own hybrid command(s) onto the
# bot. This only needs to happen once, so it happens here at startup
# rather than inside on_ready - on_ready can technically fire more
# than once (e.g. after a reconnect), and registering the same command
# twice would raise an error.
ping.setup(bot)
explore.setup(bot)
catch.setup(bot)
promo.setup(bot)
collection.setup(bot)
shop.setup(bot)
dev.setup(bot)
inventory.setup(bot)
move.setup(bot)
evolve.setup(bot)


@bot.event
async def on_ready():

    if TEST_GUILD:
        # Slash commands are normally registered globally (usable in
        # every server the bot is in), but Discord can take up to an
        # hour to push a global change out to clients. copy_global_to()
        # takes a copy of the commands we just registered and syncs
        # THAT copy to one specific server only, which Discord applies
        # straight away - much better while actively developing.
        bot.tree.copy_global_to(guild=TEST_GUILD)
        synced = await bot.tree.sync(guild=TEST_GUILD)
        print(f"Synced {len(synced)} slash commands instantly to test server {TEST_GUILD_ID}")
    else:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands globally (can take up to an hour to appear)")

    print(f"Logged in as {bot.user}")
    print("Every command also works with the ';' prefix, e.g. ';catch' or ';explore Viridian Forest'.")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    """
    Global error handler - every command in the bot funnels errors
    through here (both the ';prefix' and '/slash' forms, since hybrid
    commands share the same underlying dispatch).

    WITHOUT this, discord.py's default behaviour for something as
    simple as forgetting an argument (e.g. typing just ";move" with
    nothing after it) is to print a big Python traceback in the
    terminal and say NOTHING back in Discord - so from the player's
    side, the command just looks like it silently did nothing. This
    catches the common "typed the command wrong" cases and replies
    with a helpful usage hint instead. Anything else still gets
    printed to the terminal exactly like before, so real bugs in the
    code aren't accidentally hidden by this handler.
    """
    if isinstance(error, commands.CommandNotFound):
        # Someone typed something starting with ';' that isn't one of
        # our commands at all - ctx.command is None here (there's no
        # matching command object to attach), so this has to be
        # checked and returned BEFORE anything below touches
        # ctx.command - nothing useful to say back anyway, and not
        # worth logging either.
        return

    # ctx.command.qualified_name / ctx.command.signature are built into
    # discord.py - signature auto-generates something like
    # "<pokemon_name> <position>" from the command's own parameters, so
    # this doesn't need to be hand-written per command. Safe to access
    # ctx.command here since CommandNotFound (the one case where it's
    # None) already returned above.
    usage = f"`;{ctx.command.qualified_name} {ctx.command.signature}`".strip()

    if isinstance(error, commands.CommandOnCooldown):
        # Raised automatically by discord.py for any command decorated
        # with @commands.cooldown (see commands/catch.py's ;catch) when
        # it's used again before its cooldown is up. error.retry_after
        # is a float number of seconds left (e.g. 2.73) - rounded UP
        # with math.ceil rather than down, so the player is never told
        # a time that's already passed by the time they read it.
        seconds_left = math.ceil(error.retry_after)
        plural = "" if seconds_left == 1 else "s"
        embed = discord.Embed(
            title="⏳ Cooldown",
            description=f"Try again in {seconds_left} second{plural}!",
            colour=discord.Colour.orange(),
        )
        await ctx.send(embed=embed)
        return

    if isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            description=f"❌ Missing `{error.param.name}`.\nUsage: {usage}",
            colour=discord.Colour.red(),
        )
        await ctx.send(embed=embed)
        return

    if isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            description=f"❌ That doesn't look right - {error}\nUsage: {usage}",
            colour=discord.Colour.red(),
        )
        await ctx.send(embed=embed)
        return

    # Anything else (a real bug, not a usage mistake) is still printed
    # to the terminal, the same way discord.py would print it by
    # default, so it's still visible while developing.
    print(f"Unhandled error in command '{ctx.command}':")
    traceback.print_exception(type(error), error, error.__traceback__)


bot.run(TOKEN)
