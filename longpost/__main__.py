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
from .data import names as name_data
from .post import assign, record, resolve as resolve_mod, summary as summary_mod
from .post.carrier import Carrier
from .post.courier import Courier
from .render import ending, ink, words
from .render.vignette import Vignettes
from .sound import Sound
from .render.chart_view import ChartView
from .render.log import Log
from .render.panel import Panel
from .world import map as world_map
from .world import season as season_mod
from .world.settlement import GOODS


class Game:
    PLAN, RESOLVE, LAST_RUN, PULL_BACK, SUMMARY = (
        "PLAN", "RESOLVE", "LAST RUN", "PULL BACK", "SUMMARY")

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

        self.fleet = [Carrier(id=i, kind=kind, at=self._first_station(kind))
                      for i, kind in enumerate(STARTING_FLEET)]
        self.couriers = self._first_couriers()
        self.foals = []               # (year of use, kind, where)
        self.plan = assign.Plan()
        self.standing = assign.Standing()
        self.resolution = None
        self.last_resolution = None   # kept for F4, and for reading afterwards
        self.plan_at_commit = {}
        self.trace = []               # every season as it was committed
        self.ending_reason = ""
        self.largest_year = T.START_YEAR
        self.largest_count = 0
        self.last_run = None          # (carrier, courier, edge, cargo)
        self.summary = None
        self.replaying = False
        self.camera_taken = False     # until the player moves it themselves
        self.pull_back_t = 0.0
        self.resolve_t = 0.0

        self.selected_edge = None
        self.selected_carrier = None
        self.selected_courier = None
        # a standing route may name a courier, or take whoever is fit
        self.pin_courier = False

        self.chart = ChartView(T.CHART_RECT, self.world)
        self.panel = Panel(T.PANEL_RECT)
        self.log = Log(T.LOG_RECT)
        self.overlay = Overlay()
        self.vignettes = Vignettes()
        self.sound = Sound(seed=seed)
        self.sound.set_season(self.season)
        self.chart.season = self.season
        self.chart.game = self

        self.log.write("the post keeps this chart. "
                       f"{words.count(len(self.world.known_settlements()), 'settlement')}"
                       " are on it.", self.year, self.season)
        self._report_season()

    def _first_couriers(self):
        """The people the post starts with, from the settlements it serves."""
        import numpy as np

        from .render.ink import seed_of

        gen = np.random.default_rng(seed_of("couriers", self.seed))
        known = self.world.known_settlements()
        couriers = []
        for i in range(T.COURIERS_AT_START):
            home = known[i % len(known)]
            couriers.append(Courier(id=i, name=name_data.person_name(gen),
                                    home=home.id, at=home.id))
        return couriers

    def _first_station(self, kind):
        """Where a carrier of this kind starts: the settlement on the chart it
        has the most work from. A fleet that begins where it cannot move is a
        fleet the player has to spend a year repositioning."""
        carrier = Carrier(id=-1, kind=kind, at=0)
        best, best_count = None, -1
        for settlement in self.world.known_settlements():
            carrier.at = settlement.id
            count = sum(1 for edge in self.world.edges_of(settlement.id)
                        for season in T.SEASONS
                        if self.world.settlements[
                            self.world.other_end(edge, settlement.id)].known
                        and edge.is_usable(season)
                        and carrier.can_run(season, edge) and carrier.reaches(edge))
            if count > best_count:
                best, best_count = settlement.id, count
        return best if best is not None else self.world.known_settlements()[0].id

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
        """The run ends when the network cannot hold itself together, or when
        ten years are up. In a well-played run it is the latter, and the
        population is still falling."""
        return self.turn + 1 >= T.TURNS or self.connected < T.CONNECTED_MINIMUM

    @property
    def connected(self) -> int:
        groups = self.world.components(season=self.season, known_only=True)
        return max((len(group) for group in groups), default=0)

    def _note_ending(self):
        if self.connected < T.CONNECTED_MINIMUM:
            self.ending_reason = ("the network could no longer hold itself"
                                  " together")
        else:
            self.ending_reason = "ten years"

    def begin_last_run(self):
        """One more run. What do you carry?

        No score is attached to it and nothing is calculated from it. The
        player loads one carrier, on one leg, and watches it at FOCUS.
        """
        self._note_ending()
        self.phase = self.LAST_RUN
        self.plan.clear()
        self.standing.routes.clear()
        self.selected_edge = None
        self.selected_carrier = None
        candidates = [e for e in self.world.known_edges() if e.is_usable(self.season)]
        if candidates:
            self.select_edge(candidates[0])
        self.log.write("one more run. what do you carry?", self.year, self.season)

    def commit_last_run(self):
        """The last assignment. It plays at FOCUS and the chart is all there is."""
        if self.phase != self.LAST_RUN:
            return
        order = self.order_for_selection()
        if order is None or self.selected_edge is None:
            return
        edge = self.selected_edge
        a = self.world.settlements[edge.a].pos
        b = self.world.settlements[edge.b].pos
        self.chart.camera.look_at(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), T.ZOOM_FOCUS)
        self.resolution = resolve_mod.resolve(self.world, self.fleet, self.couriers,
                                              self.plan, self.turn, self.year,
                                              self.season)
        self.resolution.duration = T.LAST_RUN_SECONDS
        self.last_resolution = self.resolution
        self.plan.clear()
        self.phase = self.RESOLVE
        self.resolve_t = 0.0
        self._shown_lines = len(self.resolution.lines)   # no log line for this one
        self._shown_frames = set()
        self.last_run = True
        self.chart.routes.dirty = True

    # --- planning ---
    def select_edge(self, edge):
        self.selected_edge = edge
        self.selected_carrier = None
        self.selected_courier = None
        if edge is None:
            return
        options = assign.candidates(self.world, self.fleet, edge, self.season)
        existing = self.plan.on_edge(edge.id)
        if existing:
            self.selected_carrier = self.fleet[existing[0].carrier_id]
            if existing[0].courier_id >= 0:
                self.selected_courier = self.couriers[existing[0].courier_id]
        elif options:
            self.selected_carrier = options[0]
        if self.selected_courier is None:
            self.selected_courier = self._best_courier(edge)

    def _best_courier(self, edge):
        """The freshest person standing at either end who knows the leg."""
        able = assign.couriers_for(self.couriers, edge, None)
        if not able:
            return None
        return max(able, key=lambda c: (c.condition + c.familiarity(edge.id) * 100.0,
                                        -c.id))

    def cycle_courier(self, step=1):
        if self.selected_edge is None:
            return
        able = assign.couriers_for(self.couriers, self.selected_edge, None)
        if not able:
            self.selected_courier = None
            return
        if self.selected_courier in able:
            index = (able.index(self.selected_courier) + step) % len(able)
        else:
            index = 0
        self.selected_courier = able[index]
        order = self.order_for_selection()
        if order is not None:
            order.courier_id = self.selected_courier.id

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
        runner = self.selected_courier or self._best_courier(edge)
        self.plan.set(assign.Order(edge_id=edge.id, carrier_id=carrier.id,
                                   origin=origin.id, cargo=cargo,
                                   courier_id=runner.id if runner else -1))

    def adjust_cargo(self, good, delta):
        edge, carrier = self.selected_edge, self.selected_carrier
        if edge is None or carrier is None:
            return
        order = self.plan.for_carrier(carrier.id)
        if order is None:
            runner = self.selected_courier or self._best_courier(edge)
            order = assign.Order(edge_id=edge.id, carrier_id=carrier.id,
                                 origin=carrier.at, cargo={},
                                 courier_id=runner.id if runner else -1)
            self.plan.set(order)
        order.edge_id = edge.id
        order.origin = carrier.at
        if self.selected_courier is not None:
            order.courier_id = self.selected_courier.id
        held = self.world.settlements[carrier.at].stores.get(good, 0.0)
        room = carrier.type.capacity - order.total() + order.cargo.get(good, 0.0)
        amount = order.cargo.get(good, 0.0) + delta
        order.cargo[good] = max(0.0, min(amount, held, room))
        if order.total() <= 0:
            self.plan.clear_carrier(carrier.id)

    def toggle_standing(self):
        """Keep this route, or stop keeping it.

        Available from the first turn. It becomes necessary somewhere around
        the ninth active leg, which is the honest version of that transition:
        the network outgrows the player's attention rather than unlocking
        something.
        """
        edge, carrier = self.selected_edge, self.selected_carrier
        if edge is None or carrier is None:
            return
        if self.standing.for_carrier(carrier.id) is not None:
            self.standing.clear_carrier(carrier.id)
            self.log.write(f"{carrier.name} no longer keeps the"
                           f" {self._leg_words(edge)}.", self.year, self.season)
            return
        runner = self.selected_courier
        # a load already set by hand becomes the route's instruction; otherwise
        # the route reads the far end's need every season, as a clerk would
        order = self.plan.for_carrier(carrier.id)
        priority = tuple(sorted(order.loaded())) if order and order.loaded() else ()
        self.standing.set(assign.StandingOrder(
            edge_id=edge.id, carrier_id=carrier.id,
            courier_id=runner.id if runner is not None and self.pin_courier else -1,
            started_year=self.year, priority=priority))
        carrying = (", ".join(g.lower() for g in priority) if priority
                    else "whatever is wanted")
        self.log.write(f"{carrier.name} keeps the {self._leg_words(edge)},"
                       f" carrying {carrying}.", self.year, self.season)

    def _leg_words(self, edge) -> str:
        return edge.name or (f"{self.world.settlements[edge.a].name.lower()} — "
                             f"{self.world.settlements[edge.b].name.lower()} leg")

    def toggle_digging(self):
        """Put this season's team on the excavation instead of the water."""
        edge, carrier = self.selected_edge, self.selected_carrier
        if edge is None or carrier is None or not edge.tunnel_site or edge.tunnel_built:
            return
        order = self.plan.for_carrier(carrier.id)
        runner = self.selected_courier or self._best_courier(edge)
        if order is None:
            order = assign.Order(edge_id=edge.id, carrier_id=carrier.id,
                                 origin=carrier.at, cargo={},
                                 courier_id=runner.id if runner else -1)
            self.plan.set(order)
        order.edge_id = edge.id
        order.origin = carrier.at
        order.digging = not order.digging
        if order.digging:
            order.cargo = {}

    def breed(self):
        """Summer only. A foal is three years from being any use."""
        if self.season != T.BREED_SEASON:
            self.log.write("horses are bred in summer.", self.year, self.season)
            return
        carrier = self.selected_carrier
        if carrier is None or carrier.type.key not in ("FAST_HORSE", "HARDY_HORSE"):
            self.log.write("a horse is bred from horses.", self.year, self.season)
            return
        where = self.world.settlements[carrier.at]
        if where.stores.get("GRAIN", 0.0) < T.BREED_GRAIN:
            self.log.write(f"{where.name} has not the grain to keep a foal.",
                           self.year, self.season)
            return
        where.stores["GRAIN"] -= T.BREED_GRAIN
        self.foals.append((self.year + T.BREED_YEARS, carrier.kind, where.id))
        self.log.write(f"a foal at {where.name}, out of {carrier.name}."
                       f" It will be of use in year {self.year + T.BREED_YEARS}.",
                       self.year, self.season)

    def _grown_foals(self):
        """Foals that have become carriers, at the start of a year."""
        for born, kind, where in list(self.foals):
            if born > self.year:
                continue
            self.foals.remove((born, kind, where))
            carrier = Carrier(id=len(self.fleet), kind=kind, at=where)
            self.fleet.append(carrier)
            self.log.write(f"{carrier.name} is in harness at"
                           f" {self.world.settlements[where].name}.",
                           self.year, self.season)

    def drop_order(self):
        if self.selected_carrier is not None:
            self.plan.clear_carrier(self.selected_carrier.id)

    # --- the turn ---
    def commit(self):
        """Irreversible. The season resolves."""
        if self.phase != self.PLAN:
            return
        _made, notices = assign.standing_orders(self.world, self.fleet, self.couriers,
                                                self.standing, self.season, self.plan)
        for notice in notices:
            self.log.write(notice, self.year, self.season)
        # what was actually committed, kept so the season can be read back —
        # and written into the trace, which is the whole of a save
        self.plan_at_commit = dict(self.plan.orders)
        record.remember(self)
        self.resolution = resolve_mod.resolve(self.world, self.fleet, self.couriers,
                                              self.plan, self.turn, self.year,
                                              self.season)
        self.last_resolution = self.resolution
        self.plan.clear()
        self.phase = self.RESOLVE
        self.replaying = False
        self.camera_taken = False
        self.resolve_t = 0.0
        self._shown_lines = 0
        self._shown_frames = set()
        self.chart.routes.dirty = True

    def run_season(self):
        """Commit, and let the season resolve at once rather than over six
        seconds. Headless play — tests and balance runs — comes through here,
        so it is the same code the window drives."""
        self.commit()
        if self.resolution is not None:
            self.resolve_t = self.resolution.duration
            self.update(0.0)

    def save(self):
        where = record.write(self)
        self.log.write(f"the run is written down at {where}.", self.year, self.season)
        return where

    def replay(self):
        """F4. Watch the last season again.

        The resolution is a record of what was already decided, so playing it
        back changes nothing — no line is written twice and no effect is
        applied twice. It is the visible half of the promise in §2: the same
        seed and the same orders unfold identically, and here is the proof you
        can watch.
        """
        if self.last_resolution is None or self.phase != self.PLAN:
            return
        self.resolution = self.last_resolution
        self.phase = self.RESOLVE
        self.replaying = True
        self.resolve_t = 0.0
        self._shown_lines = len(self.resolution.lines)   # the log already has them
        self._shown_frames = set()
        self.camera_taken = False
        self.log.write("the last season again.", self.year, self.season)

    def skip_resolution(self):
        if self.phase == self.RESOLVE:
            self.resolve_t = self.resolution.duration

    def update(self, dt):
        if self.phase == self.PULL_BACK:
            self.pull_back_t += dt
            if self.pull_back_t >= T.PULL_BACK_SECONDS:
                self.phase = self.SUMMARY
                self.summary = summary_mod.build(self)
            return
        if self.phase != self.RESOLVE:
            return
        self.resolve_t += dt
        self.vignettes.update(dt)
        share = self.resolve_t / max(self.resolution.duration, 1e-6)
        lines = self.resolution.lines_before(min(share, 1.0),
                                             exceptions_only=len(self.standing) > 0)
        while self._shown_lines < len(lines):
            text, accent = lines[self._shown_lines]
            self.log.write(text, self.year, self.season, accent=accent)
            # the pen: every line of the log is a mark going onto the paper
            self.sound.scratch()
            self._shown_lines += 1
        self._follow_the_season(share)
        for at, kind, subject in self.resolution.vignettes:
            if at <= share and (at, kind, subject) not in self._shown_frames:
                self._shown_frames.add((at, kind, subject))
                self.vignettes.show(kind, self.world.seed, subject)
                if kind == "arrival":
                    self.sound.arrival_tone()
                elif kind in ("avalanche", "storm", "ice"):
                    self.sound.loss_tone()
        if self.resolve_t >= self.resolution.duration:
            self._end_resolution()

    def _follow_the_season(self, share):
        """The camera goes to the leg that matters most — and gives it up the
        moment the player touches it.

        §3.11: during resolution the camera auto-focuses on the most
        consequential leg, but the player may override it at any moment and go
        watch something else. The game never takes the camera away from them.
        """
        if self.camera_taken or self.resolution is None:
            return
        leg = self.resolution.consequential()
        if leg is None or share < leg.start:
            return
        a = self.world.settlements[leg.origin].pos
        b = self.world.settlements[leg.destination].pos
        self.chart.camera.look_at(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
                                  T.ZOOM_FOCUS * 0.55)

    def _end_resolution(self):
        if self.replaying:
            # nothing happened; it was already seen once
            self.replaying = False
            self.phase = self.PLAN
            self.resolution = None
            return
        self.resolution = None
        self.selected_edge = None
        self.selected_carrier = None
        self.selected_courier = None
        self.chart.routes.dirty = True
        self.chart.places.dirty = True

        if self.last_run:
            # the view pulls back to the whole chart as it now stands, and holds
            self.phase = self.PULL_BACK
            self.pull_back_t = 0.0
            self.chart.camera.look_at((T.WORLD_W / 2, T.WORLD_H / 2), T.ZOOM_CHART)
            return

        self.phase = self.PLAN
        if self.over:
            self.begin_last_run()
            return
        self.turn += 1
        self.chart.set_season(self.season)
        self.sound.set_season(self.season)
        if self.season == "SPRING":
            self._grown_foals()
        self._report_season()

    @property
    def winter_severity(self) -> float:
        """How hard this year's winter will be, said in the autumn before it."""
        return self.world.winters.get(self.year, 1.0)

    def _report_season(self):
        world = self.world
        season = self.season
        # the coming winter, said in the autumn before it and carried in every
        # projected shortfall from then on
        hard = world.winters.get(self.year, 1.0)
        for settlement in world.settlements:
            settlement.winter_factor = hard
        if season == "AUTUMN":
            if hard >= T.WINTER_HARD:
                self.log.write("the winter will be a hard one.", self.year, season)
            elif hard <= T.WINTER_MILD:
                self.log.write("the winter looks mild.", self.year, season)
            else:
                self.log.write("an ordinary winter is coming.", self.year, season)
        if any(s.doomed(self.seasons_to_winter) or s.projected_deaths(
                self.seasons_to_winter) for s in world.known_settlements()
                if s.alive):
            self.sound.shortfall_tone()
        standing = len([s for s in world.known_settlements() if s.alive])
        if standing > self.largest_count:
            self.largest_count, self.largest_year = standing, self.year
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
    """python -m longpost [seed] [--resume]"""
    argv = sys.argv[1:] if argv is None else argv
    resuming = "--resume" in argv
    seed = int(next((a for a in argv if not a.startswith("-")), 1))

    # asked for before pygame.init, or the mixer takes its own defaults and
    # the buffer is large enough to put the pen a beat behind the mark
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=1, buffer=512)
    pygame.init()
    pygame.display.set_caption(T.TITLE)
    screen = pygame.display.set_mode((T.WINDOW_W, T.WINDOW_H))
    clock = pygame.time.Clock()

    game = None
    if resuming:
        saved = record.read(record.path_for(seed))
        if saved is not None:
            game = record.resume(saved, Game)
            game.log.write(f"the run was taken up again at turn {game.turn + 1}.",
                           game.year, game.season)
    if game is None:
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
                game.camera_taken = True

        game.update(dt)
        game.chart.update(dt)

        screen.blit(paper, (0, 0))
        if game.phase == game.SUMMARY:
            ending.draw_summary(screen, game)
        else:
            game.chart.draw(screen)
            if game.phase in (game.LAST_RUN, game.PULL_BACK) or game.last_run:
                # for this one run the chart is all there is
                if game.phase == game.LAST_RUN:
                    ending.draw_prompt(screen, game)
            else:
                game.panel.draw(screen, game)
                game.log.draw(screen)
            game.overlay.draw(screen, game)
            # the chart is still visible behind the frame; the world does not
            # stop for this
            game.vignettes.draw(screen)
        # the sheet's grain lies on top of the ink, not under it
        screen.blit(grain, (0, 0), special_flags=pygame.BLEND_MULT)
        pygame.display.flip()

    game.sound.stop()
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
        game.camera_taken = True
        if game.panel.rect.collidepoint(pygame.mouse.get_pos()):
            game.panel.scroll_by(-event.y * 2)      # the panel is a document too
        else:
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
        game.camera_taken = True
    elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
        camera.zoom_by(1 / T.ZOOM_STEP, camera.rect.center)
        game.camera_taken = True
    elif event.key == pygame.K_f:
        camera.look_at((T.WORLD_W / 2, T.WORLD_H / 2), T.ZOOM_CHART)
        game.camera_taken = True
    elif event.key == pygame.K_F3:
        game.reseed()
    elif event.key == pygame.K_F4:
        game.replay()
    elif event.key == pygame.K_F5:
        game.save()
    elif event.key == pygame.K_m:
        game.sound.toggle_mute()
    elif event.key in (pygame.K_F1, pygame.K_F2):
        game.overlay.toggle(event.key)
    elif game.phase == game.RESOLVE:
        if game.vignettes.current is not None:
            game.vignettes.dismiss()    # any key, and immediately
        elif not game.last_run:
            game.skip_resolution()      # the last run is not skippable
    elif game.phase == game.PULL_BACK:
        game.phase = game.SUMMARY
        game.summary = summary_mod.build(game)
    elif game.phase == game.SUMMARY:
        return False
    elif event.key == pygame.K_SPACE:
        if game.phase == game.LAST_RUN:
            game.commit_last_run()
        else:
            game.commit()
    elif event.key == pygame.K_c:
        game.cycle_carrier(-1 if event.mod & pygame.KMOD_SHIFT else 1)
    elif event.key == pygame.K_v:
        game.cycle_courier(-1 if event.mod & pygame.KMOD_SHIFT else 1)
    elif event.key == pygame.K_l:
        game.load_by_need()
    elif event.key == pygame.K_x:
        game.drop_order()
    elif event.key == pygame.K_d:
        game.toggle_digging()
    elif event.key == pygame.K_b:
        game.breed()
    elif event.key == pygame.K_s:
        game.toggle_standing()
    elif event.key == pygame.K_p:
        game.pin_courier = not game.pin_courier
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
