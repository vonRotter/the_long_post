"""The ground under everything: one elevation field, read at several levels.

A real coast of this kind — skerries, then islands, then fjords cutting far
inland behind them — is not a line that wanders. It is what happens when water
meets rough ground. So the world is a noise field, the shore is one contour of
it, the depths and the lines behind the shore are contours a little either
side, and the mountains are a contour further up. Everything the chart draws
about land and water comes out of this one array, which is also why none of it
can disagree with itself.

The contour extraction is marching squares, ported from map maker's.
"""

import numpy as np

from .. import tuning as T

# case table. corner bits: TL 1, TR 2, BR 4, BL 8. edges: 0 top, 1 right,
# 2 bottom, 3 left. entries are [from, to] pairs.
CASES = [
    [], [3, 0], [0, 1], [3, 1], [1, 2], [], [0, 2], [3, 2],
    [2, 3], [2, 0], [], [2, 1], [1, 3], [1, 0], [0, 3], [],
]


def _upsample(field, shape):
    """Bilinear upscale of a low-frequency grid."""
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
    ty = ty * ty * (3 - 2 * ty)          # smoothstep, or the grid shows through
    tx = tx * tx * (3 - 2 * tx)
    top = a * (1 - tx) + b * tx
    bottom = c * (1 - tx) + d * tx
    return (top * (1 - ty) + bottom * ty).astype(np.float32)


def _fbm(gen, shape, octaves=6, base=(3, 5), persistence=0.55, stretch=1.0):
    """Fractal noise. `stretch` elongates features east to west, which is what
    turns a rough coast into one with fjords behind it."""
    rows, cols = shape
    out = np.zeros(shape, dtype=np.float32)
    amplitude = 1.0
    total = 0.0
    # the stretch sets the shape of the largest features and every octave
    # doubles from there; applying it per octave would band the field
    ry, rx = base[0], base[1] / stretch
    for _ in range(octaves):
        grid = gen.random((max(2, int(ry)), max(2, int(rx)))).astype(np.float32)
        out += _upsample(grid, shape) * amplitude
        total += amplitude
        amplitude *= persistence
        ry *= 2.0
        rx *= 2.0
    out /= total
    # stretched to the full range: summed octaves cluster round the middle, and
    # a field that never leaves the middle makes one smooth island and no coast
    low, high = float(out.min()), float(out.max())
    return (out - low) / max(high - low, 1e-6)


def _sample(field, xs, ys):
    """Bilinear sample of a grid at arbitrary cell coordinates."""
    rows, cols = field.shape
    xs = np.clip(xs, 0, cols - 1.001)
    ys = np.clip(ys, 0, rows - 1.001)
    x0 = xs.astype(int)
    y0 = ys.astype(int)
    tx = xs - x0
    ty = ys - y0
    a = field[y0, x0]
    b = field[y0, x0 + 1]
    c = field[y0 + 1, x0]
    d = field[y0 + 1, x0 + 1]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


class Terrain:
    """An elevation field over the whole world, and the contours of it."""

    def __init__(self, seed, cell=None):
        self.cell = float(cell or T.TERRAIN_CELL)
        self.cols = int(T.WORLD_W / self.cell) + 1
        self.rows = int(T.WORLD_H / self.cell) + 1
        gen = np.random.default_rng(seed)

        shape = (self.rows, self.cols)
        rough = _fbm(gen, shape, octaves=8, base=T.COAST_BASE, persistence=T.COAST_ROUGHNESS,
                     stretch=T.COAST_STRETCH)

        # the ground is warped before it is read, which is what stops the
        # coastline reading as noise laid over a gradient
        warp_x = _fbm(gen, shape, octaves=4, base=(3, 3), persistence=0.5)
        warp_y = _fbm(gen, shape, octaves=4, base=(3, 3), persistence=0.5)
        ys, xs = np.mgrid[0:self.rows, 0:self.cols].astype(np.float32)
        amount = T.COAST_WARP / self.cell
        rough = _sample(rough, xs + (warp_x - 0.5) * amount,
                        ys + (warp_y - 0.5) * amount)

        # Land rises to the east, but not evenly: deep water in the far west,
        # then a wide shelf sitting just under the waterline — the belt the
        # skerries and the outer islands stand on — then the ground proper.
        across = xs / max(self.cols - 1, 1)
        stops = np.array([p[0] for p in T.COAST_PROFILE])
        heights = np.array([p[1] for p in T.COAST_PROFILE])
        gradient = np.interp(across, stops, heights).astype(np.float32)

        elevation = rough * (1.0 - T.COAST_GRADIENT) + gradient * T.COAST_GRADIENT
        # squeezed toward the waterline: more ground sits near sea level, which
        # is what puts skerries and sounds along the shore instead of one edge
        offset = elevation - T.SEA_LEVEL
        elevation = T.SEA_LEVEL + np.sign(offset) * np.abs(offset) ** T.COAST_SHELF

        # the skerries: fine noise applied only to the shallows, so water that
        # is barely water breaks up into the scatter of rock a real coast has
        shallow = np.exp(-((elevation - T.SEA_LEVEL + T.SKERRY_DEPTH)
                           / T.SKERRY_BAND) ** 2)
        fine = _fbm(gen, shape, octaves=3, base=(34, 26), persistence=0.5)
        elevation = elevation + shallow * (fine - 0.46) * T.SKERRY_AMOUNT
        # a rim of open water all round, so nothing runs off the sheet
        margin = np.minimum(
            np.minimum(xs, self.cols - 1 - xs) / max(self.cols * 0.04, 1),
            np.minimum(ys, self.rows - 1 - ys) / max(self.rows * 0.04, 1))
        elevation = np.where(across < 0.5, elevation * np.clip(margin, 0, 1),
                             elevation)

        self.elevation = elevation.astype(np.float32)
        self.mask = self.elevation > T.SEA_LEVEL

    # --- queries ---
    def is_land(self, point) -> bool:
        col = int(point[0] / self.cell)
        row = int(point[1] / self.cell)
        if not (0 <= col < self.cols and 0 <= row < self.rows):
            return False
        return bool(self.mask[row, col])

    def height(self, point) -> float:
        col = int(np.clip(point[0] / self.cell, 0, self.cols - 1))
        row = int(np.clip(point[1] / self.cell, 0, self.rows - 1))
        return float(self.elevation[row, col])

    def is_mountain(self, point) -> bool:
        return self.height(point) >= T.MOUNTAIN_LEVEL

    def distance_to_water(self, point, reach=6) -> float:
        """Roughly how far this site is from the sea, in world units."""
        col = int(np.clip(point[0] / self.cell, 0, self.cols - 1))
        row = int(np.clip(point[1] / self.cell, 0, self.rows - 1))
        for ring in range(1, reach + 1):
            lo_r, hi_r = max(0, row - ring), min(self.rows, row + ring + 1)
            lo_c, hi_c = max(0, col - ring), min(self.cols, col + ring + 1)
            if not self.mask[lo_r:hi_r, lo_c:hi_c].all():
                return ring * self.cell
        return (reach + 1) * self.cell

    def land_fraction(self) -> float:
        return float(self.mask.mean())

    # --- contours ---
    def contours(self, level, minimum_points=6, smooth=2):
        """Every closed line where the field crosses `level`, in world units."""
        field = self.elevation
        tl = field[:-1, :-1]
        tr = field[:-1, 1:]
        br = field[1:, 1:]
        bl = field[1:, :-1]

        index = ((tl > level).astype(np.uint8)
                 | ((tr > level).astype(np.uint8) << 1)
                 | ((br > level).astype(np.uint8) << 2)
                 | ((bl > level).astype(np.uint8) << 3))
        rows, cols = np.nonzero((index > 0) & (index < 15))
        if len(rows) == 0:
            return []

        cell = self.cell
        wide = self.cols
        horizontal = self.rows * wide
        points = {}
        following = {}

        def crossing(edge_id, ca, ra, cb, rb, va, vb):
            if edge_id in points:
                return
            span = vb - va
            t = 0.5 if abs(span) < 1e-9 else (level - va) / span
            t = min(max(t, 0.0), 1.0)
            points[edge_id] = (((ca + (cb - ca) * t) * cell),
                               ((ra + (rb - ra) * t) * cell))

        for r, c in zip(rows.tolist(), cols.tolist()):
            a = float(field[r, c])
            b = float(field[r, c + 1])
            d = float(field[r + 1, c + 1])
            e = float(field[r + 1, c])
            case = index[r, c]
            pairs = CASES[case]
            if case in (5, 10):
                # a saddle: the mean of the corners decides which way the two
                # curves bend, or the coast pinches at every diagonal neck
                middle = (a + b + d + e) / 4.0
                if case == 5:
                    pairs = [1, 0, 3, 2] if middle > level else [3, 0, 1, 2]
                else:
                    pairs = [0, 3, 2, 1] if middle > level else [0, 1, 2, 3]
            if not pairs:
                continue

            ids = (r * wide + c,                      # top
                   horizontal + r * wide + c + 1,     # right
                   (r + 1) * wide + c,                # bottom
                   horizontal + r * wide + c)         # left
            for edge in set(pairs):
                if edge == 0:
                    crossing(ids[0], c, r, c + 1, r, a, b)
                elif edge == 1:
                    crossing(ids[1], c + 1, r, c + 1, r + 1, b, d)
                elif edge == 2:
                    crossing(ids[2], c, r + 1, c + 1, r + 1, e, d)
                else:
                    crossing(ids[3], c, r, c, r + 1, a, e)
            for i in range(0, len(pairs), 2):
                following[ids[pairs[i]]] = ids[pairs[i + 1]]

        loops = []
        seen = set()
        for start in following:
            if start in seen:
                continue
            loop = []
            edge = start
            while edge not in seen:
                seen.add(edge)
                if edge in points:
                    loop.append(points[edge])
                edge = following.get(edge)
                if edge is None:
                    break
            if len(loop) >= minimum_points:
                loops.append(chaikin(loop, smooth))
        return loops


def chaikin(points, iterations=2):
    """Corner cutting. Two passes turn marching squares into a drawn line.

    Returns the array itself: a contour is transformed on every re-ink, and
    handing back a list of tuples means converting it back a moment later.
    """
    current = np.asarray(points, dtype=np.float64)
    for _ in range(iterations):
        if len(current) < 3:
            break
        following = np.roll(current, -1, axis=0)
        out = np.empty((len(current) * 2, 2))
        out[0::2] = current * 0.75 + following * 0.25
        out[1::2] = current * 0.25 + following * 0.75
        current = out
    return current


def ring_area(points) -> float:
    p = np.asarray(points)
    q = np.roll(p, -1, axis=0)
    return float(np.abs(np.sum(p[:, 0] * q[:, 1] - q[:, 0] * p[:, 1])) / 2.0)
