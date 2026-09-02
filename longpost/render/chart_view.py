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
                self.pending = [view._cache_centre(), camera.zoom,
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
        # the view, so its re-ink is spread across frames. The legs and the
        # settlements are cheap and always finished in one — and they are kept
        # apart because the season change re-inks the legs every frame while
        # the settlements stand still.
        self.ground = DocumentCache(size, self._ground_stages,
                                    slice_ms=T.INK_SLICE_MS, warm_at=0.25)
        self.routes = DocumentCache(size, self._route_stages, warm_at=0.06)
        self.places = DocumentCache(size, self._place_stages, warm_at=0.06)
        self.dynamic = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        self.season = T.SEASONS[0]
        self.previous_season = None
        self.redraw_t = 1.0          # 0..1, the season-change re-inking
        self.hover_edge = None
        self.game = None          # set by the game; the chart reads it, never writes
        self._mask = None

    # --- state ---
    @property
    def caches(self):
        return (self.ground, self.routes, self.places)

    @property
    def network(self):
        """The legs and the places together — what the post put on the chart."""
        return self.routes

    @property
    def dirty(self) -> bool:
        return any(cache.dirty for cache in self.caches)

    @dirty.setter
    def dirty(self, value):
        for cache in self.caches:
            cache.dirty = bool(value)

    @property
    def _rebuilds(self) -> int:
        return sum(cache.rebuilds for cache in self.caches)

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

    def _cache_centre(self):
        """Where the next bitmap is inked from: where the camera is now.

        The bitmap is bigger than the chart rect by the pan margin, and the
        slack test decides when the view has eaten that margin — so there is
        nothing to gain by rounding the centre to a grid, and half the margin
        to lose before a drag has even started.
        """
        return self.camera.centre.copy()

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
        """A screen-space mask of the land, taken straight off the field."""
        step = self.MASK_STEP
        size = (self._render_size[0] // step + 1, self._render_size[1] // step + 1)
        ground = self.world.terrain
        small = pygame.Surface((ground.cols, ground.rows))
        pygame.surfarray.blit_array(
            small, np.where(ground.mask.T, 255, 0).astype(np.uint8)[:, :, None]
                     .repeat(3, axis=2))
        scale = self.camera.scale * ground.cell / step
        target = (max(1, int(ground.cols * scale)), max(1, int(ground.rows * scale)))
        scaled = pygame.transform.scale(small, target)
        mask = pygame.Surface(size)
        mask.fill((0, 0, 0))
        origin = self._local((0.0, 0.0))
        mask.blit(scaled, (origin[0] / step, origin[1] / step))
        return pygame.surfarray.array2d(mask) != 0

    # --- the document ---
    def _ground_stages(self):
        """The sheet: what the water and the land are doing.

        Handed over in small pieces — a few contours at a time — so that a
        re-ink can stop between any two of them and finish next frame. A stage
        that costs more than the slice makes the slice meaningless.
        """
        def mask(_surf):
            self._mask = self._land_mask()

        def ice(surf):
            if self.season == "WINTER":
                self._draw_ice(surf, self._mask)

        def chunks(paths, size=6):
            return [paths[i:i + size] for i in range(0, len(paths), size)]

        bands = 3
        stages = [mask]
        stages += [lambda surf, b=b: self._draw_sea(surf, b, bands) for b in range(bands)]
        stages.append(ice)

        for level, rings in enumerate(self.world.depth_lines):
            if self.camera.zoom < 0.8 and level > 0:
                continue
            stages += [lambda surf, c=c, level=level: self._ink_contours(surf, c, "faint",
                                                                        ("depth", level))
                       for c in chunks(rings, 10)]
        for rings in chunks(self.world.coast_paths, 5):
            stages.append(lambda surf, c=rings: self._ink_contours(surf, c, "normal",
                                                                   ("coast",)))
        for level, rings in enumerate(self.world.coast_offsets):
            stages += [lambda surf, c=c, level=level: self._ink_contours(surf, c, "faint",
                                                                        ("shore", level))
                       for c in chunks(rings, 10)]
        for rings in chunks(self.world.mountains, 4):
            stages.append(lambda surf, c=rings: self._draw_mountains(surf, c))
        stages.append(self._draw_land_tone)
        stages.append(self._draw_soundings)
        return stages

    def _route_stages(self):
        """The legs. Re-inked every frame of the season change, so kept apart
        from the settlements, which are not."""
        return [self._draw_edges]

    def _place_stages(self):
        """The settlements, and the marks the run leaves on the document."""
        return [self._draw_settlements, self._draw_marks]

    def _draw_sea(self, surf, band=0, bands=1):
        """Faint hatching, thickening as the player draws in. No filled areas.

        Drawn in bands so a re-ink can stop between them.
        """
        zoom = self.camera.zoom
        # The water carries its depths and its soundings now, so the ambient
        # tone is only a whisper: hatching belongs to danger, ice and weather,
        # and it cannot read as those if the whole sea is hatched.
        density = 0.02 + 0.09 * min(zoom, 4.0)
        spacing = T.HATCH_SPACING_MAX + (T.HATCH_SPACING_MIN - T.HATCH_SPACING_MAX) * density
        spacing = max(spacing, 15.0)
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
                          alpha=int(46 + 16 * min(zoom, 3.0)))

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

    def _paths_on_sheet(self, paths, margin=140):
        """Contours with anything on the sheet, in document coordinates.

        Transformed with numpy and culled by bounding box: a coast of a hundred
        loops is tens of thousands of points, and doing that a point at a time
        in Python costs more than inking them.
        """
        scale = self.camera.scale
        cx, cy = self._render_size[0] / 2.0, self._render_size[1] / 2.0
        ox, oy = float(self._render_centre[0]), float(self._render_centre[1])
        width, height = self._render_size
        out = []
        for path in paths:
            arr = np.asarray(path, dtype=np.float64)
            xs = cx + (arr[:, 0] - ox) * scale
            ys = cy + (arr[:, 1] - oy) * scale
            if (xs.max() < -margin or xs.min() > width + margin
                    or ys.max() < -margin or ys.min() > height + margin):
                continue
            out.append(np.stack([xs, ys], axis=1))
        return out

    def _contour_step(self):
        """How much of a contour to keep. Far out, every third point is enough
        and the difference is a pen's width."""
        return 1 if self.camera.zoom >= 2.0 else 3

    def _ink_contours(self, surf, paths, weight, identity):
        ink.ink_paths(surf, self._paths_on_sheet(paths), weight,
                      ink.seed_of(*identity), step=self._contour_step())

    def _draw_mountains(self, surf, paths):
        """High ground, drawn the way a chart shows relief: its outline, and
        short strokes down the slope inside it."""
        on_sheet = self._paths_on_sheet(paths)
        ink.ink_paths(surf, on_sheet, "faint", ink.seed_of("mountain"),
                      step=self._contour_step() + 1)
        if self.camera.zoom < T.DETAIL_HACHURE:
            return              # far out, high ground is its outline and no more
        for index, pts in enumerate(on_sheet):
            if len(pts) < 40:          # only ground worth calling high ground
                continue
            gen = ink.rng("hachure", index, round(self.camera.zoom, 1))
            for i in range(0, len(pts), max(6, len(pts) // 9)):
                a = pts[i]
                b = pts[(i + 2) % len(pts)]
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / length, dx / length
                reach = float(gen.uniform(2.5, 5.0)) * min(self.camera.zoom, 2.0)
                ink.ink_line(surf, a, (a[0] - nx * reach, a[1] - ny * reach), "faint",
                             ink.seed_of("hachure", index, i))

    def _draw_land_tone(self, surf):
        """Land carries very light stipple. There are no filled areas anywhere."""
        w, h = self._render_size
        gen = ink.rng("land tone", self.world.seed, round(self.camera.zoom, 1))
        count = int(w * h * (0.00034 + 0.00008 * min(self.camera.zoom, 3.0)))
        pts = gen.uniform([0, 0], [w, h], (count, 2))
        xi = np.clip((pts[:, 0] / self.MASK_STEP).astype(int), 0, self._mask.shape[0] - 1)
        yi = np.clip((pts[:, 1] / self.MASK_STEP).astype(int), 0, self._mask.shape[1] - 1)
        pts = pts[self._mask[xi, yi]]
        surf.lock()
        for x, y in pts:
            surf.set_at((int(x), int(y)), (*T.INK, 84))
        surf.unlock()

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
                ink.dashed_line(surf, a, b, "route", seed, reveal=reveal)
            else:
                # a route the post uses heavily darkens, as though re-inked
                weight = "route" if edge.runs < 6 else "heavy"
                ink.ink_line(surf, a, b, weight, seed, reveal=reveal)

            if edge.danger > 0.0:
                self._draw_danger(surf, a, b, edge, seed)

            if self.game is not None and self.game.selected_edge is edge:
                self._draw_selection(surf, a, b, seed)

            if self.camera.zoom >= T.DETAIL_MEASURE and reveal >= 1.0:
                self._draw_measure(surf, a, b, edge, seed)

    def _draw_danger(self, surf, a, b, edge, seed):
        """A dangerous leg is not a different colour. It is more densely
        hatched, and the hatching sits on the side the watching comes from."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux

        source = self.world.settlements[edge.danger_source] if edge.danger_source >= 0 \
            else None
        side = 1.0
        if source is not None:
            here = self._local(source.pos)
            middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            side = 1.0 if (here[0] - middle[0]) * nx + (here[1] - middle[1]) * ny > 0 else -1.0

        spacing = max(5.0, 22.0 - 16.0 * min(edge.danger, 1.0))
        reach = 4.0 + 7.0 * min(edge.danger, 1.0)
        steps = max(2, int(length / spacing))
        for i in range(1, steps):
            t = i / steps
            p = (a[0] + dx * t, a[1] + dy * t)
            lean = 0.45 * side
            ink.ink_line(surf, p,
                         (p[0] + (nx * side + ux * lean) * reach,
                          p[1] + (ny * side + uy * lean) * reach),
                         "heavy" if edge.danger > T.BAND_ROAD_HARD else "normal",
                         ink.seed_of(seed, "danger", i))

    def _draw_selection(self, surf, a, b, seed):
        """The leg the player is looking at, ticked in the margin of the line."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        for side in (-1, 1):
            off = (nx * 5 * side, ny * 5 * side)
            ink.ink_line(surf, (a[0] + off[0], a[1] + off[1]),
                         (b[0] + off[0], b[1] + off[1]), "faint",
                         ink.seed_of(seed, "selected", side))

    def _draw_ice_road(self, surf, a, b, seed, reveal):
        """Sketched in a lighter, provisional hand, and marked as ice."""
        ink.dashed_line(surf, a, b, "normal", seed, dash=15.0, gap=6.0, reveal=reveal)
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

    def _margin_cross(self, surf, a, b, year, seed, index=0):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        t = 0.5 + 0.12 * ((index % 3) - 1)
        p = (a[0] + dx * t + nx * 15, a[1] + dy * t + ny * 15)
        ink.mark(surf, "cross", p, ink.seed_of(seed, "loss", year, index), 5.0)
        lettering.draw(surf, str(year), (p[0] + 7, p[1] - 4), size=8, alpha=120)

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
            elif s.doomed(self._seasons_to_winter()):
                # the way a chart marks something no longer to be relied on. Not
                # red: red is for what has already ended. This is a settlement
                # still alive, still receiving post, and known to be finished.
                ink.circle(surf, p, r, "route", seed, broken=True)
            else:
                ink.circle(surf, p, r, "route", seed)

            if s.alive and s.desperation > T.BAND_CALM * 100:
                self._draw_pressure(surf, p, r, s, seed)

            if zoom >= T.DETAIL_ROOFS and s.alive:
                self._draw_roofs(surf, p, r, seed)

            if zoom >= T.DETAIL_NAMES:
                lettering.draw(surf, s.name, (p[0] + r + 7, p[1] - 7),
                               size=11, alpha=195, spacing=1.4, caps=True)

    def _draw_pressure(self, surf, p, r, settlement, seed):
        """How hard it is here, as ticks round the circle.

        Density is the game's one continuous visual variable, and this is what
        it carries: a settlement in trouble grows a denser ring of marks, and
        the player reads the shape of the trouble across the whole chart
        without a legend and without a number.
        """
        share = min(1.0, settlement.desperation / 100.0)
        strokes = int(5 + 19 * share)
        gen = ink.rng("pressure", seed)
        start = float(gen.uniform(0, math.tau))
        for i in range(strokes):
            angle = start + math.tau * i / strokes
            cos, sin = math.cos(angle), math.sin(angle)
            inner = r * 1.12
            reach = r * (0.28 + 0.55 * share)
            ink.ink_line(surf, (p[0] + cos * inner, p[1] + sin * inner),
                         (p[0] + cos * (inner + reach), p[1] + sin * (inner + reach)),
                         "normal" if share > T.BAND_STRAINED else "faint",
                         ink.seed_of(seed, "pressure", i))

    def _seasons_to_winter(self) -> int:
        if self.game is not None:
            return self.game.seasons_to_winter
        index = T.SEASONS.index(self.season)
        return (T.SEASONS.index("WINTER") - index) % len(T.SEASONS) + 1

    def _draw_marks(self, surf):
        """What the run has written on the chart and will not take off it.

        A leg where a courier was lost carries a small cross in the margin, with
        the year beside it in tiny type. It stays for the rest of the run, on a
        leg that is closed as much as on one that is open, because the chart is
        a record and not a readout.
        """
        for edge in self.world.known_edges():
            if not edge.losses:
                continue
            a = self._local(self.world.settlements[edge.a].pos)
            b = self._local(self.world.settlements[edge.b].pos)
            if not (self._visible(a) or self._visible(b)):
                continue
            seed = world_map.edge_seed(edge)
            for index, (year, _name) in enumerate(edge.losses):
                self._margin_cross(surf, a, b, year, seed, index)

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

        for cache in self.caches:
            surface = cache.service(self, self.camera)
            factor = self.camera.zoom / cache.zoom
            if abs(factor - 1.0) < 1e-6:
                target.blit(surface, self._blit_at(cache.centre, cache.size))
                continue
            # inked at another zoom: scale it while the new one is being inked,
            # rather than make one frame pay for the whole sheet
            self._blit_scaled(target, surface, cache.centre, factor)

        self.dynamic.fill((0, 0, 0, 0))
        self._draw_runs(self.dynamic)
        target.blit(self.dynamic, self.rect.topleft)
        target.set_clip(clip)

    # --- what is moving ---
    def _screen(self, world_pt):
        x, y = self.camera.world_to_screen(world_pt)
        return (x - self.rect.x, y - self.rect.y)

    def _draw_runs(self, surf):
        """Cargo in transit: a single small dot at CHART, a drawn hull, sledge
        or team once the player has drawn in."""
        game = self.game
        if game is None or game.phase != "RESOLVE" or game.resolution is None:
            return
        share = game.resolve_t / max(game.resolution.duration, 1e-6)
        for leg in game.resolution.legs:
            if not leg.arrived and share > leg.start:
                continue
            span = max(leg.end - leg.start, 1e-6)
            t = (share - leg.start) / span
            if t < 0:
                continue
            t = min(t, 1.0)
            a = self._screen(self.world.settlements[leg.origin].pos)
            b = self._screen(self.world.settlements[leg.destination].pos)
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            carrier = game.fleet[leg.carrier_id]
            if self.camera.zoom >= T.DETAIL_HULLS:
                self._draw_carrier(surf, p, a, b, carrier, leg)
            else:
                ink.mark(surf, "dot", p, ink.seed_of("run", leg.carrier_id), 2.0)

    def _draw_carrier(self, surf, p, a, b, carrier, leg):
        """Six or seven lines, no more, and a wake or a track behind it."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        size = float(np.clip(self.camera.zoom * 3.0, 6.0, 26.0))
        seed = ink.seed_of("carrier", carrier.id, leg.edge_id)

        kind = carrier.type.key
        if kind in ("SMALL_BOAT", "DEEP_VESSEL"):
            stern = (p[0] - ux * size, p[1] - uy * size)
            bow = (p[0] + ux * size * 1.2, p[1] + uy * size * 1.2)
            beam = size * 0.42
            port = (p[0] + nx * beam, p[1] + ny * beam)
            starboard = (p[0] - nx * beam, p[1] - ny * beam)
            ink.ink_curve(surf, [stern, port, bow], "normal", seed, samples=4)
            ink.ink_curve(surf, [stern, starboard, bow], "normal", seed + 1, samples=4)
            mast = (p[0] + ny * size * 1.1, p[1] - nx * size * 1.1)
            ink.ink_line(surf, p, mast, "normal", seed + 2)
        elif kind == "DOG_SLED":
            ink.ink_line(surf, (p[0] - ux * size, p[1] - uy * size),
                         (p[0] + ux * size * 0.4, p[1] + uy * size * 0.4), "normal", seed)
            ink.ink_line(surf, (p[0] - ux * size + nx * 3, p[1] - uy * size + ny * 3),
                         (p[0] - ux * size - nx * 3, p[1] - uy * size - ny * 3),
                         "normal", seed + 1)
            for i in range(2):
                lead = (p[0] + ux * size * (0.9 + i * 0.5), p[1] + uy * size * (0.9 + i * 0.5))
                ink.ink_line(surf, lead, (lead[0] + ux * size * 0.3,
                                          lead[1] + uy * size * 0.3), "normal", seed + 2 + i)
        else:
            body = (p[0] + ux * size * 0.7, p[1] + uy * size * 0.7)
            ink.ink_line(surf, (p[0] - ux * size * 0.5, p[1] - uy * size * 0.5), body,
                         "normal", seed)
            for i, foot in enumerate((-0.3, 0.3)):
                base = (p[0] + ux * size * foot, p[1] + uy * size * foot)
                ink.ink_line(surf, base, (base[0] + nx * size * 0.5,
                                          base[1] + ny * size * 0.5), "normal", seed + 3 + i)

        # the wake, or the track
        for i in range(1, 5):
            back = (p[0] - ux * size * (1.2 + i * 0.7), p[1] - uy * size * (1.2 + i * 0.7))
            spread = size * 0.18 * i
            ink.ink_line(surf, (back[0] + nx * spread, back[1] + ny * spread),
                         (back[0] - nx * spread, back[1] - ny * spread), "faint",
                         ink.seed_of(seed, "wake", i))

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
