"""Technology tree screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ...offerings import Era
from ...tech import BRANCHES, TECHS, Tech, ERA_THRESHOLDS, tech_by_name
from .. import theme
from ..widgets import Button, draw_panel, draw_pill

if TYPE_CHECKING:
    from ..app import App


class TechScreen:
    name = "TECH"

    def __init__(self) -> None:
        self.tech_rects: list[tuple[pygame.Rect, Tech]] = []
        self.buttons: list[Button] = []

    def enter(self, app: "App") -> None:
        self.rebuild(app)

    def rebuild(self, app: "App") -> None:
        self.buttons = []

    def update(self, app: "App", mouse_pos) -> None:
        for b in self.buttons:
            b.update(mouse_pos)

    def handle_event(self, app: "App", event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, tech in self.tech_rects:
                if rect.collidepoint(event.pos):
                    self._set_research(app, tech)
                    return True
        return False

    def _set_research(self, app: "App", tech: Tech) -> None:
        if tech.name in app.world.player.research.completed:
            return
        if tech.era > app.world.player.era:
            app.log("That tech is locked behind a future era.")
            return
        ok = app.world.player.research.set_research(tech.name)
        if ok:
            app.log(f"Researching {tech.name}.")

    def draw(self, app: "App", surface: pygame.Surface) -> None:
        rect = pygame.Rect(
            theme.PAD,
            theme.TOP_BAR_H + theme.PAD,
            theme.WIDTH - 2 * theme.PAD,
            theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD,
        )
        inner = draw_panel(surface, rect, title="TECHNOLOGY", title_font=app.font_tiny)

        # Header
        research = app.world.player.research
        cur = research.current
        if cur is None:
            cur_text = "No active research — click a tech to begin."
            color = theme.WARN
        else:
            t = tech_by_name(cur)
            if t is None:
                cur_text = "..."
                color = theme.TEXT
            else:
                rem = research.cost_remaining()
                cur_text = f"Researching: {t.name} ({t.branch}) — {research.progress}/{t.cost} ({rem} remaining)"
                color = theme.SCIENCE
        surface.blit(app.font_body_bold.render(cur_text, True, color), (inner.x, inner.y))
        # Total science / next era threshold
        next_era_threshold = None
        for era, thresh in ERA_THRESHOLDS.items():
            if era > app.world.player.era:
                next_era_threshold = (era, thresh)
                break
        if next_era_threshold is not None:
            label = (f"Total science: {research.total_science}   "
                     f"Next era ({next_era_threshold[0].name.title()}): {next_era_threshold[1]}")
        else:
            label = f"Total science: {research.total_science}   At max era."
        surface.blit(app.font_small.render(label, True, theme.TEXT_MUTED),
                     (inner.x, inner.y + 22))

        # Grid: rows = branches, cols = eras up to current
        grid_y = inner.y + 60
        col_w = (inner.right - inner.x - 100) // 7
        row_h = 70
        # Header row of era names
        for col, era in enumerate(Era):
            cx = inner.x + 100 + col * col_w
            era_label = app.font_tiny.render(era.name.title(), True,
                                              theme.TEXT if era <= app.world.player.era else theme.TEXT_DIM)
            surface.blit(era_label, (cx + 4, grid_y))

        self.tech_rects = []
        for row, branch in enumerate(BRANCHES):
            ry = grid_y + 22 + row * row_h
            label_surf = app.font_body_bold.render(branch, True, theme.TEXT)
            surface.blit(label_surf, (inner.x, ry + row_h // 2 - label_surf.get_height() // 2))
            for col, era in enumerate(Era):
                cx = inner.x + 100 + col * col_w
                cell = pygame.Rect(cx, ry, col_w - 6, row_h - 8)
                tech = next((t for t in TECHS if t.branch == branch and t.era == era), None)
                if tech is None:
                    continue
                self._draw_tech_cell(app, surface, cell, tech)
                self.tech_rects.append((cell, tech))

        for b in self.buttons:
            b.draw(surface, app.font_body, app.font_small)

    def _draw_tech_cell(self, app: "App", surface: pygame.Surface,
                        rect: pygame.Rect, tech: Tech) -> None:
        completed = tech.name in app.world.player.research.completed
        is_current = app.world.player.research.current == tech.name
        locked = tech.era > app.world.player.era
        hovered = rect.collidepoint(pygame.mouse.get_pos())

        if completed:
            bg = (40, 80, 50)
            border = theme.OK
        elif is_current:
            bg = (50, 60, 100)
            border = theme.SCIENCE
        elif locked:
            bg = theme.SLOT_DISABLED
            border = theme.PANEL_BORDER
        else:
            bg = theme.SLOT_HOVER if hovered else theme.SLOT_BG
            border = theme.PANEL_BORDER
        pygame.draw.rect(surface, bg, rect, border_radius=6)
        pygame.draw.rect(surface, border, rect, 1, border_radius=6)

        text_color = theme.TEXT if not locked else theme.TEXT_DIM
        name_surf = app.font_body_bold.render(tech.name, True, text_color)
        surface.blit(name_surf, (rect.x + 6, rect.y + 4))
        cost = app.font_tiny.render(f"{tech.cost}sci", True, theme.SCIENCE if not locked else theme.TEXT_DIM)
        surface.blit(cost, (rect.x + 6, rect.y + 22))
        eff = app.font_tiny.render(tech.effect[:36], True, theme.TEXT_MUTED if not locked else theme.TEXT_DIM)
        surface.blit(eff, (rect.x + 6, rect.y + 36))

        if completed:
            done = app.font_tiny.render("DONE", True, theme.OK)
            surface.blit(done, done.get_rect(topright=(rect.right - 4, rect.y + 4)))
        elif is_current:
            t = app.font_tiny.render("ACTIVE", True, theme.SCIENCE)
            surface.blit(t, t.get_rect(topright=(rect.right - 4, rect.y + 4)))
