"""Tunable constants for the shop loop prototype."""

STARTING_AP = 3
STARTING_GOLD = 100
STARTING_ARMY_CAP = 5
PITY_TIMER_THRESHOLD = 5
LOCK_COST = 5
REROLL_COSTS = [2, 4, 8, 16, 32]
ERA_PRICE_MULTIPLIER = 1.5

SHOP_SIZE = 8
UNIT_FLOOR = 3
BUILDING_FLOOR = 2
SPECIAL_FLOOR = 1
FLEX_SLOTS = SHOP_SIZE - UNIT_FLOOR - BUILDING_FLOOR - SPECIAL_FLOOR

PATH_WEIGHT_PER_LEVEL = 1.5
BASE_PATH_WEIGHT = 1.0
MUSTER_AP_COST = 1
PATH_INVEST_AP_COST = 1

TIER_UP_COUNT = 3

AP_CURVE = [
    (1, 10, 3),
    (11, 25, 4),
    (26, 50, 5),
    (51, 75, 6),
    (76, 100, 7),
]
AP_CAP = 8


def ap_for_turn(turn: int) -> int:
    for low, high, ap in AP_CURVE:
        if low <= turn <= high:
            return ap
    return AP_CAP
