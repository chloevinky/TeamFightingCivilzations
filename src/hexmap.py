"""Procedural hex map: terrain, resources, fog of war, hex math.

Uses *axial* coordinates (q, r).  Pixel conversions assume pointy-top hexes.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional


class Terrain(Enum):
    OCEAN = "Ocean"
    COAST = "Coast"
    PLAINS = "Plains"
    GRASSLAND = "Grassland"
    FOREST = "Forest"
    DESERT = "Desert"
    HILLS = "Hills"
    MOUNTAIN = "Mountain"


PASSABLE = {
    Terrain.PLAINS, Terrain.GRASSLAND, Terrain.FOREST,
    Terrain.HILLS, Terrain.DESERT, Terrain.COAST,
}

CITY_BUILDABLE = {
    Terrain.PLAINS, Terrain.GRASSLAND, Terrain.FOREST,
    Terrain.HILLS, Terrain.DESERT,
}


# Resource pool with terrain biases.  Each resource may appear on a tile.
RESOURCES_BY_TERRAIN: dict[Terrain, list[str]] = {
    Terrain.PLAINS: ["Wheat", "Horses"],
    Terrain.GRASSLAND: ["Wheat", "Horses", "Cattle"],
    Terrain.FOREST: ["Furs", "Wood"],
    Terrain.HILLS: ["Iron", "Coal", "Stone"],
    Terrain.DESERT: ["Oil", "Gold"],
    Terrain.MOUNTAIN: ["Iron", "Coal"],
    Terrain.COAST: ["Fish"],
    Terrain.OCEAN: ["Fish", "Whales"],
}

RESOURCE_DENSITY = 0.18


# Yields per terrain: (food, gold, science)
TERRAIN_YIELD: dict[Terrain, tuple[int, int, int]] = {
    Terrain.OCEAN:     (1, 0, 0),
    Terrain.COAST:     (1, 1, 0),
    Terrain.PLAINS:    (2, 1, 0),
    Terrain.GRASSLAND: (3, 0, 0),
    Terrain.FOREST:    (1, 1, 1),
    Terrain.HILLS:     (1, 2, 0),
    Terrain.DESERT:    (0, 1, 0),
    Terrain.MOUNTAIN:  (0, 0, 1),
}


@dataclass
class Tile:
    q: int
    r: int
    terrain: Terrain
    resource: Optional[str] = None
    owner: Optional[str] = None  # civ name
    city: Optional[str] = None   # city name if a city sits here
    # fog: per-civ-name visibility state.  "unseen" / "seen" / "visible"
    fog: dict[str, str] = field(default_factory=dict)

    @property
    def passable(self) -> bool:
        return self.terrain in PASSABLE

    @property
    def buildable(self) -> bool:
        return self.terrain in CITY_BUILDABLE and self.city is None

    def yields(self) -> tuple[int, int, int]:
        food, gold, sci = TERRAIN_YIELD[self.terrain]
        if self.resource:
            # Resources add a flat bonus.
            food += 1 if self.resource in {"Wheat", "Cattle", "Fish"} else 0
            gold += 1 if self.resource in {"Gold", "Furs", "Whales", "Oil"} else 0
            sci += 1 if self.resource in {"Iron", "Coal", "Stone"} else 0
        return (food, gold, sci)


# Six axial neighbour offsets.
NEIGHBORS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def neighbors(q: int, r: int) -> list[tuple[int, int]]:
    return [(q + dq, r + dr) for dq, dr in NEIGHBORS]


def hex_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    aq, ar = a
    bq, br = b
    return (abs(aq - bq) + abs(aq + ar - bq - br) + abs(ar - br)) // 2


def axial_to_pixel(q: int, r: int, size: float) -> tuple[float, float]:
    # Pointy-top hex layout.
    x = size * math.sqrt(3) * (q + r / 2.0)
    y = size * 1.5 * r
    return x, y


@dataclass
class HexMap:
    radius: int
    tiles: dict[tuple[int, int], Tile] = field(default_factory=dict)

    def __iter__(self):
        return iter(self.tiles.values())

    def get(self, q: int, r: int) -> Optional[Tile]:
        return self.tiles.get((q, r))

    def coords(self) -> Iterable[tuple[int, int]]:
        return self.tiles.keys()

    def passable_neighbors(self, q: int, r: int) -> list[Tile]:
        return [
            self.tiles[c] for c in neighbors(q, r)
            if c in self.tiles and self.tiles[c].passable
        ]


def generate_map(radius: int = 6, rng: Optional[random.Random] = None) -> HexMap:
    """Generate a hex map of the given radius using simple noise heuristics."""
    rng = rng or random.Random()
    m = HexMap(radius=radius)
    coords: list[tuple[int, int]] = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            if -q - r < -radius or -q - r > radius:
                continue
            coords.append((q, r))

    # Seed a few "land cores" and grow outward, with mountains as barriers.
    for q, r in coords:
        d_edge = max(0, radius - max(abs(q), abs(r), abs(-q - r)))
        # tiles near the edge tend toward ocean
        edge_factor = (radius - d_edge) / max(1, radius)
        roll = rng.random() + (edge_factor - 0.4) * 0.6
        if roll < 0.18:
            terrain = Terrain.OCEAN
        elif roll < 0.30:
            terrain = Terrain.COAST
        elif roll < 0.38:
            terrain = Terrain.MOUNTAIN
        elif roll < 0.50:
            terrain = Terrain.FOREST
        elif roll < 0.60:
            terrain = Terrain.HILLS
        elif roll < 0.70:
            terrain = Terrain.DESERT
        elif roll < 0.85:
            terrain = Terrain.PLAINS
        else:
            terrain = Terrain.GRASSLAND
        m.tiles[(q, r)] = Tile(q=q, r=r, terrain=terrain)

    # Sprinkle resources by terrain.
    for tile in m:
        pool = RESOURCES_BY_TERRAIN.get(tile.terrain, [])
        if pool and rng.random() < RESOURCE_DENSITY:
            tile.resource = rng.choice(pool)
    return m


def find_starting_tiles(m: HexMap, num: int, rng: random.Random) -> list[tuple[int, int]]:
    """Pick `num` buildable tiles spaced apart for civ starts."""
    candidates = [(t.q, t.r) for t in m if t.buildable]
    rng.shuffle(candidates)
    chosen: list[tuple[int, int]] = []
    min_dist = max(3, m.radius - 1)
    for c in candidates:
        if all(hex_distance(c, x) >= min_dist for x in chosen):
            chosen.append(c)
            if len(chosen) == num:
                break
    # Relax if we couldn't find enough spacing.
    while len(chosen) < num and candidates:
        c = candidates.pop()
        if c not in chosen:
            chosen.append(c)
    return chosen


def reveal_around(m: HexMap, civ: str, center: tuple[int, int], radius: int) -> None:
    """Mark a radius of tiles as visible to a civ."""
    for c in m.coords():
        if hex_distance(center, c) <= radius:
            m.tiles[c].fog[civ] = "visible"


def degrade_visible_to_seen(m: HexMap, civ: str) -> None:
    for tile in m:
        if tile.fog.get(civ) == "visible":
            tile.fog[civ] = "seen"
