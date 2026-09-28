"""
Tests for bot.py - specifically, that every command module actually
registers its command(s) on startup, and that the global
on_command_error() handler responds correctly to each kind of error it
promises to handle.

This automates the same kind of check the report's Section 5.2
describes doing with a "purpose-built stub of the relevant parts of
the Discord API" - proving each command registers correctly and that
error handling behaves as expected, WITHOUT needing a real Discord
connection or a real bot token.

How this loads bot.py without connecting to Discord
-----------------------------------------------------
bot.py's very last line is "bot.run(TOKEN)", which would try to
actually log into Discord (and fail, since there's no valid token in a
test environment) the moment the file is imported normally. Instead,
_load_bot_module() below reads bot.py's own source code as TEXT,
strips that one line off the end, and runs everything else - this is
the exact same technique used earlier in this project's development to
verify the on_command_error bug fix, just saved here as a real,
repeatable test instead of a one-off check.

It also points database/db.py at a temporary, throwaway database
(same idea as tests/test_db_migration.py) BEFORE loading bot.py, since
bot.py calls init_db() the moment it's imported - without this, every
test run would touch the real data/pokerealm.db file.
"""

import asyncio
import re
import types

import pytest
from discord.ext import commands

import database.db as db


def _load_bot_module():
    """Import bot.py's code with the final bot.run(TOKEN) line removed."""
    with open("bot.py", "r", encoding="utf-8") as f:
        source = f.read()

    source = re.sub(r"^bot\.run\(TOKEN\)\s*$", "", source, flags=re.MULTILINE)

    module = types.ModuleType("bot_under_test")
    module.__file__ = "bot.py"
    exec(compile(source, "bot.py", "exec"), module.__dict__)
    return module


@pytest.fixture
def loaded_bot(tmp_path, monkeypatch):
    """
    Load bot.py fresh for one test, with its database pointed at a
    throwaway temporary file rather than the real save data.
    """
    monkeypatch.setattr(db, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test_only.db"))
    return _load_bot_module()


class FakeContext:
    """
    A minimal stand-in for discord.ext.commands.Context - just enough
    for on_command_error() to work with (it only ever reads
    ctx.command and calls ctx.send()).

    Every call to send() is recorded in .sent_messages instead of
    actually contacting Discord, so a test can check exactly what the
    bot would have replied with.
    """

    def __init__(self, command=None):
        self.command = command
        self.sent_messages = []

    async def send(self, *args, **kwargs):
        self.sent_messages.append((args, kwargs))


def _run(coroutine):
    """Small helper so tests can call the async on_command_error() without needing pytest-asyncio."""
    return asyncio.run(coroutine)


# --- Command registration -------------------------------------------------

def test_every_command_module_registers_its_command(loaded_bot):
    # One name per hybrid command currently in the project - if a
    # command module is ever added and forgotten in bot.py's setup()
    # calls (see bot.py), or a typo breaks registration, this fails
    # immediately instead of only being noticed the next time someone
    # happens to try that exact command in Discord.
    expected_commands = {
        "ping", "explore", "catch", "promo", "team", "box",
        "shop", "coins", "givecoins", "spawn", "setlevel", "inventory", "move", "evolve", "help",
    }
    registered_commands = {command.name for command in loaded_bot.bot.commands}

    assert expected_commands.issubset(registered_commands)


def test_catch_command_has_the_configured_cooldown(loaded_bot):
    # Confirms the 4-second-per-user cooldown (see
    # claude/design-decisions.md) is actually wired onto the real
    # registered command object, not just present somewhere in the
    # source code.
    catch_command = loaded_bot.bot.get_command("catch")
    cooldown = catch_command._buckets._cooldown

    assert cooldown.rate == 1
    assert cooldown.per == 4
    assert catch_command._buckets._type == commands.BucketType.user


# --- on_command_error() ----------------------------------------------------

def test_command_not_found_is_ignored_silently(loaded_bot):
    # Typing something like ";not_a_real_command" should NOT crash and
    # should NOT send anything back - see bot.py's own comment on why
    # (there's nothing useful to say, and ctx.command is None here).
    ctx = FakeContext(command=None)
    error = commands.CommandNotFound("not_a_real_command")

    _run(loaded_bot.on_command_error(ctx, error))

    assert ctx.sent_messages == []


def test_missing_required_argument_sends_a_usage_hint(loaded_bot):
    move_command = loaded_bot.bot.get_command("move")
    ctx = FakeContext(command=move_command)

    class FakeParam:
        name = "pokemon_name"
        displayed_name = None

    error = commands.MissingRequiredArgument(FakeParam())

    _run(loaded_bot.on_command_error(ctx, error))

    assert len(ctx.sent_messages) == 1
    _, sent_kwargs = ctx.sent_messages[0]
    sent_text = sent_kwargs["embed"].description
    assert "pokemon_name" in sent_text
    assert "move" in sent_text  # the usage hint should name the command


def test_command_on_cooldown_sends_a_cooldown_embed(loaded_bot):
    catch_command = loaded_bot.bot.get_command("catch")
    ctx = FakeContext(command=catch_command)

    error = commands.CommandOnCooldown(commands.Cooldown(1, 4), 2.7, commands.BucketType.user)

    _run(loaded_bot.on_command_error(ctx, error))

    assert len(ctx.sent_messages) == 1
    _, sent_kwargs = ctx.sent_messages[0]
    embed = sent_kwargs["embed"]
    # error.retry_after (2.7) should be rounded UP to 3, per bot.py's
    # own comment on why math.ceil is used instead of a plain int().
    assert "3 second" in embed.description
