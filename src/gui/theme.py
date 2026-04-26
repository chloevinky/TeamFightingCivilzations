"""Visual constants for the graphical prototype.

Keeps colors, spacings, and layout numbers in one place so the look can be
iterated without touching the app logic.
"""

from __future__ import annotations

from ..hexmap import Terrain


# --- Window / layout ---

WIDTH = 1360
HEIGHT = 820
FPS = 60

TOP_BAR_H = 80
BOTTOM_BAR_H = 96
LEFT_W = 270
RIGHT_W = 320
PAD = 12

SHOP_COLS = 4
SHOP_ROWS = 2
CARD_GAP = 14

# --- Palette (dark, warm accents) ---

BG = (16, 18, 26)
PANEL = (28, 32, 44)
PANEL_ALT = (36, 40, 54)
PANEL_BORDER = (58, 66, 88)
DIVIDER = (44, 50, 68)

TEXT = (232, 232, 240)
TEXT_MUTED = (150, 158, 180)
TEXT_DIM = (96, 104, 124)

GOLD = (228, 180, 88)
AP = (130, 200, 240)
SCIENCE = (160, 210, 255)
WARN = (230, 110, 110)
OK = (120, 210, 140)
LOCK = (230, 170, 70)

SLOT_BG = (40, 46, 62)
SLOT_HOVER = (58, 66, 88)
SLOT_DISABLED = (30, 34, 46)

# Category accents — shown as a left-edge stripe on each shop card.
CATEGORY_COLOR = {
    "unit": (110, 190, 130),
    "building": (120, 150, 220),
    "wonder": (228, 180, 88),
    "event": (210, 130, 210),
}

# Path colors — shown on path rows and unit stripes.
PATH_COLOR = {
    "Melee": (220, 96, 96),
    "Ranged": (140, 210, 130),
    "Cavalry": (230, 180, 90),
    "Navy": (98, 170, 230),
    "Siege": (186, 130, 220),
    "Airforce": (200, 200, 210),
}

# Terrain colors for the hex map.
TERRAIN_COLOR = {
    Terrain.OCEAN:     (28, 60, 110),
    Terrain.COAST:     (68, 130, 180),
    Terrain.PLAINS:    (180, 170, 90),
    Terrain.GRASSLAND: (100, 170, 80),
    Terrain.FOREST:    (40, 110, 60),
    Terrain.HILLS:     (130, 110, 70),
    Terrain.DESERT:    (220, 200, 130),
    Terrain.MOUNTAIN:  (110, 110, 110),
}

FOG_UNSEEN_COLOR = (10, 12, 18)
FOG_SEEN_OVERLAY = (0, 0, 0, 110)

# Civ default colors (used as border/accent).
CIV_COLORS = {
    "Player":   (100, 200, 255),
    "Caesarius": (220, 96, 96),
    "Mercatia":  (228, 180, 88),
    "Lyceum":    (140, 200, 240),
    "Khanate":   (220, 130, 180),
    "Albion":    (160, 220, 170),
}


def tier_color(tier: int) -> tuple[int, int, int]:
    """Visual tier indicator — warmer for higher tiers."""
    if tier >= 3:
        return (230, 120, 90)
    if tier == 2:
        return (230, 190, 100)
    return (180, 190, 210)
