"""The panel: readouts and, from M1, the assignment UI.

Numbers are set here and never on the chart. The panel accumulates over the
run and is never compacted, filtered, or shortened.
"""

import pygame

from .. import tuning as T
from ..world import season as season_mod
from . import ink, lettering, words


class Panel:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.scroll = 0

    def scroll_by(self, lines):
        self.scroll = max(0, self.scroll + lines)

    def draw(self, target, game):
        r = self.rect
        layer = pygame.Surface(r.size, pygame.SRCALPHA)
        ink.ink_line(layer, (2, 8), (2, r.h - 8), "faint", ink.seed_of("panel rule"))

        x = 18
        y = 18
        world = game.world

        y = self._heading(layer, x, y, "THE LONG POST")
        y += 6
        lettering.draw(layer, f"year {game.year} of {T.YEARS}", (x, y), size=12, alpha=200)
        y += 17
        lettering.draw(layer, f"{game.season.lower()}", (x, y), size=14, alpha=225,
                       spacing=1.6, caps=True)
        y += 17
        lettering.draw(layer, season_mod.CHARACTER[game.season], (x, y), size=10, alpha=150)
        y += 16
        lettering.draw(layer, f"turn {game.turn + 1} of {T.TURNS}", (x, y), size=11, alpha=170)
        y += 24

        population = sum(s.population for s in world.known_settlements() if s.alive)
        lettering.draw(layer, "population", (x, y), size=11, alpha=170, spacing=1.2, caps=True)
        lettering.draw(layer, str(population), (r.w - 18, y), size=12, alpha=215, align="right")
        y += 15
        change = population - game.population_at_start
        lettering.draw(layer, f"{change:+d} since the first turn", (x, y), size=10,
                       alpha=140)
        y += 20

        connected = max((len(c) for c in world.components(season=game.season,
                                                          known_only=True)), default=0)
        lettering.draw(layer, "connected this season", (x, y), size=11, alpha=170,
                       spacing=1.2, caps=True)
        lettering.draw(layer, str(connected), (r.w - 18, y), size=12, alpha=215, align="right")
        y += 26

        ink.ink_line(layer, (x, y), (r.w - 18, y), "faint", ink.seed_of("panel div", 1))
        y += 14

        y = self._heading(layer, x, y, "SETTLEMENTS")
        y += 8
        for s in world.known_settlements()[self.scroll:]:
            if y > r.h - 90:
                break
            alpha = 210 if s.alive else 110
            colour = T.INK if s.alive else T.OXIDE
            lettering.draw(layer, s.name, (x, y), size=12, alpha=alpha, spacing=1.0,
                           caps=True, colour=colour)
            lettering.draw(layer, str(s.population), (r.w - 18, y), size=11,
                           alpha=alpha, align="right")
            y += 14
            detail = "surplus " + ", ".join(g.lower() for g in s.surplus)
            lettering.draw(layer, detail, (x + 6, y), size=9, alpha=130)
            y += 13
            open_legs = sum(1 for e in world.edges_of(s.id)
                            if e.is_usable(game.season)
                            and world.settlements[world.other_end(e, s.id)].known)
            lettering.draw(layer, f"{words.count(open_legs, 'leg')} open, "
                                  f"standing {int(s.standing)}",
                           (x + 6, y), size=9, alpha=130)
            y += 18

        # keys, plainly set
        y = r.h - 74
        ink.ink_line(layer, (x, y), (r.w - 18, y), "faint", ink.seed_of("panel div", 2))
        y += 12
        for line in ("space — the season turns",
                     "wheel, + and −  — zoom;  drag — pan",
                     "f — fit the chart;  f1–f4 — debug"):
            lettering.draw(layer, line, (x, y), size=9, alpha=125)
            y += 13

        target.blit(layer, r.topleft)

    def _heading(self, layer, x, y, text):
        lettering.draw(layer, text, (x, y), size=13, alpha=235, spacing=2.0, caps=True)
        return y + 18
