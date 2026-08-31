"""The five drawing primitives, and the paper they go onto.

Everything visible in the game is made of these. Two rules govern the module:

* No line is straight and no area is filled. Tone is hatching, always.
* Every wobble is derived from the identity of the thing being drawn, never
  from time. A mark drawn twice in two frames is the same mark, to the pixel.
"""

import zlib

import numpy as np
import pygame

from .. import tuning as T

# --- deterministic randomness --------------------------------------------


def seed_of(*parts) -> int:
    """A stable 32-bit seed from any identity. Never uses hash()."""
    key = "|".join(repr(p) for p in parts).encode("utf-8")
    return zlib.crc32(key)


def rng(*parts) -> np.random.Generator:
    return np.random.default_rng(seed_of(*parts))


def _smooth(gen: np.random.Generator, n: int, knots: int = 5) -> np.ndarray:
    """n smoothly varying values in roughly [-1, 1]."""
    if n <= 1:
        return np.zeros(n)
    knots = max(2, min(knots, n))
    control = gen.uniform(-1.0, 1.0, knots)
    x = np.linspace(0.0, knots - 1.0, n)
    i = np.clip(x.astype(int), 0, knots - 2)
    t = x - i
    t = 0.5 - 0.5 * np.cos(np.pi * t)          # cosine interpolation
    return control[i] * (1.0 - t) + control[i + 1] * t


def _upsample(field: np.ndarray, shape) -> np.ndarray:
    """Bilinear upscale of a low-frequency field. Keeps paper free of blocking."""
    h, w = shape
    fh, fw = field.shape
    ys = np.linspace(0, fh - 1, h)
    xs = np.linspace(0, fw - 1, w)
    y0 = np.clip(ys.astype(int), 0, fh - 2)
    x0 = np.clip(xs.astype(int), 0, fw - 2)
    ty = (ys - y0)[:, None]
    tx = (xs - x0)[None, :]
    a = field[np.ix_(y0, x0)]
    b = field[np.ix_(y0, x0 + 1)]
    c = field[np.ix_(y0 + 1, x0)]
    d = field[np.ix_(y0 + 1, x0 + 1)]
    top = a * (1 - tx) + b * tx
    bot = c * (1 - tx) + d * tx
    return (top * (1 - ty) + bot * ty).astype(np.float32)


# --- paper ----------------------------------------------------------------


def make_paper(size, seed) -> pygame.Surface:
    """Chart paper: coarse fibre, fine grain, a vignette, a few stains.

    Generated once at startup and blitted every frame at zero cost.
    """
    w, h = size
    gen = rng("paper", seed, w, h)
    base = np.array(T.PAPER_BASE, dtype=np.float32)

    fibre = _upsample(gen.normal(0.0, 1.0, (h // 14 + 2, w // 14 + 2)), (h, w))
    fibre += 0.5 * _upsample(gen.normal(0.0, 1.0, (h // 5 + 2, w // 5 + 2)), (h, w))
    grain = gen.normal(0.0, 1.0, (h, w)).astype(np.float32)

    tone = fibre * T.PAPER_FIBRE + grain * T.PAPER_GRAIN

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx / max(w - 1, 1)) * 2.0 - 1.0
    ny = (yy / max(h - 1, 1)) * 2.0 - 1.0
    radius = np.sqrt(nx * nx + ny * ny) / np.sqrt(2.0)
    vignette = 1.0 - T.PAPER_VIGNETTE * radius ** 2

    stains = np.zeros((h, w), dtype=np.float32)
    for i in range(gen.integers(*T.PAPER_STAINS)):
        cx = gen.uniform(0, w)
        cy = gen.uniform(0, h)
        rx = gen.uniform(w * 0.06, w * 0.22)
        ry = rx * gen.uniform(0.6, 1.5)
        d = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
        stains += np.exp(-d * 1.6) * gen.uniform(5.0, 11.0)

    field = (base[None, None, :] + tone[:, :, None]) * vignette[:, :, None]
    field -= stains[:, :, None]
    field = np.clip(field, 0, 255).astype(np.uint8)

    surf = pygame.Surface((w, h))
    pygame.surfarray.blit_array(surf, np.transpose(field, (1, 0, 2)))
    return surf


# --- 3.1 the most important function in the project -----------------------


def wobble_polyline(a, b, seed, amplitude=None, segment_px=None):
    """The wandering path a pen takes between two points."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length = float(np.hypot(dx, dy))
    if length < 1e-6:
        return [(ax, ay), (bx, by)]

    seg = segment_px or T.INK_SEGMENT_PX
    n = max(1, int(length / seg))
    if amplitude is None:
        amplitude = min(
            T.INK_WOBBLE_MAX, T.INK_WOBBLE_BASE + length * T.INK_WOBBLE_PER_PX
        )

    t = np.linspace(0.0, 1.0, n + 1)
    px, py = -dy / length, dx / length
    noise = _smooth(rng("wobble", seed), n + 1)
    noise[0] = noise[-1] = 0.0
    taper = np.sin(np.pi * t) ** 0.6          # the pen settles at both ends
    off = noise * amplitude * taper

    xs = ax + dx * t + px * off
    ys = ay + dy * t + py * off
    return list(zip(xs.tolist(), ys.tolist()))


def _strokes(surface, points, weight, seed, color):
    """Stroke a polyline two or three times at small offsets and alphas."""
    passes, alphas, spread = T.INK_WEIGHTS[weight]
    if len(points) < 2:
        return
    pts = np.asarray(points, dtype=np.float64)
    d = np.gradient(pts, axis=0)
    norm = np.hypot(d[:, 0], d[:, 1])
    norm[norm < 1e-9] = 1.0
    perp = np.stack([-d[:, 1] / norm, d[:, 0] / norm], axis=1)

    gen = rng("stroke", seed)
    for i in range(passes):
        alpha = alphas[i]
        if spread:
            jitter = gen.uniform(-spread, spread)
            wander = _smooth(rng("pass", seed, i), len(pts), knots=3) * spread * 0.5
            shifted = pts + perp * (jitter + wander)[:, None]
        else:
            shifted = pts
        pygame.draw.aalines(
            surface, (*color, alpha), False, [tuple(p) for p in shifted]
        )

    # a heavier deposit where the pen starts and stops
    if weight == "faint":
        return
    for end in (pts[0], pts[-1]):
        pygame.draw.aaline(
            surface,
            (*color, alphas[-1]),
            (end[0] - 0.6, end[1]),
            (end[0] + 0.6, end[1]),
        )


def ink_line(surface, a, b, weight="normal", seed=0, color=T.INK, reveal=1.0,
             segment_px=None):
    """Never a straight line. This is most of the hand-drawn look.

    `reveal` draws only the first fraction of the stroke, which is how the
    season change inks a new edge in over about a second.
    """
    pts = wobble_polyline(a, b, seed, segment_px=segment_px)
    if reveal < 1.0:
        keep = max(2, int(len(pts) * max(reveal, 0.0)))
        pts = pts[:keep]
    _strokes(surface, pts, weight, seed, color)


def faint_strokes(surface, spans, seed, color=T.INK, alpha=None, segment_px=20.0):
    """Many faint lines at once — ambient tone such as the sea.

    Identical in look to calling ink_line per span, but the wobble for every
    span is drawn from one batch, which is what makes a screenful affordable.
    """
    if not spans:
        return
    alpha = T.INK_WEIGHTS["faint"][1][0] if alpha is None else alpha
    a = np.array([s[0] for s in spans], dtype=np.float64)
    b = np.array([s[1] for s in spans], dtype=np.float64)
    d = b - a
    length = np.hypot(d[:, 0], d[:, 1])
    n = int(max(2, min(24, np.median(length) / segment_px + 2)))
    t = np.linspace(0.0, 1.0, n)[None, :]

    gen = rng("faint field", seed)
    knots = 4
    control = gen.uniform(-1.0, 1.0, (len(spans), knots))
    x = np.linspace(0.0, knots - 1.0, n)
    i = np.clip(x.astype(int), 0, knots - 2)
    frac = 0.5 - 0.5 * np.cos(np.pi * (x - i))
    noise = control[:, i] * (1.0 - frac)[None, :] + control[:, i + 1] * frac[None, :]

    amp = np.clip(T.INK_WOBBLE_BASE + length * T.INK_WOBBLE_PER_PX, 0, T.INK_WOBBLE_MAX)
    off = noise * (amp[:, None]) * (np.sin(np.pi * t) ** 0.6)
    with np.errstate(invalid="ignore", divide="ignore"):
        px = np.where(length > 0, -d[:, 1] / length, 0.0)[:, None]
        py = np.where(length > 0, d[:, 0] / length, 0.0)[:, None]

    xs = a[:, 0][:, None] + d[:, 0][:, None] * t + px * off
    ys = a[:, 1][:, None] + d[:, 1][:, None] * t + py * off
    stroke = (*color, alpha)
    surface.lock()
    for row in range(len(spans)):
        pygame.draw.aalines(surface, stroke, False,
                            list(zip(xs[row].tolist(), ys[row].tolist())))
    surface.unlock()


def ruled_line(surface, a, b, weight="normal", color=T.INK):
    """The one exception in the game: a tunnel, drawn by an engineer."""
    passes, alphas, _ = T.INK_WEIGHTS[weight]
    for i in range(passes):
        pygame.draw.aaline(surface, (*color, alphas[i]), a, b)


# --- 3.2 ------------------------------------------------------------------


def catmull_rom(points, samples_per_span=8):
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 3:
        return [tuple(p) for p in pts]
    ext = np.vstack([pts[0] + (pts[0] - pts[1]), pts, pts[-1] + (pts[-1] - pts[-2])])
    out = []
    for i in range(len(ext) - 3):
        p0, p1, p2, p3 = ext[i : i + 4]
        t = np.linspace(0.0, 1.0, samples_per_span, endpoint=False)[:, None]
        out.append(
            0.5
            * (
                (2 * p1)
                + (-p0 + p2) * t
                + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3
            )
        )
    out.append(pts[-1][None, :])
    return [tuple(p) for p in np.vstack(out)]


def ink_curve(surface, points, weight="normal", seed=0, color=T.INK, closed=False,
              samples=6):
    if len(points) < 2:
        return
    ctrl = list(points) + [points[0]] if closed else list(points)
    curve = catmull_rom(ctrl, samples_per_span=samples)
    pts = np.asarray(curve)
    d = np.gradient(pts, axis=0)
    norm = np.hypot(d[:, 0], d[:, 1])
    norm[norm < 1e-9] = 1.0
    perp = np.stack([-d[:, 1] / norm, d[:, 0] / norm], axis=1)
    amp = min(T.INK_WOBBLE_MAX, T.INK_WOBBLE_BASE + norm.sum() * T.INK_WOBBLE_PER_PX * 0.25)
    off = _smooth(rng("curve", seed), len(pts), knots=max(4, len(ctrl))) * amp
    if not closed:
        off[0] = off[-1] = 0.0
    _strokes(surface, pts + perp * off[:, None], weight, seed, color)


# --- 3.3 ------------------------------------------------------------------


def _clip_segment_to_polygon(a, b, polygon):
    """Every sub-segment of a-b that lies inside the polygon."""
    poly = np.asarray(polygon, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    d = b - a
    p = np.roll(poly, -1, axis=0) - poly
    denom = d[0] * p[:, 1] - d[1] * p[:, 0]
    ok = np.abs(denom) > 1e-12
    diff = poly - a
    t = np.where(ok, (diff[:, 0] * p[:, 1] - diff[:, 1] * p[:, 0]) / np.where(ok, denom, 1), -1.0)
    u = np.where(ok, (diff[:, 0] * d[1] - diff[:, 1] * d[0]) / np.where(ok, denom, 1), -1.0)
    hits = sorted(t[ok & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)].tolist())
    cuts = [0.0] + hits + [1.0]
    spans = []
    for lo, hi in zip(cuts, cuts[1:]):
        if hi - lo < 1e-6:
            continue
        mid = a + d * ((lo + hi) * 0.5)
        if point_in_polygon(mid, poly):
            spans.append((tuple(a + d * lo), tuple(a + d * hi)))
    return spans


def points_in_polygon(points, polygon) -> np.ndarray:
    """Ray casting over many points at once."""
    poly = np.asarray(polygon, dtype=np.float64)
    pts = np.asarray(points, dtype=np.float64)
    x1, y1 = poly[:, 0][None, :], poly[:, 1][None, :]
    x2, y2 = np.roll(poly[:, 0], -1)[None, :], np.roll(poly[:, 1], -1)[None, :]
    px, py = pts[:, 0][:, None], pts[:, 1][:, None]
    straddles = (y1 > py) != (y2 > py)
    denom = np.where(y2 != y1, y2 - y1, 1.0)
    xint = x1 + (py - y1) * (x2 - x1) / denom
    return (np.count_nonzero(straddles & (px < xint), axis=1) % 2).astype(bool)


def point_in_polygon(point, polygon) -> bool:
    poly = np.asarray(polygon, dtype=np.float64)
    x, y = float(point[0]), float(point[1])
    x1, y1 = poly[:, 0], poly[:, 1]
    x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
    straddles = (y1 > y) != (y2 > y)
    with np.errstate(divide="ignore", invalid="ignore"):
        xint = np.where(straddles, x1 + (y - y1) * (x2 - x1) / np.where(y2 != y1, y2 - y1, 1), np.inf)
    return bool(np.count_nonzero(straddles & (x < xint)) % 2)


def hatch(surface, region, density, angle, seed, weight="faint", color=T.INK, clip=None):
    """Parallel ink lines filling a region. All tone in the game is this.

    `region` is a polygon. `density` in 0..1 is the game's primary continuous
    visual variable: a dangerous edge is not a colour, it is denser hatching.
    """
    if density <= 0.0:
        return
    poly = np.asarray(region, dtype=np.float64)
    if len(poly) < 3:
        return
    spacing = T.HATCH_SPACING_MAX + (T.HATCH_SPACING_MIN - T.HATCH_SPACING_MAX) * min(density, 1.0)
    centre = poly.mean(axis=0)
    reach = float(np.max(np.hypot(*(poly - centre).T))) + spacing

    ca, sa = np.cos(angle), np.sin(angle)
    gen = rng("hatch", seed)
    n = int(2 * reach / spacing) + 1
    for i in range(n):
        offset = -reach + i * spacing + gen.uniform(-spacing * 0.18, spacing * 0.18)
        mid = centre + np.array([-sa, ca]) * offset
        a = mid - np.array([ca, sa]) * reach
        b = mid + np.array([ca, sa]) * reach
        for s0, s1 in _clip_segment_to_polygon(a, b, poly):
            if clip is not None and not clip.clipline(s0, s1):
                continue
            ink_line(surface, s0, s1, weight, seed_of(seed, "h", i), color)


# --- 3.4 ------------------------------------------------------------------


def stipple(surface, region, density, seed, color=T.INK, alpha=110, clip=None):
    """Dots at controlled density. Snowfield, ice, the soft edge of hatching."""
    poly = np.asarray(region, dtype=np.float64)
    if len(poly) < 3 or density <= 0.0:
        return
    lo = poly.min(axis=0)
    hi = poly.max(axis=0)
    area = float((hi[0] - lo[0]) * (hi[1] - lo[1]))
    count = int(area * density * 0.010)
    if count <= 0:
        return
    gen = rng("stipple", seed)
    pts = gen.uniform(lo, hi, (min(count, 6000), 2))
    pts = pts[points_in_polygon(pts, poly)]
    if clip is not None:
        inside = ((pts[:, 0] >= clip.left) & (pts[:, 0] < clip.right)
                  & (pts[:, 1] >= clip.top) & (pts[:, 1] < clip.bottom))
        pts = pts[inside]
    for p in pts:
        surface.set_at((int(p[0]), int(p[1])), (*color, alpha))


# --- 3.5 ------------------------------------------------------------------


def mark(surface, kind, position, seed=0, scale=6.0, weight="normal", color=T.INK):
    """The chart's marginalia: a cross, a circled dot, a tick, a query, a strike."""
    x, y = position
    s = scale

    if kind == "cross":
        ink_line(surface, (x - s, y - s), (x + s, y + s), weight, seed_of(seed, 1), color)
        ink_line(surface, (x - s, y + s), (x + s, y - s), weight, seed_of(seed, 2), color)
    elif kind == "circled_dot":
        circle(surface, (x, y), s, weight, seed_of(seed, 3), color)
        surface.set_at((int(x), int(y)), (*color, 235))
    elif kind == "tick":
        ink_line(surface, (x - s, y), (x - s * 0.2, y + s * 0.7), weight, seed_of(seed, 4), color)
        ink_line(surface, (x - s * 0.2, y + s * 0.7), (x + s, y - s), weight, seed_of(seed, 5), color)
    elif kind == "query":
        arc = [(x - s * 0.6, y - s * 0.5), (x, y - s), (x + s * 0.6, y - s * 0.3),
               (x, y + s * 0.2), (x, y + s * 0.5)]
        ink_curve(surface, arc, weight, seed_of(seed, 6), color)
        surface.set_at((int(x), int(y + s)), (*color, 235))
    elif kind == "strike":
        ink_line(surface, (x - s, y + s * 0.2), (x + s, y - s * 0.2), weight, seed_of(seed, 7), color)
    elif kind == "dot":
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            surface.set_at((int(x) + dx, int(y) + dy), (*color, 220))
    else:
        raise ValueError(f"unknown mark: {kind}")


def circle(surface, centre, radius, weight="normal", seed=0, color=T.INK, broken=False):
    """A hand-drawn circle. `broken` is how a chart marks what cannot be relied on."""
    cx, cy = centre
    n = max(12, int(radius * 2.4))
    t = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    wob = _smooth(rng("circle", seed), n, knots=5) * max(0.5, radius * 0.09)
    r = radius + wob
    # the pen does not quite close the loop
    xs = cx + np.cos(t) * r
    ys = cy + np.sin(t) * r
    pts = list(zip(xs.tolist(), ys.tolist()))
    pts.append(pts[0])

    if not broken:
        _strokes(surface, pts, weight, seed, color)
        return
    dashes, gap = 7, 2
    i = 0
    while i < len(pts) - 1:
        chunk = pts[i : i + dashes]
        if len(chunk) > 1:
            _strokes(surface, chunk, weight, seed_of(seed, i), color)
        i += dashes + gap


def dashed_line(surface, a, b, weight="normal", seed=0, color=T.INK, dash=9.0,
                gap=6.0, reveal=1.0):
    """How an edge that is hard this season is drawn."""
    pts = wobble_polyline(a, b, seed)
    arr = np.asarray(pts)
    seg = np.hypot(*np.diff(arr, axis=0).T)
    walked = np.concatenate([[0.0], np.cumsum(seg)])
    total = walked[-1] * max(0.0, min(1.0, reveal))
    pos = 0.0
    i = 0
    while pos < total:
        end = min(pos + dash, total)
        chunk = [tuple(np.interp([pos, end], walked, arr[:, k]) ) for k in (0, 1)]
        _strokes(surface, list(zip(chunk[0], chunk[1])), weight, seed_of(seed, "d", i), color)
        pos = end + gap
        i += 1
