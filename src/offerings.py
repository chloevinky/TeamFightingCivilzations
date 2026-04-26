"""Offering data for the Hexfall prototype.

Covers all eras, all paths, all 7 wonders, and the full event roster from the
README.  Battle stats are attached to units so the auto-resolver has something
to work with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


PATHS = ("Melee", "Ranged", "Cavalry", "Navy", "Siege", "Airforce")


@dataclass(frozen=True)
class Unit:
    name: str
    path: str
    tier: int
    base_cost: int
    era: Era = Era.ANCIENT
    required_resource: Optional[str] = None
    # Battle stats
    hp: int = 20
    attack: int = 5
    defense: int = 2
    speed: int = 3
    rng: int = 1            # attack range in grid columns; >1 = ranged
    prefers_back: bool = False

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
    gold_per_turn: int = 0
    science_per_turn: int = 0
    food_per_turn: int = 0
    defense_bonus: int = 0
    shop_weight_path: Optional[str] = None

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
    kind: str = "flavor"   # used by the resolver to apply effects
    era: Era = Era.ANCIENT

    @property
    def category(self) -> str:
        return "event"

    def label(self) -> str:
        return "Event"


# --- Units ---------------------------------------------------------------
# Tier 1 base cost = 20, T2 = 60, T3 = 180.  Stats scale with tier.
UNITS: list[Unit] = [
    # Melee
    Unit("Warrior", "Melee", 1, 20, hp=22, attack=6, defense=2, speed=3),
    Unit("Super Warrior", "Melee", 2, 60, hp=42, attack=11, defense=4, speed=3),
    Unit("Swordsman", "Melee", 2, 60, required_resource="Iron",
         hp=46, attack=13, defense=5, speed=3),
    Unit("Champion", "Melee", 3, 180, era=Era.MEDIEVAL,
         hp=78, attack=20, defense=8, speed=3),
    Unit("Musketeer", "Melee", 3, 180, era=Era.RENAISSANCE,
         hp=70, attack=24, defense=6, speed=3, rng=2),
    Unit("Infantry", "Melee", 3, 180, era=Era.INDUSTRIAL,
         hp=88, attack=28, defense=10, speed=3, rng=2),
    Unit("Marine", "Melee", 3, 180, era=Era.MODERN,
         hp=96, attack=32, defense=12, speed=4, rng=2),

    # Ranged
    Unit("Archer", "Ranged", 1, 20, hp=16, attack=7, defense=1, speed=3,
         rng=3, prefers_back=True),
    Unit("Crossbowman", "Ranged", 2, 60, hp=28, attack=14, defense=2, speed=3,
         rng=3, prefers_back=True),
    Unit("Longbowman", "Ranged", 3, 180, era=Era.MEDIEVAL,
         hp=42, attack=22, defense=3, speed=3, rng=4, prefers_back=True),
    Unit("Rifleman", "Ranged", 3, 180, era=Era.INDUSTRIAL,
         hp=58, attack=30, defense=5, speed=3, rng=4, prefers_back=True),

    # Cavalry
    Unit("Scout Rider", "Cavalry", 1, 20, hp=20, attack=6, defense=1, speed=6),
    Unit("Horseman", "Cavalry", 2, 60, required_resource="Horses",
         hp=40, attack=14, defense=3, speed=7),
    Unit("Knight", "Cavalry", 3, 180, era=Era.MEDIEVAL, required_resource="Iron",
         hp=70, attack=22, defense=6, speed=7),
    Unit("Cavalry", "Cavalry", 3, 180, era=Era.RENAISSANCE,
         hp=64, attack=24, defense=4, speed=8),
    Unit("Tank", "Cavalry", 3, 180, era=Era.MODERN,
         hp=120, attack=38, defense=14, speed=6, rng=2),

    # Navy
    Unit("Raft", "Navy", 1, 20, hp=18, attack=5, defense=1, speed=3),
    Unit("Galley", "Navy", 2, 60, hp=34, attack=11, defense=3, speed=4, rng=2),
    Unit("Frigate", "Navy", 3, 180, era=Era.RENAISSANCE,
         hp=58, attack=22, defense=5, speed=4, rng=4, prefers_back=True),
    Unit("Battleship", "Navy", 3, 180, era=Era.INDUSTRIAL,
         hp=110, attack=34, defense=10, speed=4, rng=5, prefers_back=True),

    # Siege
    Unit("Catapult", "Siege", 1, 20, hp=14, attack=10, defense=1, speed=2,
         rng=4, prefers_back=True),
    Unit("Ballista", "Siege", 2, 60, hp=24, attack=18, defense=2, speed=2,
         rng=5, prefers_back=True),
    Unit("Trebuchet", "Siege", 3, 180, era=Era.MEDIEVAL,
         hp=36, attack=26, defense=2, speed=2, rng=6, prefers_back=True),
    Unit("Cannon", "Siege", 3, 180, era=Era.RENAISSANCE,
         hp=46, attack=34, defense=3, speed=2, rng=6, prefers_back=True),
    Unit("Artillery", "Siege", 3, 180, era=Era.INDUSTRIAL,
         hp=58, attack=42, defense=4, speed=2, rng=7, prefers_back=True),

    # Airforce (Industrial+)
    Unit("Biplane", "Airforce", 1, 60, era=Era.INDUSTRIAL,
         hp=24, attack=14, defense=2, speed=8, rng=4, prefers_back=True),
    Unit("Fighter", "Airforce", 2, 180, era=Era.MODERN,
         hp=44, attack=28, defense=4, speed=10, rng=5, prefers_back=True),
    Unit("Jet Fighter", "Airforce", 3, 540, era=Era.ATOMIC,
         hp=68, attack=44, defense=6, speed=12, rng=6, prefers_back=True),
]

# --- Buildings -----------------------------------------------------------
BUILDINGS: list[Building] = [
    Building("Granary", 50, "+1 food per turn", food_per_turn=1),
    Building("Barracks", 50, "Shop weights Melee/Ranged",
             shop_weight_path="Melee"),
    Building("Library", 50, "+1 science per turn", science_per_turn=1),
    Building("Market", 50, "+2 gold per turn", gold_per_turn=2),
    Building("Walls", 120, "City defense +5", advanced=True, defense_bonus=5),
    Building("Workshop", 120, "+2 gold, +1 science", advanced=True,
             gold_per_turn=2, science_per_turn=1),
    Building("Bank", 120, "+4 gold per turn", advanced=True,
             era=Era.MEDIEVAL, gold_per_turn=4),
    Building("University", 120, "+3 science per turn", advanced=True,
             era=Era.MEDIEVAL, science_per_turn=3),
    Building("Factory", 120, "+5 gold per turn", advanced=True,
             era=Era.INDUSTRIAL, gold_per_turn=5),
    Building("Research Lab", 120, "+5 science per turn", advanced=True,
             era=Era.INDUSTRIAL, science_per_turn=5),
]

# --- Wonders (1 per era, 7 total) ----------------------------------------
WONDERS: list[Wonder] = [
    Wonder("Great Library", 500, Era.ANCIENT,
           "+2 science per city; pity timer reduced by 1 reroll"),
    Wonder("Colosseum", 600, Era.CLASSICAL,
           "+1 AP per turn, permanent"),
    Wonder("Grand Bazaar", 700, Era.MEDIEVAL,
           "+1 shop slot; reduced reroll costs"),
    Wonder("Royal Observatory", 850, Era.RENAISSANCE,
           "Reveal all enemy army composition before battles"),
    Wonder("Statue of Liberty", 1000, Era.INDUSTRIAL,
           "+1 free refresh per turn"),
    Wonder("Pentagon", 1200, Era.MODERN,
           "Army cap +5"),
    Wonder("Space Elevator", 1500, Era.ATOMIC,
           "Auto-win if held for 5 consecutive turns without losing a city"),
]

# --- Events --------------------------------------------------------------
EVENTS: list[Event] = [
    Event("Mercenary Contract", 100,
          "Receive a tier-2 unit from any unlocked path", kind="mercenary"),
    Event("Foreign Scholar", 80,
          "Instantly complete 25% of current research", kind="scholar"),
    Event("Migration Wave", 60,
          "One city gains population immediately", kind="migration"),
    Event("Resource Cache", 70,
          "Temporary access to a random resource for 5 turns", kind="cache"),
    Event("Veteran Trainer", 90,
          "One owned unit gains a permanent trait", kind="veteran"),
    Event("Black Market", 200,
          "Immediately tier-up any one unit regardless of count",
          kind="black_market"),
    Event("Spy Network", 60,
          "Reveal a rival civ's army composition and tech level", kind="spy"),
    Event("Rebellious City", 150,
          "Flip a contested enemy city to neutral", kind="rebellion"),
]


Offering = Unit | Building | Wonder | Event


TIER_UP_REQUIREMENTS: dict[tuple[str, int], Optional[str]] = {
    # (path, target_tier) -> resource required to combine (or None for generic)
    ("Melee", 2): None,
    ("Ranged", 2): None,
    ("Cavalry", 2): None,
    ("Navy", 2): None,
    ("Siege", 2): None,
    ("Airforce", 2): None,
    ("Melee", 3): None,
    ("Ranged", 3): None,
    ("Cavalry", 3): None,
    ("Navy", 3): None,
    ("Siege", 3): None,
    ("Airforce", 3): None,
}


def price_for(offering: Offering, era: Era) -> int:
    """Current era multiplies the base cost by 1.5^(era delta)."""
    delta = max(0, int(era) - int(offering.era))
    multiplier = 1.5 ** delta
    return int(round(offering.base_cost * multiplier))


def units_in_era(era: Era) -> list[Unit]:
    return [u for u in UNITS if u.era <= era]


def buildings_in_era(era: Era) -> list[Building]:
    return [b for b in BUILDINGS if b.era <= era]


def wonders_in_era(era: Era) -> list[Wonder]:
    return [w for w in WONDERS if w.era <= era]
