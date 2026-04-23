"""Text rendering for the shop loop prototype."""

from __future__ import annotations

from collections import Counter

from .game_state import GameState
from .offerings import Unit
from .shop import Shop


def format_turn_header(state: GameState) -> str:
    paths_str = ", ".join(
        f"{p} {v}" for p, v in state.path_investment.items() if v > 0
    ) or "(none)"
    units_str = format_army(state) or "(none)"
    locked_str = "(none)" if state.locked_slot is None else f"slot {state.locked_slot + 1}"
    return (
        f"=== TURN {state.turn} ===\n"
        f"Gold: {state.gold}  |  AP: {state.ap}  |  Era: {state.era.name.title()}\n"
        f"Paths: {paths_str}\n"
        f"Owned units: {units_str}\n"
        f"Buildings: {', '.join(state.buildings) or '(none)'}\n"
        f"Wonders: {', '.join(state.wonders) or '(none)'}\n"
        f"Locked: {locked_str}  |  Pity: {state.pity_counter}/5"
    )


def format_army(state: GameState) -> str:
    counts: Counter[str] = Counter(u.name for u in state.army)
    return ", ".join(f"{name} x{n}" for name, n in counts.most_common())


def format_shop(shop: Shop) -> str:
    lines = ["SHOP:"]
    for i, slot in enumerate(shop.slots):
        marker = "*" if slot.locked else " "
        off = slot.offering
        req = ""
        if isinstance(off, Unit) and off.required_resource:
            req = f"   [req: {off.required_resource}]"
        label = off.label()
        lines.append(
            f" {marker}[{i + 1}] {off.name:<22} ({label:<18}) {slot.price}g{req}"
        )
    lines.append(f"Next reroll cost: {shop.state.reroll_cost()}g")
    return "\n".join(lines)


HELP_TEXT = """Commands:
  buy <slot>          - purchase an offering (1-8)
  reroll              - refresh shop (costs escalating gold)
  lock <slot>         - lock a slot (5g)
  unlock              - unlock the currently locked slot
  path <name>         - invest 1 AP in a path (Melee/Ranged/Cavalry/Navy/Siege)
  muster <path>       - spend 1 AP for a guaranteed unit from an invested path
  status              - show full state
  help                - show this help text
  end                 - end turn
  quit                - exit prototype
"""
