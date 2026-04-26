"""Civilization model.  Used for both the player and AI civs.

The player's civ piggybacks on the existing GameState (kept for backwards
compatibility with the original shop-loop tests).  AI civs use this lighter
model that only tracks the data needed for the AI loop and battle resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .offerings import Era, Unit
from .tech import ResearchState

if TYPE_CHECKING:
    from .cities import City


@dataclass
class Personality:
    aggression: int = 50
    economic: int = 50
    scientific: int = 50
    diplomatic: int = 50


ARCHETYPES: dict[str, Personality] = {
    "Warmonger": Personality(aggression=85, economic=40, scientific=35, diplomatic=20),
    "Merchant":  Personality(aggression=25, economic=85, scientific=45, diplomatic=80),
    "Scholar":   Personality(aggression=35, economic=50, scientific=85, diplomatic=55),
}


@dataclass
class Civilization:
    name: str
    color: tuple[int, int, int]
    is_player: bool = False
    archetype: str = "Warmonger"
    personality: Personality = field(default_factory=Personality)

    cities: list["City"] = field(default_factory=list)
    army: list[Unit] = field(default_factory=list)
    buildings: list[str] = field(default_factory=list)
    wonders: list[str] = field(default_factory=list)
    owned_resources: set[str] = field(default_factory=set)

    gold: int = 100
    ap: int = 3
    era: Era = Era.ANCIENT
    research: ResearchState = field(default_factory=ResearchState)
    path_investment: dict[str, int] = field(default_factory=dict)

    discovered: set[str] = field(default_factory=set)  # names of civs we've met
    capital_lost: bool = False
    eliminated: bool = False

    # Wonder counters
    space_elevator_turns: int = 0

    def __post_init__(self) -> None:
        from .offerings import PATHS
        for p in PATHS:
            self.path_investment.setdefault(p, 0)

    @property
    def alive(self) -> bool:
        return not self.eliminated

    @property
    def capital(self) -> Optional["City"]:
        for c in self.cities:
            if c.capital:
                return c
        return None

    def army_strength(self) -> int:
        """Rough rating used for AI war decisions."""
        return sum(u.attack + u.hp // 4 for u in self.army)

    def total_pop(self) -> int:
        return sum(c.population for c in self.cities)
