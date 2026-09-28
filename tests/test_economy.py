"""
Tests for pokemon/economy.py - coin rewards and the shop's item list.
"""

from pokemon.economy import (
    COIN_REWARD_RANGE,
    QUEST_COIN_REWARD_RANGE,
    SHOP_ITEMS,
    roll_coin_reward,
    roll_quest_coin_reward,
)


def test_roll_coin_reward_stays_within_its_declared_range_for_every_rarity():
    for rarity, (low, high) in COIN_REWARD_RANGE.items():
        for _ in range(200):
            assert low <= roll_coin_reward(rarity) <= high


def test_roll_quest_coin_reward_stays_within_its_declared_range():
    low, high = QUEST_COIN_REWARD_RANGE
    for _ in range(200):
        assert low <= roll_quest_coin_reward() <= high


def test_every_shop_item_has_the_fields_commands_shop_py_relies_on():
    # commands/shop.py builds its /shop embed and "Buy" buttons
    # straight from this dict (see economy.py's own comment on this),
    # so a missing field here wouldn't be caught by Python at all until
    # someone actually ran /shop and hit a KeyError - this catches that
    # kind of mistake immediately instead.
    required_fields = {"name", "price", "description", "kind"}

    for item_id, item in SHOP_ITEMS.items():
        missing = required_fields - item.keys()
        assert not missing, f"{item_id} is missing: {missing}"


def test_every_shop_item_has_a_sensible_price_and_a_valid_kind():
    for item_id, item in SHOP_ITEMS.items():
        assert isinstance(item["price"], int) and item["price"] > 0, item_id
        # commands/shop.py only knows how to handle these two kinds
        # (see economy.py's comment above SHOP_ITEMS) - any other value
        # here would silently fail to do anything when bought.
        assert item["kind"] in ("upgrade", "consumable"), item_id
