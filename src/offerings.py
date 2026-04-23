"""Offering data for the shop loop prototype.

The prototype only exercises the Ancient era. Later eras stay as enum values
so that shop filtering and era multipliers have the right shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class Era(IntEnum):
    ANCIENT = 0
    CLASSICAL = 1
    MEDIEVAL = 2
    RENAISSANCE = 3
    INDUSTRIAL = 4
    MODERN = 5
    ATOMIC = 6


PATHS = ("Melee", "Ranged", "Cavalry", "Navy", "Siege")


@dataclass(frozen=True)
class Unit:
    name: str
    path: str
    tier: int
    base_cost: int
    era: Era = Era.ANCIENT
    required_resource: Optional[str] = None

    @property
    def category(self) -> str:
        return "unit"

    def label(self) -> str:
        return f"{self.path} T{self.tier}"


@dataclass(frozen=True)
class Building:
    name: str
    base_cost: int
    effect: str
    era: Era = Era.ANCIENT
    advanced: bool = False

    @property
    def category(self) -> str:
        return "building"

    def label(self) -> str:
        return "Advanced Building" if self.advanced else "Building"


@dataclass(frozen=True)
class Wonder:
    name: str
    base_cost: int
    era: Era
    effect: str

    @property
    def category(self) -> str:
        return "wonder"

    def label(self) -> str:
        return f"Wonder ({self.era.name.title()})"


@dataclass(frozen=True)
class Event:
    name: str
    base_cost: int
    effect: str
    era: Era = Era.ANCIENT

    @property
    def category(self) -> str:
        return "event"

    def label(self) -> str:
        return "Event"


UNITS: list[Unit] = [
    Unit("Warrior", "Melee", 1, 20),
    Unit("Super Warrior", "Melee", 2, 60),
    Unit("Swordsman", "Melee", 2, 60, required_resource="Iron"),
    Unit("Archer", "Ranged", 1, 20),
    Unit("Crossbowman", "Ranged", 2, 60),
    Unit("Scout Rider", "Cavalry", 1, 20),
    Unit("Horseman", "Cavalry", 2, 60, required_resource="Horses"),
    Unit("Raft", "Navy", 1, 20),
    Unit("Galley", "Navy", 2, 60),
    Unit("Catapult", "Siege", 1, 20),
    Unit("Ballista", "Siege", 2, 60),
]

BUILDINGS: list[Building] = [
    Building("Granary", 50, "+1 food per turn (flavor)"),
    Building("Barracks", 50, "Shop weights Melee/Ranged +10% (flavor)"),
    Building("Library", 50, "+1 science per turn (flavor)"),
    Building("Market", 50, "+10% gold per turn (flavor)"),
    Building("Walls", 120, "City defense +5 (flavor)", advanced=True),
    Building("Workshop", 120, "Unlocks tier-up hints (flavor)", advanced=True),
]

WONDERS: list[Wonder] = [
    Wonder("Great Library", 500, Era.ANCIENT,
           "+2 science per city; pity timer reduced by 1 reroll"),
]

EVENTS: list[Event] = [
    Event("Mercenary Contract", 100, "Receive a tier-2 unit from any unlocked path"),
    Event("Foreign Scholar", 80, "Instantly complete 25% of current research"),
    Event("Migration Wave", 60, "One city gains population immediately"),
    Event("Resource Cache", 70, "Temporary access to a random resource for 5 turns"),
    Event("Veteran Trainer", 90, "One owned unit gains a permanent trait"),
    Event("Black Market", 200, "Immediately tier-up any one unit regardless of count"),
    Event("Spy Network", 60, "Reveal a rival civ's army composition and tech level"),
    Event("Rebellious City", 150, "Flip a contested enemy city to neutral"),
]


Offering = Unit | Building | Wonder | Event


TIER_UP_REQUIREMENTS: dict[tuple[str, int], Optional[str]] = {
    # (path, target_tier) -> resource required to combine (or None for generic)
    ("Melee", 2): None,         # 3 Warriors -> Super Warrior
    ("Ranged", 2): None,
    ("Cavalry", 2): None,
    ("Navy", 2): None,
    ("Siege", 2): None,
}


def price_for(offering: Offering, era: Era) -> int:
    """Current era multiplies the base cost by 1.5^(era delta)."""
    delta = max(0, int(era) - int(offering.era))
    multiplier = 1.5 ** delta
    return int(round(offering.base_cost * multiplier))
