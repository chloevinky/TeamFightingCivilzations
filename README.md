# Hexfall

> A hex-based 4X strategy game with autochess army composition. Compressed turns, rare decisive battles, one shop to rule them all.

## Overview

Hexfall is a turn-based strategy game inspired by Civilization but restructured around autochess mechanics. Players manage a civilization on a procedurally generated hex map, expanding through economic growth, investing in military doctrines, and composing armies from a randomized recruitment shop. Battles are infrequent but decisive: they transition to a separate tactical grid where units auto-resolve based on positioning, composition, and synergies.

The design goals are:

- **Compressed, dense turns** — every turn has multiple meaningful decisions.
- **No unit micromanagement on the map** — units exist abstractly until battle.
- **Rare, high-stakes combat** — battles punctuate an economic/strategic game rather than dominating it.
- **Unified shop economy** — units, buildings, wonders, and events all flow through a single decision surface.
- **Domination-only win condition** — every system serves the question of whether your armies are ready when war comes.

Target run length: **60–90 minutes**.

---

## Table of Contents

1. [Game Design](#game-design)
   1. [Map](#map)
   2. [Cities and Expansion](#cities-and-expansion)
   3. [Turns and Action Points](#turns-and-action-points)
   4. [The Shop](#the-shop)
   5. [Skill Tree Paths](#skill-tree-paths)
   6. [Unit Tier-Up](#unit-tier-up)
   7. [Army Management](#army-management)
   8. [Battles](#battles)
   9. [Diplomacy](#diplomacy)
   10. [Technology](#technology)
   11. [Eras and Wonders](#eras-and-wonders)
   12. [Events](#events)
   13. [AI Civilizations](#ai-civilizations)
   14. [Win Condition](#win-condition)
2. [Starting Values and Formulas](#starting-values-and-formulas)
3. [Development Roadmap](#development-roadmap)
4. [Starting Point: Shop Loop Prototype](#starting-point-shop-loop-prototype)
5. [Project Structure](#project-structure)
6. [Running the Prototype](#running-the-prototype)

---

## Game Design

### Map

The game takes place on a hex-based map, procedurally generated per game. The map contains terrain types (plains, forest, mountain, desert, coast, ocean), resources tied to specific tiles (iron, horses, oil, wheat, etc.), and natural features. Fog of war covers unexplored hexes.

Multiple civilizations share the map — the player and AI opponents. Civilizations are represented by their cities and territorial borders. **Units never appear on the map**; they exist in an abstract army layer and only materialize on the battle grid when combat triggers.

### Cities and Expansion

Cities occupy a single hex and control the surrounding hexes within a radius, forming borders. Controlled hexes provide resource access and contribute to per-turn output of gold, science, and population.

Expansion happens two ways:

- **Organic growth**: When a city's population crosses a threshold, it automatically founds a new city on a valid adjacent hex.
- **Gold-purchased founding**: The player can spend gold to manually found a city on any valid hex within their borders.

Expansion is tied directly to the economy. A thriving empire sprawls naturally; a stagnant one stays small.

### Turns and Action Points

Each turn the player receives **Action Points (AP)** on a fixed, turn-scaling curve. AP is the strategic currency — it governs what kind of civilization you are becoming.

| Turn Range | AP per Turn |
|------------|-------------|
| 1–10       | 3           |
| 11–25      | 4           |
| 26–50      | 5           |
| 51–75      | 6           |
| 76–100     | 7           |
| 101+       | 8 (cap)     |

AP does **not** scale with economy, tech, or wonders, with two exceptions: the Colosseum wonder (+1 permanent) and specific Governance tech nodes (+1 each, limited). This keeps pacing predictable.

AP is spent across parallel systems:

- Skill tree path investment
- Proactive diplomacy
- Technology research direction
- Economic upgrades
- Targeted muster (guaranteed unit summon)

Gold income accumulates each turn from cities and economic upgrades. **Gold carries over between turns; AP does not.**

### The Shop

The shop is the core decision surface of the game. Every turn it presents **8 randomized offerings** drawn from multiple categories.

**Category distribution (enforced floors):**

- 3 Unit slots (minimum)
- 2 Building slots (minimum)
- 1 Special slot (Wonder or Event)
- 2 Flex slots (filled by weighted random draw)

**Shop economy:**

- 1 free refresh per turn at turn start
- Additional rerolls cost gold, escalating within the turn: 2 → 4 → 8 → 16 → 32 (resets next turn)
- Purchases cost gold (or gold + resources for some offerings)
- Player may lock 1 offering between refreshes for a small gold cost (5g); locked offerings persist until purchased or unlocked

**Flex slot weighting factors (applied top-down):**

1. Category floors satisfied first
2. Era-appropriate offerings filtered in
3. Path investment depth biases unit and building categories
4. Diplomatic history biases event types (friendly history → resource-sharing events; hostile history → military events)
5. Remaining flex slots filled randomly from the eligible pool

### Skill Tree Paths

Skill tree paths define military doctrines. Starting paths:

- **Melee**
- **Ranged**
- **Cavalry**
- **Navy**
- **Siege**
- **Airforce** (unlocks from Industrial era)

Investing AP in a path does four things:

1. **Unlocks** unit types in that path (gated by minimum investment).
2. **Weights** the shop toward that path's units and related buildings.
3. **Applies passive stat buffs** to units of that path.
4. **Bleeds traits** into units of other paths (see Trait Bleed).

**Pity timer:** If the shop has not offered a unit from the player's deepest-invested path across 5 consecutive rerolls, the next refresh guarantees one from that path.

**Targeted Muster:** Once per turn, the player may spend 1 AP to summon a guaranteed unit from an invested path. Unit tier scales with investment depth in that path.

**Trait Bleed (starting table):**

| Investment            | Grants Trait To                      |
|-----------------------|--------------------------------------|
| Navy ≥ 2              | Amphibious → Melee units             |
| Airforce ≥ 2          | Recon → all units                    |
| Cavalry ≥ 2           | Charge → Melee units                 |
| Siege ≥ 2             | Siege → Ranged units                 |
| Ranged ≥ 2            | Volley → Siege units                 |
| Melee ≥ 2             | Guard → Ranged and Siege units       |

### Unit Tier-Up

Three identical units of the same tier automatically combine into one unit of the next tier.

Some tier-ups require a specific unlocked resource. Resources are unlocked through map tile control and technology research.

**Example progression:**

- 3 Warriors → 1 Super Warrior
- 2 Warriors + Iron → 1 Swordsman
- 2 Swordsmen + Horses → 1 Knight

### Army Management

Purchased units live in an army menu, separate from the map. Units have no location until a battle begins.

**Army cap formula:**

```
Army Cap = 5 + (Turn / 10) + (Tech Tier × 2) + Wonder bonuses
```

| Turn | Tech Tier | Wonders      | Cap |
|------|-----------|--------------|-----|
| 10   | 1         | —            | 8   |
| 30   | 3         | —            | 14  |
| 60   | 5         | —            | 21  |
| 100  | 7         | Pentagon(+5) | 34  |

### Battles

Battles are infrequent, high-stakes, and automated in execution but player-directed in setup.

**Triggers:**

- On discovering an AI civilization, a **15-turn countdown** begins.
- When the countdown expires, battle auto-triggers.
- Either side may declare war early, triggering battle immediately.

**Battle flow:**

1. Game transitions from map view to battle screen.
2. Battle screen shows a tactical grid (8 columns × 4 rows per side, 8×8 total).
3. Player positions their units on their half of the grid.
4. Combat auto-resolves:
   - Units roll initiative (speed + random 0–5).
   - Units act in initiative order, targeting per AI priority (lowest HP in range, front-row first, trait overrides).
   - Damage = `max(1, attack - defense)`.
   - Round ends after all units act.
   - Combat ends at elimination or 20-round cap (draw → attacker loses).
5. Winner claims contested territory. Captured cities transfer ownership and continue operating. Nothing is permanently destroyed.
6. Surviving units return to the army menu. Dead units are removed permanently.

**Row effects:**

- Front row: engages melee first, absorbs first hits.
- Back row: protected, suited for ranged/support.
- Column placement affects flanking and area attacks.

### Diplomacy

Diplomacy operates as a **separate proactive system** alongside the shop (which generates passive diplomatic offerings in its Event slots). Proactive actions cost AP:

| Action              | AP Cost | Effect                                                                 |
|---------------------|---------|------------------------------------------------------------------------|
| Open Borders        | 1       | Allows scouting target civ's territory                                |
| Trade Offer         | 1       | Opens trade menu (gold / resources / tech)                            |
| Non-Aggression Pact | 2       | Neither civ can declare war for 10 turns (both must agree)            |
| Alliance            | 3       | Mutual defense; requires high relations                               |
| Denounce            | 1       | Damages relations; increases shop weighting of military events        |
| Demand Tribute      | 2       | Target pays gold or war begins immediately                            |

**Relations scale:** −100 (hostile) to +100 (allied). Modified by actions, proximity, path similarity, and accepted or rejected offers.

Early friendly diplomatic behavior increases the weighting of diplomatic events appearing in future shops.

### Technology

Technology has two tracks:

1. **Passive research**: Each city generates science per turn, accumulating toward the currently researched tech.
2. **Tech boosts**: Shop events that inject instant progress on current research.

**Tech branches (extensible):**

- **Agriculture** — population caps, growth rate, food resources
- **Engineering** — building unlocks, construction, wonder prerequisites
- **Metallurgy** — resource unlocks (iron, steel), tier-up enablers
- **Economics** — gold multipliers, shop cost reductions
- **Military** — path unlocks, unit tier caps, combat traits
- **Governance** — one-time AP bonuses, diplomatic capacity

Each era contains 4–6 techs across branches. One active research slot at a time.

### Eras and Wonders

Era advances globally when any civilization accumulates enough cumulative science. When the era advances, new offerings enter the shop pool for all players; previous-era offerings phase out (they stop appearing in new shops but owned instances retain their value).

**Eras:** Ancient → Classical → Medieval → Renaissance → Industrial → Modern → Atomic

**Wonders: 1 per era, 7 total per game.** Each is unique, permanent, and global. First civilization to purchase it owns it; it disappears from all shops.

| Era         | Wonder               | Effect                                                            |
|-------------|----------------------|-------------------------------------------------------------------|
| Ancient     | Great Library        | +2 science per city; pity timer reduced by 1 reroll               |
| Classical   | Colosseum            | +1 AP per turn, permanent                                         |
| Medieval    | Grand Bazaar         | +1 shop slot; reduced reroll costs                                |
| Renaissance | Royal Observatory    | Reveal all enemy army composition before battles                  |
| Industrial  | Statue of Liberty    | +1 free refresh per turn                                          |
| Modern      | Pentagon             | Army cap +5                                                       |
| Atomic      | Space Elevator       | Auto-win if held for 5 consecutive turns without losing a city    |

### Events

Events occupy the Special shop slot alongside wonders. They are one-time purchases that resolve immediately.

**Starting event types:**

- **Mercenary Contract** — Pay gold, receive a tier-2 unit from any unlocked path
- **Foreign Scholar** — Pay gold, instantly complete 25% of current research
- **Migration Wave** — Pay gold, one city gains population immediately
- **Resource Cache** — Pay gold, temporary access to a random resource for 5 turns
- **Veteran Trainer** — Pay gold, one owned unit gains a permanent trait
- **Black Market** — Pay gold, immediately tier-up any one unit regardless of count
- **Spy Network** — Pay gold, reveal a rival civ's army composition and tech level
- **Rebellious City** — Pay gold, flip a contested enemy city to neutral

### AI Civilizations

Each AI civilization has personality weights assigned at game start:

- Aggression (0–100)
- Economic (0–100)
- Scientific (0–100)
- Diplomatic (0–100)

**Behavior loop:** Each turn the AI spends AP and gold proportional to its weights.

**War logic:** AI declares war when `aggression × (own military / player military) > threshold`.

**Diplomatic logic:** High diplomatic weight → generates many offers. Low diplomatic weight → ignores player overtures.

**Target selection:** AI targets the weakest discovered rival first.

**Starting archetypes:**

- **Warmonger** — High aggression, low diplomatic. Declares war early, snowballs military.
- **Merchant** — High economic and diplomatic. Rich, sends many offers, weaker army.
- **Scholar** — High scientific, medium diplomatic. Tech-rushes and builds wonders aggressively.

### Win Condition

**Domination only.** The player wins by capturing the capital of every AI civilization, or by eliminating all AI civilizations.

---

## Starting Values and Formulas

| Value                                      | Starting Value |
|--------------------------------------------|----------------|
| Starting AP (turn 1)                       | 3              |
| Starting gold                              | 100            |
| Starting cities                            | 1 (capital)    |
| Starting army cap                          | 5              |
| Starting units                             | 2 Warriors     |
| Pity timer threshold                       | 5 rerolls      |
| Discovery-to-battle countdown              | 15 turns       |
| Starting relations with AI                 | 0 (neutral)    |
| Lock slot cost                             | 5 gold         |
| Reroll cost curve                          | 2 → 4 → 8 → 16 → 32 |
| Era price multiplier                       | ×1.5 per era   |

**Ancient era base prices:**

| Offering              | Gold |
|-----------------------|------|
| Tier 1 Unit           | 20   |
| Tier 2 Unit           | 60   |
| Tier 3 Unit           | 180  |
| Basic Building        | 50   |
| Advanced Building     | 120  |
| Wonder                | 500  |
| Event                 | 30–200 (varies) |
| Found City            | 150  |

---

## Development Roadmap

Development proceeds in phases. Each phase builds on the previous and is playable on its own.

1. **Shop loop prototype** (current phase) — text UI, validates the core shop mechanics.
2. **Economy layer** — abstract cities that generate gold and science per turn.
3. **Tech tree and eras** — passive research, era transitions expand shop pool.
4. **Path trait bleed and targeted muster** — full skill tree mechanics.
5. **Diplomacy panel** — proactive diplomacy alongside shop events.
6. **Army cap and management** — enforce caps, display army composition.
7. **Battle prototype** — separate tactical grid, auto-resolve combat.
8. **AI opponents** — parallel AI civilizations running their own shops and economies.
9. **Map generation and territory** — hex map, city placement, border growth.
10. **GUI migration** — move from text UI to Godot or Arcade once mechanics are locked.

---

## Starting Point: Shop Loop Prototype

### Scope

The prototype implements the minimum viable shop interaction loop:

- Player state: gold, AP, path investment, owned units, locked slot, turn counter
- Shop generates 8 randomized offerings per turn respecting category floors and path weighting
- Commands for buy, reroll, lock, path investment, targeted muster, end turn
- Tier-up logic (3 identical units auto-combine)
- Pity timer tracking
- State persists across turns

**Explicitly out of scope for this phase:** map, cities, battles, actual diplomacy, AI opponents, resources for tier-up gating, wonders/events resolving effects (they print effects but don't modify the game).

### Why Text UI First

- Iteration on mechanics takes hours instead of days
- No rendering, no asset pipeline, no UI framework overhead
- Logic is portable to any engine later
- Forces focus on game feel through mechanics, not visuals

### Tech Stack

- **Python 3.11+**
- Standard library only for the prototype — no dependencies
- Text-based I/O, runs in any terminal

### Build Order

1. **Data layer** — define offerings (units, buildings, events, wonders) as dataclasses in `offerings.py`
2. **Game state** — `GameState` class in `game_state.py` tracking all player state
3. **Shop generator** — `Shop` class in `shop.py` handling generation, reroll, lock, purchase
4. **Paths module** — path investment, weighting, pity timer, trait bleed logic
5. **Turn loop** — `main.py` implementing the REPL, command parser, display
6. **Tier-up logic** — auto-combine on 3 identical units
7. **Tuning iteration** — play 20+ turns, adjust `config.py` constants

### Key Questions the Prototype Should Answer

1. Does 8 slots feel right, or crowded, or sparse?
2. Is the escalating reroll cost the right shape?
3. Does path investment visibly bias the shop?
4. Does the pity timer fire at a satisfying frequency?
5. Is locking worth the 5g cost — do players actually use it?
6. Can a "good shop turn" and a "bad shop turn" be distinguished?

### Expected Turn Display

```
=== TURN 5 ===
Gold: 145  |  AP: 4
Paths: Melee 2, Navy 1
Owned units: Warrior x2, Archer x1, Raft x1
Locked: (none)

SHOP:
[1] Warrior          (Melee T1)     20g
[2] Archer           (Ranged T1)    20g
[3] Horseman         (Cavalry T2)   60g   [req: Horses]
[4] Library          (Building)     50g
[5] Market           (Building)     50g
[6] Mercenary Contract (Event)      100g
[7] Swordsman        (Melee T2)     60g   [req: Iron]
[8] Raft             (Navy T1)      20g

Commands:
  buy <slot>          - purchase an offering
  reroll              - refresh shop (costs escalating gold)
  lock <slot>         - lock a slot (5g)
  unlock              - unlock the currently locked slot
  path <name>         - invest 1 AP in a path
  muster <path>       - spend 1 AP for guaranteed unit from invested path
  status              - show full state
  end                 - end turn
  quit                - exit prototype

>
```

---

## Project Structure

```
TeamFightingCivilzations/
├── README.md
├── LICENSE
├── requirements.txt              # pygame (for the graphical prototype)
├── src/
│   ├── __init__.py
│   ├── main.py                   # text REPL, command parser
│   ├── config.py                 # tunable constants
│   ├── game_state.py             # GameState class
│   ├── shop.py                   # Shop class, generation logic
│   ├── paths.py                  # path investment, weighting, trait bleed
│   ├── offerings.py              # data definitions
│   ├── display.py                # text formatting
│   └── gui/                      # graphical prototype (pygame)
│       ├── __init__.py
│       ├── __main__.py           # `python -m src.gui`
│       ├── app.py                # main App class, rendering, input
│       ├── theme.py              # palette, layout constants
│       └── widgets.py            # Button and panel helpers
└── tests/
    └── test_shop_distribution.py # statistical tests on shop generation
```

---

## Running the Prototype

Clone the repo and launch either the text or the graphical prototype.

### Text prototype (no dependencies)

```bash
git clone https://github.com/chloevinky/TeamFightingCivilzations.git
cd TeamFightingCivilzations
python -m src.main
```

### Graphical prototype (pygame)

```bash
pip install -r requirements.txt
python -m src.gui
```

Requires Python 3.11+ and pygame 2.5+. Pass `--seed=N` for a reproducible run.

**Controls:**

- **Left click** a shop card to buy.
- **Right click** a shop card to lock / unlock (5g).
- **`+`** buttons in the paths panel invest 1 AP in that path.
- **Muster** buttons appear for invested paths and cost 1 AP.
- **Reroll** and **End Turn** buttons sit in the bottom bar.
- Keyboard: **`1`–`8`** buy, **`R`** reroll, **`Space`** end turn, **`Esc`** quit.

The graphical prototype is a visual skin over the text shop loop — all game
logic lives in `src/game_state.py`, `src/shop.py`, and `src/paths.py` and is
shared between the two front ends.

---

## Contributing

This is a personal design and prototype project. Contributions, suggestions, and issues are welcome once the shop loop is playable.

## License

TBD.
