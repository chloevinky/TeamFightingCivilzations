"""City model: population growth, per-turn yields, organic founding."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .hexmap import CITY_BUILDABLE, HexMap, Tile, hex_distance, neighbors

if TYPE_CHECKING:
    from .civilization import Civilization


CITY_RADIUS = 2  # rings of hexes a city works
POP_GROWTH_THRESHOLD_BASE = 12  # food required for next pop
ORGANIC_FOUND_POP = 6  # crossing this pop founds a new city
FOUND_CITY_GOLD_COST = 150


@dataclass
class City:
    name: str
    owner: str  # civ name
    q: int
    r: int
    population: int = 1
    food_storage: int = 0
    capital: bool = False
    buildings: list[str] = field(default_factory=list)

    def coord(self) -> tuple[int, int]:
        return (self.q, self.r)

    def worked_tiles(self, m: HexMap) -> list[Tile]:
        out = []
        for c in m.coords():
            if hex_distance(self.coord(), c) <= CITY_RADIUS:
                tile = m.tiles[c]
                if tile.owner == self.owner or tile.owner is None:
                    out.append(tile)
        return out

    def yields(self, m: HexMap) -> tuple[int, int, int]:
        """Per-turn (food, gold, science) from worked tiles, capped by pop+1."""
        tiles = sorted(
            self.worked_tiles(m),
            key=lambda t: sum(t.yields()),
            reverse=True,
        )
        cap = self.population + 1  # center tile is always worked
        food = gold = sci = 0
        for t in tiles[:cap]:
            f, g, s = t.yields()
            food += f
            gold += g
            sci += s
        return food, gold, sci


def found_city(
    civ: "Civilization",
    m: HexMap,
    coord: tuple[int, int],
    *,
    name: Optional[str] = None,
    capital: bool = False,
) -> City:
    """Create a city for `civ` at `coord`, claim surrounding tiles."""
    q, r = coord
    name = name or _generate_city_name(civ)
    city = City(name=name, owner=civ.name, q=q, r=r, capital=capital)
    civ.cities.append(city)
    tile = m.tiles[(q, r)]
    tile.city = name
    tile.owner = civ.name
    # Claim the radius.
    for c in m.coords():
        if hex_distance(coord, c) <= CITY_RADIUS:
            t = m.tiles[c]
            if t.owner is None:
                t.owner = civ.name
    return city


def organic_growth(
    civ: "Civilization", m: HexMap, rng: random.Random
) -> Optional[City]:
    """If any city has crossed the founding threshold and a valid neighbour
    exists, found a new city."""
    for city in list(civ.cities):
        if city.population < ORGANIC_FOUND_POP:
            continue
        candidates = []
        # Look 2..3 hexes out for a buildable, unoccupied tile.
        for coord in m.coords():
            if hex_distance(city.coord(), coord) not in (2, 3):
                continue
            t = m.tiles[coord]
            if not t.buildable:
                continue
            if t.owner is not None and t.owner != civ.name:
                continue
            candidates.append(coord)
        if not candidates:
            continue
        rng.shuffle(candidates)
        new_coord = candidates[0]
        city.population -= 2
        new_city = found_city(civ, m, new_coord)
        return new_city
    return None


_CITY_NAME_POOL = {
    "Player": ["Argo", "Helion", "Mariq", "Vaelin", "Dornak", "Sylex", "Karith"],
    "Caesarius": ["Roma", "Ostia", "Capua", "Veii", "Tarentum", "Brundisium"],
    "Mercatia": ["Bazaaria", "Goldhaven", "Silkmoor", "Caravanrest", "Coinquay"],
    "Lyceum": ["Athena", "Sophia", "Logos", "Heliotrope", "Astralis"],
    "Khanate": ["Karakorum", "Sukh", "Tengri", "Ordu", "Steppemark"],
    "Albion": ["Avalon", "Camelot", "Tintagel", "Lyonesse", "Brigant"],
}


def _generate_city_name(civ: "Civilization") -> str:
    pool = _CITY_NAME_POOL.get(civ.name, ["Newhold", "Outpost", "Frontier"])
    used = {c.name for c in civ.cities}
    for n in pool:
        if n not in used:
            return n
    # Fallback with numeric suffix.
    base = pool[0]
    i = 2
    while f"{base} {i}" in used:
        i += 1
    return f"{base} {i}"
