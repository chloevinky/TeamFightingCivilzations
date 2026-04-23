"""Central mutable game state for the shop loop prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import config
from .offerings import Era, PATHS, Unit, UNITS, TIER_UP_REQUIREMENTS


@dataclass
class GameState:
    turn: int = 1
    gold: int = config.STARTING_GOLD
    ap: int = config.STARTING_AP
    era: Era = Era.ANCIENT

    path_investment: dict[str, int] = field(
        default_factory=lambda: {p: 0 for p in PATHS}
    )

    # army is a list of Unit instances (same Unit reference duplicated per copy)
    army: list[Unit] = field(default_factory=list)
    buildings: list[str] = field(default_factory=list)
    wonders: list[str] = field(default_factory=list)

    # shop-related turn state
    rerolls_this_turn: int = 0
    locked_slot: Optional[int] = None  # index into current shop
    pity_counter: int = 0
    mustered_this_turn: bool = False

    # transient log that display.py renders after each command
    log: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.army:
            warrior = next(u for u in UNITS if u.name == "Warrior")
            self.army = [warrior, warrior]

    # --- turn lifecycle ---

    def begin_turn(self) -> None:
        self.ap = config.ap_for_turn(self.turn)
        self.rerolls_this_turn = 0
        self.mustered_this_turn = False
        # locked_slot persists; caller rebuilds shop preserving locked offering

    def end_turn(self) -> None:
        self.turn += 1

    # --- army ops ---

    def add_unit(self, unit: Unit) -> list[str]:
        """Append a unit and resolve cascading tier-ups. Return log lines."""
        self.army.append(unit)
        return self._resolve_tier_ups()

    def _resolve_tier_ups(self) -> list[str]:
        messages: list[str] = []
        changed = True
        while changed:
            changed = False
            counts: dict[Unit, int] = {}
            for u in self.army:
                counts[u] = counts.get(u, 0) + 1
            for unit, count in counts.items():
                if count < config.TIER_UP_COUNT:
                    continue
                upgraded = _next_tier(unit)
                if upgraded is None:
                    continue
                # consume 3, produce 1
                for _ in range(config.TIER_UP_COUNT):
                    self.army.remove(unit)
                self.army.append(upgraded)
                messages.append(
                    f"Tier-up: 3 {unit.name} -> 1 {upgraded.name}"
                )
                changed = True
                break
        return messages

    # --- shop helpers ---

    def reroll_cost(self) -> int:
        idx = self.rerolls_this_turn
        if idx < len(config.REROLL_COSTS):
            return config.REROLL_COSTS[idx]
        return config.REROLL_COSTS[-1]

    def deepest_path(self) -> Optional[str]:
        invested = {p: v for p, v in self.path_investment.items() if v > 0}
        if not invested:
            return None
        return max(invested, key=invested.get)


def _next_tier(unit: Unit) -> Optional[Unit]:
    """Return the generic same-path tier-up (no resource variant) for a unit."""
    if unit.required_resource is not None:
        # resource-gated variants do not auto-combine in the prototype
        return None
    target_tier = unit.tier + 1
    req = TIER_UP_REQUIREMENTS.get((unit.path, target_tier), "MISSING")
    if req == "MISSING":
        return None
    # pick the first unit in the same path at target_tier with no resource req
    for candidate in UNITS:
        if (
            candidate.path == unit.path
            and candidate.tier == target_tier
            and candidate.required_resource is None
        ):
            return candidate
    return None
