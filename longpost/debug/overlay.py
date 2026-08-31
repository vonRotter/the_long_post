"""Debug overlay. F1 edge risk and season profile, F2 desperation, F3 reseed,
F4 replay last season's resolution.

Numbers that are bands in the game proper are plain numbers here.
"""

import pygame

from .. import tuning as T
from ..render import ink, lettering


class Overlay:
    def __init__(self):
        self.edges = False        # F1
        self.pressure = False     # F2

    def toggle(self, key):
        if key == pygame.K_F1:
            self.edges = not self.edges
        elif key == pygame.K_F2:
            self.pressure = not self.pressure

    @property
    def active(self):
        return self.edges or self.pressure

    def draw(self, target, game):
        if not self.active:
            return
        view = game.chart
        layer = pygame.Surface(view.rect.size, pygame.SRCALPHA)

        if self.edges:
            for edge in game.world.known_edges():
                a = view.camera.world_to_screen(game.world.settlements[edge.a].pos)
                b = view.camera.world_to_screen(game.world.settlements[edge.b].pos)
                mid = ((a[0] + b[0]) / 2 - view.rect.x, (a[1] + b[1]) / 2 - view.rect.y)
                profile = "".join(edge.availability(s)[0] for s in T.SEASONS)
                text = (f"{edge.terrain[:4].lower()} {edge.days:g}d {profile}"
                        f" r{edge.danger:.2f}")
                lettering.draw(layer, text, (mid[0] + 4, mid[1] + 3), size=9,
                               alpha=200, colour=T.OXIDE)

        if self.pressure:
            for s in game.world.known_settlements():
                sx, sy = view.camera.world_to_screen(s.pos)
                p = (sx - view.rect.x, sy - view.rect.y)
                lettering.draw(layer, f"d{s.desperation:.0f} st{s.standing:.0f}",
                               (p[0] + 4, p[1] + 10), size=9, alpha=200, colour=T.OXIDE)

        lettering.draw(layer, f"seed {game.world.seed}  rebuilds {view._rebuilds}"
                              f"  zoom {view.camera.zoom:.2f}",
                       (10, view.rect.h - 16), size=9, alpha=180, colour=T.OXIDE)
        target.blit(layer, view.rect.topleft)
