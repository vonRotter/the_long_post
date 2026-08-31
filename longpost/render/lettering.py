"""Type. One face, plainly set.

Settlement names are small caps, letter-spaced, beside the circle. Numbers are
set in the panel, never on the chart.
"""

import os
from functools import lru_cache

import pygame

from .. import tuning as T

FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chart.ttf")


@lru_cache(maxsize=32)
def font(size: int) -> pygame.font.Font:
    return pygame.font.Font(FONT_PATH, size)


@lru_cache(maxsize=4096)
def _glyph(ch: str, size: int, colour: tuple, alpha: int) -> pygame.Surface:
    surf = font(size).render(ch, True, colour)
    surf = surf.convert_alpha()
    surf.set_alpha(alpha)
    return surf


def draw(surface, text, pos, size=13, colour=T.INK, alpha=210, spacing=0.0,
         caps=False, align="left"):
    """Draw a line of type. Returns its width."""
    if caps:
        text = text.upper()
    glyphs = [_glyph(ch, size, tuple(colour), alpha) for ch in text]
    width = sum(g.get_width() for g in glyphs) + spacing * max(0, len(glyphs) - 1)
    x, y = pos
    if align == "right":
        x -= width
    elif align == "centre":
        x -= width / 2
    for g in glyphs:
        surface.blit(g, (int(x), int(y)))
        x += g.get_width() + spacing
    return width


def width(text, size=13, spacing=0.0, caps=False) -> float:
    if caps:
        text = text.upper()
    f = font(size)
    return sum(f.size(ch)[0] for ch in text) + spacing * max(0, len(text) - 1)
