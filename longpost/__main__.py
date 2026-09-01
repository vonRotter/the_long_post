"""Window, turn loop, phases.

Run from the repo root:  python -m longpost [seed]

Each turn is a season: the report stands in the panel and the log, the player
plans, commits, and the season resolves over about six seconds.
"""

import sys

import pygame

from . import tuning as T
from .data.carriers import CARRIERS, STARTING_FLEET
from .debug.overlay import Overlay
from .post import assign, resolve as resolve_mod
from .post.carrier import Carrier
from .render import ink, words
from .render.chart_view import ChartView
from .render.log import Log
from .render.panel import Panel
from .world import map as world_map
from .world import season as season_mod
from .world.settlement import GOODS


class Game:
    PLAN, RESOLVE = "PLAN", "RESOLVE"

    def __init__(self, seed: int):
        self.seed = seed
        self.world = world_map.generate(seed)
        self.turn = 0
        self.phase = self.PLAN
        # The whole north, not only what is on the chart: settlements the post
        # has not found are still people, and the figure has to be the truth
        # about the world rather than the truth about the document. It is also
        # the one number the game promises falls from the first turn.
        self.population_at_start = sum(s.population for s in self.world.settlements)

        home = self.world.known_settlements()[0].id
        self.fleet = [Carrier(id=i, kind=kind, at=home)
                      for i, kind in enumerate(STARTING_FLEET)]
        self.plan = assign.Plan()
        self.resolution = None
        self.last_resolution = None   # kept for F4, and for reading afterwards
        self.resolve_t = 0.0

        self.selected_edge = None
        self.selected_carrier = None

        self.chart = ChartView(T.CHART_RECT, self.world)
        self.panel = Panel(T.PANEL_RECT)
        self.log = Log(T.LOG_RECT)
        self.overlay = Overlay()
        self.chart.season = self.season
        self.chart.game = self

        self.log.write("the post keeps this chart. "
                       f"{words.count(len(self.world.known_settlements()), 'settlement')}"
                       " are on it.", self.year, self.season)
        self._report_season()

    # --- turn state ---
    @property
    def season(self) -> str:
        return season_mod.season_of_turn(self.turn)

    @property
    def year(self) -> int:
        return season_mod.year_of_turn(self.turn)

    @property
    def seasons_to_winter(self) -> int:
        """How many more seasons are consumed before the winter check."""
        index = T.SEASONS.index(self.season)
        return (T.SEASONS.index("WINTER") - index) % len(T.SEASONS) + 1

    @property
    def over(self) -> bool:
        return self.turn + 1 >= T.TURNS

    # --- planning ---
    def select_edge(self, edge):
        self.selected_edge = edge
        self.selected_carrier = None
        if edge is None:
            return
        options = assign.candidates(self.world, self.fleet, edge, self.season)
        existing = self.plan.on_edge(edge.id)
        if existing:
            self.selected_carrier = self.fleet[existing[0].carrier_id]
        elif options:
            self.selected_carrier = options[0]

    def cycle_carrier(self, step=1):
        if self.selected_edge is None:
            return
        options = assign.candidates(self.world, self.fleet, self.selected_edge,
                                    self.season)
        if not options:
            self.selected_carrier = None
            return
        if self.selected_carrier in options:
            index = (options.index(self.selected_carrier) + step) % len(options)
        else:
            index = 0
        self.selected_carrier = options[index]

    def order_for_selection(self):
        if self.selected_carrier is None:
            return None
        return self.plan.for_carrier(self.selected_carrier.id)

    def load_by_need(self):
        """The load the destination is shortest of, which the origin can spare."""
        edge, carrier = self.selected_edge, self.selected_carrier
        if edge is None or carrier is None:
            return
        origin = self.world.settlements[carrier.at]
        destination = self.world.settlements[self.world.other_end(edge, carrier.at)]
        cargo = assign.fill_by_need(self.world, origin, destination,
                                    carrier.type.capacity)
        self.plan.set(assign.Order(edge_id=edge.id, carrier_id=carrier.id,
                                   origin=origin.id, cargo=cargo))

    def adjust_cargo(self, good, delta):
        edge, carrier = self.selected_edge, self.selected_carrier
        if edge is None or carrier is None:
            return
        order = self.plan.for_carrier(carrier.id)
        if order is None:
            order = assign.Order(edge_id=edge.id, carrier_id=carrier.id,
                                 origin=carrier.at, cargo={})
            self.plan.set(order)
        order.edge_id = edge.id
        order.origin = carrier.at
        held = self.world.settlements[carrier.at].stores.get(good, 0.0)
        room = carrier.type.capacity - order.total() + order.cargo.get(good, 0.0)
        amount = order.cargo.get(good, 0.0) + delta
        order.cargo[good] = max(0.0, min(amount, held, room))
        if order.total() <= 0:
            self.plan.clear_carrier(carrier.id)

    def drop_order(self):
        if self.selected_carrier is not None:
            self.plan.clear_carrier(self.selected_carrier.id)

    # --- the turn ---
    def commit(self):
        """Irreversible. The season resolves."""
        if self.phase != self.PLAN:
            return
        self.resolution = resolve_mod.resolve(self.world, self.fleet, self.plan,
                                              self.turn, self.year, self.season)
        self.last_resolution = self.resolution
        self.plan.clear()
        self.phase = self.RESOLVE
        self.resolve_t = 0.0
        self._shown_lines = 0
        self.chart.routes.dirty = True

    def run_season(self):
        """Commit, and let the season resolve at once rather than over six
        seconds. Headless play — tests and balance runs — comes through here,
        so it is the same code the window drives."""
        self.commit()
        if self.resolution is not None:
            self.resolve_t = self.resolution.duration
            self.update(0.0)

    def skip_resolution(self):
        if self.phase == self.RESOLVE:
            self.resolve_t = self.resolution.duration

    def update(self, dt):
        if self.phase != self.RESOLVE:
            return
        self.resolve_t += dt
        share = self.resolve_t / max(self.resolution.duration, 1e-6)
        lines = self.resolution.lines_before(min(share, 1.0))
        while self._shown_lines < len(lines):
            text, accent = lines[self._shown_lines]
            self.log.write(text, self.year, self.season, accent=accent)
            self._shown_lines += 1
        if self.resolve_t >= self.resolution.duration:
            self._end_resolution()

    def _end_resolution(self):
        self.phase = self.PLAN
        self.resolution = None
        self.selected_edge = None
        self.selected_carrier = None
        self.chart.routes.dirty = True
        if self.over:
            self.log.write("ten years. the post stops here.", self.year, self.season)
            return
        self.turn += 1
        self.chart.set_season(self.season)
        self._report_season()

    def _report_season(self):
        world = self.world
        season = self.season
        usable = [e for e in world.known_edges() if e.is_usable(season)]
        ice = [e for e in usable if e.terrain == "ICE"]
        hard = [e for e in usable if e.availability(season) == T.HARD]
        self.log.write(
            f"{season.lower()}: {words.count(len(usable), 'leg')} stand, "
            f"{len(hard)} of them hard."
            + (f" {words.count(len(ice), 'ice road')} open." if ice else ""),
            self.year, season)
        for s in world.known_settlements():
            if not s.alive:
                continue
            if s.doomed(self.seasons_to_winter):
                self.log.write(f"{s.name} cannot survive this winter.", self.year,
                               season)

    def reseed(self):
        """F3."""
        self.__init__(self.seed + 1)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    seed = int(argv[0]) if argv else 1

    pygame.init()
    pygame.display.set_caption(T.TITLE)
    screen = pygame.display.set_mode((T.WINDOW_W, T.WINDOW_H))
    clock = pygame.time.Clock()

    game = Game(seed)
    paper = ink.make_paper((T.WINDOW_W, T.WINDOW_H), seed)
    grain = ink.make_grain((T.WINDOW_W, T.WINDOW_H), seed)

    dragging = False
    running = True
    while running:
        dt = clock.tick(T.FPS) / 1000.0
        for event in pygame.event.get():
            running = handle(event, game) and running
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                dragging = game.chart.rect.collidepoint(event.pos)
                game._drag_from = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                game.chart.camera.pan_screen(*event.rel)

        game.update(dt)
        game.chart.update(dt)

        screen.blit(paper, (0, 0))
        game.chart.draw(screen)
        game.panel.draw(screen, game)
        game.log.draw(screen)
        game.overlay.draw(screen, game)
        # the sheet's grain lies on top of the ink, not under it
        screen.blit(grain, (0, 0), special_flags=pygame.BLEND_MULT)
        pygame.display.flip()

    pygame.quit()
    return 0


GOOD_KEYS = {pygame.K_1: "GRAIN", pygame.K_2: "FUEL", pygame.K_3: "MEDICINE",
             pygame.K_4: "TOOLS", pygame.K_5: "POST"}


def handle(event, game) -> bool:
    """Returns False when the window should close."""
    camera = game.chart.camera
    if event.type == pygame.QUIT:
        return False

    if event.type == pygame.MOUSEWHEEL:
        camera.zoom_by(T.ZOOM_STEP ** event.y, pygame.mouse.get_pos())
        return True

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if game.chart.rect.collidepoint(event.pos) and game.phase == game.PLAN:
            edge = game.chart.edge_at(event.pos)
            if edge is not None:
                game.select_edge(edge)
        return True

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
        settlement = game.chart.settlement_at(event.pos)
        edge = game.chart.edge_at(event.pos)
        if settlement is not None:
            camera.look_at(settlement.pos, max(camera.target_zoom, T.ZOOM_FOCUS))
        elif edge is not None:
            a = game.world.settlements[edge.a].pos
            b = game.world.settlements[edge.b].pos
            camera.look_at(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
                           max(camera.target_zoom, T.ZOOM_FOCUS * 0.6))
        return True

    if event.type != pygame.KEYDOWN:
        return True

    if event.key in (pygame.K_ESCAPE, pygame.K_q):
        return False

    # the camera answers in every phase; the game never takes it away
    if event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
        camera.zoom_by(T.ZOOM_STEP, camera.rect.center)
    elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
        camera.zoom_by(1 / T.ZOOM_STEP, camera.rect.center)
    elif event.key == pygame.K_f:
        camera.look_at((T.WORLD_W / 2, T.WORLD_H / 2), T.ZOOM_CHART)
    elif event.key == pygame.K_F3:
        game.reseed()
    elif event.key in (pygame.K_F1, pygame.K_F2):
        game.overlay.toggle(event.key)
    elif game.phase == game.RESOLVE:
        game.skip_resolution()
    elif event.key == pygame.K_SPACE:
        game.commit()
    elif event.key == pygame.K_c:
        game.cycle_carrier(-1 if event.mod & pygame.KMOD_SHIFT else 1)
    elif event.key == pygame.K_l:
        game.load_by_need()
    elif event.key == pygame.K_x:
        game.drop_order()
    elif event.key == pygame.K_TAB:
        edges = [e for e in game.world.known_edges() if e.is_usable(game.season)]
        if edges:
            index = edges.index(game.selected_edge) + 1 if game.selected_edge in edges else 0
            game.select_edge(edges[index % len(edges)])
    elif event.key in GOOD_KEYS:
        step = -1 if event.mod & pygame.KMOD_SHIFT else 1
        game.adjust_cargo(GOOD_KEYS[event.key], step)
    return True


if __name__ == "__main__":
    raise SystemExit(main())
