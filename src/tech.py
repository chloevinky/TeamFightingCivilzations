"""Technology tree definitions and research helpers.

Each Tech belongs to a branch and an era.  Research a tech to unlock its
effects.  An era advances globally when *any* civilization accumulates the
era's cumulative science threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .offerings import Era


BRANCHES = (
    "Agriculture",
    "Engineering",
    "Metallurgy",
    "Economics",
    "Military",
    "Governance",
)


@dataclass(frozen=True)
class Tech:
    name: str
    branch: str
    era: Era
    cost: int
    effect: str = ""
    grants_resource: Optional[str] = None
    grants_path: Optional[str] = None
    grants_ap: int = 0


# Each era contains 4-6 techs; cost roughly doubles each era.
TECHS: list[Tech] = [
    # Ancient
    Tech("Pottery", "Agriculture", Era.ANCIENT, 30,
         "Unlocks Granary effect; +1 city pop cap"),
    Tech("Masonry", "Engineering", Era.ANCIENT, 30,
         "Unlocks Walls; +5 city defense"),
    Tech("Bronze Working", "Metallurgy", Era.ANCIENT, 35,
         "Unlocks Iron resource", grants_resource="Iron"),
    Tech("Currency", "Economics", Era.ANCIENT, 30,
         "Unlocks Market"),
    Tech("Warrior Code", "Military", Era.ANCIENT, 30,
         "Unlocks Melee path bonuses"),
    Tech("Code of Laws", "Governance", Era.ANCIENT, 40,
         "+1 AP one-time", grants_ap=1),

    # Classical
    Tech("Animal Husbandry", "Agriculture", Era.CLASSICAL, 60,
         "Unlocks Horses resource", grants_resource="Horses"),
    Tech("Construction", "Engineering", Era.CLASSICAL, 60,
         "Cheaper buildings"),
    Tech("Iron Working", "Metallurgy", Era.CLASSICAL, 70,
         "Iron-tier units cheaper"),
    Tech("Trade", "Economics", Era.CLASSICAL, 60,
         "+10% gold per turn"),
    Tech("Mathematics", "Military", Era.CLASSICAL, 70,
         "Siege path bonus"),
    Tech("Civil Service", "Governance", Era.CLASSICAL, 80,
         "+1 AP one-time", grants_ap=1),

    # Medieval
    Tech("Crop Rotation", "Agriculture", Era.MEDIEVAL, 120,
         "+1 food in all cities"),
    Tech("Engineering", "Engineering", Era.MEDIEVAL, 120,
         "Unlocks Trebuchet, advanced buildings"),
    Tech("Steel", "Metallurgy", Era.MEDIEVAL, 140,
         "Tier-3 melee units stronger"),
    Tech("Banking", "Economics", Era.MEDIEVAL, 140,
         "Reduced reroll cost"),
    Tech("Chivalry", "Military", Era.MEDIEVAL, 140,
         "Unlocks Knight, Cavalry T3"),
    Tech("Feudalism", "Governance", Era.MEDIEVAL, 160,
         "+1 AP one-time", grants_ap=1),

    # Renaissance
    Tech("Astronomy", "Agriculture", Era.RENAISSANCE, 240,
         "Reveal more of the map"),
    Tech("Printing Press", "Engineering", Era.RENAISSANCE, 240,
         "+1 science per city"),
    Tech("Gunpowder", "Metallurgy", Era.RENAISSANCE, 280,
         "Unlocks Musketeer, Cannon"),
    Tech("Economics", "Economics", Era.RENAISSANCE, 240,
         "Shop costs reduced 10%"),
    Tech("Military Science", "Military", Era.RENAISSANCE, 280,
         "Unlocks Frigate, Cavalry"),

    # Industrial
    Tech("Industrialization", "Economics", Era.INDUSTRIAL, 480,
         "Unlocks Factory"),
    Tech("Steam Power", "Engineering", Era.INDUSTRIAL, 480,
         "Unlocks Battleship"),
    Tech("Rifling", "Metallurgy", Era.INDUSTRIAL, 520,
         "Unlocks Rifleman, Artillery"),
    Tech("Flight", "Military", Era.INDUSTRIAL, 560,
         "Unlocks Airforce path", grants_path="Airforce"),
    Tech("Scientific Method", "Governance", Era.INDUSTRIAL, 520,
         "Unlocks Research Lab"),

    # Modern
    Tech("Refrigeration", "Agriculture", Era.MODERN, 900,
         "+2 food in all cities"),
    Tech("Mass Production", "Economics", Era.MODERN, 900,
         "Cheaper units"),
    Tech("Combustion", "Metallurgy", Era.MODERN, 1000,
         "Unlocks Tank, Marine"),
    Tech("Radar", "Military", Era.MODERN, 1000,
         "Reveal enemy army composition"),

    # Atomic
    Tech("Computers", "Engineering", Era.ATOMIC, 1600,
         "+5 science per city"),
    Tech("Rocketry", "Military", Era.ATOMIC, 1700,
         "Unlocks Jet Fighter"),
    Tech("Globalization", "Economics", Era.ATOMIC, 1600,
         "+10 gold per city"),
]


def techs_by_era(era: Era) -> list[Tech]:
    return [t for t in TECHS if t.era == era]


def tech_by_name(name: str) -> Optional[Tech]:
    for t in TECHS:
        if t.name == name:
            return t
    return None


# Cumulative science required to enter each era.  Era 0 is free.
ERA_THRESHOLDS = {
    Era.ANCIENT: 0,
    Era.CLASSICAL: 100,
    Era.MEDIEVAL: 350,
    Era.RENAISSANCE: 900,
    Era.INDUSTRIAL: 2000,
    Era.MODERN: 4000,
    Era.ATOMIC: 7500,
}


def era_for_total_science(total: int) -> Era:
    current = Era.ANCIENT
    for era, threshold in ERA_THRESHOLDS.items():
        if total >= threshold:
            current = era
    return current


@dataclass
class ResearchState:
    """Per-civ research progress."""
    completed: set[str] = field(default_factory=set)
    current: Optional[str] = None
    progress: int = 0
    total_science: int = 0  # cumulative science generated, used for era

    def cost_remaining(self) -> int:
        if self.current is None:
            return 0
        t = tech_by_name(self.current)
        if t is None:
            return 0
        return max(0, t.cost - self.progress)

    def add_science(self, amount: int) -> list[str]:
        """Add science.  Returns log messages for any techs completed."""
        msgs: list[str] = []
        self.total_science += amount
        if self.current is None:
            return msgs
        self.progress += amount
        t = tech_by_name(self.current)
        if t is None:
            self.current = None
            self.progress = 0
            return msgs
        if self.progress >= t.cost:
            msgs.append(f"Researched {t.name} ({t.branch}).")
            self.completed.add(t.name)
            self.current = None
            self.progress = 0
        return msgs

    def set_research(self, tech_name: str) -> bool:
        t = tech_by_name(tech_name)
        if t is None or t.name in self.completed:
            return False
        self.current = t.name
        self.progress = 0
        return True

    def available(self, era: Era) -> list[Tech]:
        return [
            t for t in TECHS
            if t.era <= era and t.name not in self.completed
        ]
