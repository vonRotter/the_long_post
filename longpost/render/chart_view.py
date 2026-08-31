"""CHART / FOCUS / VIGNETTE scales, and the camera.

Zoom is a player verb, not a scripted effect. The scale is continuous: CHART
and FOCUS are ends of a range, and detail is added progressively as the player
draws in. The game never takes the camera away from the player.
"""

import math
import time

import numpy as np
import pygame

from .. import tuning as T
from ..world import map as world_map
from ..world import season as season_mod
from . import ink, lettering


class Camera:
    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.base = min(rect.w / T.WORLD_W, rect.h / T.WORLD_H) * 0.92
        self.centre = np.array([T.WORLD_W / 2, T.WORLD_H / 2], dtype=float)
        self.zoom = T.ZOOM_CHART
        self.target_centre = self.centre.copy()
        self.target_zoom = self.zoom
        self.moved = True

    # --- transforms ---
    @property
    def scale(self) -> float:
        return self.base * self.zoom

    def world_to_screen(self, p):
        return (self.rect.centerx + (p[0] - self.centre[0]) * self.scale,
                self.rect.centery + (p[1] - self.centre[1]) * self.scale)

    def screen_to_world(self, p):
        return (self.centre[0] + (p[0] - self.rect.centerx) / self.scale,
                self.centre[1] + (p[1] - self.rect.centery) / self.scale)

    # --- player control ---
    def zoom_by(self, factor, anchor=None):
        """Zoom, keeping the point under the cursor where it is."""
        old = self.target_zoom
        self.target_zoom = float(np.clip(old * factor, T.ZOOM_MIN, T.ZOOM_MAX))
        if anchor is not None and self.target_zoom != old:
            w = np.array(self.screen_to_world(anchor))
            ratio = 1.0 - old / self.target_zoom
            self.target_centre = self.target_centre + (w - self.target_centre) * ratio

    def pan_screen(self, dx, dy):
        self.target_centre -= np.array([dx, dy], dtype=float) / self.scale
        self.centre -= np.array([dx, dy], dtype=float) / self.scale   # immediate

    def look_at(self, world_point, zoom=None):
        self.target_centre = np.array(world_point, dtype=float)
        if zoom is not None:
            self.target_zoom = float(np.clip(zoom, T.ZOOM_MIN, T.ZOOM_MAX))

    @property
    def settled(self) -> bool:
        return abs(self.target_zoom - self.zoom) < T.ZOOM_SETTLE

    def update(self):
        """Smoothed but immediate: responds on the frame the input arrives."""
        before = (self.centre.copy(), self.zoom)
        self.centre += (self.target_centre - self.centre) * T.CAMERA_EASE
        self.zoom += (self.target_zoom - self.zoom) * T.CAMERA_EASE
        if abs(self.target_zoom - self.zoom) < T.ZOOM_SETTLE:
            # snapped at the same threshold `settled` uses, or the document is
            # re-inked once a frame while the last thousandth eases out
            self.zoom = self.target_zoom
        if np.hypot(*(self.target_centre - self.centre)) < T.CAMERA_SNAP:
            self.centre = self.target_centre.copy()
        self.moved = (not np.allclose(before[0], self.centre)) or before[1] != self.zoom
        return self.moved


class DocumentCache:
    """One cached bitmap of the chart, inked at a pan-quantised centre.

    Two ideas, both borrowed from map maker's layer cache: the bitmap is larger
    than the chart rect and inked at a centre rounded to a grid, so panning is a
    blit rather than a re-ink; and the ink work is split into stages so a
    re-ink can be spread over several frames while the old bitmap is still on
    screen. Nothing here decides *what* is drawn — the stages do.
    """

    def __init__(self, size, stages, slice_ms=None, warm_at=0.04):
        self.size = size
        self.stages = stages          # () -> list of callables taking a surface
        self.slice_ms = slice_ms      # None: always finish in one frame
        # How little of the bitmap's reach may be left before the next one is
        # started, as a fraction of that reach. A sliced layer starts early
        # because it needs several frames; a cheap one waits, so a drag does
        # not re-ink it twice over. Both must sit below the slack a centred
        # bitmap has (the margin over the chart rect), or it re-inks at rest.
        self.warm_at = warm_at
        self.front = pygame.Surface(size, pygame.SRCALPHA)
        self.back = pygame.Surface(size, pygame.SRCALPHA)
        self.centre = None            # the world point at the bitmap's middle
        self.zoom = None
        self.dirty = True
        self.pending = None           # [centre, zoom, remaining stages]
        self.rebuilds = 0

    @property
    def ready(self) -> bool:
        return self.centre is not None

    def slack(self, camera, rect) -> float:
        """How much of the bitmap's reach is unused, 0..1. Negative: the view
        has moved past what it holds, and it has to be re-inked now.

        Measured in world units, so zooming *in* does not consume slack: a
        bitmap inked at CHART scale still covers the leg the player drew in on.
        """
        if self.centre is None:
            return -1.0
        cached = np.array(self.size, dtype=float) / 2.0 / (camera.base * self.zoom)
        view = np.array([rect.w, rect.h], dtype=float) / 2.0 / camera.scale
        offset = np.abs(np.asarray(self.centre) - camera.centre)
        return float(np.min((cached - view - offset) / np.maximum(cached, 1e-6)))

    def service(self, view, camera):
        """Ink what is needed this frame. Returns the surface to show."""
        slack = self.slack(camera, view.rect)
        stale = slack < 0.0
        outdated = stale or self.dirty or self.zoom != camera.zoom

        if self.pending is None and (outdated or slack < self.warm_at):
            # a zoom in flight would start a bitmap a frame; the scaled one
            # carries the view until the camera settles
            if camera.settled or stale:
                self.back.fill((0, 0, 0, 0))
                self.pending = [view._quantised_centre(), camera.zoom,
                                list(self.stages())]
                self.dirty = False

        if self.pending is not None:
            self._advance(view, must_finish=stale)
        return self.front

    def _advance(self, view, must_finish):
        centre, zoom, remaining = self.pending
        started = time.perf_counter()
        view._render_centre = centre
        view._render_size = self.size
        while remaining:
            remaining.pop(0)(self.back)
            if must_finish or self.slice_ms is None:
                continue
            if (time.perf_counter() - started) * 1000 >= self.slice_ms:
                break
        if remaining:
            return
        self.front, self.back = self.back, self.front
        self.centre, self.zoom = centre, zoom
        self.pending = None
        self.rebuilds += 1


class ChartView:
    """Draws the chart. Everything static is cached and re-inked only when the
    document actually changes."""

    def __init__(self, rect, world: world_map.WorldMap):
        self.rect = pygame.Rect(rect)
        self.world = world
        self.camera = Camera(self.rect)
        # The document is inked onto a surface larger than the chart rect, at a
        # camera centre rounded to the pan grid, so panning is a blit.
        quantum = T.PAN_QUANTUM
        size = (self.rect.w + 2 * quantum, self.rect.h + 2 * quantum)
        self._render_size = size
        self._render_centre = None     # the world point being inked against

        # The ground is the expensive half and changes only with the season and
        # the view, so its re-ink is spread across frames. The network is cheap
        # and changes whenever the chart does, including every frame of the
        # season redraw, so it is always finished in one.
        self.ground = DocumentCache(size, self._ground_stages,
                                    slice_ms=T.INK_SLICE_MS, warm_at=0.16)
        self.network = DocumentCache(size, self._network_stages)
        self.dynamic = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        self.season = T.SEASONS[0]
        self.previous_season = None
        self.redraw_t = 1.0          # 0..1, the season-change re-inking
        self.hover_edge = None
        self._mask = None

    # --- state ---
    @property
    def dirty(self) -> bool:
        return self.ground.dirty or self.network.dirty

    @dirty.setter
    def dirty(self, value):
        self.ground.dirty = self.network.dirty = bool(value)

    @property
    def _rebuilds(self) -> int:
        return self.ground.rebuilds + self.network.rebuilds

    def set_season(self, season):
        """The chart redraws: closed edges are erased, new ones inked in."""
        self.previous_season = self.season
        self.season = season
        self.redraw_t = 0.0
        self.dirty = True

    def update(self, dt):
        self.camera.update()
        if self.redraw_t < 1.0:
            self.redraw_t = min(1.0, self.redraw_t + dt / T.REDRAW_SECONDS)
            self.network.dirty = True

    # --- helpers ---
    def _visible(self, doc_pt, margin=80):
        return (-margin <= doc_pt[0] <= self._render_size[0] + margin
                and -margin <= doc_pt[1] <= self._render_size[1] + margin)

    def _local(self, world_pt):
        """World point to a position on the cached document."""
        scale = self.camera.scale
        cx, cy = self._render_size[0] / 2, self._render_size[1] / 2
        return (cx + (world_pt[0] - self._render_centre[0]) * scale,
                cy + (world_pt[1] - self._render_centre[1]) * scale)

    def _quantised_centre(self):
        """The camera centre, rounded to the pan grid, in world units."""
        scale = self.camera.scale
        quantum = T.PAN_QUANTUM
        return np.array([round(self.camera.centre[0] * scale / quantum) * quantum / scale,
                         round(self.camera.centre[1] * scale / quantum) * quantum / scale])

    def _blit_scaled(self, target, surface, centre, factor):
        """Blit a bitmap inked at another zoom, scaling only what is on screen."""
        size = surface.get_size()
        origin = self._blit_at(centre, (size[0] * factor, size[1] * factor))
        # the part of the bitmap the chart rect can actually see
        left = max(0, int((self.rect.left - origin[0]) / factor) - 1)
        top = max(0, int((self.rect.top - origin[1]) / factor) - 1)
        right = min(size[0], int((self.rect.right - origin[0]) / factor) + 2)
        bottom = min(size[1], int((self.rect.bottom - origin[1]) / factor) + 2)
        if right <= left or bottom <= top:
            return
        piece = surface.subsurface(pygame.Rect(left, top, right - left, bottom - top))
        scaled = pygame.transform.smoothscale(
            piece, (max(1, int((right - left) * factor)),
                    max(1, int((bottom - top) * factor))))
        target.blit(scaled, (origin[0] + left * factor, origin[1] + top * factor))

    def _blit_at(self, centre, size):
        """Where a cached bitmap goes, given where the camera is now looking."""
        anchor = self.camera.world_to_screen(centre)
        return (anchor[0] - size[0] / 2, anchor[1] - size[1] / 2)

    MASK_STEP = 2   # the sea mask is coarse; tone does not need pixel accuracy

    def _land_mask(self):
        """A screen-space mask of the land, so sea tone can avoid it cheaply."""
        step = self.MASK_STEP
        size = (self._render_size[0] // step + 1, self._render_size[1] // step + 1)
        mask = pygame.Surface(size)
        mask.fill((0, 0, 0))
        for poly in self.world.land:
            pts = [(x / step, y / step) for x, y in (self._local(p) for p in poly)]
            pygame.draw.polygon(mask, (255, 255, 255), pts)
        return pygame.surfarray.array2d(mask) != 0

    # --- the document ---
    def _ground_stages(self):
        """The sheet: what the water and the land are doing. Sliced across
        frames, so no single frame pays for all of it."""
        def mask(_surf):
            self._mask = self._land_mask()

        def ice(surf):
            if self.season == "WINTER":
                self._draw_ice(surf, self._mask)

        bands = 3
        stages = [mask]
        stages += [lambda surf, b=b: self._draw_sea(surf, b, bands) for b in range(bands)]
        stages.append(ice)
        stages += [lambda surf, level=level: self._draw_water_lines(surf, level)
                   for level in range(len(self.world.depth_lines)
                                      + len(self.world.coast_offsets))]
        for index in range(len(self.world.land)):
            stages.append(lambda surf, i=index: self._draw_coast_of(surf, i))
        stages.append(self._draw_ridge)
        stages.append(self._draw_soundings)
        return stages

    def _network_stages(self):
        """What the post has on the chart: legs, settlements, and the marks a
        run leaves behind. Cheap, and redrawn whenever any of it changes."""
        return [self._draw_edges, self._draw_settlements]

    def _draw_sea(self, surf, band=0, bands=1):
        """Faint hatching, thickening as the player draws in. No filled areas.

        Drawn in bands so a re-ink can stop between them.
        """
        zoom = self.camera.zoom
        density = 0.10 + 0.10 * min(zoom, 3.0)
        spacing = T.HATCH_SPACING_MAX + (T.HATCH_SPACING_MIN - T.HATCH_SPACING_MAX) * density
        spacing = max(spacing, 12.0)
        angle = 0.30 if self.season != "WINTER" else 0.16
        w, h = self._render_size
        mask = self._mask
        reach = math.hypot(w, h)
        ca, sa = math.cos(angle), math.sin(angle)
        n = int(2 * reach / spacing)
        centre = np.array([w / 2, h / 2])
        spans = []
        for i in range(band, n, bands):
            offset = -reach + i * spacing
            mid = centre + np.array([-sa, ca]) * offset
            a = mid - np.array([ca, sa]) * reach
            b = mid + np.array([ca, sa]) * reach
            spans.extend(_visible_spans(a, b, w, h, mask, self.MASK_STEP))
        ink.faint_strokes(surf, spans, ink.seed_of("sea", self.season, n, band),
                          alpha=88)

    def _draw_ice(self, surf, mask):
        """Winter closes the sea. It is drawn as ice: stipple, not hatching."""
        w, h = self._render_size
        gen = ink.rng("ice", self.world.seed, round(self.camera.zoom, 1))
        pts = gen.uniform([0, 0], [w, h], (4200, 2))
        xi = np.clip((pts[:, 0] / self.MASK_STEP).astype(int), 0, mask.shape[0] - 1)
        yi = np.clip((pts[:, 1] / self.MASK_STEP).astype(int), 0, mask.shape[1] - 1)
        pts = pts[~mask[xi, yi]]
        surf.lock()
        for x, y in pts:
            surf.set_at((int(x), int(y)), (*T.INK, 82))
        surf.unlock()

    def _draw_coast_of(self, surf, index):
        """One landmass: its shoreline and the light stipple inland."""
        poly = self.world.land[index]
        pts = [self._local(p) for p in poly]
        if not any(self._visible(p, margin=200) for p in pts):
            return
        step = max(1, len(pts) // 26)
        ink.ink_curve(surf, pts[::step], "normal", ink.seed_of("coast", index),
                      closed=True, samples=5)
        self._draw_land_tone(surf, index, pts)

    def _draw_ridge(self, surf):
        """The mountain spine, as sparse hatching along its length."""
        ridge = [self._local(p) for p in self.world.ridge]
        for i, (a, b) in enumerate(zip(ridge, ridge[1:])):
            if not (self._visible(a, margin=120) or self._visible(b, margin=120)):
                continue
            for k in range(5):
                t0, t1 = k / 5.0, (k + 0.75) / 5.0
                p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
                p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
                nx, ny = -(p1[1] - p0[1]), (p1[0] - p0[0])
                d = math.hypot(nx, ny) or 1.0
                nx, ny = nx / d * 7, ny / d * 7
                ink.ink_line(surf, (p0[0] - nx, p0[1] - ny), (p1[0] + nx, p1[1] + ny),
                             "faint", ink.seed_of("ridge", i, k))

    def _draw_water_lines(self, surf, level=None):
        """Inward lines behind the shore, and the depths out at sea.

        A chart says what the water is doing. Both sets are read off the same
        shape, so neither costs new geometry, and both are faint: the shoreline
        itself stays the darkest line on the chart.
        """
        depths = len(self.world.depth_lines)
        for ring_index, runs in enumerate(self.world.depth_lines):
            if level is not None and level != ring_index:
                continue
            if self.camera.zoom < 0.8 and ring_index > 0:
                continue
            for run_index, run in enumerate(runs):
                pts = [self._local(p) for p in run]
                if not any(self._visible(p, margin=200) for p in pts):
                    continue
                step = max(1, len(pts) // 22)
                ink.ink_curve(surf, pts[::step], "faint",
                              ink.seed_of("depth", ring_index, run_index), samples=4)
        for ring_index, rings in enumerate(self.world.coast_offsets):
            if level is not None and level != depths + ring_index:
                continue
            for poly_index, poly in enumerate(rings):
                pts = [self._local(p) for p in poly]
                if not any(self._visible(p, margin=200) for p in pts):
                    continue
                step = max(1, len(pts) // 26)
                ink.ink_curve(surf, pts[::step], "faint",
                              ink.seed_of("offset", ring_index, poly_index),
                              closed=True, samples=5)

    def _draw_land_tone(self, surf, index, screen_poly):
        """Land carries very light stipple. There are no filled areas anywhere."""
        clip = pygame.Rect(0, 0, *self._render_size)
        ink.stipple(surf, screen_poly, 0.085 + 0.04 * min(self.camera.zoom, 3.0),
                    ink.seed_of("land", index, round(self.camera.zoom, 1)),
                    alpha=78, clip=clip)

    def _draw_soundings(self, surf):
        if self.camera.zoom < 0.85:
            return
        size = 9 if self.camera.zoom < 2.5 else 10
        for i, (x, y, value) in enumerate(self.world.soundings):
            p = self._local((x, y))
            if not (0 <= p[0] <= self._render_size[0] and 0 <= p[1] <= self._render_size[1]):
                continue
            lettering.draw(surf, str(value), p, size=size, alpha=70)

    def _edge_endpoints(self, edge):
        a = self._local(self.world.settlements[edge.a].pos)
        b = self._local(self.world.settlements[edge.b].pos)
        return a, b

    def _draw_edges(self, surf):
        season = self.season
        anim = self.redraw_t
        for edge in self.world.known_edges():
            a, b = self._edge_endpoints(edge)
            if not (self._visible(a) or self._visible(b)):
                continue
            seed = world_map.edge_seed(edge)
            state = edge.availability(season)
            was = edge.availability(self.previous_season) if self.previous_season else state

            if state == T.CLOSED:
                if was != T.CLOSED and anim < 1.0:
                    # erased: the hand takes it off the document
                    ink.ink_line(surf, a, b, "faint", seed, reveal=1.0 - anim)
                elif edge.terrain == "ICE" and season == "SPRING":
                    self._ghost(surf, a, b, seed)
                continue

            reveal = anim if was == T.CLOSED else 1.0
            if edge.tunnel_built:
                ink.ruled_line(surf, a, b, "normal")
                ink.ruled_line(surf, (a[0], a[1] + 3), (b[0], b[1] + 3), "normal")
            elif edge.terrain == "ICE":
                self._draw_ice_road(surf, a, b, seed, reveal)
            elif state == T.HARD:
                ink.dashed_line(surf, a, b, "normal", seed, reveal=reveal)
            else:
                weight = "normal" if edge.runs < 6 else "heavy"
                ink.ink_line(surf, a, b, weight, seed, reveal=reveal)

            if self.camera.zoom >= T.DETAIL_MEASURE and reveal >= 1.0:
                self._draw_measure(surf, a, b, edge, seed)

            for year, _name in edge.losses:
                self._margin_cross(surf, a, b, year, seed)

    def _draw_ice_road(self, surf, a, b, seed, reveal):
        """Sketched in a lighter, provisional hand, and marked as ice."""
        ink.dashed_line(surf, a, b, "faint", seed, dash=15.0, gap=6.0, reveal=reveal)
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        ticks = max(2, int(length / 34))
        for i in range(1, ticks):
            t = i / ticks
            if t > reveal:
                break
            p = (a[0] + dx * t, a[1] + dy * t)
            ink.ink_line(surf, (p[0] - nx * 4, p[1] - ny * 4),
                         (p[0] + nx * 4, p[1] + ny * 4), "faint",
                         ink.seed_of(seed, "ice tick", i))

    def _ghost(self, surf, a, b, seed):
        pts = ink.wobble_polyline(a, b, seed)
        for i in range(0, len(pts) - 1, 3):
            pygame.draw.aaline(surf, (*T.INK, 34), pts[i], pts[i + 1])

    def _draw_measure(self, surf, a, b, edge, seed):
        """A hand-ruled measure along the leg, one tick per travel day."""
        days = max(1, int(round(edge.days)))
        for i in range(days + 1):
            t = i / days
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            dx, dy = b[0] - a[0], b[1] - a[1]
            d = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / d, dx / d
            size = 6 if i % 5 else 10
            ink.ink_line(surf, (p[0] + nx * 3, p[1] + ny * 3),
                         (p[0] + nx * (3 + size), p[1] + ny * (3 + size)),
                         "faint", ink.seed_of(seed, "tick", i))

    def _margin_cross(self, surf, a, b, year, seed):
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        ink.mark(surf, "cross", (mid[0] + 14, mid[1] - 12), ink.seed_of(seed, year), 4.5)
        lettering.draw(surf, str(year), (mid[0] + 20, mid[1] - 10), size=8, alpha=110)

    def _draw_settlements(self, surf):
        zoom = self.camera.zoom
        for s in self.world.known_settlements():
            p = self._local(s.pos)
            if not (-120 <= p[0] <= self._render_size[0] + 120
                    and -120 <= p[1] <= self._render_size[1] + 120):
                continue
            r = s.radius() * float(np.clip(zoom ** 0.72, 0.75, 5.0))
            seed = ink.seed_of("settlement", s.id, s.name)

            if not s.alive:
                ink.circle(surf, p, r, "faint", seed)
                ink.mark(surf, "strike", p, seed, r * 1.3, "correction", T.OXIDE)
                ink.mark(surf, "strike", (p[0], p[1] + 3), seed + 1, r * 1.3,
                         "correction", T.OXIDE)
            else:
                ink.circle(surf, p, r, "normal", seed)

            if zoom >= T.DETAIL_ROOFS and s.alive:
                self._draw_roofs(surf, p, r, seed)

            if zoom >= T.DETAIL_NAMES:
                lettering.draw(surf, s.name, (p[0] + r + 7, p[1] - 7),
                               size=11, alpha=195, spacing=1.4, caps=True)

    def _draw_roofs(self, surf, p, r, seed):
        """At FOCUS a circle resolves into a cluster of roofs and a jetty."""
        gen = ink.rng("roofs", seed)
        for i in range(8):
            ox = float(gen.uniform(-r * 0.6, r * 0.6))
            oy = float(gen.uniform(-r * 0.5, r * 0.5))
            w = r * 0.30
            base = (p[0] + ox, p[1] + oy)
            ink.ink_line(surf, (base[0] - w, base[1]), (base[0], base[1] - w * 0.8),
                         "normal", ink.seed_of(seed, "roof", i, 0))
            ink.ink_line(surf, (base[0], base[1] - w * 0.8), (base[0] + w, base[1]),
                         "normal", ink.seed_of(seed, "roof", i, 1))
        ink.ink_line(surf, (p[0] + r * 0.7, p[1] + r * 0.7),
                     (p[0] + r * 1.5, p[1] + r * 1.1), "normal",
                     ink.seed_of(seed, "jetty"))

    # --- frame ---
    def draw(self, target):
        clip = target.get_clip()
        target.set_clip(self.rect)

        for cache in (self.ground, self.network):
            surface = cache.service(self, self.camera)
            factor = self.camera.zoom / cache.zoom
            if abs(factor - 1.0) < 1e-6:
                target.blit(surface, self._blit_at(cache.centre, cache.size))
                continue
            # inked at another zoom: scale it while the new one is being inked,
            # rather than make one frame pay for the whole sheet
            self._blit_scaled(target, surface, cache.centre, factor)

        self.dynamic.fill((0, 0, 0, 0))
        # moving things go here at M1: cargo dots, hulls, teams
        target.blit(self.dynamic, self.rect.topleft)
        target.set_clip(clip)

    # --- picking ---
    def edge_at(self, screen_pos, radius=9.0):
        best, best_d = None, radius
        for edge in self.world.known_edges():
            a = self.camera.world_to_screen(self.world.settlements[edge.a].pos)
            b = self.camera.world_to_screen(self.world.settlements[edge.b].pos)
            d = _point_segment_distance(screen_pos, a, b)
            if d < best_d:
                best, best_d = edge, d
        return best

    def settlement_at(self, screen_pos):
        for s in self.world.known_settlements():
            p = self.camera.world_to_screen(s.pos)
            r = s.radius() * float(np.clip(self.camera.zoom ** 0.72, 0.75, 5.0))
            if math.hypot(screen_pos[0] - p[0], screen_pos[1] - p[1]) <= r + 4:
                return s
        return None


def _point_segment_distance(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - (ax + dx * t), p[1] - (ay + dy * t))


def _visible_spans(a, b, w, h, mask, mask_step=1, step=9.0):
    """The parts of a-b that lie on the surface and off the land."""
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(2, int(length / step))
    ts = np.linspace(0.0, 1.0, n)
    xs = a[0] + (b[0] - a[0]) * ts
    ys = a[1] + (b[1] - a[1]) * ts
    inside = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
    xi = np.clip((xs / mask_step).astype(int), 0, mask.shape[0] - 1)
    yi = np.clip((ys / mask_step).astype(int), 0, mask.shape[1] - 1)
    good = inside & ~mask[xi, yi]

    spans = []
    start = None
    for i, ok in enumerate(good):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            if i - start > 1:
                spans.append(((xs[start], ys[start]), (xs[i - 1], ys[i - 1])))
            start = None
    if start is not None and len(good) - start > 1:
        spans.append(((xs[start], ys[start]), (xs[-1], ys[-1])))
    return spans
