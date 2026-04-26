"""World container: holds the map, all civs, the diplomacy table, and drives
the global turn cycle (player turn -> AI turns -> tick).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from . import ai, config
from .battle import BattleState, resolve_battle
from .cities import (
    CITY_RADIUS,
    City,
    FOUND_CITY_GOLD_COST,
    POP_GROWTH_THRESHOLD_BASE,
    found_city,
    organic_growth,
)
from .civilization import ARCHETYPES, Civilization
from .diplomacy import (
    DISCOVERY_BATTLE_COUNTDOWN,
    DiplomacyTable,
    Relation,
    TRIBUTE_AMOUNT,
)
from .game_state import GameState
from .hexmap import (
    HexMap,
    NEIGHBORS,
    Tile,
    degrade_visible_to_seen,
    find_starting_tiles,
    generate_map,
    hex_distance,
    neighbors,
    reveal_around,
)
from .offerings import Era, UNITS, Unit
from .tech import era_for_total_science, tech_by_name


PLAYER_NAME = "Player"

AI_PRESETS = [
    ("Caesarius",  (220, 96, 96),  "Warmonger"),
    ("Mercatia",   (228, 180, 88), "Merchant"),
    ("Lyceum",     (140, 200, 240), "Scholar"),
]


@dataclass
class PendingBattle:
    attacker: str
    defender: str
    contested_city: Optional[str] = None  # name of city the attacker is going for


class World:
    """Top-level game container.  The pygame app holds exactly one of these."""

    def __init__(
        self,
        seed: Optional[int] = None,
        *,
        num_ai: int = 3,
        map_radius: int = 6,
    ) -> None:
        self.rng = random.Random(seed)
        self.turn: int = 1

        self.map: HexMap = generate_map(radius=map_radius, rng=self.rng)
        self.player = GameState()
        self.player.name = PLAYER_NAME
        self.civs: list = [self.player]
        self.civ_by_name: dict[str, object] = {self.player.name: self.player}

        for i in range(num_ai):
            preset = AI_PRESETS[i % len(AI_PRESETS)]
            archetype = preset[2]
            civ = Civilization(
                name=preset[0],
                color=preset[1],
                archetype=archetype,
                personality=ARCHETYPES[archetype],
            )
            self.civs.append(civ)
            self.civ_by_name[civ.name] = civ

        # Place capitals.
        starts = find_starting_tiles(self.map, len(self.civs), self.rng)
        for civ, coord in zip(self.civs, starts):
            cap = found_city(civ, self.map, coord, capital=True)
            reveal_around(self.map, civ.name, coord, radius=2)
            # Each civ starts with 2 Warriors (or whatever).
            warrior = next(u for u in UNITS if u.name == "Warrior")
            if not isinstance(civ, GameState):
                civ.army.extend([warrior, warrior])

        self.diplomacy = DiplomacyTable()
        self.claimed_wonders: set[str] = set()
        self.broadcast_log: list[str] = []
        self.notifications: list[str] = []
        self.pending_battle: Optional[PendingBattle] = None
        self.last_battle: Optional[BattleState] = None
        self.winner: Optional[str] = None
        self.game_over: bool = False

        # Apply initial visibility for each civ.
        for civ in self.civs:
            for c in civ.cities:
                reveal_around(self.map, civ.name, c.coord(), radius=2)

    # --- helpers -----------------------------------------------------------

    def broadcast(self, msg: str) -> None:
        self.broadcast_log.append(f"T{self.turn}: {msg}")
        self.broadcast_log = self.broadcast_log[-40:]
        self.notifications.append(msg)
        self.notifications = self.notifications[-8:]

    def army_cap(self, civ) -> int:
        tech_tier = self._tech_tier(civ)
        wonders_bonus = 5 if "Pentagon" in civ.wonders else 0
        return config.STARTING_ARMY_CAP + self.turn // 10 + tech_tier * 2 + wonders_bonus

    def _tech_tier(self, civ) -> int:
        return len(civ.research.completed) // 3

    def visible_civs(self, civ) -> list:
        return [c for c in self.civs if c.name in getattr(civ, "discovered", set())]

    # --- per-turn flow -----------------------------------------------------

    def end_player_turn(self) -> list[str]:
        """Advance the world by one turn after the player has acted."""
        log: list[str] = []

        # 1. City output for the player.
        log.extend(self._civ_economic_tick(self.player))

        # 2. AI civs take their turns.
        for civ in self.civs[1:]:
            if not civ.alive:
                continue
            civ.ap = config.ap_for_turn(self.turn)
            log.extend(self._civ_economic_tick(civ))
            log.extend(ai.take_turn(civ, self, self.rng))

        # 3. Era progression: take the max era anyone has reached.
        new_era = max(era_for_total_science(c.research.total_science) for c in self.civs)
        for c in self.civs:
            if new_era > c.era:
                c.era = new_era
                if c is self.player:
                    self.broadcast(f"You enter the {new_era.name.title()} era!")
                else:
                    self.broadcast(f"{c.name} enters the {new_era.name.title()} era.")

        # 4. Discovery: civs whose territory touches another's see them.
        self._update_discovery()

        # 5. Diplomacy timers.  Returns pairs that must fight this turn.
        battle_pairs = self.diplomacy.tick(self.turn)
        for a, b in battle_pairs:
            self._enqueue_battle(a, b)

        # 6. Wonder special: Space Elevator hold-to-win.
        for c in self.civs:
            if "Space Elevator" in c.wonders and not c.capital_lost:
                c.space_elevator_turns += 1
                if c.space_elevator_turns >= 5:
                    self.winner = c.name
                    self.game_over = True
                    self.broadcast(f"{c.name} wins via Space Elevator!")
            else:
                c.space_elevator_turns = 0

        # 7. Win condition check.
        self._check_win()

        # 8. Bump the turn counter and player AP.
        self.turn += 1
        self.player.turn = self.turn
        self.player.begin_turn()

        # 9. Pop any 'visible' fog back to 'seen' before re-revealing.
        for civ in self.civs:
            degrade_visible_to_seen(self.map, civ.name)
            for c in civ.cities:
                reveal_around(self.map, civ.name, c.coord(), radius=2)

        return log

    def _civ_economic_tick(self, civ) -> list[str]:
        """Apply per-turn yields, organic growth, research, building bonuses."""
        log: list[str] = []
        food = gold = sci = 0
        for city in list(civ.cities):
            cf, cg, cs = city.yields(self.map)
            food += cf
            gold += cg
            sci += cs
            # Building bonuses (just the player tracks specific buildings; AI
            # uses the bonuses applied when they buy them).
        # Building bonuses from the civ's purchased buildings (player only).
        from .offerings import BUILDINGS
        bld_index = {b.name: b for b in BUILDINGS}
        for bname in civ.buildings:
            b = bld_index.get(bname)
            if not b:
                continue
            food += b.food_per_turn
            gold += b.gold_per_turn
            sci += b.science_per_turn
        # Wonders that grant per-turn bonuses
        if "Great Library" in civ.wonders:
            sci += 2 * len(civ.cities)
        # Population growth: every city accumulates food.
        for city in list(civ.cities):
            city.food_storage += max(0, food // max(1, len(civ.cities)))
            threshold = POP_GROWTH_THRESHOLD_BASE + city.population * 4
            if city.food_storage >= threshold:
                city.food_storage -= threshold
                city.population += 1
        # Apply gold and research science
        civ.gold += gold
        if sci:
            log.extend(civ.research.add_science(sci))
        # Resources from controlled tiles.
        for tile in self.map:
            if tile.owner == civ.name and tile.resource:
                civ.owned_resources.add(tile.resource)
        # Organic growth.
        new_city = organic_growth(civ, self.map, self.rng)
        if new_city:
            self.broadcast(f"{civ.name} founds {new_city.name} ({new_city.q},{new_city.r}).")
        return log

    def _update_discovery(self) -> None:
        """If any pair of civs has tiles within 2 hexes, they discover each other."""
        owned: dict[str, list[tuple[int, int]]] = {}
        for tile in self.map:
            if tile.owner is not None:
                owned.setdefault(tile.owner, []).append((tile.q, tile.r))
        names = list(owned.keys())
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                for ca in owned[a]:
                    found_pair = False
                    for cb in owned[b]:
                        if hex_distance(ca, cb) <= 4:
                            self._meet(a, b)
                            found_pair = True
                            break
                    if found_pair:
                        break

    def _meet(self, a: str, b: str) -> None:
        ca = self.civ_by_name[a]
        cb = self.civ_by_name[b]
        if b in ca.discovered and a in cb.discovered:
            return
        ca.discovered.add(b)
        cb.discovered.add(a)
        self.broadcast(f"{a} has met {b}.  Battle countdown: {DISCOVERY_BATTLE_COUNTDOWN} turns.")
        self.diplomacy.start_countdown(a, b, DISCOVERY_BATTLE_COUNTDOWN)

    def _enqueue_battle(self, a: str, b: str) -> None:
        ca = self.civ_by_name.get(a)
        cb = self.civ_by_name.get(b)
        if ca is None or cb is None or not ca.alive or not cb.alive:
            return
        # If neither civ is the player, auto-resolve in the background.
        if a != PLAYER_NAME and b != PLAYER_NAME:
            self._resolve_npc_battle(a, b)
            return
        # If a player battle is already queued, NPC opponents auto-resolve
        # against each other to avoid clobbering the queue.
        if self.pending_battle is not None:
            return
        attacker, defender = a, b
        if defender == PLAYER_NAME and attacker != PLAYER_NAME:
            attacker, defender = b, a
        target_city = self._target_city_for(attacker, defender)
        self.pending_battle = PendingBattle(
            attacker, defender, target_city.name if target_city else None,
        )
        self.broadcast(f"BATTLE: {attacker} vs {defender}.  Open the battle screen.")

    def _target_city_for(self, attacker: str, defender: str) -> Optional[City]:
        atk = self.civ_by_name[attacker]
        defc = self.civ_by_name[defender]
        if not atk.cities or not defc.cities:
            return None
        # closest enemy city to any of attacker's cities
        best: Optional[tuple[int, City]] = None
        for ca in atk.cities:
            for cb in defc.cities:
                d = hex_distance(ca.coord(), cb.coord())
                if best is None or d < best[0]:
                    best = (d, cb)
        return best[1] if best else None

    def _resolve_npc_battle(self, a: str, b: str) -> None:
        ca = self.civ_by_name[a]
        cb = self.civ_by_name[b]
        result = resolve_battle(
            list(ca.army), list(cb.army), (a, b), self.rng,
            attacker=0,
        )
        winner = a if result.winner == 0 else b
        loser = b if winner == a else a
        # Reduce loser army by 60%, retain survivors for winner.
        winner_civ = self.civ_by_name[winner]
        loser_civ = self.civ_by_name[loser]
        survivors = [u.template for u in result.sides[result.winner] if u.alive]
        winner_civ.army = survivors[:]
        # Loser keeps any units that weren't engaged - simplification: nothing.
        loser_civ.army = []
        # Capture the contested city, if any.
        target = self._target_city_for(winner, loser)
        if target is not None:
            self._transfer_city(target, loser, winner)
        self.broadcast(f"{winner} defeats {loser} in battle.")
        self.diplomacy.make_peace(a, b)
        self._check_win()

    def resolve_player_battle(
        self,
        result: BattleState,
        attacker: str,
        defender: str,
    ) -> None:
        """Apply the outcome of a player-involved battle."""
        winner = attacker if result.winner == 0 else defender
        loser = defender if winner == attacker else attacker
        winner_civ = self.civ_by_name[winner]
        loser_civ = self.civ_by_name[loser]

        survivors = [cu.template for cu in result.sides[result.winner] if cu.alive]
        # Update the winner's army to just the survivors who fought.
        # (Simplification: the player committed all units in the prototype.)
        winner_civ.army = survivors[:]
        loser_civ.army = []

        # City transfer.
        if self.pending_battle and self.pending_battle.contested_city:
            city = self._city_by_name(self.pending_battle.contested_city)
            if city is not None and city.owner == loser:
                self._transfer_city(city, loser, winner)
        self.broadcast(f"{winner} wins the battle against {loser}.")
        self.diplomacy.make_peace(attacker, defender)
        self.pending_battle = None
        self.last_battle = result
        self._check_win()

    def _city_by_name(self, name: str) -> Optional[City]:
        for civ in self.civs:
            for c in civ.cities:
                if c.name == name:
                    return c
        return None

    def _transfer_city(self, city: City, from_civ_name: str, to_civ_name: str) -> None:
        from_civ = self.civ_by_name[from_civ_name]
        to_civ = self.civ_by_name[to_civ_name]
        if city in from_civ.cities:
            from_civ.cities.remove(city)
        city.owner = to_civ_name
        if city.capital:
            from_civ.capital_lost = True
            # The captured city remains a city but loses capital status.
            city.capital = False
        to_civ.cities.append(city)
        # Re-claim tiles within radius for the new owner.
        for c in self.map.coords():
            t = self.map.tiles[c]
            if hex_distance(city.coord(), c) <= CITY_RADIUS and t.owner == from_civ_name:
                t.owner = to_civ_name
        self.map.tiles[city.coord()].owner = to_civ_name
        self.map.tiles[city.coord()].city = city.name
        self.broadcast(f"{to_civ_name} captures {city.name} from {from_civ_name}.")
        # If the loser has no cities, eliminate them.
        if not from_civ.cities:
            from_civ.eliminated = True
            self.broadcast(f"{from_civ_name} has been eliminated!")

    def _check_win(self) -> None:
        if self.winner is not None:
            return
        living = [c for c in self.civs if c.alive]
        if len(living) == 1:
            self.winner = living[0].name
            self.game_over = True
            self.broadcast(f"{self.winner} achieves DOMINATION VICTORY!")
        elif self.player.eliminated:
            self.winner = "AI"
            self.game_over = True
            self.broadcast("The Player has been eliminated.")

    # --- Player actions that affect the world ------------------------------

    def player_found_city(self, coord: tuple[int, int]) -> str:
        """Called from the GUI when the player wants to gold-found a city."""
        if self.player.gold < FOUND_CITY_GOLD_COST:
            return f"Need {FOUND_CITY_GOLD_COST}g to found a city."
        tile = self.map.get(*coord)
        if tile is None or not tile.buildable:
            return "Invalid tile."
        if tile.owner not in (None, self.player.name):
            return "Tile is owned by another civ."
        # Must be within current borders.
        if tile.owner != self.player.name:
            return "Tile must be within your borders."
        self.player.gold -= FOUND_CITY_GOLD_COST
        new_city = found_city(self.player, self.map, coord)
        reveal_around(self.map, self.player.name, coord, radius=2)
        return f"Founded {new_city.name}."

    def player_declare_war(self, target: str) -> str:
        if target == self.player.name:
            return "Cannot declare war on yourself."
        if target not in self.player.discovered:
            return f"You have not met {target}."
        rel = self.diplomacy.get(self.player.name, target)
        if rel.at_war:
            return "Already at war."
        self.diplomacy.declare_war(self.player.name, target, self.turn)
        self.broadcast(f"You declare WAR on {target}!")
        return f"War declared on {target}."

    def player_make_peace(self, target: str) -> str:
        rel = self.diplomacy.get(self.player.name, target)
        if not rel.at_war:
            return "Not currently at war."
        if self.player.ap < 1:
            return "Need 1 AP."
        self.player.ap -= 1
        self.diplomacy.make_peace(self.player.name, target)
        return f"Made peace with {target}."

    def player_demand_tribute(self, target: str) -> str:
        if self.player.ap < 2:
            return "Need 2 AP."
        if target not in self.player.discovered:
            return f"You have not met {target}."
        self.player.ap -= 2
        target_civ = self.civ_by_name[target]
        # Aggressive AI refuses; others pay.
        agg = getattr(target_civ, "personality", None)
        if agg and agg.aggression > 60:
            self.diplomacy.declare_war(self.player.name, target, self.turn)
            self.broadcast(f"{target} refuses tribute and declares WAR!")
            return f"{target} refuses and declares war."
        if target_civ.gold < TRIBUTE_AMOUNT:
            target_civ.gold = 0
            self.player.gold += target_civ.gold
        else:
            target_civ.gold -= TRIBUTE_AMOUNT
            self.player.gold += TRIBUTE_AMOUNT
        self.diplomacy.adjust(self.player.name, target, -10)
        return f"{target} pays {TRIBUTE_AMOUNT}g tribute."

    def player_open_borders(self, target: str) -> str:
        if self.player.ap < 1:
            return "Need 1 AP."
        if target not in self.player.discovered:
            return "Unknown civ."
        self.player.ap -= 1
        self.diplomacy.open_borders(self.player.name, target)
        return f"Open borders signed with {target}."

    def player_sign_nap(self, target: str) -> str:
        if self.player.ap < 2:
            return "Need 2 AP."
        rel = self.diplomacy.get(self.player.name, target)
        if rel.at_war:
            return "Cannot sign NAP while at war."
        self.player.ap -= 2
        self.diplomacy.sign_nap(self.player.name, target, self.turn)
        return f"NAP signed with {target}."

    def player_alliance(self, target: str) -> str:
        if self.player.ap < 3:
            return "Need 3 AP."
        rel = self.diplomacy.get(self.player.name, target)
        if rel.score < 30:
            return "Relations too low for alliance."
        self.player.ap -= 3
        self.diplomacy.sign_alliance(self.player.name, target)
        return f"Alliance with {target}."

    def player_denounce(self, target: str) -> str:
        if self.player.ap < 1:
            return "Need 1 AP."
        self.player.ap -= 1
        self.diplomacy.denounce(self.player.name, target)
        return f"You denounce {target}."

    def trigger_player_battle_now(self, target: str) -> bool:
        """Force-trigger a battle the player has lined up."""
        if target not in self.player.discovered:
            return False
        rel = self.diplomacy.get(self.player.name, target)
        if not rel.at_war:
            self.diplomacy.declare_war(self.player.name, target, self.turn)
        target_city = self._target_city_for(self.player.name, target)
        self.pending_battle = PendingBattle(
            self.player.name, target, target_city.name if target_city else None
        )
        return True
