"""Window, turn loop, phases.

Run from the repo root:  python -m longpost [seed]

M0: the chart, the seasons, and free zoom. Cargo, couriers and resolution
arrive at M1 and after.
"""

import sys

import pygame

from . import tuning as T
from .debug.overlay import Overlay
from .render import ink, words
from .render.chart_view import ChartView
from .render.log import Log
from .render.panel import Panel
from .world import map as world_map
from .world import season as season_mod


class Game:
    def __init__(self, seed: int):
        self.seed = seed
        self.world = world_map.generate(seed)
        self.turn = 0
        self.population_at_start = sum(s.population
                                       for s in self.world.known_settlements())
        self.chart = ChartView(T.CHART_RECT, self.world)
        self.panel = Panel(T.PANEL_RECT)
        self.log = Log(T.LOG_RECT)
        self.overlay = Overlay()
        self.chart.season = self.season
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

    def advance(self):
        if self.turn + 1 >= T.TURNS:
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
        cut = [s for s in world.known_settlements()
               if s.alive and not any(e.is_usable(season) for e in world.edges_of(s.id))]
        for s in cut:
            self.log.write(f"{s.name} has no leg open this season.", self.year, season)

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
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                game.chart.camera.pan_screen(*event.rel)
                game.chart.dirty = True

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


def handle(event, game) -> bool:
    """Returns False when the window should close."""
    camera = game.chart.camera
    if event.type == pygame.QUIT:
        return False
    if event.type == pygame.MOUSEWHEEL:
        camera.zoom_by(T.ZOOM_STEP ** event.y, pygame.mouse.get_pos())
    elif event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_ESCAPE, pygame.K_q):
            return False
        if event.key == pygame.K_SPACE:
            game.advance()
        elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            camera.zoom_by(T.ZOOM_STEP, camera.rect.center)
        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            camera.zoom_by(1 / T.ZOOM_STEP, camera.rect.center)
        elif event.key == pygame.K_f:
            camera.look_at((T.WORLD_W / 2, T.WORLD_H / 2), T.ZOOM_CHART)
        elif event.key == pygame.K_F3:
            game.reseed()
        elif event.key in (pygame.K_F1, pygame.K_F2):
            game.overlay.toggle(event.key)
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
        edge = game.chart.edge_at(event.pos)
        settlement = game.chart.settlement_at(event.pos)
        if settlement is not None:
            camera.look_at(settlement.pos, max(camera.target_zoom, T.ZOOM_FOCUS))
        elif edge is not None:
            a = game.world.settlements[edge.a].pos
            b = game.world.settlements[edge.b].pos
            camera.look_at(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
                           max(camera.target_zoom, T.ZOOM_FOCUS * 0.6))
    return True


if __name__ == "__main__":
    raise SystemExit(main())
