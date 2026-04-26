"""Player civilization state for the shop loop / full Hexfall prototype.

`GameState` represents the *player's* civ.  AI civs use the lighter
`Civilization` model.  The original shop-loop tests construct GameState
directly with no arguments, so the existing public surface is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from . import config
from .offerings import Era, PATHS, Unit, UNITS, TIER_UP_REQUIREMENTS
from .tech import ResearchState

if TYPE_CHECKING:
    from .cities import City


@dataclass
class GameState:
    turn: int = 1
    gold: int = config.STARTING_GOLD
    ap: int = config.STARTING_AP
    era: Era = Era.ANCIENT

    path_investment: dict[str, int] = field(
        default_factory=lambda: {p: 0 for p in PATHS}
    )

    army: list[Unit] = field(default_factory=list)
    buildings: list[str] = field(default_factory=list)
    wonders: list[str] = field(default_factory=list)

    # shop-related turn state
    rerolls_this_turn: int = 0
    locked_slot: Optional[int] = None
    pity_counter: int = 0
    mustered_this_turn: bool = False

    log: list[str] = field(default_factory=list)

    # --- Full-game additions (no-op for the bare shop-loop tests) ---
    name: str = "Player"
    cities: list["City"] = field(default_factory=list)
    research: ResearchState = field(default_factory=ResearchState)
    owned_resources: set[str] = field(default_factory=set)
    discovered: set[str] = field(default_factory=set)
    capital_lost: bool = False
    eliminated: bool = False
    # bonuses granted by wonders
    extra_shop_slot: int = 0
    extra_free_refresh: int = 0
    permanent_ap_bonus: int = 0
    space_elevator_turns: int = 0
    pity_reduction: int = 0  # Great Library

    def __post_init__(self) -> None:
        if not self.army:
            warrior = next(u for u in UNITS if u.name == "Warrior")
            self.army = [warrior, warrior]
        # Make sure new paths (e.g. Airforce) appear in the dict.
        for p in PATHS:
            self.path_investment.setdefault(p, 0)

    # --- turn lifecycle ---

    def begin_turn(self) -> None:
        self.ap = config.ap_for_turn(self.turn) + self.permanent_ap_bonus
        self.rerolls_this_turn = 0
        self.mustered_this_turn = False

    def end_turn(self) -> None:
        self.turn += 1

    # --- army ops ---

    def add_unit(self, unit: Unit) -> list[str]:
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

    @property
    def capital(self) -> Optional["City"]:
        for c in self.cities:
            if c.capital:
                return c
        return None

    @property
    def alive(self) -> bool:
        return not self.eliminated

    def army_strength(self) -> int:
        return sum(u.attack + u.hp // 4 for u in self.army)

    def total_pop(self) -> int:
        return sum(c.population for c in self.cities)


def _next_tier(unit: Unit) -> Optional[Unit]:
    """Return the generic same-path tier-up for a unit (no resource variant)."""
    if unit.required_resource is not None:
        return None
    target_tier = unit.tier + 1
    req = TIER_UP_REQUIREMENTS.get((unit.path, target_tier), "MISSING")
    if req == "MISSING":
        return None
    for candidate in UNITS:
        if (
            candidate.path == unit.path
            and candidate.tier == target_tier
            and candidate.required_resource is None
        ):
            return candidate
    return None
