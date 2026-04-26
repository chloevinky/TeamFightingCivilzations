"""Battle module: 8x8 tactical grid auto-resolver.

A battle has two sides.  Each side's units occupy 8 columns x 4 rows.  Player
column 0 = front, increasing toward the enemy.  Combined grid has 8 columns
total (4 per side) x 4 rows.  We model attack range in *grid columns* across
the combined arena.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .offerings import Unit


GRID_ROWS = 4
GRID_COLS_PER_SIDE = 4   # each side has 4 columns
GRID_COLS_TOTAL = GRID_COLS_PER_SIDE * 2  # 8 columns end-to-end
MAX_ROUNDS = 20


@dataclass
class CombatUnit:
    """A unit instance on the battle grid (mutable HP)."""
    template: Unit
    side: int      # 0 = attacker (left), 1 = defender (right)
    col: int       # 0..GRID_COLS_TOTAL-1
    row: int       # 0..GRID_ROWS-1
    hp: int = 0
    initiative: int = 0
    alive: bool = True

    def __post_init__(self) -> None:
        if self.hp == 0:
            self.hp = self.template.hp

    @property
    def name(self) -> str:
        return self.template.name


@dataclass
class BattleState:
    sides: tuple[list[CombatUnit], list[CombatUnit]]
    civ_names: tuple[str, str]
    round_num: int = 0
    log: list[str] = field(default_factory=list)
    winner: Optional[int] = None  # 0 / 1 / None for in-progress
    attacker: int = 0  # which side is the *attacker* (loses on draw)

    def all_units(self) -> list[CombatUnit]:
        return self.sides[0] + self.sides[1]

    def alive_units(self, side: int) -> list[CombatUnit]:
        return [u for u in self.sides[side] if u.alive]

    def grid(self) -> list[list[Optional[CombatUnit]]]:
        g: list[list[Optional[CombatUnit]]] = [
            [None for _ in range(GRID_COLS_TOTAL)] for _ in range(GRID_ROWS)
        ]
        for u in self.all_units():
            if u.alive:
                g[u.row][u.col] = u
        return g


def auto_place(units: list[Unit], side: int) -> list[CombatUnit]:
    """Auto-place a list of unit templates on a side.  Front/back rows are
    chosen by `prefers_back`.  Used both for AI and as the player's initial
    layout (which they can then nudge).
    """
    placed: list[CombatUnit] = []
    # Side 0 occupies columns 0..3 (front=3 facing center), side 1 occupies 4..7 (front=4)
    front_col = GRID_COLS_PER_SIDE - 1 if side == 0 else GRID_COLS_PER_SIDE
    back_col = 0 if side == 0 else GRID_COLS_TOTAL - 1
    front_units = [u for u in units if not u.prefers_back]
    back_units = [u for u in units if u.prefers_back]

    # Distribute front-row units across the rows of the front column.
    used = set()
    for i, u in enumerate(front_units[: GRID_ROWS]):
        placed.append(CombatUnit(u, side, front_col, i))
        used.add((front_col, i))
    overflow = front_units[GRID_ROWS:]
    # Push overflow into a near-front column.
    near_col = front_col - 1 if side == 0 else front_col + 1
    for i, u in enumerate(overflow[: GRID_ROWS]):
        placed.append(CombatUnit(u, side, near_col, i))
        used.add((near_col, i))

    # Place back units on the back column, then fill in.
    for i, u in enumerate(back_units[: GRID_ROWS]):
        placed.append(CombatUnit(u, side, back_col, i))
        used.add((back_col, i))
    rest = back_units[GRID_ROWS:]
    middle_col = back_col + 1 if side == 0 else back_col - 1
    for i, u in enumerate(rest[: GRID_ROWS]):
        placed.append(CombatUnit(u, side, middle_col, i))
        used.add((middle_col, i))

    return placed


def col_distance(a: CombatUnit, b: CombatUnit) -> int:
    """Manhattan-style distance on the grid (cols + rows)."""
    return abs(a.col - b.col) + abs(a.row - b.row)


def in_range(attacker: CombatUnit, target: CombatUnit) -> bool:
    return col_distance(attacker, target) <= attacker.template.rng


def pick_target(attacker: CombatUnit, enemies: list[CombatUnit]) -> Optional[CombatUnit]:
    in_rng = [e for e in enemies if e.alive and in_range(attacker, e)]
    if not in_rng:
        return None
    # Front-row first, then lowest HP.
    in_rng.sort(key=lambda e: (-_front_score(attacker, e), e.hp))
    return in_rng[0]


def _front_score(attacker: CombatUnit, target: CombatUnit) -> int:
    if attacker.side == 0:
        return -target.col  # smaller col = farther from us
    return target.col


def step_toward(attacker: CombatUnit, enemies: list[CombatUnit], grid_occupied: set[tuple[int, int]]) -> None:
    """Advance one column toward the nearest enemy if no target is in range."""
    living = [e for e in enemies if e.alive]
    if not living:
        return
    # nearest enemy
    target = min(living, key=lambda e: col_distance(attacker, e))
    desired_dx = 0
    if target.col > attacker.col:
        desired_dx = 1
    elif target.col < attacker.col:
        desired_dx = -1
    new_col = attacker.col + desired_dx
    if new_col < 0 or new_col >= GRID_COLS_TOTAL:
        return
    if (new_col, attacker.row) in grid_occupied:
        return
    grid_occupied.discard((attacker.col, attacker.row))
    attacker.col = new_col
    grid_occupied.add((new_col, attacker.row))


def resolve_battle(
    side_a_units: list[Unit],
    side_b_units: list[Unit],
    civ_names: tuple[str, str],
    rng: Optional[random.Random] = None,
    *,
    side_a_placement: Optional[list[CombatUnit]] = None,
    side_b_placement: Optional[list[CombatUnit]] = None,
    attacker: int = 0,
) -> BattleState:
    rng = rng or random.Random()
    a = side_a_placement or auto_place(side_a_units, 0)
    b = side_b_placement or auto_place(side_b_units, 1)
    state = BattleState(sides=(a, b), civ_names=civ_names, attacker=attacker)
    state.log.append(
        f"Battle: {civ_names[0]} ({len(a)}) vs {civ_names[1]} ({len(b)})"
    )

    while state.round_num < MAX_ROUNDS:
        state.round_num += 1
        # Roll initiative.
        for u in state.all_units():
            if u.alive:
                u.initiative = u.template.speed + rng.randint(0, 5)
        order = sorted(
            (u for u in state.all_units() if u.alive),
            key=lambda u: -u.initiative,
        )
        occupied = {(u.col, u.row) for u in state.all_units() if u.alive}
        for u in order:
            if not u.alive:
                continue
            enemy_side = 1 - u.side
            enemies = state.alive_units(enemy_side)
            if not enemies:
                break
            target = pick_target(u, enemies)
            if target is None:
                step_toward(u, enemies, occupied)
                target = pick_target(u, enemies)
                if target is None:
                    continue
            dmg = max(1, u.template.attack - target.template.defense)
            target.hp -= dmg
            state.log.append(
                f"R{state.round_num}: {u.name} hits {target.name} for {dmg} (->{max(0, target.hp)} hp)"
            )
            if target.hp <= 0:
                target.alive = False
                occupied.discard((target.col, target.row))
                state.log.append(f"        {target.name} ({civ_names[target.side]}) is destroyed.")
        # End-of-round elimination check.
        a_alive = bool(state.alive_units(0))
        b_alive = bool(state.alive_units(1))
        if not a_alive and not b_alive:
            state.winner = 1 - attacker  # mutual annihilation -> attacker loses
            break
        if not a_alive:
            state.winner = 1
            break
        if not b_alive:
            state.winner = 0
            break

    if state.winner is None:
        # Round cap reached: attacker loses on a draw.
        state.winner = 1 - attacker
        state.log.append("Round cap reached: attacker loses on draw.")
    state.log.append(f"WINNER: {civ_names[state.winner]}")
    return state
