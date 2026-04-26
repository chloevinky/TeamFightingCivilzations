"""Main pygame application: top bar with screen tabs, routing to per-screen
modules, shared event/turn flow.
"""

from __future__ import annotations

import random
from typing import Optional

import pygame

from .. import config, paths
from ..offerings import UNITS, Unit
from ..shop import Shop
from ..world import World
from . import theme
from .screens.army_screen import ArmyScreen
from .screens.battle_screen import BattleScreen
from .screens.diplomacy_screen import DiplomacyScreen
from .screens.map_screen import MapScreen
from .screens.shop_screen import ShopScreen
from .screens.tech_screen import TechScreen
from .widgets import Button


SCREEN_ORDER = ["MAP", "SHOP", "TECH", "DIPLOMACY", "ARMY", "BATTLE"]


class App:
    def __init__(self, seed: Optional[int] = None) -> None:
        self.world = World(seed=seed)
        self.shop = Shop(self.world.player, rng=self.world.rng)
        self.shop.refresh(is_free=True)

        pygame.init()
        pygame.display.set_caption("Hexfall — Full Game Prototype")
        self.screen_surf = pygame.display.set_mode((theme.WIDTH, theme.HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_h1 = pygame.font.SysFont("arial", 26, bold=True)
        self.font_h2 = pygame.font.SysFont("arial", 18, bold=True)
        self.font_body = pygame.font.SysFont("arial", 15)
        self.font_body_bold = pygame.font.SysFont("arial", 15, bold=True)
        self.font_small = pygame.font.SysFont("arial", 13)
        self.font_tiny = pygame.font.SysFont("arial", 11, bold=True)

        self.log_lines: list[str] = ["Welcome to Hexfall.  Explore, expand, conquer."]
        self.screens = {
            "MAP": MapScreen(),
            "SHOP": ShopScreen(),
            "TECH": TechScreen(),
            "DIPLOMACY": DiplomacyScreen(),
            "ARMY": ArmyScreen(),
            "BATTLE": BattleScreen(),
        }
        self.current_screen = "MAP"
        self.tab_buttons: list[tuple[pygame.Rect, str]] = []
        self.bottom_buttons: list[Button] = []
        self._rebuild_chrome()
        self.screens[self.current_screen].enter(self)
        self.running = True

    # --- frame loop ----------------------------------------------------

    def run(self) -> int:
        while self.running:
            self.clock.tick(theme.FPS)
            self._handle_events()
            self._draw()
            pygame.display.flip()
        pygame.quit()
        return 0

    # --- screens / chrome ---------------------------------------------

    def set_screen(self, name: str) -> None:
        if name not in self.screens:
            return
        self.current_screen = name
        self.screens[name].enter(self)

    def _rebuild_chrome(self) -> None:
        self.tab_buttons = []
        x = theme.PAD + 130
        y = 8
        for name in SCREEN_ORDER:
            label = name
            w = self.font_body.size(label)[0] + 22
            rect = pygame.Rect(x, y, w, 28)
            self.tab_buttons.append((rect, name))
            x += w + 6

        # Bottom bar buttons.
        bar_y = theme.HEIGHT - theme.BOTTOM_BAR_H + 18
        bar_h = theme.BOTTOM_BAR_H - 36
        self.bottom_buttons = [
            Button(
                (theme.WIDTH - 220 - theme.PAD, bar_y, 220, bar_h),
                "End Turn", self.do_end_turn, accent=theme.OK, subtitle="SPACE",
            ),
        ]

    # --- event handling ------------------------------------------------

    def _handle_events(self) -> None:
        mouse_pos = pygame.mouse.get_pos()
        self.screens[self.current_screen].update(self, mouse_pos)
        for b in self.bottom_buttons:
            b.update(mouse_pos)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if self.world.game_over and event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    continue
                if event.key == pygame.K_SPACE:
                    self.do_end_turn()
                    continue
                if event.key == pygame.K_TAB:
                    idx = SCREEN_ORDER.index(self.current_screen)
                    self.set_screen(SCREEN_ORDER[(idx + 1) % len(SCREEN_ORDER)])
                    continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Tab clicks
                clicked_tab = False
                for rect, name in self.tab_buttons:
                    if rect.collidepoint(event.pos):
                        self.set_screen(name)
                        clicked_tab = True
                        break
                if clicked_tab:
                    continue
                for b in self.bottom_buttons:
                    if b.handle_click(event.pos):
                        break
                else:
                    self.screens[self.current_screen].handle_event(self, event)
                    continue
            else:
                self.screens[self.current_screen].handle_event(self, event)

        # Auto-switch to Battle screen if a battle is pending and we're not there.
        if self.world.pending_battle is not None and self.current_screen != "BATTLE":
            self.set_screen("BATTLE")

    # --- player actions exposed to screens -----------------------------

    def log(self, msg: str) -> None:
        if not msg:
            return
        for line in msg.splitlines():
            line = line.strip()
            if line:
                self.log_lines.append(line)
        self.log_lines = self.log_lines[-8:]

    def do_buy(self, idx: int) -> None:
        self.log(self.shop.buy(idx))
        self.screens["SHOP"].rebuild(self)

    def do_lock(self, idx: int) -> None:
        self.log(self.shop.lock(idx))
        self.screens["SHOP"].rebuild(self)

    def do_unlock(self) -> None:
        self.log(self.shop.unlock())
        self.screens["SHOP"].rebuild(self)

    def do_reroll(self) -> None:
        self.log(self.shop.paid_reroll())
        self.screens["SHOP"].rebuild(self)

    def do_invest(self, path: str) -> None:
        if self.world.player.ap < config.PATH_INVEST_AP_COST:
            self.log("Not enough AP.")
            return
        self.world.player.ap -= config.PATH_INVEST_AP_COST
        paths.invest(self.world.player.path_investment, path)
        self.log(f"Invested in {path} (now {self.world.player.path_investment[path]}).")
        self.screens["SHOP"].rebuild(self)

    def do_muster(self, path: str) -> None:
        if self.world.player.mustered_this_turn:
            self.log("Already mustered this turn.")
            return
        if self.world.player.path_investment.get(path, 0) <= 0:
            self.log(f"Cannot muster from {path}.")
            return
        if self.world.player.ap < config.MUSTER_AP_COST:
            self.log("Not enough AP.")
            return
        tier = paths.muster_tier(self.world.player.path_investment, path)
        cands = [u for u in UNITS if u.path == path and u.tier <= tier
                 and u.required_resource is None and u.era <= self.world.player.era]
        if not cands:
            self.log(f"No muster candidates for {path}.")
            return
        pick = max(cands, key=lambda u: u.tier)
        self.world.player.ap -= config.MUSTER_AP_COST
        self.world.player.mustered_this_turn = True
        self.log(f"Mustered {pick.name} ({pick.path} T{pick.tier}).")
        for line in self.world.player.add_unit(pick):
            self.log(line)
        self.screens["SHOP"].rebuild(self)

    def do_end_turn(self) -> None:
        if self.world.game_over:
            self.running = False
            return
        # Preserve turn counter consistency with the world.
        self.world.player.end_turn()
        log = self.world.end_player_turn()
        for line in log:
            self.log(line)
        # Refresh shop with new locked-slot logic.
        self.shop.refresh(is_free=True)
        if self.shop.state.locked_slot is not None:
            pass
        self.log(f"--- Turn {self.world.turn} begins ---")
        self.screens[self.current_screen].enter(self)
        # If a battle is pending, go to battle screen.
        if self.world.pending_battle is not None:
            self.set_screen("BATTLE")

    def trigger_battle(self, target: str) -> None:
        if self.world.trigger_player_battle_now(target):
            self.set_screen("BATTLE")

    # --- drawing -------------------------------------------------------

    def _draw(self) -> None:
        self.screen_surf.fill(theme.BG)
        if self.world.game_over:
            self._draw_game_over()
            return
        self._draw_top_bar()
        self.screens[self.current_screen].draw(self, self.screen_surf)
        self._draw_bottom_bar()
        for b in self.bottom_buttons:
            b.draw(self.screen_surf, self.font_body, self.font_small)

    def _draw_top_bar(self) -> None:
        bar = pygame.Rect(0, 0, theme.WIDTH, theme.TOP_BAR_H)
        pygame.draw.rect(self.screen_surf, theme.PANEL, bar)
        pygame.draw.line(self.screen_surf, theme.PANEL_BORDER,
                         (0, theme.TOP_BAR_H), (theme.WIDTH, theme.TOP_BAR_H), 1)
        # Title
        title = self.font_h1.render("HEXFALL", True, theme.GOLD)
        self.screen_surf.blit(title, (theme.PAD + 4, 4))

        # Tab buttons
        for rect, name in self.tab_buttons:
            active = name == self.current_screen
            bg = theme.SLOT_HOVER if active else theme.SLOT_BG
            pygame.draw.rect(self.screen_surf, bg, rect, border_radius=6)
            color = theme.GOLD if active else theme.PANEL_BORDER
            pygame.draw.rect(self.screen_surf, color, rect, 1, border_radius=6)
            label_surf = self.font_body.render(name, True, theme.TEXT if active else theme.TEXT_MUTED)
            self.screen_surf.blit(label_surf, label_surf.get_rect(center=rect.center))

        # Stats
        stats_y = 38
        x = theme.WIDTH - theme.PAD
        x = self._stat_pill("ERA", self.world.player.era.name.title(), x, stats_y, theme.SCIENCE)
        x = self._stat_pill("AP", f"{self.world.player.ap}/{config.ap_for_turn(self.world.turn)}",
                            x, stats_y, theme.AP)
        x = self._stat_pill("GOLD", f"{self.world.player.gold}", x, stats_y, theme.GOLD)
        x = self._stat_pill("TURN", f"{self.world.turn}", x, stats_y, theme.TEXT)
        # Research progress mini-pill
        res = self.world.player.research
        if res.current is not None:
            from ..tech import tech_by_name
            t = tech_by_name(res.current)
            if t:
                pct_text = f"{res.progress}/{t.cost}"
                x = self._stat_pill("RESEARCH", pct_text, x, stats_y, theme.SCIENCE)

    def _stat_pill(self, label, value, right_x, y, color):
        label_surf = self.font_tiny.render(label, True, theme.TEXT_MUTED)
        value_surf = self.font_h2.render(value, True, color)
        w = max(label_surf.get_width(), value_surf.get_width()) + 20
        h = label_surf.get_height() + value_surf.get_height() + 10
        rect = pygame.Rect(right_x - w, y, w, h)
        pygame.draw.rect(self.screen_surf, theme.PANEL_ALT, rect, border_radius=6)
        pygame.draw.rect(self.screen_surf, theme.PANEL_BORDER, rect, 1, border_radius=6)
        self.screen_surf.blit(label_surf,
                              label_surf.get_rect(midtop=(rect.centerx, rect.y + 4)))
        self.screen_surf.blit(value_surf,
                              value_surf.get_rect(midtop=(rect.centerx, rect.y + 4 + label_surf.get_height())))
        return rect.x - 8

    def _draw_bottom_bar(self) -> None:
        rect = pygame.Rect(0, theme.HEIGHT - theme.BOTTOM_BAR_H,
                           theme.WIDTH, theme.BOTTOM_BAR_H)
        pygame.draw.rect(self.screen_surf, theme.PANEL, rect)
        pygame.draw.line(self.screen_surf, theme.PANEL_BORDER,
                         (0, rect.y), (rect.right, rect.y), 1)
        log_x = theme.PAD + 8
        log_w = theme.WIDTH - log_x - 240 - theme.PAD
        log_y = rect.y + 8
        self.screen_surf.blit(self.font_tiny.render("LOG / NOTIFICATIONS",
                              True, theme.TEXT_MUTED), (log_x, log_y))
        line_y = log_y + 16
        merged = list(self.log_lines[-3:]) + list(self.world.notifications[-3:])
        for line in merged[-6:]:
            surf = self.font_small.render(line[:160], True, theme.TEXT)
            self.screen_surf.blit(surf, (log_x, line_y))
            line_y += 16

    def _draw_game_over(self) -> None:
        overlay = pygame.Surface((theme.WIDTH, theme.HEIGHT))
        overlay.fill((10, 12, 20))
        self.screen_surf.blit(overlay, (0, 0))
        winner = self.world.winner or "?"
        result_text = "VICTORY!" if winner == self.world.player.name else f"DEFEAT — {winner} wins"
        color = theme.OK if winner == self.world.player.name else theme.WARN
        title = self.font_h1.render(result_text, True, color)
        self.screen_surf.blit(title, title.get_rect(center=(theme.WIDTH // 2, theme.HEIGHT // 2 - 60)))
        sub = self.font_body.render(
            f"Turn {self.world.turn}.  Press Esc to exit.", True, theme.TEXT_MUTED)
        self.screen_surf.blit(sub, sub.get_rect(center=(theme.WIDTH // 2, theme.HEIGHT // 2)))


def run(seed: Optional[int] = None) -> int:
    app = App(seed=seed)
    return app.run()
