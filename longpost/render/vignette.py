"""The six vignettes, and the restraint that governs them.

A vignette is a glance, not an elegy. Two seconds, dismissible immediately, the
chart still visible behind the frame, no text inside it ever, no slow motion,
no fade, no hold on a final frame. The world does not stop for this.

The weight arrives next season, in the assignment panel, when the player sees
who is left — which is why these are built from the same five primitives as
everything else and add nothing to them.

If a vignette feels like the game asking for a reaction, it is too long.
"""

import math

import pygame

from .. import tuning as T
from . import ink

KINDS = ("avalanche", "storm", "ice", "bandits", "arrival", "abandonment")

_SLIPS = {}


def _slip(seed):
    """The paper the vignette is drawn on. Cached: there are six of these."""
    if seed not in _SLIPS:
        paper = ink.make_paper(T.VIGNETTE_SIZE, seed).convert_alpha()
        # a fresh slip, so it sits a shade lighter than the sheet it is on
        paper.fill((26, 24, 20, 0), special_flags=pygame.BLEND_RGB_ADD)
        paper.set_alpha(244)
        _SLIPS[seed] = paper
    return _SLIPS[seed]


class Vignette:
    """One framed moment, pasted onto the chart."""

    def __init__(self, kind, seed, subject=""):
        self.kind = kind
        self.seed = ink.seed_of("vignette", kind, seed, subject)
        self.t = 0.0
        self.done = False
        self.surface = None

    @property
    def duration(self) -> float:
        return (T.VIGNETTE_ARRIVAL_SECONDS if self.kind == "arrival"
                else T.VIGNETTE_SECONDS)

    def update(self, dt):
        self.t += dt
        if self.t >= self.duration:
            self.done = True

    def dismiss(self):
        """Any key. Immediately — never after a beat."""
        self.done = True

    # --- drawing ---
    def draw(self, target):
        if self.surface is None:
            self.surface = self._render()
        rect = self.surface.get_rect(center=(T.WINDOW_W // 2, T.WINDOW_H // 2))
        target.blit(self.surface, rect.topleft)

    def _render(self):
        w, h = T.VIGNETTE_SIZE
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        # its own slip of paper, pasted onto the chart: the chart stays visible
        # around it, and the drawing is legible because it is not drawn through
        surf.blit(_slip(self.seed), (0, 0))
        # the border is ruled, but ruled by the same hand as everything else
        for inset in (2, 6):
            corners = [(inset, inset), (w - inset, inset),
                       (w - inset, h - inset), (inset, h - inset)]
            for i, (a, b) in enumerate(zip(corners, corners[1:] + corners[:1])):
                ink.ink_line(surf, a, b, "normal",
                             ink.seed_of(self.seed, "frame", inset, i))

        drawing = getattr(self, f"_{self.kind}")
        drawing(surf, w, h)
        return surf

    # --- the six ---
    def _avalanche(self, surf, w, h):
        """A mass of heavy hatching sweeping down over a thin line of a sledge."""
        mass = [(w * 0.05, h * 0.05), (w * 0.75, h * 0.02), (w * 0.95, h * 0.55),
                (w * 0.30, h * 0.60), (w * 0.06, h * 0.35)]
        ink.hatch(surf, mass, 0.85, -0.9, ink.seed_of(self.seed, "mass"), "heavy")
        ink.hatch(surf, mass, 0.35, -0.5, ink.seed_of(self.seed, "mass2"), "normal")
        base = h * 0.82
        ink.ink_line(surf, (w * 0.18, base), (w * 0.52, base - 6), "normal",
                     ink.seed_of(self.seed, "sledge"))
        for i in range(3):
            x = w * (0.56 + i * 0.08)
            ink.ink_line(surf, (x, base - 4), (x + 12, base - 10), "normal",
                         ink.seed_of(self.seed, "team", i))

    def _storm(self, surf, w, h):
        """A small hull, heavy sea hatching at a steep angle, the horizon lost."""
        # the sea, steeply hatched — and a trough left bare, which is what
        # makes the hull read as being in it rather than drawn over it
        cx, cy = w * 0.46, h * 0.66
        above = [(w * 0.02, h * 0.30), (w * 0.98, h * 0.16),
                 (w * 0.98, h * 0.46), (w * 0.02, h * 0.56)]
        below = [(w * 0.02, h * 0.80), (w * 0.98, h * 0.72),
                 (w * 0.98, h * 0.98), (w * 0.02, h * 0.98)]
        ink.hatch(surf, above, 0.70, 1.15, ink.seed_of(self.seed, "sea"), "heavy")
        ink.hatch(surf, below, 0.55, 1.05, ink.seed_of(self.seed, "sea2"), "heavy")
        ink.ink_curve(surf, [(w * 0.02, h * 0.60), (w * 0.30, h * 0.52),
                             (w * 0.62, h * 0.64), (w * 0.98, h * 0.52)],
                      "normal", ink.seed_of(self.seed, "swell"))

        beam = w * 0.13
        ink.ink_curve(surf, [(cx - beam, cy - 10), (cx - beam * 0.4, cy + 14),
                             (cx + beam * 0.6, cy + 10), (cx + beam, cy - 16)],
                      "heavy", ink.seed_of(self.seed, "hull"))
        ink.ink_line(surf, (cx - beam * 0.1, cy + 6), (cx - beam * 0.5, cy - 66),
                     "heavy", ink.seed_of(self.seed, "mast"))
        ink.ink_line(surf, (cx - beam * 0.5, cy - 66), (cx + beam * 0.5, cy - 44),
                     "normal", ink.seed_of(self.seed, "yard"))

    def _ice(self, surf, w, h):
        """A jagged strike across a flat stippled plane, the track ending at it."""
        plane = [(w * 0.02, h * 0.30), (w * 0.98, h * 0.30), (w * 0.98, h * 0.98),
                 (w * 0.02, h * 0.98)]
        ink.stipple(surf, plane, 0.9, ink.seed_of(self.seed, "snow"), alpha=95)
        track_y = h * 0.66
        ink.ink_line(surf, (w * 0.06, track_y), (w * 0.44, track_y - 8), "normal",
                     ink.seed_of(self.seed, "track"))
        points = [(w * 0.46, h * 0.30), (w * 0.52, h * 0.50), (w * 0.44, h * 0.62),
                  (w * 0.56, h * 0.78), (w * 0.49, h * 0.96)]
        for a, b in zip(points, points[1:]):
            ink.ink_line(surf, a, b, "correction", ink.seed_of(self.seed, "crack", a))

    def _bandits(self, surf, w, h):
        """Upright strokes at the edge of a track, and cargo marks scattered."""
        track_y = h * 0.70
        ink.ink_line(surf, (w * 0.04, track_y), (w * 0.96, track_y - 10), "normal",
                     ink.seed_of(self.seed, "track"))
        gen = ink.rng("bandits", self.seed)
        for i in range(5):
            x = w * (0.30 + i * 0.11) + float(gen.uniform(-8, 8))
            top = track_y - 54 - float(gen.uniform(0, 14))
            ink.ink_line(surf, (x, track_y - 14), (x, top), "heavy",
                         ink.seed_of(self.seed, "figure", i))
        for i in range(6):
            x = w * float(gen.uniform(0.10, 0.92))
            y = track_y + float(gen.uniform(10, 46))
            ink.mark(surf, "circled_dot", (x, y), ink.seed_of(self.seed, "load", i), 5)

    def _arrival(self, surf, w, h):
        """A jetty, a small crowd of strokes, a hull alongside.

        The counterweight, and it matters as much as the disasters: a game that
        frames only its catastrophes teaches the player that success is
        invisible.
        """
        water = [(w * 0.02, h * 0.70), (w * 0.98, h * 0.64), (w * 0.98, h * 0.98),
                 (w * 0.02, h * 0.98)]
        ink.hatch(surf, water, 0.12, 0.18, ink.seed_of(self.seed, "water"))
        for i in range(3):
            y = h * (0.78 + i * 0.06)
            ink.ink_curve(surf, [(w * 0.06, y), (w * 0.34, y - 5), (w * 0.66, y + 4),
                                 (w * 0.94, y - 3)], "faint",
                          ink.seed_of(self.seed, "ripple", i))
        jetty_y = h * 0.60
        ink.ink_line(surf, (w * 0.10, jetty_y), (w * 0.62, jetty_y + 6), "normal",
                     ink.seed_of(self.seed, "jetty"))
        for i in range(5):
            x = w * (0.14 + i * 0.11)
            ink.ink_line(surf, (x, jetty_y + 4), (x, jetty_y + 26), "faint",
                         ink.seed_of(self.seed, "pile", i))
        gen = ink.rng("crowd", self.seed)
        for i in range(7):
            x = w * (0.16 + i * 0.06) + float(gen.uniform(-5, 5))
            ink.ink_line(surf, (x, jetty_y - 4), (x, jetty_y - 30
                                                  - float(gen.uniform(0, 10))),
                         "normal", ink.seed_of(self.seed, "person", i))
        cx, cy = w * 0.76, jetty_y + 4
        ink.ink_curve(surf, [(cx - 46, cy - 10), (cx, cy + 12), (cx + 48, cy - 12)],
                      "normal", ink.seed_of(self.seed, "hull"))
        ink.ink_line(surf, (cx, cy), (cx - 4, cy - 52), "normal",
                     ink.seed_of(self.seed, "mast"))

    def _abandonment(self, surf, w, h):
        """A settlement drawn in full, then struck through in oxide red."""
        cx, cy = w * 0.5, h * 0.55
        ink.circle(surf, (cx, cy), h * 0.26, "normal", ink.seed_of(self.seed, "ring"))
        gen = ink.rng("roofs", self.seed)
        for i in range(7):
            ox = float(gen.uniform(-h * 0.16, h * 0.16))
            oy = float(gen.uniform(-h * 0.12, h * 0.12))
            width = h * 0.06
            base = (cx + ox, cy + oy)
            ink.ink_line(surf, (base[0] - width, base[1]),
                         (base[0], base[1] - width * 0.8), "normal",
                         ink.seed_of(self.seed, "roof", i, 0))
            ink.ink_line(surf, (base[0], base[1] - width * 0.8),
                         (base[0] + width, base[1]), "normal",
                         ink.seed_of(self.seed, "roof", i, 1))
        share = min(1.0, self.t / max(self.duration * 0.6, 1e-6))
        ink.ink_line(surf, (cx - h * 0.34, cy - h * 0.10),
                     (cx + h * 0.34, cy + h * 0.10), "correction",
                     ink.seed_of(self.seed, "strike"), color=T.OXIDE)


class Vignettes:
    """The queue. One at a time, and never more than one waiting."""

    def __init__(self):
        self.current = None

    def show(self, kind, seed, subject=""):
        if kind not in KINDS:
            raise ValueError(f"there is no {kind} vignette")
        if self.current is not None:
            return          # the world does not stop twice for one season
        self.current = Vignette(kind, seed, subject)

    def update(self, dt):
        if self.current is None:
            return
        self.current.update(dt)
        if self.current.done:
            self.current = None

    def dismiss(self):
        if self.current is not None:
            self.current.dismiss()
            self.current = None

    def draw(self, target):
        if self.current is not None:
            self.current.draw(target)
