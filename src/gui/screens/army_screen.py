"""Army screen: full army roster with stats and tier-up hints."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import pygame

from ...offerings import Unit
from .. import theme
from ..widgets import Button, draw_panel

if TYPE_CHECKING:
    from ..app import App


class ArmyScreen:
    name = "ARMY"

    def __init__(self) -> None:
        self.buttons: list[Button] = []

    def enter(self, app: "App") -> None:
        self.rebuild(app)

    def rebuild(self, app: "App") -> None:
        self.buttons = []

    def update(self, app: "App", mouse_pos) -> None:
        for b in self.buttons:
            b.update(mouse_pos)

    def handle_event(self, app: "App", event) -> bool:
        for b in self.buttons:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if b.handle_click(event.pos):
                    return True
        return False

    def draw(self, app: "App", surface: pygame.Surface) -> None:
        rect = pygame.Rect(
            theme.PAD,
            theme.TOP_BAR_H + theme.PAD,
            theme.WIDTH - 2 * theme.PAD,
            theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD,
        )
        cap = app.world.army_cap(app.world.player)
        inner = draw_panel(
            surface, rect,
            title=f"ARMY  ({len(app.world.player.army)}/{cap})",
            title_font=app.font_tiny,
        )

        counts: Counter[Unit] = Counter(app.world.player.army)
        col_w = (inner.width - 2 * theme.PAD) // 3
        x = inner.x
        y = inner.y
        items = sorted(counts.items(), key=lambda kv: (-kv[0].tier, kv[0].name))

        for i, (unit, count) in enumerate(items):
            col = i % 3
            row = i // 3
            cx = inner.x + col * col_w
            cy = inner.y + row * 100
            cell = pygame.Rect(cx, cy, col_w - 8, 92)
            self._draw_unit_card(app, surface, cell, unit, count)

        # Footer: cities + buildings/wonders summary
        footer_y = inner.bottom - 80
        pygame.draw.line(surface, theme.DIVIDER,
                         (inner.x, footer_y - 4), (inner.right, footer_y - 4), 1)
        surface.blit(app.font_tiny.render("CITIES", True, theme.TEXT_MUTED),
                     (inner.x, footer_y))
        cities = ", ".join(f"{c.name}(p{c.population})" for c in app.world.player.cities)
        surface.blit(app.font_small.render(cities or "(none)", True, theme.TEXT),
                     (inner.x + 80, footer_y))
        surface.blit(app.font_tiny.render("WONDERS", True, theme.TEXT_MUTED),
                     (inner.x, footer_y + 22))
        surface.blit(app.font_small.render(
            ", ".join(app.world.player.wonders) or "(none)",
            True, theme.GOLD if app.world.player.wonders else theme.TEXT),
            (inner.x + 80, footer_y + 22))
        surface.blit(app.font_tiny.render("RESOURCES", True, theme.TEXT_MUTED),
                     (inner.x, footer_y + 44))
        surface.blit(app.font_small.render(
            ", ".join(sorted(app.world.player.owned_resources)) or "(none)",
            True, theme.TEXT), (inner.x + 80, footer_y + 44))

    def _draw_unit_card(self, app: "App", surface: pygame.Surface,
                        rect: pygame.Rect, unit: Unit, count: int) -> None:
        pygame.draw.rect(surface, theme.SLOT_BG, rect, border_radius=6)
        pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1, border_radius=6)
        color = theme.PATH_COLOR.get(unit.path, theme.TEXT)
        stripe = pygame.Rect(rect.x, rect.y, 4, rect.height)
        pygame.draw.rect(surface, color, stripe,
                         border_top_left_radius=6, border_bottom_left_radius=6)
        x = rect.x + 12
        y = rect.y + 6
        surface.blit(app.font_body_bold.render(unit.name, True, theme.TEXT), (x, y))
        y += 22
        surface.blit(app.font_small.render(
            f"{unit.path}  T{unit.tier}", True, theme.TEXT_MUTED), (x, y))
        y += 18
        stats = f"HP {unit.hp}  ATK {unit.attack}  DEF {unit.defense}  SPD {unit.speed}  RNG {unit.rng}"
        surface.blit(app.font_tiny.render(stats, True, theme.TEXT_MUTED), (x, y))
        # Count badge
        cnt_color = theme.GOLD if count >= 2 else theme.TEXT
        cnt_surf = app.font_h2.render(f"x{count}", True, cnt_color)
        surface.blit(cnt_surf, cnt_surf.get_rect(topright=(rect.right - 8, rect.y + 4)))
        if count >= 2:
            tier_msg = "tier up ready" if count >= 3 else f"{3 - count} to tier up"
            surface.blit(app.font_tiny.render(
                tier_msg, True, theme.OK if count >= 3 else theme.TEXT_MUTED),
                (rect.right - 110, rect.bottom - 18))
