"""Main pygame application for the Hexfall graphical prototype.

This is a visual skin over the existing text-UI shop loop. All game logic lives
in ``src/game_state.py``, ``src/shop.py``, ``src/paths.py`` and is reused
unchanged; this module only handles rendering and input.

Run with:
    python -m src.gui
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Optional

import pygame

from .. import config, paths
from ..game_state import GameState
from ..offerings import (
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
)
from ..shop import Shop, Slot
from . import theme
from .widgets import Button, draw_panel, draw_pill, draw_text, draw_text_right


class App:
    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = random.Random(seed)
        self.state = GameState()
        self.shop = Shop(self.state, rng=self.rng)
        self.shop.refresh(is_free=True)

        pygame.init()
        pygame.display.set_caption("Hexfall — Graphical Prototype")
        self.screen = pygame.display.set_mode((theme.WIDTH, theme.HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_h1 = pygame.font.SysFont("arial", 26, bold=True)
        self.font_h2 = pygame.font.SysFont("arial", 18, bold=True)
        self.font_body = pygame.font.SysFont("arial", 15)
        self.font_body_bold = pygame.font.SysFont("arial", 15, bold=True)
        self.font_small = pygame.font.SysFont("arial", 13)
        self.font_tiny = pygame.font.SysFont("arial", 11, bold=True)

        self.log_lines: list[str] = [
            "Welcome to Hexfall. Build an army, then end the turn.",
        ]
        self.shop_slot_rects: list[pygame.Rect] = []
        self.buttons: list[Button] = []
        self._rebuild_controls()
        self.running = True

    # --- lifecycle ---

    def run(self) -> int:
        while self.running:
            self.clock.tick(theme.FPS)
            self._handle_events()
            self._draw()
            pygame.display.flip()
        pygame.quit()
        return 0

    # --- actions (wire to game logic) ---

    def _log(self, msg: str) -> None:
        for line in msg.splitlines():
            if line.strip():
                self.log_lines.append(line)
        self.log_lines = self.log_lines[-6:]

    def _on_buy(self, idx: int) -> None:
        self._log(self.shop.buy(idx))
        self._rebuild_controls()

    def _on_lock(self, idx: int) -> None:
        self._log(self.shop.lock(idx))
        self._rebuild_controls()

    def _on_unlock(self) -> None:
        self._log(self.shop.unlock())
        self._rebuild_controls()

    def _on_reroll(self) -> None:
        self._log(self.shop.paid_reroll())
        self._rebuild_controls()

    def _on_end_turn(self) -> None:
        self.state.end_turn()
        self.state.begin_turn()
        self.shop.refresh(is_free=True)
        self._log(f"--- Turn {self.state.turn} begins ---")
        self._rebuild_controls()

    def _on_invest(self, path: str) -> None:
        if self.state.ap < config.PATH_INVEST_AP_COST:
            self._log("Not enough AP to invest.")
            return
        self.state.ap -= config.PATH_INVEST_AP_COST
        paths.invest(self.state.path_investment, path)
        traits = paths.traits_for(path, self.state.path_investment)
        trait_str = ", ".join(traits) if traits else "none"
        self._log(
            f"Invested in {path} (now {self.state.path_investment[path]}). "
            f"Traits: {trait_str}."
        )
        self._rebuild_controls()

    def _on_muster(self, path: str) -> None:
        if self.state.mustered_this_turn:
            self._log("Already mustered this turn.")
            return
        if self.state.path_investment.get(path, 0) <= 0:
            self._log(f"Cannot muster from {path}: no investment.")
            return
        if self.state.ap < config.MUSTER_AP_COST:
            self._log("Not enough AP to muster.")
            return
        tier = paths.muster_tier(self.state.path_investment, path)
        candidates = [
            u for u in UNITS
            if u.path == path and u.tier <= tier and u.required_resource is None
        ]
        if not candidates:
            self._log(f"No muster candidates for {path} at tier {tier}.")
            return
        pick = max(candidates, key=lambda u: u.tier)
        self.state.ap -= config.MUSTER_AP_COST
        self.state.mustered_this_turn = True
        self._log(f"Mustered {pick.name} ({pick.path} T{pick.tier}).")
        for line in self.state.add_unit(pick):
            self._log(line)
        self._rebuild_controls()

    # --- event handling ---

    def _handle_events(self) -> None:
        mouse_pos = pygame.mouse.get_pos()
        for b in self.buttons:
            b.update(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self._on_end_turn()
                elif event.key == pygame.K_r:
                    self._on_reroll()
                elif pygame.K_1 <= event.key <= pygame.K_8:
                    idx = event.key - pygame.K_1
                    if idx < len(self.shop.slots):
                        self._on_buy(idx)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    for b in self.buttons:
                        if b.handle_click(event.pos):
                            break
                    else:
                        for i, r in enumerate(self.shop_slot_rects):
                            if r.collidepoint(event.pos):
                                self._on_buy(i)
                                break
                elif event.button == 3:
                    for i, r in enumerate(self.shop_slot_rects):
                        if r.collidepoint(event.pos):
                            if self.state.locked_slot == i:
                                self._on_unlock()
                            else:
                                self._on_lock(i)
                            break

    # --- layout / controls ---

    def _rebuild_controls(self) -> None:
        """Recompute buttons based on current state. Called after every action."""
        self.buttons = []
        self.shop_slot_rects = []

        # Left sidebar: path invest + muster buttons
        left_x = theme.PAD
        y = theme.TOP_BAR_H + theme.PAD

        # Paths panel occupies upper-left; placement mirrors _draw_paths_panel.
        paths_panel = pygame.Rect(
            left_x,
            y,
            theme.LEFT_W - theme.PAD,
            420,
        )
        inner = paths_panel.inflate(-2 * theme.PAD, -2 * theme.PAD)
        inner.topleft = (paths_panel.x + theme.PAD, paths_panel.y + theme.PAD)
        # Skip title height
        row_y = inner.y + 28
        row_h = 30
        for path_name in PATHS:
            invest_btn_rect = (
                inner.right - 32,
                row_y + 2,
                26,
                row_h - 8,
            )
            can_invest = self.state.ap >= config.PATH_INVEST_AP_COST
            self.buttons.append(
                Button(
                    invest_btn_rect,
                    "+",
                    lambda p=path_name: self._on_invest(p),
                    disabled=not can_invest,
                    accent=theme.PATH_COLOR.get(path_name),
                )
            )
            row_y += row_h

        # Muster buttons — one per invested path. Leave room for pity + label.
        muster_y = row_y + 52
        for path_name in PATHS:
            level = self.state.path_investment.get(path_name, 0)
            if level <= 0:
                continue
            can_muster = (
                not self.state.mustered_this_turn
                and self.state.ap >= config.MUSTER_AP_COST
            )
            tier = paths.muster_tier(self.state.path_investment, path_name)
            self.buttons.append(
                Button(
                    (inner.x, muster_y, inner.width, 28),
                    f"Muster {path_name} (T{tier})  -1 AP",
                    lambda p=path_name: self._on_muster(p),
                    disabled=not can_muster,
                    accent=theme.PATH_COLOR.get(path_name),
                )
            )
            muster_y += 32

        # Bottom bar buttons
        bar_y = theme.HEIGHT - theme.BOTTOM_BAR_H + 18
        bar_h = theme.BOTTOM_BAR_H - 36
        reroll_cost = self.state.reroll_cost()
        self.buttons.append(
            Button(
                (theme.PAD, bar_y, 180, bar_h),
                "Reroll",
                self._on_reroll,
                disabled=self.state.gold < reroll_cost,
                accent=theme.AP,
                subtitle=f"{reroll_cost}g  (R)",
            )
        )
        self.buttons.append(
            Button(
                (
                    theme.WIDTH - 220 - theme.PAD,
                    bar_y,
                    220,
                    bar_h,
                ),
                "End Turn",
                self._on_end_turn,
                accent=theme.OK,
                subtitle="SPACE",
            )
        )

        # Shop card rects (computed so event handling can hit-test them)
        shop_x = theme.LEFT_W + theme.PAD
        shop_y = theme.TOP_BAR_H + theme.PAD
        shop_w = theme.WIDTH - theme.LEFT_W - theme.RIGHT_W - theme.PAD
        shop_h = theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD
        # account for panel title
        inner_x = shop_x + theme.PAD
        inner_y = shop_y + theme.PAD + 28
        inner_w = shop_w - 2 * theme.PAD
        inner_h = shop_h - 2 * theme.PAD - 28
        card_w = (inner_w - (theme.SHOP_COLS - 1) * theme.CARD_GAP) // theme.SHOP_COLS
        card_h = (inner_h - (theme.SHOP_ROWS - 1) * theme.CARD_GAP) // theme.SHOP_ROWS
        for i in range(min(theme.SHOP_COLS * theme.SHOP_ROWS, len(self.shop.slots))):
            c = i % theme.SHOP_COLS
            r = i // theme.SHOP_COLS
            x = inner_x + c * (card_w + theme.CARD_GAP)
            y_ = inner_y + r * (card_h + theme.CARD_GAP)
            self.shop_slot_rects.append(pygame.Rect(x, y_, card_w, card_h))

    # --- drawing ---

    def _draw(self) -> None:
        self.screen.fill(theme.BG)
        self._draw_top_bar()
        self._draw_paths_panel()
        self._draw_shop()
        self._draw_army_panel()
        self._draw_bottom_bar()
        # buttons are drawn last so they sit above panels
        for b in self.buttons:
            b.draw(self.screen, self.font_body, self.font_small)

    def _draw_top_bar(self) -> None:
        bar = pygame.Rect(0, 0, theme.WIDTH, theme.TOP_BAR_H)
        pygame.draw.rect(self.screen, theme.PANEL, bar)
        pygame.draw.line(
            self.screen,
            theme.PANEL_BORDER,
            (0, theme.TOP_BAR_H),
            (theme.WIDTH, theme.TOP_BAR_H),
            1,
        )

        # Title
        title = self.font_h1.render("HEXFALL", True, theme.GOLD)
        self.screen.blit(title, (theme.PAD + 4, theme.TOP_BAR_H // 2 - title.get_height() // 2))
        sub = self.font_small.render(
            "graphical prototype", True, theme.TEXT_MUTED
        )
        self.screen.blit(sub, (theme.PAD + 4 + title.get_width() + 8, theme.TOP_BAR_H - sub.get_height() - 6))

        # Stats row, right-aligned, pills drawn right-to-left
        stats_y = theme.TOP_BAR_H // 2 - 22
        x = theme.WIDTH - theme.PAD
        x = self._draw_stat_pill("ERA", self.state.era.name.title(), x, stats_y, theme.SCIENCE)
        x = self._draw_stat_pill(
            "AP", f"{self.state.ap}/{config.ap_for_turn(self.state.turn)}", x, stats_y, theme.AP
        )
        x = self._draw_stat_pill("GOLD", f"{self.state.gold}", x, stats_y, theme.GOLD)
        x = self._draw_stat_pill("TURN", f"{self.state.turn}", x, stats_y, theme.TEXT)

    def _draw_stat_pill(
        self,
        label: str,
        value: str,
        right_x: int,
        y: int,
        color: tuple[int, int, int],
    ) -> int:
        label_surf = self.font_tiny.render(label, True, theme.TEXT_MUTED)
        value_surf = self.font_h2.render(value, True, color)
        w = max(label_surf.get_width(), value_surf.get_width()) + 20
        h = label_surf.get_height() + value_surf.get_height() + 10
        rect = pygame.Rect(right_x - w, y, w, h)
        pygame.draw.rect(self.screen, theme.PANEL_ALT, rect, border_radius=6)
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, rect, 1, border_radius=6)
        self.screen.blit(
            label_surf,
            label_surf.get_rect(midtop=(rect.centerx, rect.y + 4)),
        )
        self.screen.blit(
            value_surf,
            value_surf.get_rect(
                midtop=(rect.centerx, rect.y + 4 + label_surf.get_height())
            ),
        )
        return rect.x - 8

    def _draw_paths_panel(self) -> None:
        rect = pygame.Rect(
            theme.PAD,
            theme.TOP_BAR_H + theme.PAD,
            theme.LEFT_W - theme.PAD,
            420,
        )
        inner = draw_panel(
            self.screen, rect, title="SKILL PATHS", title_font=self.font_tiny
        )

        row_y = inner.y
        row_h = 30
        for path_name in PATHS:
            level = self.state.path_investment.get(path_name, 0)
            color = theme.PATH_COLOR.get(path_name, theme.TEXT)
            # color swatch
            swatch = pygame.Rect(inner.x, row_y + 6, 6, row_h - 12)
            pygame.draw.rect(self.screen, color, swatch, border_radius=2)
            # path name
            name_surf = self.font_body.render(path_name, True, theme.TEXT)
            self.screen.blit(name_surf, (inner.x + 14, row_y + row_h // 2 - name_surf.get_height() // 2))
            # level dots
            dots_x = inner.x + 14 + 70
            for d in range(5):
                cx = dots_x + d * 10
                cy = row_y + row_h // 2
                if d < level:
                    pygame.draw.circle(self.screen, color, (cx, cy), 4)
                else:
                    pygame.draw.circle(self.screen, theme.DIVIDER, (cx, cy), 4, 1)
            row_y += row_h

        # pity indicator
        pity_y = row_y + 10
        deepest = self.state.deepest_path()
        if deepest:
            txt = f"Pity: {self.state.pity_counter}/{config.PITY_TIMER_THRESHOLD} ({deepest})"
        else:
            txt = "Pity: (no investment)"
        surf = self.font_small.render(txt, True, theme.TEXT_MUTED)
        self.screen.blit(surf, (inner.x, pity_y))

        pygame.draw.line(
            self.screen,
            theme.DIVIDER,
            (inner.x, pity_y + 24),
            (inner.right, pity_y + 24),
            1,
        )
        muster_label = self.font_tiny.render("TARGETED MUSTER", True, theme.TEXT_MUTED)
        self.screen.blit(muster_label, (inner.x, pity_y + 30))
        if not any(v > 0 for v in self.state.path_investment.values()):
            hint = self.font_small.render(
                "Invest in a path to unlock",
                True,
                theme.TEXT_DIM,
            )
            self.screen.blit(hint, (inner.x, pity_y + 52))

    def _draw_shop(self) -> None:
        shop_x = theme.LEFT_W + theme.PAD
        shop_y = theme.TOP_BAR_H + theme.PAD
        shop_w = theme.WIDTH - theme.LEFT_W - theme.RIGHT_W - theme.PAD
        shop_h = theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD
        rect = pygame.Rect(shop_x, shop_y, shop_w, shop_h)
        draw_panel(
            self.screen,
            rect,
            title=f"SHOP  —  {len(self.shop.slots)} offerings   "
            f"(left click to buy, right click to lock)",
            title_font=self.font_tiny,
        )
        for i, slot in enumerate(self.shop.slots):
            if i >= len(self.shop_slot_rects):
                break
            self._draw_shop_card(self.shop_slot_rects[i], i, slot)

    def _draw_shop_card(self, rect: pygame.Rect, idx: int, slot: Slot) -> None:
        off = slot.offering
        cat_color = theme.CATEGORY_COLOR.get(off.category, theme.TEXT)
        mouse_pos = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse_pos)

        bg = theme.SLOT_HOVER if hovered else theme.SLOT_BG
        pygame.draw.rect(self.screen, bg, rect, border_radius=8)
        border_color = theme.LOCK if slot.locked else theme.PANEL_BORDER
        border_width = 2 if slot.locked else 1
        pygame.draw.rect(self.screen, border_color, rect, border_width, border_radius=8)

        # left category stripe
        stripe = pygame.Rect(rect.x, rect.y, 4, rect.height)
        pygame.draw.rect(self.screen, cat_color, stripe, border_top_left_radius=8, border_bottom_left_radius=8)

        inner_x = rect.x + 14
        top_y = rect.y + 10

        # index badge
        idx_surf = self.font_tiny.render(f"[{idx + 1}]", True, theme.TEXT_DIM)
        self.screen.blit(idx_surf, (inner_x, top_y))

        # lock badge top-right
        if slot.locked:
            draw_pill(
                self.screen,
                "LOCKED",
                (rect.right - 72, top_y),
                self.font_tiny,
                bg=theme.LOCK,
                fg=(30, 24, 10),
                padding=(8, 3),
            )

        # name — shrink font if it would overflow the card.
        name = off.name
        max_name_w = rect.right - inner_x - 14
        name_font = self.font_h2
        if name_font.size(name)[0] > max_name_w:
            name_font = self.font_body_bold
        name_surf = name_font.render(name, True, theme.TEXT)
        self.screen.blit(name_surf, (inner_x, top_y + 16))

        # category label
        label_text = off.label()
        label_surf = self.font_small.render(label_text, True, cat_color)
        self.screen.blit(label_surf, (inner_x, top_y + 16 + name_surf.get_height() + 2))

        # details block
        details_y = top_y + 16 + name_surf.get_height() + 2 + label_surf.get_height() + 10
        self._draw_card_details(off, inner_x, details_y, rect)

        # bottom: price + buy hint
        price_surf = self.font_h2.render(f"{slot.price}g", True, theme.GOLD)
        self.screen.blit(
            price_surf,
            price_surf.get_rect(bottomleft=(inner_x, rect.bottom - 10)),
        )
        can_afford = self.state.gold >= slot.price
        if not can_afford:
            note = self.font_tiny.render("need more gold", True, theme.WARN)
            self.screen.blit(
                note,
                note.get_rect(bottomright=(rect.right - 10, rect.bottom - 10)),
            )
        elif hovered:
            note = self.font_tiny.render("click to buy", True, theme.OK)
            self.screen.blit(
                note,
                note.get_rect(bottomright=(rect.right - 10, rect.bottom - 10)),
            )

    def _draw_card_details(
        self,
        off: Offering,
        x: int,
        y: int,
        card: pygame.Rect,
    ) -> None:
        if isinstance(off, Unit):
            # tier chips
            tier_color = theme.tier_color(off.tier)
            draw_pill(
                self.screen,
                f"TIER {off.tier}",
                (x, y),
                self.font_tiny,
                bg=tier_color,
                fg=(20, 20, 24),
                padding=(8, 3),
            )
            # path chip
            path_color = theme.PATH_COLOR.get(off.path, theme.TEXT)
            draw_pill(
                self.screen,
                off.path.upper(),
                (x + 60, y),
                self.font_tiny,
                bg=path_color,
                fg=(20, 20, 24),
                padding=(8, 3),
            )
            # traits from path investment
            traits = paths.traits_for(off.path, self.state.path_investment)
            if traits:
                trait_surf = self.font_small.render(
                    "Traits: " + ", ".join(traits),
                    True,
                    theme.TEXT_MUTED,
                )
                self.screen.blit(trait_surf, (x, y + 26))
            # resource requirement
            if off.required_resource:
                req_surf = self.font_small.render(
                    f"Requires: {off.required_resource}",
                    True,
                    theme.WARN,
                )
                self.screen.blit(req_surf, (x, y + 46 if traits else y + 26))
        elif isinstance(off, Building):
            tag = "ADVANCED" if off.advanced else "BASIC"
            draw_pill(
                self.screen,
                tag,
                (x, y),
                self.font_tiny,
                bg=theme.CATEGORY_COLOR["building"],
                fg=(20, 20, 24),
                padding=(8, 3),
            )
            self._wrap_text(off.effect, x, y + 26, card.right - x - 14, self.font_small, theme.TEXT_MUTED)
        elif isinstance(off, Wonder):
            draw_pill(
                self.screen,
                "WONDER",
                (x, y),
                self.font_tiny,
                bg=theme.CATEGORY_COLOR["wonder"],
                fg=(30, 24, 10),
                padding=(8, 3),
            )
            era_surf = self.font_small.render(off.era.name.title(), True, theme.TEXT_MUTED)
            self.screen.blit(era_surf, (x + 80, y + 2))
            self._wrap_text(off.effect, x, y + 26, card.right - x - 14, self.font_small, theme.TEXT_MUTED)
        elif isinstance(off, Event):
            draw_pill(
                self.screen,
                "EVENT",
                (x, y),
                self.font_tiny,
                bg=theme.CATEGORY_COLOR["event"],
                fg=(20, 20, 24),
                padding=(8, 3),
            )
            self._wrap_text(off.effect, x, y + 26, card.right - x - 14, self.font_small, theme.TEXT_MUTED)

    def _wrap_text(
        self,
        text: str,
        x: int,
        y: int,
        max_width: int,
        font: pygame.font.Font,
        color: tuple[int, int, int],
    ) -> None:
        words = text.split()
        line = ""
        line_y = y
        line_h = font.get_linesize()
        for word in words:
            trial = (line + " " + word).strip()
            if font.size(trial)[0] <= max_width:
                line = trial
            else:
                if line:
                    surf = font.render(line, True, color)
                    self.screen.blit(surf, (x, line_y))
                    line_y += line_h
                line = word
        if line:
            surf = font.render(line, True, color)
            self.screen.blit(surf, (x, line_y))

    def _draw_army_panel(self) -> None:
        x = theme.WIDTH - theme.RIGHT_W
        y = theme.TOP_BAR_H + theme.PAD
        h = theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD
        rect = pygame.Rect(x, y, theme.RIGHT_W - theme.PAD, h)
        inner = draw_panel(
            self.screen,
            rect,
            title=f"ARMY  ({len(self.state.army)}/{self._army_cap()})",
            title_font=self.font_tiny,
        )

        counts: Counter[Unit] = Counter(self.state.army)
        row_y = inner.y
        row_h = 26
        for unit, count in sorted(counts.items(), key=lambda kv: (-kv[0].tier, kv[0].name)):
            color = theme.PATH_COLOR.get(unit.path, theme.TEXT)
            pygame.draw.rect(
                self.screen,
                color,
                pygame.Rect(inner.x, row_y + 6, 4, row_h - 12),
                border_radius=2,
            )
            name_surf = self.font_body.render(unit.name, True, theme.TEXT)
            self.screen.blit(name_surf, (inner.x + 10, row_y + 4))
            meta_surf = self.font_small.render(
                f"{unit.path} T{unit.tier}",
                True,
                theme.TEXT_MUTED,
            )
            self.screen.blit(meta_surf, (inner.x + 10, row_y + 4 + name_surf.get_height()))
            count_surf = self.font_h2.render(f"x{count}", True, theme.GOLD if count >= 2 else theme.TEXT)
            self.screen.blit(
                count_surf,
                count_surf.get_rect(topright=(inner.right, row_y + 4)),
            )
            # tier-up progress indicator
            if count >= 2:
                hint = self.font_tiny.render(
                    f"{3 - count} to tier up" if count < 3 else "tier up ready",
                    True,
                    theme.OK if count >= 3 else theme.TEXT_MUTED,
                )
                self.screen.blit(
                    hint,
                    hint.get_rect(topright=(inner.right, row_y + 4 + count_surf.get_height())),
                )
            row_y += row_h + 6
            if row_y > inner.bottom - 80:
                break

        # buildings and wonders at the bottom
        footer_y = inner.bottom - 70
        pygame.draw.line(
            self.screen, theme.DIVIDER,
            (inner.x, footer_y - 6),
            (inner.right, footer_y - 6),
            1,
        )
        b_label = self.font_tiny.render("BUILDINGS", True, theme.TEXT_MUTED)
        self.screen.blit(b_label, (inner.x, footer_y))
        b_text = ", ".join(self.state.buildings) or "(none)"
        b_surf = self.font_small.render(b_text, True, theme.TEXT)
        self.screen.blit(b_surf, (inner.x + 80, footer_y))

        w_label = self.font_tiny.render("WONDERS", True, theme.TEXT_MUTED)
        self.screen.blit(w_label, (inner.x, footer_y + 20))
        w_text = ", ".join(self.state.wonders) or "(none)"
        w_surf = self.font_small.render(w_text, True, theme.GOLD if self.state.wonders else theme.TEXT)
        self.screen.blit(w_surf, (inner.x + 80, footer_y + 20))

        lock_label = self.font_tiny.render("LOCKED SLOT", True, theme.TEXT_MUTED)
        self.screen.blit(lock_label, (inner.x, footer_y + 40))
        if self.state.locked_slot is not None:
            lock_text = f"slot {self.state.locked_slot + 1}"
            lock_color = theme.LOCK
        else:
            lock_text = "(none)"
            lock_color = theme.TEXT_DIM
        lock_surf = self.font_small.render(lock_text, True, lock_color)
        self.screen.blit(lock_surf, (inner.x + 80, footer_y + 40))

    def _army_cap(self) -> int:
        return config.STARTING_ARMY_CAP + self.state.turn // 10

    def _draw_bottom_bar(self) -> None:
        rect = pygame.Rect(
            0,
            theme.HEIGHT - theme.BOTTOM_BAR_H,
            theme.WIDTH,
            theme.BOTTOM_BAR_H,
        )
        pygame.draw.rect(self.screen, theme.PANEL, rect)
        pygame.draw.line(
            self.screen,
            theme.PANEL_BORDER,
            (0, rect.y),
            (rect.right, rect.y),
            1,
        )

        # Log in the center
        log_x = theme.PAD + 200
        log_w = theme.WIDTH - log_x - 240 - theme.PAD
        log_y = rect.y + 10
        log_label = self.font_tiny.render("LOG", True, theme.TEXT_MUTED)
        self.screen.blit(log_label, (log_x, log_y))
        line_y = log_y + 16
        for line in self.log_lines[-4:]:
            surf = self.font_small.render(line[:140], True, theme.TEXT)
            self.screen.blit(surf, (log_x, line_y))
            line_y += surf.get_height() + 2


def run(seed: Optional[int] = None) -> int:
    app = App(seed=seed)
    return app.run()
