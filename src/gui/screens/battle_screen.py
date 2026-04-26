"""Battle screen: place units, auto-resolve combat, show outcome."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pygame

from ...battle import (
    BattleState,
    CombatUnit,
    GRID_COLS_PER_SIDE,
    GRID_COLS_TOTAL,
    GRID_ROWS,
    auto_place,
    resolve_battle,
)
from .. import theme
from ..widgets import Button, draw_panel

if TYPE_CHECKING:
    from ..app import App


class BattleScreen:
    name = "BATTLE"

    def __init__(self) -> None:
        self.buttons: list[Button] = []
        self.placement: Optional[list[CombatUnit]] = None
        self.battle_result: Optional[BattleState] = None
        self.attacker: str = ""
        self.defender: str = ""
        self.dragging: Optional[CombatUnit] = None
        self.cell_size = 56

    def enter(self, app: "App") -> None:
        pb = app.world.pending_battle
        if pb is None:
            return
        self.attacker = pb.attacker
        self.defender = pb.defender
        # Player is always rendered as side 0 (left) for clarity.
        if app.world.player.name == self.attacker:
            self.player_side = 0
        else:
            self.player_side = 0  # always show player on the left
            # but the attacker label is the actual attacker
        self.placement = auto_place(list(app.world.player.army), 0)
        self.battle_result = None
        self.rebuild(app)

    def rebuild(self, app: "App") -> None:
        self.buttons = [
            Button(
                (theme.PAD + 10, theme.HEIGHT - theme.BOTTOM_BAR_H - 50, 200, 38),
                "Auto-arrange",
                lambda: self._auto_arrange(app),
                accent=theme.AP,
            ),
            Button(
                (theme.WIDTH - 220 - theme.PAD, theme.HEIGHT - theme.BOTTOM_BAR_H - 50, 200, 38),
                "Begin Battle",
                lambda: self._begin(app),
                accent=theme.OK,
                disabled=self.battle_result is not None,
            ),
            Button(
                (theme.WIDTH // 2 - 100, theme.HEIGHT - theme.BOTTOM_BAR_H - 50, 200, 38),
                "Continue",
                lambda: self._finish(app),
                accent=theme.OK,
                disabled=self.battle_result is None,
            ),
        ]

    def _auto_arrange(self, app: "App") -> None:
        self.placement = auto_place(list(app.world.player.army), 0)

    def _begin(self, app: "App") -> None:
        if self.placement is None:
            return
        # Determine the enemy units.
        enemy = app.world.civ_by_name[
            self.defender if app.world.player.name == self.attacker else self.attacker
        ]
        attacker_idx = 0  # player is "side a" in our display
        # Decide who is the *attacker* in combat (loses on draw).
        attacker_for_combat = 0 if app.world.player.name == self.attacker else 1
        result = resolve_battle(
            list(app.world.player.army),
            list(enemy.army),
            (app.world.player.name, enemy.name),
            app.world.rng,
            side_a_placement=self.placement,
            attacker=attacker_for_combat,
        )
        self.battle_result = result
        self.rebuild(app)

    def _finish(self, app: "App") -> None:
        if self.battle_result is None:
            return
        attacker_name = self.attacker
        defender_name = self.defender
        app.world.resolve_player_battle(self.battle_result, attacker_name, defender_name)
        self.battle_result = None
        self.placement = None
        app.set_screen("MAP")

    def update(self, app: "App", mouse_pos) -> None:
        for b in self.buttons:
            b.update(mouse_pos)

    def handle_event(self, app: "App", event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.handle_click(event.pos):
                    return True
            if self.battle_result is None:
                cu = self._unit_at(event.pos)
                if cu is not None and cu.side == 0:
                    self.dragging = cu
                    return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging is not None:
                cell = self._cell_at(event.pos)
                if cell is not None and cell[1] < GRID_COLS_PER_SIDE:
                    # check empty
                    if not any(u.col == cell[1] and u.row == cell[0]
                               for u in (self.placement or [])
                               if u is not self.dragging):
                        self.dragging.row = cell[0]
                        self.dragging.col = cell[1]
                self.dragging = None
                return True
        return False

    # --- drawing -------------------------------------------------------

    def draw(self, app: "App", surface: pygame.Surface) -> None:
        rect = pygame.Rect(
            theme.PAD,
            theme.TOP_BAR_H + theme.PAD,
            theme.WIDTH - 2 * theme.PAD,
            theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD,
        )
        attacker_label = self.attacker
        defender_label = self.defender
        inner = draw_panel(
            surface, rect,
            title=f"BATTLE — {attacker_label} (attacker) vs {defender_label}",
            title_font=app.font_tiny,
        )

        grid_w = self.cell_size * GRID_COLS_TOTAL
        grid_h = self.cell_size * GRID_ROWS
        gx = inner.centerx - grid_w // 2
        gy = inner.y + 60

        # Draw grid background and side tints.
        for col in range(GRID_COLS_TOTAL):
            for row in range(GRID_ROWS):
                cell = pygame.Rect(gx + col * self.cell_size,
                                   gy + row * self.cell_size,
                                   self.cell_size, self.cell_size)
                tint = (44, 60, 90) if col < GRID_COLS_PER_SIDE else (90, 50, 50)
                pygame.draw.rect(surface, tint, cell)
                pygame.draw.rect(surface, theme.PANEL_BORDER, cell, 1)

        # Center divider
        cx = gx + grid_w // 2
        pygame.draw.line(surface, theme.GOLD, (cx, gy), (cx, gy + grid_h), 2)

        # Side labels
        label_y = gy - 26
        l1 = app.font_body_bold.render("YOU (drag to position)", True, theme.AP)
        surface.blit(l1, (gx, label_y))
        l2 = app.font_body_bold.render(
            f"{defender_label if app.world.player.name == self.attacker else self.attacker}",
            True, theme.WARN)
        surface.blit(l2, l2.get_rect(topright=(gx + grid_w, label_y)))

        # Determine which units to draw.
        if self.battle_result is not None:
            units = self.battle_result.all_units()
        else:
            # placement (player) + auto-placed enemy preview
            enemy = app.world.civ_by_name[
                self.defender if app.world.player.name == self.attacker else self.attacker
            ]
            enemy_placement = auto_place(list(enemy.army), 1)
            units = (self.placement or []) + enemy_placement

        for u in units:
            self._draw_unit(app, surface, u, gx, gy)

        # Result banner
        if self.battle_result is not None:
            winner_idx = self.battle_result.winner
            winner_name = self.battle_result.civ_names[winner_idx]
            color = theme.OK if winner_name == app.world.player.name else theme.WARN
            text = "VICTORY!" if winner_name == app.world.player.name else "DEFEAT"
            banner = app.font_h1.render(text, True, color)
            surface.blit(banner, banner.get_rect(midtop=(inner.centerx, gy + grid_h + 20)))
            # Last log lines
            log_y = gy + grid_h + 60
            for line in self.battle_result.log[-6:]:
                surface.blit(app.font_small.render(line[:120], True, theme.TEXT_MUTED),
                             (inner.x + 20, log_y))
                log_y += 18

        for b in self.buttons:
            b.draw(surface, app.font_body, app.font_small)

    def _draw_unit(self, app: "App", surface: pygame.Surface,
                   u: CombatUnit, gx: int, gy: int) -> None:
        rect = pygame.Rect(
            gx + u.col * self.cell_size + 4,
            gy + u.row * self.cell_size + 4,
            self.cell_size - 8, self.cell_size - 8,
        )
        path_color = theme.PATH_COLOR.get(u.template.path, theme.TEXT)
        side_color = theme.AP if u.side == 0 else theme.WARN
        if not u.alive:
            pygame.draw.rect(surface, (60, 60, 60), rect, border_radius=4)
            pygame.draw.line(surface, theme.WARN, rect.topleft, rect.bottomright, 2)
            pygame.draw.line(surface, theme.WARN, rect.topright, rect.bottomleft, 2)
            return
        pygame.draw.rect(surface, path_color, rect, border_radius=4)
        pygame.draw.rect(surface, side_color, rect, 2, border_radius=4)
        # Tier number
        tier_surf = app.font_tiny.render(f"T{u.template.tier}", True, (20, 20, 24))
        surface.blit(tier_surf, (rect.x + 4, rect.y + 2))
        # Name (short)
        short = u.template.name[:7]
        nm = app.font_tiny.render(short, True, (20, 20, 24))
        surface.blit(nm, (rect.centerx - nm.get_width() // 2, rect.y + rect.height // 2 - 8))
        # HP bar
        hp_pct = max(0, u.hp) / max(1, u.template.hp)
        bar_rect = pygame.Rect(rect.x + 4, rect.bottom - 8, rect.width - 8, 4)
        pygame.draw.rect(surface, (40, 40, 40), bar_rect)
        pygame.draw.rect(surface, theme.OK if hp_pct > 0.5 else theme.WARN,
                         pygame.Rect(bar_rect.x, bar_rect.y,
                                     int(bar_rect.width * hp_pct), bar_rect.height))

    def _unit_at(self, pos) -> Optional[CombatUnit]:
        gx, gy, _, _ = self._grid_geom()
        for u in (self.placement or []):
            rect = pygame.Rect(
                gx + u.col * self.cell_size + 4,
                gy + u.row * self.cell_size + 4,
                self.cell_size - 8, self.cell_size - 8,
            )
            if rect.collidepoint(pos):
                return u
        return None

    def _cell_at(self, pos) -> Optional[tuple[int, int]]:
        gx, gy, gw, gh = self._grid_geom()
        if not (gx <= pos[0] < gx + gw and gy <= pos[1] < gy + gh):
            return None
        col = (pos[0] - gx) // self.cell_size
        row = (pos[1] - gy) // self.cell_size
        return (row, col)

    def _grid_geom(self) -> tuple[int, int, int, int]:
        grid_w = self.cell_size * GRID_COLS_TOTAL
        grid_h = self.cell_size * GRID_ROWS
        rect = pygame.Rect(
            theme.PAD,
            theme.TOP_BAR_H + theme.PAD,
            theme.WIDTH - 2 * theme.PAD,
            theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD,
        )
        gx = rect.centerx - grid_w // 2
        gy = rect.y + 60 + 28  # account for panel title
        return gx, gy, grid_w, grid_h
