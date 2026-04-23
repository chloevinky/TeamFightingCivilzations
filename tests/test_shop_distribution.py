"""Statistical sanity tests for the shop loop prototype.

Runs with the standard-library unittest:
    python -m unittest tests.test_shop_distribution
"""

from __future__ import annotations

import random
import unittest
from collections import Counter

from src import config
from src.game_state import GameState
from src.offerings import Unit
from src.shop import Shop


def _fresh_shop(seed: int = 0) -> Shop:
    state = GameState()
    shop = Shop(state, rng=random.Random(seed))
    shop.refresh(is_free=True)
    return shop


class ShopFloorTests(unittest.TestCase):
    def test_shop_size_is_exactly_eight(self):
        for seed in range(50):
            shop = _fresh_shop(seed)
            self.assertEqual(len(shop.slots), config.SHOP_SIZE)

    def test_category_floors_respected(self):
        for seed in range(50):
            shop = _fresh_shop(seed)
            cats = Counter(s.category for s in shop.slots)
            self.assertGreaterEqual(cats["unit"], config.UNIT_FLOOR, f"seed {seed}")
            self.assertGreaterEqual(cats["building"], config.BUILDING_FLOOR, f"seed {seed}")
            self.assertGreaterEqual(cats["wonder"] + cats["event"], config.SPECIAL_FLOOR, f"seed {seed}")


class PathWeightingTests(unittest.TestCase):
    def test_melee_investment_biases_unit_draws(self):
        """With heavy Melee investment, Melee units should dominate unit slots."""
        rng = random.Random(42)
        state = GameState()
        state.path_investment["Melee"] = 5
        shop = Shop(state, rng=rng)

        melee = 0
        total = 0
        for _ in range(200):
            shop.refresh(is_free=True)
            for s in shop.slots:
                if isinstance(s.offering, Unit):
                    total += 1
                    if s.offering.path == "Melee":
                        melee += 1
        self.assertGreater(melee / total, 0.45,
                           f"expected Melee-biased draws; got {melee}/{total}")


class PityTimerTests(unittest.TestCase):
    def test_pity_guarantees_deep_path_unit_after_threshold(self):
        """Force the shop to have no Cavalry unit and confirm pity fires."""
        state = GameState()
        state.path_investment["Cavalry"] = 3
        # Pre-seed pity counter at threshold so next refresh must include Cavalry.
        state.pity_counter = config.PITY_TIMER_THRESHOLD
        rng = random.Random(7)
        shop = Shop(state, rng=rng)
        shop.refresh(is_free=True)

        has_cavalry = any(
            isinstance(s.offering, Unit) and s.offering.path == "Cavalry"
            for s in shop.slots
        )
        self.assertTrue(has_cavalry, "pity timer should force a Cavalry offering")

    def test_pity_resets_when_deep_path_offered(self):
        state = GameState()
        state.path_investment["Melee"] = 2
        rng = random.Random(1)
        shop = Shop(state, rng=rng)
        # Starting army has Warrior (Melee) and Melee investment biases toward Melee
        # units, so the initial refresh almost certainly contains a Melee unit
        # and resets the pity counter to 0.
        shop.refresh(is_free=True)
        has_melee = any(
            isinstance(s.offering, Unit) and s.offering.path == "Melee"
            for s in shop.slots
        )
        if has_melee:
            self.assertEqual(state.pity_counter, 0)


class PurchaseAndTierUpTests(unittest.TestCase):
    def test_buy_deducts_gold_and_adds_unit(self):
        state = GameState()
        rng = random.Random(3)
        shop = Shop(state, rng=rng)
        shop.refresh(is_free=True)

        # find the first unit slot
        for i, s in enumerate(shop.slots):
            if isinstance(s.offering, Unit) and state.gold >= s.price:
                before_gold = state.gold
                before_army = len(state.army)
                msg = shop.buy(i)
                self.assertIn("Bought", msg)
                self.assertEqual(state.gold, before_gold - s.price)
                self.assertGreaterEqual(len(state.army), before_army)  # tier-up may reduce
                return
        self.fail("no affordable unit in the generated shop")

    def test_three_warriors_combine_into_super_warrior(self):
        state = GameState()
        # Player already owns 2 warriors; adding one more should tier-up.
        from src.offerings import UNITS  # local import to stay close to the call
        warrior = next(u for u in UNITS if u.name == "Warrior")
        super_warrior = next(u for u in UNITS if u.name == "Super Warrior")

        logs = state.add_unit(warrior)
        names = Counter(u.name for u in state.army)
        self.assertEqual(names.get("Warrior", 0), 0)
        self.assertEqual(names.get(super_warrior.name, 0), 1)
        self.assertTrue(any("Tier-up" in line for line in logs))


class RerollCostTests(unittest.TestCase):
    def test_reroll_cost_escalates_and_caps(self):
        state = GameState()
        for expected in config.REROLL_COSTS:
            self.assertEqual(state.reroll_cost(), expected)
            state.rerolls_this_turn += 1
        # caps at the last value
        self.assertEqual(state.reroll_cost(), config.REROLL_COSTS[-1])


class LockTests(unittest.TestCase):
    def test_locked_offering_survives_reroll(self):
        state = GameState()
        rng = random.Random(9)
        shop = Shop(state, rng=rng)
        shop.refresh(is_free=True)
        locked_offering = shop.slots[0].offering
        self.assertIn("Locked", shop.lock(0))
        for _ in range(5):
            shop.refresh(is_free=False)
            self.assertEqual(shop.slots[0].offering, locked_offering)
            self.assertTrue(shop.slots[0].locked)


if __name__ == "__main__":
    unittest.main()
