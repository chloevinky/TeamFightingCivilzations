"""AI civilization behavior loop.

The AI runs a simplified version of the player's actions: it pulls a few
random offerings, picks the best by personality, invests AP across paths,
proposes diplomacy, and decides to declare war when its army outmatches the
player.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from . import paths as paths_module
from .civilization import Civilization
from .offerings import (
    BUILDINGS,
    EVENTS,
    PATHS,
    UNITS,
    WONDERS,
    Building,
    Event,
    Offering,
    Unit,
    Wonder,
    price_for,
)
from .tech import TECHS, Tech, tech_by_name


if TYPE_CHECKING:
    from .world import World


def take_turn(civ: Civilization, world: "World", rng: random.Random) -> list[str]:
    """Run one turn of AI actions.  Returns log lines (mostly invisible
    to the player; some surface as diplomatic notifications).
    """
    log: list[str] = []
    if not civ.alive:
        return log

    # 1. Pick a research direction if none.
    if civ.research.current is None:
        avail = civ.research.available(civ.era)
        if avail:
            preferred = _preferred_branch(civ)
            choices = sorted(avail, key=lambda t: (
                0 if t.branch == preferred else 1, t.cost
            ))
            civ.research.set_research(choices[0].name)

    # 2. Spend AP
    while civ.ap > 0:
        action = _pick_ap_action(civ, world, rng)
        if action is None:
            break
        if not action():
            break

    # 3. Buy offerings if gold permits.
    pool = _ai_shop(civ, world, rng)
    pool.sort(key=lambda o: -_score_offering(civ, o))
    for off in pool:
        price = price_for(off, civ.era)
        if civ.gold < price:
            continue
        if isinstance(off, Wonder):
            if off.name in world.claimed_wonders:
                continue
            civ.gold -= price
            civ.wonders.append(off.name)
            world.claimed_wonders.add(off.name)
            world.broadcast(f"{civ.name} builds the wonder: {off.name}.")
            _apply_wonder(civ, off)
        elif isinstance(off, Unit):
            civ.gold -= price
            _ai_add_unit(civ, off)
        elif isinstance(off, Building):
            civ.gold -= price
            civ.buildings.append(off.name)
        elif isinstance(off, Event):
            civ.gold -= price
            log.append(f"{civ.name} resolves event: {off.name}")
        if civ.gold < 30:
            break

    # 4. Diplomacy
    log.extend(_ai_diplomacy(civ, world, rng))
    return log


def _preferred_branch(civ: Civilization) -> str:
    p = civ.personality
    weights = {
        "Military": p.aggression,
        "Metallurgy": (p.aggression + p.economic) // 2,
        "Economics": p.economic,
        "Agriculture": p.economic,
        "Engineering": (p.economic + p.scientific) // 2,
        "Governance": p.diplomatic,
    }
    return max(weights, key=weights.get)


def _ai_shop(civ: Civilization, world: "World", rng: random.Random) -> list[Offering]:
    """Pick a small random pool of offerings the AI 'sees' this turn."""
    units = [u for u in UNITS if u.era <= civ.era]
    builds = [b for b in BUILDINGS if b.era <= civ.era]
    wonders = [w for w in WONDERS if w.era <= civ.era and w.name not in world.claimed_wonders]
    events = [e for e in EVENTS if e.era <= civ.era]
    pool: list[Offering] = []
    pool.extend(rng.sample(units, k=min(4, len(units))))
    pool.extend(rng.sample(builds, k=min(2, len(builds))))
    if wonders:
        pool.append(rng.choice(wonders))
    if events:
        pool.append(rng.choice(events))
    return pool


def _score_offering(civ: Civilization, off: Offering) -> float:
    p = civ.personality
    if isinstance(off, Wonder):
        # Wonders are very valuable, especially Pentagon for warmongers,
        # Great Library for scholars.
        score = 200.0
        if off.name == "Pentagon":
            score += p.aggression
        if off.name in ("Great Library", "Royal Observatory"):
            score += p.scientific
        if off.name in ("Grand Bazaar", "Statue of Liberty"):
            score += p.economic
        return score
    if isinstance(off, Unit):
        return 50.0 + off.tier * 30 + p.aggression / 2 + civ.path_investment.get(off.path, 0) * 10
    if isinstance(off, Building):
        sb = off.science_per_turn * 8 + off.gold_per_turn * 6 + off.food_per_turn * 4
        return 30.0 + sb + (p.economic + p.scientific) / 4
    if isinstance(off, Event):
        return 20.0 + p.diplomatic / 5
    return 0.0


def _pick_ap_action(civ: Civilization, world: "World", rng: random.Random):
    """Return a callable that consumes 1 AP, or None if nothing useful."""
    p = civ.personality
    # Probability-weighted choice between investing in a path and diplomacy.
    options = []
    if civ.ap >= 1:
        options.append(("invest_path", p.aggression + 30))
    if civ.ap >= 1:
        options.append(("muster", p.aggression))
    living_rels = [
        r for r in world.diplomacy.all_for(civ.name)
        if world.civ_by_name[r.other(civ.name)].alive
    ]
    if civ.ap >= 2 and any(rel.score > 30 for rel in living_rels):
        options.append(("alliance", p.diplomatic))
    if civ.ap >= 2 and living_rels:
        options.append(("nap", p.diplomatic))
    if civ.ap >= 1 and living_rels:
        options.append(("denounce", 100 - p.diplomatic))
    if not options:
        return None
    total = sum(w for _, w in options)
    if total <= 0:
        return None
    r = rng.random() * total
    acc = 0.0
    chosen = options[0][0]
    for name, w in options:
        acc += w
        if r <= acc:
            chosen = name
            break

    if chosen == "invest_path":
        path = _ai_pick_path(civ, rng)
        def action():
            if civ.ap < 1:
                return False
            civ.ap -= 1
            paths_module.invest(civ.path_investment, path)
            return True
        return action
    if chosen == "muster":
        path = max(civ.path_investment, key=civ.path_investment.get)
        if civ.path_investment.get(path, 0) <= 0:
            return None
        def action():
            if civ.ap < 1:
                return False
            tier = paths_module.muster_tier(civ.path_investment, path)
            cands = [u for u in UNITS if u.path == path and u.tier <= tier
                     and u.required_resource is None and u.era <= civ.era]
            if not cands:
                return False
            pick = max(cands, key=lambda u: u.tier)
            civ.ap -= 1
            _ai_add_unit(civ, pick)
            return True
        return action
    if chosen == "alliance":
        rels = [r for r in world.diplomacy.all_for(civ.name)
                if r.score > 30 and not r.alliance
                and world.civ_by_name[r.other(civ.name)].alive]
        if not rels:
            return None
        rel = rng.choice(rels)
        other = rel.other(civ.name)
        def action():
            if civ.ap < 2:
                return False
            civ.ap -= 2
            world.diplomacy.sign_alliance(civ.name, other)
            world.broadcast(f"{civ.name} and {other} form an alliance.")
            return True
        return action
    if chosen == "nap":
        rels = [r for r in world.diplomacy.all_for(civ.name)
                if not r.at_war and not r.nap_until_turn
                and world.civ_by_name[r.other(civ.name)].alive]
        if not rels:
            return None
        rel = rng.choice(rels)
        other = rel.other(civ.name)
        def action():
            if civ.ap < 2:
                return False
            civ.ap -= 2
            world.diplomacy.sign_nap(civ.name, other, world.turn)
            world.broadcast(f"{civ.name} signs a non-aggression pact with {other}.")
            return True
        return action
    if chosen == "denounce":
        rels = [r for r in world.diplomacy.all_for(civ.name)
                if world.civ_by_name[r.other(civ.name)].alive]
        if not rels:
            return None
        rel = rng.choice(rels)
        other = rel.other(civ.name)
        def action():
            if civ.ap < 1:
                return False
            civ.ap -= 1
            world.diplomacy.denounce(civ.name, other)
            world.broadcast(f"{civ.name} denounces {other}.")
            return True
        return action
    return None


def _ai_pick_path(civ: Civilization, rng: random.Random) -> str:
    p = civ.personality
    weights = {
        "Melee":  60 + p.aggression / 2,
        "Ranged": 50,
        "Cavalry": 40 + p.aggression / 3,
        "Navy":   30,
        "Siege":  40 + p.aggression / 4,
    }
    if civ.era >= 4:
        weights["Airforce"] = 40
    total = sum(weights.values())
    r = rng.random() * total
    acc = 0.0
    for path, w in weights.items():
        acc += w
        if r <= acc:
            return path
    return "Melee"


def _ai_add_unit(civ: Civilization, unit: Unit) -> None:
    """Add a unit to AI civ's army with the same tier-up rules as the player."""
    civ.army.append(unit)
    _resolve_tier_ups(civ)


def _resolve_tier_ups(civ: Civilization) -> None:
    from .game_state import _next_tier
    changed = True
    while changed:
        changed = False
        counts: dict[Unit, int] = {}
        for u in civ.army:
            counts[u] = counts.get(u, 0) + 1
        for unit, count in counts.items():
            if count < 3:
                continue
            up = _next_tier(unit)
            if up is None:
                continue
            for _ in range(3):
                civ.army.remove(unit)
            civ.army.append(up)
            changed = True
            break


def _apply_wonder(civ: Civilization, w: Wonder) -> None:
    if w.name == "Colosseum":
        # +1 AP next turn (added in begin_turn)
        civ.ap += 1
    if w.name == "Pentagon":
        pass  # consulted by army cap formula
    if w.name == "Statue of Liberty":
        pass


def _ai_diplomacy(civ: Civilization, world: "World", rng: random.Random) -> list[str]:
    log = []
    p = civ.personality
    # Decide war: aggression × (own_strength / target_strength) > threshold.
    for other in world.civs:
        if other.name == civ.name or not other.alive:
            continue
        if other.name not in civ.discovered:
            continue
        rel = world.diplomacy.get(civ.name, other.name)
        if rel.at_war or rel.alliance:
            continue
        if rel.nap_until_turn is not None:
            continue
        own = max(1, civ.army_strength())
        opp = max(1, other.army_strength())
        ratio = own / opp
        score = (p.aggression / 100.0) * ratio
        if score > 1.4 and rng.random() < 0.35:
            world.diplomacy.declare_war(civ.name, other.name, world.turn)
            world.broadcast(f"{civ.name} declares WAR on {other.name}!")
            log.append(f"{civ.name} -> WAR -> {other.name}")
    return log
