"""Diplomacy: relations matrix and proactive actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# AP costs for proactive diplomacy.
DIPLOMACY_COSTS = {
    "open_borders": 1,
    "trade": 1,
    "nap": 2,
    "alliance": 3,
    "denounce": 1,
    "demand_tribute": 2,
    "declare_war": 0,
    "make_peace": 1,
}

NAP_DURATION = 10
TRIBUTE_AMOUNT = 50
DISCOVERY_BATTLE_COUNTDOWN = 15


@dataclass
class Relation:
    """Pairwise relation between two civs.  Symmetric."""
    civ_a: str
    civ_b: str
    score: int = 0  # -100 .. +100
    open_borders: bool = False
    nap_until_turn: Optional[int] = None
    alliance: bool = False
    at_war: bool = False
    war_countdown: Optional[int] = None  # turns until forced battle
    war_declared_turn: Optional[int] = None

    def involves(self, name: str) -> bool:
        return name in (self.civ_a, self.civ_b)

    def other(self, name: str) -> str:
        return self.civ_b if self.civ_a == name else self.civ_a


class DiplomacyTable:
    """Holds all pairwise relations."""

    def __init__(self) -> None:
        self._relations: dict[frozenset, Relation] = {}

    def _key(self, a: str, b: str) -> frozenset:
        return frozenset((a, b))

    def get(self, a: str, b: str) -> Relation:
        key = self._key(a, b)
        if key not in self._relations:
            self._relations[key] = Relation(civ_a=a, civ_b=b, score=0)
        return self._relations[key]

    def all_for(self, name: str) -> list[Relation]:
        return [r for r in self._relations.values() if r.involves(name)]

    def all(self) -> list[Relation]:
        return list(self._relations.values())

    def adjust(self, a: str, b: str, delta: int) -> None:
        rel = self.get(a, b)
        rel.score = max(-100, min(100, rel.score + delta))

    def start_countdown(self, a: str, b: str, turns: int) -> None:
        rel = self.get(a, b)
        if rel.war_countdown is None and not rel.at_war:
            rel.war_countdown = turns

    def tick(self, current_turn: int) -> list[tuple[str, str]]:
        """Advance turn-based timers.  Returns list of (a, b) pairs that
        must trigger a battle this turn (countdown elapsed)."""
        battles = []
        for rel in self._relations.values():
            if rel.nap_until_turn is not None and current_turn >= rel.nap_until_turn:
                rel.nap_until_turn = None
            if rel.at_war and rel.war_countdown is not None and rel.war_countdown > 0:
                rel.war_countdown -= 1
                if rel.war_countdown <= 0:
                    battles.append((rel.civ_a, rel.civ_b))
            elif (
                rel.war_countdown is not None
                and not rel.at_war
                and rel.war_countdown > 0
            ):
                rel.war_countdown -= 1
                if rel.war_countdown <= 0:
                    rel.at_war = True
                    rel.war_declared_turn = current_turn
                    battles.append((rel.civ_a, rel.civ_b))
        return battles

    def declare_war(self, a: str, b: str, current_turn: int) -> None:
        rel = self.get(a, b)
        rel.at_war = True
        rel.war_declared_turn = current_turn
        rel.war_countdown = 1  # battle resolves on next tick
        rel.alliance = False
        rel.nap_until_turn = None
        self.adjust(a, b, -50)

    def make_peace(self, a: str, b: str) -> None:
        rel = self.get(a, b)
        rel.at_war = False
        rel.war_countdown = None
        self.adjust(a, b, +20)

    def sign_nap(self, a: str, b: str, current_turn: int) -> None:
        rel = self.get(a, b)
        rel.nap_until_turn = current_turn + NAP_DURATION
        self.adjust(a, b, +15)

    def sign_alliance(self, a: str, b: str) -> None:
        rel = self.get(a, b)
        rel.alliance = True
        self.adjust(a, b, +30)

    def open_borders(self, a: str, b: str) -> None:
        rel = self.get(a, b)
        rel.open_borders = True
        self.adjust(a, b, +5)

    def denounce(self, a: str, b: str) -> None:
        self.adjust(a, b, -25)
