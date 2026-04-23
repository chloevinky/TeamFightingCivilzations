"""Path investment, weighting, pity timer, and trait bleed logic."""

from __future__ import annotations

from .offerings import PATHS, Unit
from . import config


TRAIT_BLEED_TABLE = [
    # (invested_path, minimum_investment, trait, target_paths)
    ("Navy", 2, "Amphibious", ["Melee"]),
    ("Airforce", 2, "Recon", list(PATHS)),
    ("Cavalry", 2, "Charge", ["Melee"]),
    ("Siege", 2, "Siege", ["Ranged"]),
    ("Ranged", 2, "Volley", ["Siege"]),
    ("Melee", 2, "Guard", ["Ranged", "Siege"]),
]


def invest(path_investment: dict[str, int], path: str) -> None:
    """Mutate path_investment, raising if the path is unknown."""
    if path not in path_investment:
        raise ValueError(f"Unknown path: {path}")
    path_investment[path] += 1


def unit_weight(unit: Unit, path_investment: dict[str, int]) -> float:
    """Weight used when flex-filling unit slots or biasing the unit pool."""
    level = path_investment.get(unit.path, 0)
    return config.BASE_PATH_WEIGHT + level * config.PATH_WEIGHT_PER_LEVEL


def muster_tier(path_investment: dict[str, int], path: str) -> int:
    """Tier of unit received from targeted muster. Scales with depth."""
    depth = path_investment.get(path, 0)
    if depth <= 0:
        return 1
    # 1 invest -> T1, 2 -> T2, 4+ -> T3 (cap at 3 for the prototype)
    if depth >= 4:
        return 3
    if depth >= 2:
        return 2
    return 1


def unlocked_paths(path_investment: dict[str, int]) -> list[str]:
    return [p for p, v in path_investment.items() if v >= 1]


def traits_for(path: str, path_investment: dict[str, int]) -> list[str]:
    """Traits bled into units of `path` given current investments."""
    traits: list[str] = []
    for invested_path, minimum, trait, targets in TRAIT_BLEED_TABLE:
        if path in targets and path_investment.get(invested_path, 0) >= minimum:
            traits.append(trait)
    return traits
