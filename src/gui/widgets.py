"""Reusable pygame widgets for the graphical prototype."""

from __future__ import annotations

from typing import Callable, Optional

import pygame

from . import theme


class Button:
    """Rectangular clickable region with hover and disabled states."""

    def __init__(
        self,
        rect: tuple[int, int, int, int],
        label: str,
        callback: Callable[[], None],
        *,
        disabled: bool = False,
        accent: Optional[tuple[int, int, int]] = None,
        subtitle: Optional[str] = None,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.disabled = disabled
        self.accent = accent
        self.subtitle = subtitle
        self._hover = False

    def update(self, mouse_pos: tuple[int, int]) -> None:
        self._hover = self.rect.collidepoint(mouse_pos) and not self.disabled

    def handle_click(self, pos: tuple[int, int]) -> bool:
        if self.disabled or not self.rect.collidepoint(pos):
            return False
        self.callback()
        return True

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        sub_font: Optional[pygame.font.Font] = None,
    ) -> None:
        if self.disabled:
            bg = theme.SLOT_DISABLED
            text_color = theme.TEXT_DIM
        elif self._hover:
            bg = theme.SLOT_HOVER
            text_color = theme.TEXT
        else:
            bg = theme.SLOT_BG
            text_color = theme.TEXT

        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        border = self.accent if (self.accent and not self.disabled) else theme.PANEL_BORDER
        pygame.draw.rect(surface, border, self.rect, 1, border_radius=6)

        if self.accent and not self.disabled:
            stripe = pygame.Rect(self.rect.x, self.rect.y, 3, self.rect.height)
            pygame.draw.rect(surface, self.accent, stripe, border_radius=2)

        if self.subtitle and sub_font is not None:
            label_surf = font.render(self.label, True, text_color)
            sub_surf = sub_font.render(self.subtitle, True, theme.TEXT_MUTED)
            total_h = label_surf.get_height() + sub_surf.get_height() + 2
            y0 = self.rect.centery - total_h // 2
            surface.blit(
                label_surf,
                label_surf.get_rect(midtop=(self.rect.centerx, y0)),
            )
            surface.blit(
                sub_surf,
                sub_surf.get_rect(
                    midtop=(self.rect.centerx, y0 + label_surf.get_height() + 2)
                ),
            )
        else:
            text_surf = font.render(self.label, True, text_color)
            surface.blit(text_surf, text_surf.get_rect(center=self.rect.center))


def draw_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    title: Optional[str] = None,
    title_font: Optional[pygame.font.Font] = None,
) -> pygame.Rect:
    """Draw a standard panel container. Returns the inner content rect."""
    pygame.draw.rect(surface, theme.PANEL, rect, border_radius=8)
    pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1, border_radius=8)
    content = rect.inflate(-2 * theme.PAD, -2 * theme.PAD)
    content.topleft = (rect.x + theme.PAD, rect.y + theme.PAD)
    if title and title_font is not None:
        title_surf = title_font.render(title, True, theme.TEXT_MUTED)
        surface.blit(title_surf, (content.x, content.y))
        offset = title_surf.get_height() + 6
        pygame.draw.line(
            surface,
            theme.DIVIDER,
            (content.x, content.y + offset - 2),
            (content.right, content.y + offset - 2),
            1,
        )
        content.y += offset + 4
        content.height -= offset + 4
    return content


def draw_text(
    surface: pygame.Surface,
    text: str,
    pos: tuple[int, int],
    font: pygame.font.Font,
    color: tuple[int, int, int] = theme.TEXT,
) -> pygame.Rect:
    surf = font.render(text, True, color)
    return surface.blit(surf, pos)


def draw_text_right(
    surface: pygame.Surface,
    text: str,
    right_pos: tuple[int, int],
    font: pygame.font.Font,
    color: tuple[int, int, int] = theme.TEXT,
) -> pygame.Rect:
    surf = font.render(text, True, color)
    return surface.blit(surf, surf.get_rect(topright=right_pos))


def draw_pill(
    surface: pygame.Surface,
    text: str,
    pos: tuple[int, int],
    font: pygame.font.Font,
    bg: tuple[int, int, int],
    fg: tuple[int, int, int] = theme.TEXT,
    padding: tuple[int, int] = (8, 3),
) -> pygame.Rect:
    text_surf = font.render(text, True, fg)
    rect = pygame.Rect(
        pos[0],
        pos[1],
        text_surf.get_width() + padding[0] * 2,
        text_surf.get_height() + padding[1] * 2,
    )
    pygame.draw.rect(surface, bg, rect, border_radius=rect.height // 2)
    surface.blit(text_surf, (rect.x + padding[0], rect.y + padding[1]))
    return rect
