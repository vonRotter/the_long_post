"""The panel: the report, the fleet, the orders, and the settlements.

Numbers are set here and never on the chart. The panel accumulates over the run
and is never compacted, filtered, or shortened.
"""

import pygame

from .. import tuning as T
from ..world import season as season_mod
from ..world.settlement import GOODS
from . import ink, lettering, words

GOOD_LABEL = {"GRAIN": "grain", "FUEL": "fuel", "MEDICINE": "medicine",
              "TOOLS": "tools", "POST": "post"}


def _amount(value) -> str:
    """Loads, to the tenth while a tenth still matters."""
    return f"{value:.1f}" if value < 10 else str(int(round(value)))


class Panel:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.scroll = 0

    def scroll_by(self, lines):
        self.scroll = max(0, self.scroll + lines)

    # --- small helpers ---
    def _line(self, layer, x, y, text, size=11, alpha=200, colour=T.INK,
              spacing=0.0, caps=False):
        lettering.draw(layer, text, (x, y), size=size, alpha=alpha, colour=colour,
                       spacing=spacing, caps=caps)
        return y + size + 3

    def _right(self, layer, y, text, size=11, alpha=205, colour=T.INK):
        lettering.draw(layer, text, (self.rect.w - 18, y), size=size, alpha=alpha,
                       colour=colour, align="right")

    def _rule(self, layer, y, seed):
        ink.ink_line(layer, (18, y), (self.rect.w - 18, y), "faint",
                     ink.seed_of("panel rule", seed))
        return y + 12

    # --- the panel ---
    def draw(self, target, game):
        r = self.rect
        layer = pygame.Surface(r.size, pygame.SRCALPHA)
        ink.ink_line(layer, (2, 8), (2, r.h - 8), "faint", ink.seed_of("panel edge"))

        x, y = 18, 18
        y = self._line(layer, x, y, "THE LONG POST", size=13, alpha=235, spacing=2.0)
        y += 4
        y = self._line(layer, x, y, f"year {game.year} of {T.YEARS}", size=12)
        y = self._line(layer, x, y, game.season.lower(), size=14, alpha=225,
                       spacing=1.6, caps=True)
        y = self._line(layer, x, y, season_mod.CHARACTER[game.season], size=10,
                       alpha=150)
        y = self._line(layer, x, y, f"turn {game.turn + 1} of {T.TURNS}"
                                    f"   ·   {game.phase.lower()}", size=10, alpha=160)
        y += 8

        world = game.world
        population = sum(s.population for s in world.known_settlements() if s.alive)
        self._line(layer, x, y, "population", alpha=170, spacing=1.2, caps=True)
        self._right(layer, y, str(population), size=12)
        y += 15
        y = self._line(layer, x, y,
                       f"{population - game.population_at_start:+d} since the first turn",
                       size=10, alpha=140)
        y += 6
        y = self._rule(layer, y, 1)

        y = self._orders(layer, x, y, game)
        y = self._rule(layer, y, 2)
        y = self._settlements(layer, x, y, game)

        self._keys(layer, x, game)
        target.blit(layer, r.topleft)

    # --- what is being asked of the fleet ---
    def _orders(self, layer, x, y, game):
        y = self._line(layer, x, y, "the fleet", size=12, alpha=225, spacing=1.6,
                       caps=True)
        y += 2

        edge = game.selected_edge
        world = game.world
        for carrier in game.fleet:
            order = game.plan.for_carrier(carrier.id)
            chosen = carrier is game.selected_carrier
            alpha = 225 if chosen else 165
            standing = world.settlements[carrier.at]
            mark = "·" if not chosen else "+"
            self._line(layer, x, y, f"{mark} {carrier.name}", size=11, alpha=alpha)
            self._right(layer, y, standing.name.lower(), size=9, alpha=alpha - 40)
            y += 14
            if order is not None:
                destination = world.settlements[
                    world.other_end(world.edges[order.edge_id], order.origin)]
                load = ", ".join(f"{int(v)} {GOOD_LABEL[g]}"
                                 for g, v in sorted(order.loaded().items()))
                y = self._line(layer, x + 10, y,
                               f"to {destination.name.lower()}: {load or 'nothing'}",
                               size=9, alpha=alpha - 30)
            elif chosen and edge is not None:
                y = self._line(layer, x + 10, y, "no load set", size=9, alpha=130)
        y += 6

        if edge is not None:
            a = world.settlements[edge.a]
            b = world.settlements[edge.b]
            state = edge.availability(game.season).lower()
            y = self._line(layer, x, y, f"{a.name.lower()} — {b.name.lower()}",
                           size=11, alpha=215)
            y = self._line(layer, x + 10, y,
                           f"{edge.terrain.lower()}, {edge.days:g} days, {state}",
                           size=9, alpha=140)
            carrier = game.selected_carrier
            if carrier is not None:
                order = game.plan.for_carrier(carrier.id)
                held = world.settlements[carrier.at].stores
                y = self._line(layer, x + 10, y,
                               f"{carrier.name}, hold {carrier.type.capacity}"
                               f", {int(order.total()) if order else 0} loaded",
                               size=9, alpha=140)
                for index, good in enumerate(GOODS):
                    amount = order.cargo.get(good, 0.0) if order else 0.0
                    text = f"{index + 1} {GOOD_LABEL[good]}"
                    self._line(layer, x + 16, y, text, size=9,
                               alpha=180 if amount else 120)
                    self._right(layer, y, f"{int(amount)} of {int(held.get(good, 0))}",
                                size=9, alpha=180 if amount else 120)
                    y += 12
            else:
                y = self._line(layer, x + 10, y, "nothing of the post's can run it"
                                                 " this season", size=9, alpha=140)
        else:
            y = self._line(layer, x, y, "no leg chosen", size=10, alpha=130)
        return y + 6

    # --- the settlements, and what winter will cost them ---
    def _settlements(self, layer, x, y, game):
        world = game.world
        seasons_left = game.seasons_to_winter
        y = self._line(layer, x, y, "settlements", size=12, alpha=225, spacing=1.6,
                       caps=True)
        y = self._line(layer, x, y, f"shortfall by the end of winter, in {seasons_left}"
                                    f" {'season' if seasons_left == 1 else 'seasons'}",
                       size=9, alpha=135)
        y += 4

        for s in world.known_settlements()[self.scroll:]:
            if y > self.rect.h - 92:
                break
            alive = s.alive
            colour = T.INK if alive else T.OXIDE
            alpha = 215 if alive else 120
            self._line(layer, x, y, s.name, size=11, alpha=alpha, colour=colour,
                       spacing=1.0, caps=True)
            self._right(layer, y, str(s.population) if alive
                        else f"given up {s.abandoned_year}", size=10, alpha=alpha,
                        colour=colour)
            y += 13
            if not alive:
                y += 3
                continue
            gaps = s.projected_shortfall(seasons_left)
            if gaps:
                text = ", ".join(f"{_amount(v)} {GOOD_LABEL[g]}"
                                 for g, v in sorted(gaps.items()) if g != "POST")
                y = self._line(layer, x + 8, y, f"short {text}" if text else "short post",
                               size=9, alpha=170)
            else:
                y = self._line(layer, x + 8, y, "holds what it needs", size=9, alpha=130)
            toll = s.projected_deaths(seasons_left)
            if s.doomed(seasons_left):
                y = self._line(layer, x + 8, y, "cannot survive this winter", size=9,
                               alpha=200, colour=T.OXIDE)
            elif toll:
                y = self._line(layer, x + 8, y, f"the winter will cost it {toll}",
                               size=9, alpha=165)
            y += 4
        return y

    def _keys(self, layer, x, game):
        y = self.rect.h - 76
        self._rule(layer, y, 3)
        y += 10
        if game.phase == game.RESOLVE:
            lines = ("the season is running", "any key — let it be told at once")
        else:
            lines = ("click a leg  ·  tab — next leg  ·  c — carrier",
                     "l — load by need  ·  1-5 add, shift remove  ·  x — clear",
                     "space — commit the season  ·  f — fit  ·  f1-f3 debug")
        for line in lines:
            lettering.draw(layer, line, (x, y), size=9, alpha=125)
            y += 12
