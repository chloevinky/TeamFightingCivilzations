"""Diplomacy screen: relations + proactive actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .. import theme
from ..widgets import Button, draw_panel

if TYPE_CHECKING:
    from ..app import App


class DiplomacyScreen:
    name = "DIPLOMACY"

    def __init__(self) -> None:
        self.buttons: list[Button] = []
        self.selected: str | None = None

    def enter(self, app: "App") -> None:
        # Default to first discovered civ.
        if self.selected is None or self.selected not in app.world.player.discovered:
            disc = sorted(app.world.player.discovered)
            self.selected = disc[0] if disc else None
        self.rebuild(app)

    def rebuild(self, app: "App") -> None:
        self.buttons = []
        if self.selected is None:
            return
        target = self.selected
        rect_x = theme.WIDTH // 2 - 200
        y = theme.TOP_BAR_H + 250
        actions = [
            ("Open Borders (1 AP)", lambda: app.log(app.world.player_open_borders(target)), 1),
            ("Sign NAP (2 AP)",     lambda: app.log(app.world.player_sign_nap(target)), 2),
            ("Form Alliance (3 AP)", lambda: app.log(app.world.player_alliance(target)), 3),
            ("Denounce (1 AP)",     lambda: app.log(app.world.player_denounce(target)), 1),
            ("Demand Tribute (2 AP)", lambda: app.log(app.world.player_demand_tribute(target)), 2),
            ("Declare War",          lambda: app.log(app.world.player_declare_war(target)), 0),
            ("Make Peace (1 AP)",    lambda: app.log(app.world.player_make_peace(target)), 1),
        ]
        if app.world.diplomacy.get(app.world.player.name, target).at_war:
            actions.append((
                "Trigger Battle Now",
                lambda: app.trigger_battle(target),
                0,
            ))
        for i, (label, cb, ap_cost) in enumerate(actions):
            disabled = app.world.player.ap < ap_cost
            self.buttons.append(
                Button(
                    (rect_x, y + i * 42, 360, 36),
                    label, cb, disabled=disabled, accent=theme.AP,
                )
            )
        # Civ selector buttons on the left.
        for i, name in enumerate(sorted(app.world.player.discovered)):
            self.buttons.append(
                Button(
                    (theme.PAD + 10, theme.TOP_BAR_H + 60 + i * 40, 220, 34),
                    name,
                    lambda n=name: self._select(app, n),
                    accent=theme.CIV_COLORS.get(name),
                )
            )

    def _select(self, app: "App", name: str) -> None:
        self.selected = name
        self.rebuild(app)

    def update(self, app: "App", mouse_pos) -> None:
        for b in self.buttons:
            b.update(mouse_pos)

    def handle_event(self, app: "App", event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.handle_click(event.pos):
                    self.rebuild(app)
                    return True
        return False

    def draw(self, app: "App", surface: pygame.Surface) -> None:
        rect = pygame.Rect(
            theme.PAD,
            theme.TOP_BAR_H + theme.PAD,
            theme.WIDTH - 2 * theme.PAD,
            theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD,
        )
        inner = draw_panel(surface, rect, title="DIPLOMACY", title_font=app.font_tiny)

        # Left: civ list (drawn via buttons).  Header label.
        surface.blit(app.font_tiny.render("DISCOVERED CIVS", True, theme.TEXT_MUTED),
                     (inner.x + 10, inner.y))

        # If no one discovered:
        if not app.world.player.discovered:
            surface.blit(app.font_body.render(
                "No other civilizations discovered yet.  Explore the map.",
                True, theme.TEXT_MUTED), (inner.x + 250, inner.y + 60))
            return

        if self.selected is None:
            return

        # Right: detail panel for selected civ
        target = self.selected
        target_civ = app.world.civ_by_name.get(target)
        if target_civ is None:
            return
        rel = app.world.diplomacy.get(app.world.player.name, target)

        dx = 250
        dy = inner.y
        title = app.font_h2.render(target, True, theme.CIV_COLORS.get(target, theme.TEXT))
        surface.blit(title, (dx, dy))
        dy += 30
        subtitle = getattr(target_civ, "archetype", "Unknown")
        surface.blit(app.font_small.render(f"Archetype: {subtitle}", True, theme.TEXT_MUTED),
                     (dx, dy))
        dy += 22
        # Relations bar
        surface.blit(app.font_tiny.render("RELATIONS", True, theme.TEXT_MUTED), (dx, dy))
        bar_y = dy + 16
        bar_rect = pygame.Rect(dx, bar_y, 360, 14)
        pygame.draw.rect(surface, theme.PANEL_ALT, bar_rect, border_radius=4)
        score = max(-100, min(100, rel.score))
        norm = (score + 100) / 200.0  # 0..1
        fill_x = bar_rect.x + int(bar_rect.width * norm)
        # midpoint marker
        mid_x = bar_rect.x + bar_rect.width // 2
        pygame.draw.line(surface, theme.TEXT_DIM, (mid_x, bar_y), (mid_x, bar_y + 14))
        color = theme.OK if score >= 0 else theme.WARN
        if score >= 0:
            pygame.draw.rect(surface, color,
                             pygame.Rect(mid_x, bar_y, fill_x - mid_x, 14), border_radius=4)
        else:
            pygame.draw.rect(surface, color,
                             pygame.Rect(fill_x, bar_y, mid_x - fill_x, 14), border_radius=4)
        surface.blit(app.font_tiny.render(f"{score:+d}", True, theme.TEXT),
                     (bar_rect.right + 8, bar_y))

        dy = bar_y + 30
        flags = []
        if rel.alliance:
            flags.append("ALLIED")
        if rel.at_war:
            flags.append("AT WAR")
            if rel.war_countdown is not None:
                flags.append(f"battle in {rel.war_countdown}T")
        if rel.nap_until_turn:
            flags.append(f"NAP until T{rel.nap_until_turn}")
        if rel.open_borders:
            flags.append("OPEN BORDERS")
        if not rel.at_war and not rel.alliance and not rel.nap_until_turn and rel.war_countdown:
            flags.append(f"war countdown {rel.war_countdown}T")
        flag_str = ", ".join(flags) if flags else "—"
        surface.blit(app.font_small.render(f"Status: {flag_str}", True, theme.TEXT_MUTED),
                     (dx, dy))
        dy += 22
        surface.blit(app.font_small.render(
            f"Their cities: {len(target_civ.cities)}    Army strength: {target_civ.army_strength()}",
            True, theme.TEXT_MUTED), (dx, dy))

        # Buttons drawn last.
        for b in self.buttons:
            b.draw(surface, app.font_body, app.font_small)
