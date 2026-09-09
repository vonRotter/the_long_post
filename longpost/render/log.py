"""The resolution log.

Plain declarative sentences. No adjectives of feeling, no second person, and
never a line telling the player how an event should land.
"""

import pygame

from .. import tuning as T
from . import ink, lettering


class Log:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.lines = []

    def write(self, text, year=None, season=None, accent=False):
        prefix = ""
        if year is not None and season is not None:
            prefix = f"{season.lower()[:3]} {year}  "
        self.lines.append((prefix + text, accent))
        del self.lines[: max(0, len(self.lines) - T.LOG_LINES_KEPT)]

    def draw(self, target):
        r = self.rect
        layer = pygame.Surface(r.size, pygame.SRCALPHA)
        ink.ink_line(layer, (14, 3), (r.w - 14, 3), "faint", ink.seed_of("log rule"))
        y = 14
        for text, accent in self.lines[-T.LOG_LINES_SHOWN:]:
            colour = T.OXIDE if accent else T.INK
            lettering.draw(layer, text, (18, y), size=11, alpha=195, colour=colour)
            y += 16
        target.blit(layer, r.topleft)
