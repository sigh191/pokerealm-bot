"""
The game's coin economy: how many coins a catch pays out, and what's
currently available to spend those coins on in the shop.

Keeping all of this in one file (rather than scattering price numbers
across commands/catch.py and commands/shop.py) makes it easy to
rebalance the whole economy by editing values in a single place.
"""

import random

# How many coins a SUCCESSFUL catch pays out, per rarity tier. Each
# tier has a (low, high) range - the actual payout is a random number
# picked from that range every time, so it's not the exact same amount
# for every Pikachu you catch. Rarer tiers pay out more on average,
# which rewards seeking out rarer encounters, but the ranges overlap a
# little on purpose (a lucky common catch can occasionally beat an
# unlucky rare one) - that little bit of randomness is what makes
# catching feel like "a game of chance" the same way the catch % does.
#
# These numbers are easy to tune later - nothing else in the codebase
# needs to change if they're adjusted.
COIN_REWARD_RANGE = {
    "common": (2, 150),
    "uncommon": (100, 500),
    "rare": (400, 1500),
    "legendary": (1500, 5000),
}


def roll_coin_reward(rarity: str) -> int:
    """Pick a random coin payout for a successful catch of the given rarity."""
    low, high = COIN_REWARD_RANGE[rarity]
    return random.randint(low, high)


# How many coins finishing a /explore quest chain pays out. Kept as its
# own separate range rather than reusing COIN_REWARD_RANGE above - a
# completed quest isn't tied to any particular Pokémon's rarity (it's
# about the LOCATION, not what you catch there), so it wouldn't make
# sense to ask "which rarity tier is this quest?" the way a catch does.
# A single flat range keeps quest rewards a modest, steady bonus on top
# of catching, rather than a second, competing way to earn big coins.
QUEST_COIN_REWARD_RANGE = (50, 300)


def roll_quest_coin_reward() -> int:
    """
    Pick a random coin payout for finishing a quest chain
    (commands/explore.py). Deliberately NOT doubled by the Amulet Coin
    upgrade - that item's own description in SHOP_ITEMS says it doubles
    coins "from every catch", so keeping it catch-only avoids the
    upgrade quietly doing more than what it's advertised to do.
    """
    low, high = QUEST_COIN_REWARD_RANGE
    return random.randint(low, high)


# --- Shop --------------------------------------------------------------
# Every item the shop currently sells. Each entry needs:
#   - "name"        shown to the player
#   - "price"       in coins
#   - "description" shown in /shop
#   - "kind"        either "upgrade" (bought once, permanent - like
#                   Amulet Coin) or "consumable" (stacks in the
#                   player's inventory and gets used up - like Master
#                   Ball). commands/shop.py reads "kind" to decide HOW
#                   to apply a purchase, so it doesn't need a special
#                   case for every individual item.
#
# The /shop and /buy commands (see commands/shop.py) are both built to
# read straight from this dict, so adding a third item later is mostly
# just adding another entry here.
#
# Amulet Coin is a permanent account upgrade - buying it flips a
# single has_amulet_coin flag on the player's row (see
# database/player.py), which then doubles every future coin payout
# from catching.
#
# Master Ball is a stackable, consumable item - buying it adds one to
# the player's "items" dict (also in database/player.py), and using it
# in /catch (see commands/catch.py) removes one and guarantees that
# catch succeeds, no roll needed. At 2,500 coins, and an average
# successful catch paying out somewhere around 250 coins (a weighted
# mix of the COIN_REWARD_RANGE tiers above), that's roughly 10
# successful catches' worth of saving up - an early-game item you can
# realistically afford after a short grinding session, not a
# far-off end-game goal.
SHOP_ITEMS = {
    "amulet_coin": {
        "name": "Amulet Coin",
        "price": 5000,
        "description": "A permanent upgrade that **doubles** the coins you earn from every catch, forever.",
        "kind": "upgrade",
    },
    "master_ball": {
        "name": "Master Ball",
        "price": 2500,
        "description": "Guarantees your next catch - no roll needed. Used up the moment you throw it.",
        "kind": "consumable",
    },
}
