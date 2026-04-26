"""Shop screen — adapted from the original single-screen prototype."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import pygame

from ... import config, paths
from ...offerings import (
    Building,
    Event,
    Offering,
    Unit,
    UNITS,
    Wonder,
)
from ...shop import Slot
from .. import theme
from ..widgets import Button, draw_panel, draw_pill

if TYPE_CHECKING:
    from ..app import App


class ShopScreen:
    name = "SHOP"

    def __init__(self) -> None:
        self.shop_slot_rects: list[pygame.Rect] = []
        self.buttons: list[Button] = []

    def enter(self, app: "App") -> None:
        self.rebuild(app)

    # --- input ---------------------------------------------------------
    def rebuild(self, app: "App") -> None:
        self.buttons = []
        self.shop_slot_rects = []

        state = app.world.player
        # Left-side: paths panel + muster
        left_x = theme.PAD
        y = theme.TOP_BAR_H + theme.PAD
        paths_panel = pygame.Rect(left_x, y, theme.LEFT_W - theme.PAD, 460)
        inner_x = paths_panel.x + theme.PAD
        inner_y = paths_panel.y + theme.PAD + 28

        # Invest +/-
        row_y = inner_y
        row_h = 30
        for path_name in app.world.player.path_investment.keys():
            invest_btn_rect = (
                paths_panel.right - theme.PAD - 30,
                row_y + 2,
                26,
                row_h - 8,
            )
            can_invest = state.ap >= config.PATH_INVEST_AP_COST
            self.buttons.append(
                Button(
                    invest_btn_rect,
                    "+",
                    lambda p=path_name: app.do_invest(p),
                    disabled=not can_invest,
                    accent=theme.PATH_COLOR.get(path_name),
                )
            )
            row_y += row_h

        # Muster buttons
        muster_y = row_y + 70
        for path_name in state.path_investment:
            level = state.path_investment.get(path_name, 0)
            if level <= 0:
                continue
            can_muster = (
                not state.mustered_this_turn
                and state.ap >= config.MUSTER_AP_COST
            )
            tier = paths.muster_tier(state.path_investment, path_name)
            self.buttons.append(
                Button(
                    (inner_x, muster_y, theme.LEFT_W - theme.PAD - 2 * theme.PAD, 28),
                    f"Muster {path_name} (T{tier})  -1 AP",
                    lambda p=path_name: app.do_muster(p),
                    disabled=not can_muster,
                    accent=theme.PATH_COLOR.get(path_name),
                )
            )
            muster_y += 32

        # Reroll button (mid-bottom of shop area)
        bar_y = theme.HEIGHT - theme.BOTTOM_BAR_H - 50
        reroll_cost = state.reroll_cost()
        self.buttons.append(
            Button(
                (theme.LEFT_W + theme.PAD, bar_y, 200, 38),
                "Reroll Shop",
                app.do_reroll,
                disabled=state.gold < reroll_cost,
                accent=theme.AP,
                subtitle=f"{reroll_cost}g  (R)",
            )
        )

        # Shop card rects
        shop_x = theme.LEFT_W + theme.PAD
        shop_y = theme.TOP_BAR_H + theme.PAD
        shop_w = theme.WIDTH - theme.LEFT_W - theme.RIGHT_W - theme.PAD
        shop_h = theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD - 50
        inner_sx = shop_x + theme.PAD
        inner_sy = shop_y + theme.PAD + 28
        inner_sw = shop_w - 2 * theme.PAD
        inner_sh = shop_h - 2 * theme.PAD - 28
        card_w = (inner_sw - (theme.SHOP_COLS - 1) * theme.CARD_GAP) // theme.SHOP_COLS
        card_h = (inner_sh - (theme.SHOP_ROWS - 1) * theme.CARD_GAP) // theme.SHOP_ROWS
        for i in range(min(theme.SHOP_COLS * theme.SHOP_ROWS, len(app.shop.slots))):
            c = i % theme.SHOP_COLS
            r = i // theme.SHOP_COLS
            x = inner_sx + c * (card_w + theme.CARD_GAP)
            y_ = inner_sy + r * (card_h + theme.CARD_GAP)
            self.shop_slot_rects.append(pygame.Rect(x, y_, card_w, card_h))

    def update(self, app: "App", mouse_pos) -> None:
        for b in self.buttons:
            b.update(mouse_pos)

    def handle_event(self, app: "App", event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                app.do_reroll()
                return True
            if pygame.K_1 <= event.key <= pygame.K_8:
                idx = event.key - pygame.K_1
                if idx < len(app.shop.slots):
                    app.do_buy(idx)
                return True
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                for b in self.buttons:
                    if b.handle_click(event.pos):
                        return True
                for i, rect in enumerate(self.shop_slot_rects):
                    if rect.collidepoint(event.pos):
                        app.do_buy(i)
                        return True
            elif event.button == 3:
                for i, rect in enumerate(self.shop_slot_rects):
                    if rect.collidepoint(event.pos):
                        if app.world.player.locked_slot == i:
                            app.do_unlock()
                        else:
                            app.do_lock(i)
                        return True
        return False

    # --- drawing -------------------------------------------------------

    def draw(self, app: "App", surface: pygame.Surface) -> None:
        self._draw_paths(app, surface)
        self._draw_shop(app, surface)
        self._draw_army_summary(app, surface)
        for b in self.buttons:
            b.draw(surface, app.font_body, app.font_small)

    def _draw_paths(self, app: "App", surface: pygame.Surface) -> None:
        rect = pygame.Rect(theme.PAD, theme.TOP_BAR_H + theme.PAD,
                           theme.LEFT_W - theme.PAD, 460)
        inner = draw_panel(surface, rect, title="SKILL PATHS", title_font=app.font_tiny)

        state = app.world.player
        row_y = inner.y
        row_h = 30
        for path_name in state.path_investment:
            level = state.path_investment[path_name]
            color = theme.PATH_COLOR.get(path_name, theme.TEXT)
            swatch = pygame.Rect(inner.x, row_y + 6, 6, row_h - 12)
            pygame.draw.rect(surface, color, swatch, border_radius=2)
            name_surf = app.font_body.render(path_name, True, theme.TEXT)
            surface.blit(name_surf, (inner.x + 14, row_y + row_h // 2 - name_surf.get_height() // 2))
            dots_x = inner.x + 14 + 70
            for d in range(5):
                cx = dots_x + d * 10
                cy = row_y + row_h // 2
                if d < level:
                    pygame.draw.circle(surface, color, (cx, cy), 4)
                else:
                    pygame.draw.circle(surface, theme.DIVIDER, (cx, cy), 4, 1)
            row_y += row_h

        pity_y = row_y + 10
        deepest = state.deepest_path()
        if deepest:
            pity_t = max(1, config.PITY_TIMER_THRESHOLD - state.pity_reduction)
            txt = f"Pity: {state.pity_counter}/{pity_t} ({deepest})"
        else:
            txt = "Pity: (no investment)"
        surf = app.font_small.render(txt, True, theme.TEXT_MUTED)
        surface.blit(surf, (inner.x, pity_y))

        pygame.draw.line(surface, theme.DIVIDER,
                         (inner.x, pity_y + 24), (inner.right, pity_y + 24), 1)
        muster_label = app.font_tiny.render("TARGETED MUSTER", True, theme.TEXT_MUTED)
        surface.blit(muster_label, (inner.x, pity_y + 30))
        if not any(v > 0 for v in state.path_investment.values()):
            hint = app.font_small.render("Invest in a path to unlock", True, theme.TEXT_DIM)
            surface.blit(hint, (inner.x, pity_y + 52))

    def _draw_shop(self, app: "App", surface: pygame.Surface) -> None:
        shop_x = theme.LEFT_W + theme.PAD
        shop_y = theme.TOP_BAR_H + theme.PAD
        shop_w = theme.WIDTH - theme.LEFT_W - theme.RIGHT_W - theme.PAD
        shop_h = theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD - 50
        rect = pygame.Rect(shop_x, shop_y, shop_w, shop_h)
        draw_panel(
            surface, rect,
            title=f"SHOP — {len(app.shop.slots)} offerings  (left click = buy, right click = lock)",
            title_font=app.font_tiny,
        )
        for i, slot in enumerate(app.shop.slots):
            if i >= len(self.shop_slot_rects):
                break
            self._draw_card(app, surface, self.shop_slot_rects[i], i, slot)

    def _draw_card(self, app: "App", surface: pygame.Surface,
                   rect: pygame.Rect, idx: int, slot: Slot) -> None:
        off = slot.offering
        cat_color = theme.CATEGORY_COLOR.get(off.category, theme.TEXT)
        mouse_pos = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse_pos)
        bg = theme.SLOT_HOVER if hovered else theme.SLOT_BG
        pygame.draw.rect(surface, bg, rect, border_radius=8)
        border_color = theme.LOCK if slot.locked else theme.PANEL_BORDER
        border_width = 2 if slot.locked else 1
        pygame.draw.rect(surface, border_color, rect, border_width, border_radius=8)
        stripe = pygame.Rect(rect.x, rect.y, 4, rect.height)
        pygame.draw.rect(surface, cat_color, stripe,
                         border_top_left_radius=8, border_bottom_left_radius=8)

        inner_x = rect.x + 14
        top_y = rect.y + 10
        idx_surf = app.font_tiny.render(f"[{idx + 1}]", True, theme.TEXT_DIM)
        surface.blit(idx_surf, (inner_x, top_y))

        if slot.locked:
            draw_pill(surface, "LOCKED", (rect.right - 72, top_y),
                      app.font_tiny, bg=theme.LOCK, fg=(30, 24, 10), padding=(8, 3))

        name = off.name
        max_name_w = rect.right - inner_x - 14
        name_font = app.font_h2
        if name_font.size(name)[0] > max_name_w:
            name_font = app.font_body_bold
        name_surf = name_font.render(name, True, theme.TEXT)
        surface.blit(name_surf, (inner_x, top_y + 16))

        label_text = off.label()
        label_surf = app.font_small.render(label_text, True, cat_color)
        surface.blit(label_surf, (inner_x, top_y + 16 + name_surf.get_height() + 2))

        details_y = top_y + 16 + name_surf.get_height() + 2 + label_surf.get_height() + 10
        self._draw_details(app, surface, off, inner_x, details_y, rect)

        price_surf = app.font_h2.render(f"{slot.price}g", True, theme.GOLD)
        surface.blit(price_surf, price_surf.get_rect(bottomleft=(inner_x, rect.bottom - 10)))

        can_afford = app.world.player.gold >= slot.price
        if not can_afford:
            note = app.font_tiny.render("need more gold", True, theme.WARN)
            surface.blit(note, note.get_rect(bottomright=(rect.right - 10, rect.bottom - 10)))
        elif hovered:
            note = app.font_tiny.render("click to buy", True, theme.OK)
            surface.blit(note, note.get_rect(bottomright=(rect.right - 10, rect.bottom - 10)))

    def _draw_details(self, app: "App", surface: pygame.Surface,
                      off: Offering, x: int, y: int, card: pygame.Rect) -> None:
        if isinstance(off, Unit):
            tier_color = theme.tier_color(off.tier)
            draw_pill(surface, f"TIER {off.tier}", (x, y),
                      app.font_tiny, bg=tier_color, fg=(20, 20, 24), padding=(8, 3))
            path_color = theme.PATH_COLOR.get(off.path, theme.TEXT)
            draw_pill(surface, off.path.upper(), (x + 60, y),
                      app.font_tiny, bg=path_color, fg=(20, 20, 24), padding=(8, 3))
            stats = app.font_small.render(
                f"HP {off.hp}  ATK {off.attack}  DEF {off.defense}  SPD {off.speed}  RNG {off.rng}",
                True, theme.TEXT_MUTED,
            )
            surface.blit(stats, (x, y + 26))
            traits = paths.traits_for(off.path, app.world.player.path_investment)
            if traits:
                trait_surf = app.font_small.render(
                    "Traits: " + ", ".join(traits), True, theme.TEXT_MUTED)
                surface.blit(trait_surf, (x, y + 44))
            if off.required_resource:
                req_surf = app.font_small.render(
                    f"Requires: {off.required_resource}", True, theme.WARN)
                surface.blit(req_surf, (x, y + 62 if traits else y + 44))
        elif isinstance(off, Building):
            tag = "ADVANCED" if off.advanced else "BASIC"
            draw_pill(surface, tag, (x, y), app.font_tiny,
                      bg=theme.CATEGORY_COLOR["building"], fg=(20, 20, 24), padding=(8, 3))
            self._wrap_text(surface, off.effect, x, y + 26,
                            card.right - x - 14, app.font_small, theme.TEXT_MUTED)
        elif isinstance(off, Wonder):
            draw_pill(surface, "WONDER", (x, y), app.font_tiny,
                      bg=theme.CATEGORY_COLOR["wonder"], fg=(30, 24, 10), padding=(8, 3))
            era_surf = app.font_small.render(off.era.name.title(), True, theme.TEXT_MUTED)
            surface.blit(era_surf, (x + 80, y + 2))
            self._wrap_text(surface, off.effect, x, y + 26,
                            card.right - x - 14, app.font_small, theme.TEXT_MUTED)
        elif isinstance(off, Event):
            draw_pill(surface, "EVENT", (x, y), app.font_tiny,
                      bg=theme.CATEGORY_COLOR["event"], fg=(20, 20, 24), padding=(8, 3))
            self._wrap_text(surface, off.effect, x, y + 26,
                            card.right - x - 14, app.font_small, theme.TEXT_MUTED)

    def _wrap_text(self, surface, text, x, y, max_width, font, color):
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
                    surface.blit(font.render(line, True, color), (x, line_y))
                    line_y += line_h
                line = word
        if line:
            surface.blit(font.render(line, True, color), (x, line_y))

    def _draw_army_summary(self, app: "App", surface: pygame.Surface) -> None:
        x = theme.WIDTH - theme.RIGHT_W
        y = theme.TOP_BAR_H + theme.PAD
        h = theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD
        rect = pygame.Rect(x, y, theme.RIGHT_W - theme.PAD, h)
        cap = app.world.army_cap(app.world.player)
        inner = draw_panel(
            surface, rect,
            title=f"ARMY  ({len(app.world.player.army)}/{cap})",
            title_font=app.font_tiny,
        )

        counts: Counter[Unit] = Counter(app.world.player.army)
        row_y = inner.y
        row_h = 26
        for unit, count in sorted(counts.items(), key=lambda kv: (-kv[0].tier, kv[0].name)):
            color = theme.PATH_COLOR.get(unit.path, theme.TEXT)
            pygame.draw.rect(surface, color,
                             pygame.Rect(inner.x, row_y + 6, 4, row_h - 12),
                             border_radius=2)
            surface.blit(app.font_body.render(unit.name, True, theme.TEXT),
                         (inner.x + 10, row_y + 4))
            meta = app.font_small.render(f"{unit.path} T{unit.tier}", True, theme.TEXT_MUTED)
            surface.blit(meta, (inner.x + 10, row_y + 4 + 18))
            count_surf = app.font_h2.render(
                f"x{count}", True, theme.GOLD if count >= 2 else theme.TEXT)
            surface.blit(count_surf, count_surf.get_rect(topright=(inner.right, row_y + 4)))
            row_y += row_h + 6
            if row_y > inner.bottom - 80:
                break

        # Footer
        footer_y = inner.bottom - 70
        pygame.draw.line(surface, theme.DIVIDER,
                         (inner.x, footer_y - 6), (inner.right, footer_y - 6), 1)
        b_label = app.font_tiny.render("BUILDINGS", True, theme.TEXT_MUTED)
        surface.blit(b_label, (inner.x, footer_y))
        b_text = ", ".join(app.world.player.buildings) or "(none)"
        surface.blit(app.font_small.render(b_text[:48], True, theme.TEXT),
                     (inner.x + 80, footer_y))
        w_label = app.font_tiny.render("WONDERS", True, theme.TEXT_MUTED)
        surface.blit(w_label, (inner.x, footer_y + 20))
        w_text = ", ".join(app.world.player.wonders) or "(none)"
        surface.blit(
            app.font_small.render(w_text[:48], True,
                                  theme.GOLD if app.world.player.wonders else theme.TEXT),
            (inner.x + 80, footer_y + 20),
        )
        lock_label = app.font_tiny.render("LOCKED SLOT", True, theme.TEXT_MUTED)
        surface.blit(lock_label, (inner.x, footer_y + 40))
        if app.world.player.locked_slot is not None:
            lt = f"slot {app.world.player.locked_slot + 1}"
            lc = theme.LOCK
        else:
            lt, lc = "(none)", theme.TEXT_DIM
        surface.blit(app.font_small.render(lt, True, lc), (inner.x + 80, footer_y + 40))
