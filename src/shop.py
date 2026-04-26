"""Shop generation, reroll, lock, and purchase logic."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from . import config, paths
from .game_state import GameState
from .offerings import (
    BUILDINGS,
    EVENTS,
    Era,
    Offering,
    Unit,
    UNITS,
    WONDERS,
    price_for,
)


@dataclass
class Slot:
    offering: Offering
    price: int
    locked: bool = False

    @property
    def category(self) -> str:
        return self.offering.category


class Shop:
    def __init__(self, state: GameState, rng: Optional[random.Random] = None):
        self.state = state
        self.rng = rng or random.Random()
        self.slots: list[Slot] = []

    # --- generation ---

    def refresh(self, *, is_free: bool = True) -> None:
        """Rebuild the shop, preserving the locked offering if one exists."""
        locked_offering: Optional[Offering] = None
        if self.state.locked_slot is not None and 0 <= self.state.locked_slot < len(self.slots):
            locked_offering = self.slots[self.state.locked_slot].offering

        pool_offerings = self._generate_slots(locked_offering)
        self.slots = [
            Slot(off, price_for(off, self.state.era)) for off in pool_offerings
        ]

        # re-anchor the lock on the first matching slot
        if locked_offering is not None:
            for i, s in enumerate(self.slots):
                if s.offering is locked_offering:
                    s.locked = True
                    self.state.locked_slot = i
                    break
            else:
                self.state.locked_slot = None

        if not is_free:
            self.state.rerolls_this_turn += 1

        self._update_pity_on_refresh()

    def _generate_slots(self, locked: Optional[Offering]) -> list[Offering]:
        rng = self.rng
        units_pool = self._era_filter(UNITS)
        buildings_pool = self._era_filter(BUILDINGS)
        wonders_pool = [w for w in WONDERS if w.name not in self.state.wonders
                        and w.era <= self.state.era]
        events_pool = self._era_filter(EVENTS)

        chosen: list[Offering] = []
        if locked is not None:
            chosen.append(locked)

        # Unit floor
        needed_units = max(0, config.UNIT_FLOOR - sum(1 for o in chosen if o.category == "unit"))
        chosen.extend(self._weighted_sample_units(units_pool, needed_units, chosen))

        # Pity guarantee: if pity counter reached threshold, ensure a unit from
        # the deepest-invested path is present. Swap one non-locked unit slot.
        deepest = self.state.deepest_path()
        pity_threshold = max(
            1,
            config.PITY_TIMER_THRESHOLD - getattr(self.state, "pity_reduction", 0),
        )
        if (
            self.state.pity_counter >= pity_threshold
            and deepest is not None
            and not any(
                isinstance(o, Unit) and o.path == deepest for o in chosen
            )
        ):
            candidates = [u for u in units_pool if u.path == deepest]
            if candidates:
                pick = rng.choice(candidates)
                # find a non-locked unit slot to replace
                for i, o in enumerate(chosen):
                    if o is locked:
                        continue
                    if isinstance(o, Unit):
                        chosen[i] = pick
                        break
                else:
                    chosen.append(pick)

        # Building floor
        needed_buildings = max(
            0, config.BUILDING_FLOOR - sum(1 for o in chosen if o.category == "building")
        )
        chosen.extend(
            rng.sample(buildings_pool, k=min(needed_buildings, len(buildings_pool)))
        )

        # Special floor (wonder preferred if available, else event)
        has_special = any(o.category in ("wonder", "event") for o in chosen)
        if not has_special:
            special_pool: list[Offering] = []
            if wonders_pool:
                special_pool.extend(wonders_pool)
            special_pool.extend(events_pool)
            if special_pool:
                chosen.append(rng.choice(special_pool))

        # Flex slots (Grand Bazaar wonder grants +1 shop slot)
        target_size = config.SHOP_SIZE + getattr(self.state, "extra_shop_slot", 0)
        while len(chosen) < target_size:
            chosen.append(self._draw_flex(units_pool, buildings_pool, events_pool, chosen))

        # Trim in case we overshot via the pity insertion
        if len(chosen) > target_size:
            # never drop the locked one
            trimmed: list[Offering] = []
            if locked is not None:
                trimmed.append(locked)
            for o in chosen:
                if o is locked:
                    continue
                trimmed.append(o)
                if len(trimmed) == target_size:
                    break
            chosen = trimmed

        rng.shuffle(chosen)
        # But keep the locked slot pinned to index 0 for stability of display
        if locked is not None:
            chosen.remove(locked)
            chosen.insert(0, locked)
        return chosen

    def _era_filter(self, pool):
        return [o for o in pool if o.era <= self.state.era]

    def _weighted_sample_units(
        self,
        pool: list[Unit],
        k: int,
        already: list[Offering],
    ) -> list[Unit]:
        picks: list[Unit] = []
        rng = self.rng
        remaining = list(pool)
        while len(picks) < k and remaining:
            weights = [paths.unit_weight(u, self.state.path_investment) for u in remaining]
            total = sum(weights)
            if total <= 0:
                pick = rng.choice(remaining)
            else:
                r = rng.random() * total
                acc = 0.0
                pick = remaining[-1]
                for u, w in zip(remaining, weights):
                    acc += w
                    if r <= acc:
                        pick = u
                        break
            picks.append(pick)
            remaining.remove(pick)
        return picks

    def _draw_flex(self, units_pool, buildings_pool, events_pool, chosen):
        """Flex slot: weighted roll across units (biased by path), buildings, events."""
        rng = self.rng
        # Category weights biased by path investment total.
        invest_total = sum(self.state.path_investment.values())
        weights = {
            "unit": 3.0 + invest_total * 0.5,
            "building": 2.0,
            "event": 1.0,
        }
        r = rng.random() * sum(weights.values())
        acc = 0.0
        choice = "unit"
        for cat, w in weights.items():
            acc += w
            if r <= acc:
                choice = cat
                break

        if choice == "unit" and units_pool:
            picks = self._weighted_sample_units(units_pool, 1, chosen)
            if picks:
                return picks[0]
        if choice == "building" and buildings_pool:
            return rng.choice(buildings_pool)
        if events_pool:
            return rng.choice(events_pool)
        # final fallback
        return rng.choice(units_pool + buildings_pool + events_pool)

    def _update_pity_on_refresh(self) -> None:
        deepest = self.state.deepest_path()
        if deepest is None:
            self.state.pity_counter = 0
            return
        has_deep = any(
            isinstance(s.offering, Unit) and s.offering.path == deepest
            for s in self.slots
        )
        if has_deep:
            self.state.pity_counter = 0
        else:
            self.state.pity_counter += 1

    # --- player actions ---

    def buy(self, slot_index: int) -> str:
        if not (0 <= slot_index < len(self.slots)):
            return "Invalid slot."
        slot = self.slots[slot_index]
        if self.state.gold < slot.price:
            return f"Not enough gold ({self.state.gold} < {slot.price})."

        self.state.gold -= slot.price
        offering = slot.offering

        messages: list[str] = [f"Bought {offering.name} for {slot.price}g."]

        if isinstance(offering, Unit):
            if offering.required_resource is not None:
                messages.append(
                    f"  Note: requires {offering.required_resource} to tier up (not enforced in prototype)."
                )
            tier_logs = self.state.add_unit(offering)
            messages.extend(tier_logs)
        elif offering.category == "building":
            self.state.buildings.append(offering.name)
            messages.append(f"  Effect (flavor): {offering.effect}")
        elif offering.category == "wonder":
            self.state.wonders.append(offering.name)
            messages.append(f"  Wonder effect (flavor): {offering.effect}")
        elif offering.category == "event":
            messages.append(f"  Event effect (flavor): {offering.effect}")

        # remove the slot and clear its lock if applicable
        was_locked = slot.locked
        self.slots.pop(slot_index)
        if was_locked:
            self.state.locked_slot = None
        elif self.state.locked_slot is not None and slot_index < self.state.locked_slot:
            self.state.locked_slot -= 1

        return "\n".join(messages)

    def lock(self, slot_index: int) -> str:
        if not (0 <= slot_index < len(self.slots)):
            return "Invalid slot."
        if self.state.locked_slot == slot_index:
            return "That slot is already locked."
        if self.state.gold < config.LOCK_COST:
            return f"Not enough gold to lock ({self.state.gold} < {config.LOCK_COST})."
        # unlock previous
        if self.state.locked_slot is not None and self.state.locked_slot < len(self.slots):
            self.slots[self.state.locked_slot].locked = False
        self.state.gold -= config.LOCK_COST
        self.slots[slot_index].locked = True
        self.state.locked_slot = slot_index
        return f"Locked slot {slot_index + 1} for {config.LOCK_COST}g."

    def unlock(self) -> str:
        if self.state.locked_slot is None:
            return "No slot is locked."
        idx = self.state.locked_slot
        if 0 <= idx < len(self.slots):
            self.slots[idx].locked = False
        self.state.locked_slot = None
        return "Unlocked."

    def paid_reroll(self) -> str:
        cost = self.state.reroll_cost()
        if self.state.gold < cost:
            return f"Not enough gold to reroll ({self.state.gold} < {cost})."
        self.state.gold -= cost
        self.refresh(is_free=False)
        return f"Rerolled for {cost}g. Next reroll: {self.state.reroll_cost()}g."
