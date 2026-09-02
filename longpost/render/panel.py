"""The panel: the report, the fleet, the couriers, and the settlements.

Numbers are set here and never on the chart. The panel accumulates over the run
and is never compacted, filtered, or shortened: veterans with long records, the
faint names of the dead, settlements struck through. A player scrolling it in
year nine is reading a decade of their own decisions, so the only thing that
moves is the view.
"""

import pygame

from .. import tuning as T
from ..post import courier as courier_mod
from ..world import desperation as pressure
from ..world import season as season_mod
from ..world.settlement import GOODS
from . import ink, lettering, words

GOOD_LABEL = {"GRAIN": "grain", "FUEL": "fuel", "MEDICINE": "medicine",
              "TOOLS": "tools", "POST": "post"}

BODY_HEIGHT = 4200          # the document the panel is a window onto


def _amount(value) -> str:
    """Loads, to the tenth while a tenth still matters."""
    return f"{value:.1f}" if value < 10 else str(int(round(value)))


def condition_band(value) -> str:
    if value >= 75:
        return "fit"
    if value >= T.CONDITION_UNFIT:
        return "worn"
    return "spent"


def loyalty_band(value) -> str:
    if value >= 70:
        return "steady"
    if value >= 40:
        return "restless"
    return "done with it"


class Panel:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.scroll = 0
        self.reach = 0          # how far the document actually runs
        self._body = pygame.Surface((self.rect.w, BODY_HEIGHT), pygame.SRCALPHA)
        self._stamp = None      # what the body was drawn from

    def scroll_by(self, lines):
        limit = max(0, self.reach - (self.rect.h - T.PANEL_HEAD_HEIGHT
                                     - T.PANEL_KEYS_HEIGHT))
        self.scroll = max(0, min(limit, self.scroll + lines * 14))

    # --- small helpers ---
    def _line(self, layer, x, y, text, size=11, alpha=200, colour=T.INK,
              spacing=0.0, caps=False):
        lettering.draw(layer, text, (x, y), size=size, alpha=alpha, colour=colour,
                       spacing=spacing, caps=caps)
        return y + size + 3

    def _right(self, layer, y, text, size=11, alpha=205, colour=T.INK):
        lettering.draw(layer, text, (self.rect.w - 18, y), size=size, alpha=alpha,
                       colour=colour, align="right")

    def _heading(self, layer, x, y, text):
        y += 6
        ink.ink_line(layer, (18, y), (self.rect.w - 18, y), "faint",
                     ink.seed_of("panel rule", text))
        y += 10
        return self._line(layer, x, y, text, size=12, alpha=225, spacing=1.6,
                          caps=True) + 2

    # --- the panel ---
    def _stamp_of(self, game):
        """What the body depends on. Scrolling is not on the list: the document
        does not change when the window over it moves."""
        order = tuple(sorted((o.carrier_id, o.courier_id, o.edge_id, o.total())
                             for o in game.plan))
        return (game.turn, game.phase, len(game.couriers), len(game.fleet),
                id(game.selected_edge), id(game.selected_carrier),
                id(game.selected_courier), order,
                tuple(s.population for s in game.world.known_settlements()),
                tuple(round(s.desperation) for s in game.world.known_settlements()))

    def draw(self, target, game):
        r = self.rect
        head = pygame.Surface((r.w, T.PANEL_HEAD_HEIGHT), pygame.SRCALPHA)
        self._draw_head(head, game)

        stamp = self._stamp_of(game)
        body = self._body
        x = 18
        if stamp != self._stamp:
            body.fill((0, 0, 0, 0))
            y = 4
            y = self._draw_leg(body, x, y, game)
            y = self._draw_fleet(body, x, y, game)
            y = self._draw_couriers(body, x, y, game)
            y = self._draw_settlements(body, x, y, game)
            self.reach = y
            self._stamp = stamp

        window = r.h - T.PANEL_HEAD_HEIGHT - T.PANEL_KEYS_HEIGHT
        target.blit(head, r.topleft)
        target.blit(body, (r.x, r.y + T.PANEL_HEAD_HEIGHT),
                    pygame.Rect(0, self.scroll, r.w, window))

        foot = pygame.Surface((r.w, T.PANEL_KEYS_HEIGHT), pygame.SRCALPHA)
        self._draw_keys(foot, x, game)
        target.blit(foot, (r.x, r.y + r.h - T.PANEL_KEYS_HEIGHT))

        edge = pygame.Surface((4, r.h), pygame.SRCALPHA)
        ink.ink_line(edge, (2, 8), (2, r.h - 8), "faint", ink.seed_of("panel edge"))
        target.blit(edge, r.topleft)

    def _draw_head(self, layer, game):
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
        y += 6
        population = sum(s.population for s in game.world.settlements if s.alive)
        self._line(layer, x, y, "the north", alpha=170, spacing=1.2, caps=True)
        self._right(layer, y, str(population), size=12)
        y += 15
        self._line(layer, x, y, f"{population - game.population_at_start:+d}"
                                " since the first turn", size=10, alpha=140)

    # --- the leg being planned ---
    def _draw_leg(self, layer, x, y, game):
        world = game.world
        edge = game.selected_edge
        if edge is None:
            return self._line(layer, x, y + 8, "no leg chosen", size=10, alpha=130) + 6

        a, b = world.settlements[edge.a], world.settlements[edge.b]
        y = self._line(layer, x, y + 4, f"{a.name.lower()} — {b.name.lower()}",
                       size=12, alpha=225)
        y = self._line(layer, x + 10, y,
                       f"{edge.terrain.lower()}, {edge.days:g} days, "
                       f"{edge.availability(game.season).lower()}", size=9, alpha=140)
        road = pressure.road_band(edge.danger)
        if road != "safe" and edge.danger_source >= 0:
            watcher = world.settlements[edge.danger_source]
            y = self._line(layer, x + 10, y,
                           f"{road} — {watcher.name.lower()} is watching it",
                           size=9, alpha=190, colour=T.OXIDE)
        for year, name in edge.losses:
            y = self._line(layer, x + 10, y, f"{name} was lost here in year {year}",
                           size=9, alpha=140)

        carrier = game.selected_carrier
        runner = game.selected_courier
        order = game.order_for_selection()
        if carrier is None:
            return self._line(layer, x + 10, y,
                              "nothing of the post's can run it this season",
                              size=9, alpha=140) + 6

        held = world.settlements[carrier.at].stores
        y = self._line(layer, x + 10, y,
                       f"{carrier.name}, hold {carrier.type.capacity}, "
                       f"{int(order.total()) if order else 0} loaded",
                       size=9, alpha=150)
        if runner is None:
            y = self._line(layer, x + 10, y, "no one is standing here to run it",
                           size=9, alpha=150, colour=T.OXIDE)
        else:
            y = self._line(layer, x + 10, y,
                           f"{runner.name} — {condition_band(runner.condition)}, "
                           f"{loyalty_band(runner.loyalty)}", size=9, alpha=175)
            runs = runner.runs_on(edge.id)
            if runs:
                y = self._line(layer, x + 16, y,
                               f"has run this leg {words.count(runs, 'time')}",
                               size=9, alpha=140)
            risk = runner.risk_on(edge)
            if risk >= 0.05:
                y = self._line(layer, x + 16, y, "this leg may not bring them back",
                               size=9, alpha=185, colour=T.OXIDE)
            if order and order.loaded():
                destination = world.settlements[world.other_end(edge, order.origin)]
                pressures = courier_mod.theft_pressures(world, runner, edge,
                                                        order.loaded(), destination)
                visible = courier_mod.visible_pressures(pressures)
                if len(visible) >= T.THEFT_PRESSURES_NEEDED:
                    y = self._line(layer, x + 16, y,
                                   "pressures: " + ", ".join(name for name, _ in visible),
                                   size=9, alpha=175, colour=T.OXIDE)

        for index, good in enumerate(GOODS):
            amount = order.cargo.get(good, 0.0) if order else 0.0
            self._line(layer, x + 16, y, f"{index + 1} {GOOD_LABEL[good]}", size=9,
                       alpha=180 if amount else 120)
            self._right(layer, y, f"{int(amount)} of {int(held.get(good, 0))}",
                        size=9, alpha=180 if amount else 120)
            y += 12
        return y + 4

    # --- the fleet ---
    def _draw_fleet(self, layer, x, y, game):
        world = game.world
        y = self._heading(layer, x, y, "the fleet")
        for carrier in game.fleet:
            order = game.plan.for_carrier(carrier.id)
            chosen = carrier is game.selected_carrier
            alpha = 225 if chosen else 165
            self._line(layer, x, y, f"{'+' if chosen else '·'} {carrier.name}",
                       size=11, alpha=alpha)
            self._right(layer, y, world.settlements[carrier.at].name.lower(),
                        size=9, alpha=alpha - 40)
            y += 14
            if order is not None:
                destination = world.settlements[
                    world.other_end(world.edges[order.edge_id], order.origin)]
                load = ", ".join(f"{int(v)} {GOOD_LABEL[g]}"
                                 for g, v in sorted(order.loaded().items()))
                who = (game.couriers[order.courier_id].name
                       if 0 <= order.courier_id < len(game.couriers) else "no one")
                y = self._line(layer, x + 10, y,
                               f"{who} to {destination.name.lower()}:"
                               f" {load or 'nothing'}", size=9, alpha=alpha - 30)
        return y + 4

    # --- the couriers, and the record of them ---
    def _draw_couriers(self, layer, x, y, game):
        world = game.world
        y = self._heading(layer, x, y, "couriers")
        for runner in game.couriers:
            alive = runner.alive
            alpha = 215 if alive else 105
            chosen = runner is game.selected_courier
            self._line(layer, x, y, f"{'+' if chosen and alive else '·'} {runner.name}",
                       size=11, alpha=alpha)
            self._right(layer, y, world.settlements[runner.home].name.lower(),
                        size=9, alpha=alpha - 45)
            y += 13
            if alive:
                y = self._line(layer, x + 10, y,
                               f"{condition_band(runner.condition)},"
                               f" {loyalty_band(runner.loyalty)}", size=9,
                               alpha=alpha - 40)
            else:
                y = self._line(layer, x + 10, y,
                               f"lost on the {runner.lost_where}, year"
                               f" {runner.lost_year}", size=9, alpha=alpha)
            y = self._line(layer, x + 10, y, runner.history(), size=9, alpha=alpha - 55)
            leg, count = runner.worst_leg()
            if leg is not None and count > 1:
                edge = world.edges[leg]
                y = self._line(layer, x + 10, y,
                               f"{world.settlements[edge.a].name.lower()} —"
                               f" {world.settlements[edge.b].name.lower()},"
                               f" {words.count(count, 'time')}", size=9,
                               alpha=alpha - 55)
            y += 4
        return y + 4

    # --- the settlements, and what winter will cost them ---
    def _draw_settlements(self, layer, x, y, game):
        world = game.world
        seasons_left = game.seasons_to_winter
        y = self._heading(layer, x, y, "settlements")
        y = self._line(layer, x, y, f"shortfall by the end of winter, in"
                                    f" {words.count(seasons_left, 'season')}",
                       size=9, alpha=135)
        y += 4

        for s in world.known_settlements():
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
                y += 4
                continue
            gaps = s.projected_shortfall(seasons_left)
            if gaps:
                text = ", ".join(f"{_amount(v)} {GOOD_LABEL[g]}"
                                 for g, v in sorted(gaps.items()) if g != "POST")
                y = self._line(layer, x + 8, y, f"short {text}" if text else "short post",
                               size=9, alpha=170)
            else:
                y = self._line(layer, x + 8, y, "holds what it needs", size=9, alpha=130)
            state = pressure.band(s.desperation)
            if pressure.refuses_to_deal(s):
                y = self._line(layer, x + 8, y, "desperate — it will not deal",
                               size=9, alpha=200, colour=T.OXIDE)
            elif state != "calm":
                y = self._line(layer, x + 8, y, state, size=9, alpha=175,
                               colour=T.OXIDE if state == "desperate" else T.INK)
            toll = s.projected_deaths(seasons_left)
            if s.doomed(seasons_left):
                y = self._line(layer, x + 8, y, "cannot survive this winter", size=9,
                               alpha=200, colour=T.OXIDE)
            elif toll:
                y = self._line(layer, x + 8, y, f"the winter will cost it {toll}",
                               size=9, alpha=165)
            y += 4
        return y

    def _draw_keys(self, layer, x, game):
        y = 6
        ink.ink_line(layer, (18, y), (self.rect.w - 18, y), "faint",
                     ink.seed_of("panel keys"))
        y += 10
        if game.phase == game.RESOLVE:
            lines = ("the season is running", "any key — let it be told at once")
        else:
            lines = ("click a leg · tab next · c carrier · v courier · l load",
                     "1-5 add, shift remove · x clear · wheel scrolls this panel",
                     "space — commit the season · f — fit · f1-f3 debug")
        for line in lines:
            lettering.draw(layer, line, (x, y), size=9, alpha=125)
            y += 12
