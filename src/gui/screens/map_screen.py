"""Hex map screen.  Renders the world map, borders, cities, fog of war."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

import pygame

from ...hexmap import (
    HexMap,
    Tile,
    axial_to_pixel,
    hex_distance,
    neighbors,
)
from .. import theme
from ..widgets import Button, draw_panel

if TYPE_CHECKING:
    from ..app import App


HEX_SIZE = 28


class MapScreen:
    name = "MAP"

    def __init__(self) -> None:
        self.buttons: list[Button] = []
        self.selected: Optional[tuple[int, int]] = None
        self.center_offset = (0, 0)

    def enter(self, app: "App") -> None:
        self.rebuild(app)

    def rebuild(self, app: "App") -> None:
        self.buttons = []
        # Found city button at the bottom-right of the map area.
        if self.selected:
            tile = app.world.map.get(*self.selected)
            if tile and tile.buildable and tile.owner == app.world.player.name:
                self.buttons.append(
                    Button(
                        (theme.WIDTH - theme.RIGHT_W - 200, theme.HEIGHT - theme.BOTTOM_BAR_H - 50,
                         200, 38),
                        "Found City (150g)",
                        lambda: self._do_found(app),
                        accent=theme.OK,
                        disabled=app.world.player.gold < 150,
                    )
                )

    def _do_found(self, app: "App") -> None:
        if not self.selected:
            return
        msg = app.world.player_found_city(self.selected)
        app.log(msg)
        self.rebuild(app)

    def update(self, app: "App", mouse_pos) -> None:
        for b in self.buttons:
            b.update(mouse_pos)

    def handle_event(self, app: "App", event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.handle_click(event.pos):
                    return True
            tile = self._tile_at(app, event.pos)
            if tile is not None:
                self.selected = (tile.q, tile.r)
                self.rebuild(app)
                return True
        return False

    # --- drawing -------------------------------------------------------

    def draw(self, app: "App", surface: pygame.Surface) -> None:
        rect = pygame.Rect(
            theme.PAD,
            theme.TOP_BAR_H + theme.PAD,
            theme.WIDTH - theme.RIGHT_W - 2 * theme.PAD,
            theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD,
        )
        pygame.draw.rect(surface, (10, 14, 22), rect, border_radius=8)
        pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1, border_radius=8)
        clip = surface.get_clip()
        surface.set_clip(rect)
        self._draw_map(app, surface, rect)
        surface.set_clip(clip)
        self._draw_legend(app, surface)
        self._draw_tile_panel(app, surface)
        for b in self.buttons:
            b.draw(surface, app.font_body, app.font_small)

    def _hex_origin(self, app: "App", rect: pygame.Rect) -> tuple[float, float]:
        return (rect.centerx + self.center_offset[0],
                rect.centery + self.center_offset[1])

    def _hex_polygon(self, cx: float, cy: float, size: float) -> list[tuple[float, float]]:
        pts = []
        for i in range(6):
            angle = math.pi / 180 * (60 * i - 30)  # pointy-top
            pts.append((cx + size * math.cos(angle), cy + size * math.sin(angle)))
        return pts

    def _draw_map(self, app: "App", surface: pygame.Surface, rect: pygame.Rect) -> None:
        ox, oy = self._hex_origin(app, rect)
        m = app.world.map
        player_name = app.world.player.name

        for tile in m:
            px, py = axial_to_pixel(tile.q, tile.r, HEX_SIZE)
            cx, cy = ox + px, oy + py
            if cx + HEX_SIZE < rect.x or cx - HEX_SIZE > rect.right:
                continue
            if cy + HEX_SIZE < rect.y or cy - HEX_SIZE > rect.bottom:
                continue
            poly = self._hex_polygon(cx, cy, HEX_SIZE - 1)
            fog = tile.fog.get(player_name, "unseen")
            if fog == "unseen":
                pygame.draw.polygon(surface, theme.FOG_UNSEEN_COLOR, poly)
                pygame.draw.polygon(surface, (20, 22, 32), poly, 1)
                continue
            color = theme.TERRAIN_COLOR.get(tile.terrain, (60, 60, 60))
            pygame.draw.polygon(surface, color, poly)
            # Owner border tinting
            if tile.owner is not None:
                owner_color = theme.CIV_COLORS.get(tile.owner, (200, 200, 200))
                pygame.draw.polygon(surface, owner_color, poly, 2)
            else:
                pygame.draw.polygon(surface, (10, 14, 22), poly, 1)
            # Resource pip
            if tile.resource:
                pygame.draw.circle(surface, (255, 220, 120), (int(cx), int(cy + HEX_SIZE * 0.4)), 3)
            # City marker
            if tile.city:
                city_color = theme.CIV_COLORS.get(tile.owner, (240, 240, 240))
                pygame.draw.circle(surface, city_color, (int(cx), int(cy)), 8)
                pygame.draw.circle(surface, (10, 10, 10), (int(cx), int(cy)), 8, 2)
                # capital star
                if any(c.capital and c.q == tile.q and c.r == tile.r
                       for civ in app.world.civs for c in civ.cities):
                    star = app.font_small.render("*", True, (255, 255, 200))
                    surface.blit(star, star.get_rect(center=(int(cx), int(cy - 10))))
                # city name
                name_surf = app.font_tiny.render(tile.city, True, (240, 240, 240))
                surface.blit(name_surf, (int(cx) - name_surf.get_width() // 2,
                                         int(cy) + 10))
            # Fog overlay for "seen but not currently visible"
            if fog == "seen":
                fog_surf = pygame.Surface((HEX_SIZE * 2, HEX_SIZE * 2), pygame.SRCALPHA)
                pygame.draw.polygon(fog_surf, theme.FOG_SEEN_OVERLAY,
                                    self._hex_polygon(HEX_SIZE, HEX_SIZE, HEX_SIZE - 1))
                surface.blit(fog_surf, (cx - HEX_SIZE, cy - HEX_SIZE))
            # Selection
            if self.selected == (tile.q, tile.r):
                pygame.draw.polygon(surface, (255, 255, 255), poly, 3)

    def _tile_at(self, app: "App", pos: tuple[int, int]) -> Optional[Tile]:
        rect = pygame.Rect(
            theme.PAD,
            theme.TOP_BAR_H + theme.PAD,
            theme.WIDTH - theme.RIGHT_W - 2 * theme.PAD,
            theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD,
        )
        if not rect.collidepoint(pos):
            return None
        ox, oy = self._hex_origin(app, rect)
        # Brute force: check every tile.
        best: Optional[tuple[float, Tile]] = None
        for tile in app.world.map:
            px, py = axial_to_pixel(tile.q, tile.r, HEX_SIZE)
            cx, cy = ox + px, oy + py
            d = (cx - pos[0]) ** 2 + (cy - pos[1]) ** 2
            if d <= HEX_SIZE * HEX_SIZE * 0.85:
                if best is None or d < best[0]:
                    best = (d, tile)
        return best[1] if best else None

    def _draw_legend(self, app: "App", surface: pygame.Surface) -> None:
        x = theme.PAD + 8
        y = theme.TOP_BAR_H + theme.PAD + 8
        items = [
            ("Plains", theme.TERRAIN_COLOR[list(theme.TERRAIN_COLOR.keys())[2]]),
        ]
        # No big legend — keep it visually clean.

    def _draw_tile_panel(self, app: "App", surface: pygame.Surface) -> None:
        x = theme.WIDTH - theme.RIGHT_W
        y = theme.TOP_BAR_H + theme.PAD
        h = theme.HEIGHT - theme.TOP_BAR_H - theme.BOTTOM_BAR_H - 2 * theme.PAD
        rect = pygame.Rect(x, y, theme.RIGHT_W - theme.PAD, h)
        inner = draw_panel(surface, rect, title="MAP / TILE", title_font=app.font_tiny)

        if self.selected is None:
            t = app.font_small.render("Click a tile to inspect.", True, theme.TEXT_MUTED)
            surface.blit(t, (inner.x, inner.y))
        else:
            tile = app.world.map.get(*self.selected)
            if tile is None:
                return
            yy = inner.y
            terrain = app.font_body_bold.render(
                f"({tile.q},{tile.r}) {tile.terrain.value}", True, theme.TEXT)
            surface.blit(terrain, (inner.x, yy))
            yy += 24
            f, g, s = tile.yields()
            surface.blit(app.font_small.render(
                f"Yields: {f} food / {g} gold / {s} science", True, theme.TEXT_MUTED),
                (inner.x, yy))
            yy += 20
            owner_str = tile.owner or "neutral"
            surface.blit(app.font_small.render(f"Owner: {owner_str}", True, theme.TEXT_MUTED),
                         (inner.x, yy))
            yy += 20
            if tile.resource:
                surface.blit(app.font_small.render(f"Resource: {tile.resource}", True, theme.GOLD),
                             (inner.x, yy))
                yy += 20
            if tile.city:
                surface.blit(app.font_small.render(f"City: {tile.city}", True, theme.OK),
                             (inner.x, yy))
                yy += 20
            fog = tile.fog.get(app.world.player.name, "unseen")
            surface.blit(app.font_tiny.render(f"Visibility: {fog}", True, theme.TEXT_DIM),
                         (inner.x, yy))
            yy += 30
            # Cities summary
            pygame.draw.line(surface, theme.DIVIDER, (inner.x, yy), (inner.right, yy), 1)
            yy += 6
            surface.blit(app.font_tiny.render("YOUR CITIES", True, theme.TEXT_MUTED),
                         (inner.x, yy))
            yy += 18
            for c in app.world.player.cities:
                cap_marker = "*" if c.capital else " "
                line = f"{cap_marker} {c.name}  pop {c.population}  ({c.q},{c.r})"
                surface.blit(app.font_small.render(line, True, theme.TEXT), (inner.x, yy))
                yy += 18
                if yy > inner.bottom - 20:
                    break
