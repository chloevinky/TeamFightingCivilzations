"""Entry point: REPL and command parser for the shop loop prototype.

Run with:
    python -m src.main
"""

from __future__ import annotations

import random
import sys
from typing import Optional

from . import config, paths
from .display import HELP_TEXT, format_shop, format_turn_header
from .game_state import GameState
from .offerings import PATHS, UNITS, Unit
from .shop import Shop


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    seed = None
    for a in argv:
        if a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
    rng = random.Random(seed)

    state = GameState()
    shop = Shop(state, rng=rng)
    shop.refresh(is_free=True)

    print("Hexfall — Shop Loop Prototype")
    print(HELP_TEXT)
    _print_turn(state, shop)

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not raw:
            continue
        parts = raw.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "quit" or cmd == "exit":
            return 0
        if cmd == "help":
            print(HELP_TEXT)
            continue
        if cmd == "status":
            _print_turn(state, shop)
            continue
        if cmd == "end":
            _end_turn(state, shop)
            _print_turn(state, shop)
            continue
        if cmd == "buy":
            print(_handle_buy(shop, args))
            continue
        if cmd == "reroll":
            print(shop.paid_reroll())
            _print_shop(shop)
            continue
        if cmd == "lock":
            print(_handle_lock(shop, args))
            _print_shop(shop)
            continue
        if cmd == "unlock":
            print(shop.unlock())
            _print_shop(shop)
            continue
        if cmd == "path":
            print(_handle_path(state, args))
            continue
        if cmd == "muster":
            print(_handle_muster(state, args))
            continue

        print(f"Unknown command: {cmd!r}. Type 'help'.")


# --- command handlers ---

def _handle_buy(shop: Shop, args: list[str]) -> str:
    if len(args) != 1:
        return "Usage: buy <slot>"
    try:
        idx = int(args[0]) - 1
    except ValueError:
        return "Slot must be a number."
    return shop.buy(idx)


def _handle_lock(shop: Shop, args: list[str]) -> str:
    if len(args) != 1:
        return "Usage: lock <slot>"
    try:
        idx = int(args[0]) - 1
    except ValueError:
        return "Slot must be a number."
    return shop.lock(idx)


def _handle_path(state: GameState, args: list[str]) -> str:
    if len(args) != 1:
        return f"Usage: path <{'|'.join(PATHS)}>"
    name = _match_path(args[0])
    if name is None:
        return f"Unknown path. Options: {', '.join(PATHS)}"
    if state.ap < config.PATH_INVEST_AP_COST:
        return "Not enough AP."
    state.ap -= config.PATH_INVEST_AP_COST
    paths.invest(state.path_investment, name)
    return (
        f"Invested 1 AP in {name} (now {state.path_investment[name]}). "
        f"Traits for {name}: {', '.join(paths.traits_for(name, state.path_investment)) or 'none'}."
    )


def _handle_muster(state: GameState, args: list[str]) -> str:
    if len(args) != 1:
        return f"Usage: muster <{'|'.join(PATHS)}>"
    name = _match_path(args[0])
    if name is None:
        return f"Unknown path. Options: {', '.join(PATHS)}"
    if state.mustered_this_turn:
        return "Already mustered this turn."
    if state.path_investment.get(name, 0) <= 0:
        return f"Cannot muster from {name}: no investment."
    if state.ap < config.MUSTER_AP_COST:
        return "Not enough AP."

    tier = paths.muster_tier(state.path_investment, name)
    candidates = [
        u for u in UNITS
        if u.path == name and u.tier <= tier and u.required_resource is None
    ]
    if not candidates:
        return f"No mustering candidates for {name} at tier {tier}."
    # pick the highest available tier up to the cap
    pick = max(candidates, key=lambda u: u.tier)

    state.ap -= config.MUSTER_AP_COST
    state.mustered_this_turn = True
    messages = [f"Mustered {pick.name} ({pick.path} T{pick.tier})."]
    messages.extend(state.add_unit(pick))
    return "\n".join(messages)


def _match_path(arg: str) -> Optional[str]:
    arg = arg.lower()
    for p in PATHS:
        if p.lower() == arg:
            return p
    return None


# --- turn flow ---

def _end_turn(state: GameState, shop: Shop) -> None:
    state.end_turn()
    state.begin_turn()
    shop.refresh(is_free=True)


def _print_turn(state: GameState, shop: Shop) -> None:
    print()
    print(format_turn_header(state))
    print()
    _print_shop(shop)


def _print_shop(shop: Shop) -> None:
    print(format_shop(shop))


if __name__ == "__main__":
    raise SystemExit(main())
