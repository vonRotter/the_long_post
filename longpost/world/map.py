"""Nodes, edges, and generation.

The spine of the game is a graph, and every complication attaches to a specific
edge in a specific season. Geometry exists only so the chart can be drawn and
so terrain can be decided; on the chart, screen length is roughly travel days.
"""

from dataclasses import dataclass, field

import numpy as np
import pygame

from .. import tuning as T
from ..data import names as name_data
from ..render.ink import point_in_polygon, points_in_polygon, rng, seed_of
from . import season as season_mod
from .settlement import Settlement

TERRAINS = ("COAST", "INLAND", "PASS", "ICE", "TUNNEL")


@dataclass
class Edge:
    id: int
    a: int                        # settlement id
    b: int                        # settlement id
    terrain: str
    days: float
    tunnel_site: bool = False     # a collapsed pre-collapse line, excavatable
    tunnel_built: bool = False
    ice_of: int = -1              # the open-water edge this ice road replaces
    danger: float = 0.0           # derived at M2 from terrain, season, desperation
    runs: int = 0                 # how heavily the post has used this leg
    losses: list = field(default_factory=list)   # (year, courier name)

    @property
    def effective_terrain(self) -> str:
        return "TUNNEL" if self.tunnel_built else self.terrain

    def key(self):
        return (min(self.a, self.b), max(self.a, self.b))

    def availability(self, season: str) -> str:
        return season_mod.availability(self.effective_terrain, season)

    def is_open(self, season: str) -> bool:
        return self.availability(season) == T.OPEN

    def is_usable(self, season: str) -> bool:
        return self.availability(season) != T.CLOSED


@dataclass
class WorldMap:
    seed: int
    settlements: list
    edges: list
    land: list            # polygons: the main mass and its islands
    ridge: list           # the mountain spine, as a polyline
    soundings: list       # (x, y, number) — texture only, they mean nothing
    coast_offsets: list   # inward lines behind the shore, nearest first
    depth_lines: list     # seaward contours, the depths a chart carries
    coast_paths: list     # (points, closed) — the shore as it is inked

    def settlement(self, sid: int) -> Settlement:
        return self.settlements[sid]

    def known_settlements(self):
        return [s for s in self.settlements if s.known]

    def edges_of(self, sid: int):
        return [e for e in self.edges if e.a == sid or e.b == sid]

    def known_edges(self):
        return [e for e in self.edges
                if self.settlements[e.a].known and self.settlements[e.b].known]

    def other_end(self, edge: Edge, sid: int) -> int:
        return edge.b if edge.a == sid else edge.a

    def usable_edges(self, season: str, known_only=True):
        source = self.known_edges() if known_only else self.edges
        return [e for e in source if e.is_usable(season)]

    def components(self, season=None, known_only=False):
        """Connected groups of living settlements, in a season or in any season."""
        live = [s.id for s in self.settlements
                if s.alive and (s.known or not known_only)]
        index = {sid: i for i, sid in enumerate(live)}
        parent = list(range(len(live)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for e in self.edges:
            if e.a not in index or e.b not in index:
                continue
            if season is not None and not e.is_usable(season):
                continue
            ra, rb = find(index[e.a]), find(index[e.b])
            if ra != rb:
                parent[ra] = rb

        groups = {}
        for sid in live:
            groups.setdefault(find(index[sid]), []).append(sid)
        return list(groups.values())


# --- generation -----------------------------------------------------------


def _blob(gen, centre, radius, lobes=9, roughness=0.30, points=44):
    """A coastline-shaped polygon: radial noise, no straight anything.

    Radial by construction, which is what lets `_offset_ring` shrink or grow it
    without the folding that offsetting an arbitrary polygon produces at every
    inlet.
    """
    t = np.linspace(0, 2 * np.pi, points, endpoint=False)
    r = np.ones(points)
    for harmonic in (1, 2, 3, 5, 8):
        phase = gen.uniform(0, 2 * np.pi)
        r += (roughness / harmonic) * np.sin(harmonic * lobes / 3.0 * t + phase)
    r = radius * (r / r.mean())
    return list(zip(centre[0] + np.cos(t) * r, centre[1] + np.sin(t) * r * 0.8))


def _coastline(gen):
    """The shore: a wandering north-south line with water cutting into it.

    Sea to the west, mainland to the east. Returned as an open polyline running
    off both ends of the world, so it can be inked as a shoreline rather than
    as the outline of a shape.
    """
    n = 150
    ys = np.linspace(-80.0, T.WORLD_H + 80.0, n)
    base = T.WORLD_W * T.COAST_X

    drift = np.zeros(n)
    for harmonic, amplitude in ((1, 1.0), (2, 0.4), (5, 0.16)):
        phase = gen.uniform(0, 2 * np.pi)
        drift += amplitude * np.sin(harmonic * np.pi * np.linspace(0, 2, n) + phase)
    xs = base + drift / 1.56 * T.COAST_WANDER

    # fjords, and the headlands between them
    for _ in range(int(gen.integers(*T.COAST_FJORDS))):
        centre = int(gen.integers(6, n - 6))
        width = int(gen.integers(2, 5))
        depth = float(gen.uniform(*T.FJORD_DEPTH))
        for i in range(max(0, centre - width), min(n, centre + width + 1)):
            fall = 1.0 - abs(i - centre) / (width + 1.0)
            xs[i] += depth * fall ** 0.45
    for _ in range(int(gen.integers(2, 5))):
        centre = int(gen.integers(6, n - 6))
        width = int(gen.integers(5, 12))
        reach = float(gen.uniform(90.0, 260.0))
        for i in range(max(0, centre - width), min(n, centre + width + 1)):
            fall = 1.0 - abs(i - centre) / (width + 1.0)
            xs[i] -= reach * fall ** 1.4

    xs = np.clip(xs, 220.0, T.WORLD_W - 320.0)
    return list(zip(xs.tolist(), ys.tolist()))


def _mainland(coast):
    """The shore closed off along the eastern edge, for the land test."""
    return list(coast) + [(T.WORLD_W + 200.0, T.WORLD_H + 200.0),
                          (T.WORLD_W + 200.0, -200.0)]


def _offset_coast(coast, distance, smoothing=5):
    """The shore moved `distance` seaward (negative: inland).

    The line is smoothed first: an offset taken off the raw shore folds inside
    every fjord, and a fold reads as a mistake on a chart rather than as depth.
    """
    pts = np.asarray(coast, dtype=float)
    kernel = np.ones(smoothing) / smoothing
    xs = np.convolve(np.pad(pts[:, 0], (smoothing, smoothing), mode="edge"),
                     kernel, mode="same")[smoothing:-smoothing]
    smooth = np.stack([xs, pts[:, 1]], axis=1)
    tangent = np.gradient(smooth, axis=0)
    length = np.hypot(tangent[:, 0], tangent[:, 1])
    length[length < 1e-9] = 1.0
    normal = np.stack([-tangent[:, 1] / length, tangent[:, 0] / length], axis=1)
    return [tuple(p) for p in smooth + normal * distance]


def _offset_ring(polygon, centre, distance):
    """The polygon moved `distance` inward (negative: seaward), radially."""
    ring = []
    for x, y in polygon:
        dx, dy = x - centre[0], y - centre[1]
        r = float(np.hypot(dx, dy))
        if r < 1e-6:
            continue
        k = max(0.05, (r - distance) / r)
        ring.append((centre[0] + dx * k, centre[1] + dy * k))
    return ring


def _open_water_runs(ring, field, minimum=4, closed=True):
    """The parts of a line that lie in open water, as polylines."""
    ring = list(ring)
    wet = [not field(p) for p in ring]
    if all(wet):
        return [ring + [ring[0]]] if closed else [ring]
    wrap = ring[:1] if closed else []
    wrap_wet = wet[:1] if closed else []
    runs, current = [], []
    for point, is_wet in zip(ring + wrap, wet + wrap_wet):
        if is_wet:
            current.append(point)
        elif current:
            if len(current) >= minimum:
                runs.append(current)
            current = []
    if len(current) >= minimum:
        runs.append(current)
    return runs


class LandField:
    """A coarse raster of where the land is.

    Generation asks the question tens of thousands of times — every candidate
    site, every sample along every edge — and an exact polygon test per query
    costs more than the whole rest of generation. A cell is 8 world units.
    """

    CELL = 8.0

    def __init__(self, land):
        self.cols = int(T.WORLD_W / self.CELL) + 2
        self.rows = int(T.WORLD_H / self.CELL) + 2
        # rasterised rather than tested point by point: a polygon fill is the
        # one place in this project where a filled shape is the right tool,
        # and nothing ever sees it
        surface = pygame.Surface((self.cols, self.rows))
        surface.fill((0, 0, 0))
        for poly in land:
            pygame.draw.polygon(surface, (255, 255, 255),
                                [(x / self.CELL, y / self.CELL) for x, y in poly])
        self.mask = pygame.surfarray.array2d(surface) != 0

    def __call__(self, point) -> bool:
        col = int(point[0] / self.CELL)
        row = int(point[1] / self.CELL)
        if not (0 <= col < self.cols and 0 <= row < self.rows):
            return False
        return bool(self.mask[col, row])

    def any_dry(self, points) -> bool:
        return any(self(p) for p in points)


def _on_land(point, land):
    return any(point_in_polygon(point, poly) for poly in land)


def _crosses_water(a, b, field, samples=18):
    for t in np.linspace(0.10, 0.90, samples):
        p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        if not field(p):
            return True
    return False


def _crosses_ridge(a, b, ridge):
    for (r0, r1) in zip(ridge, ridge[1:]):
        if _segments_cross(a, b, r0, r1):
            return True
    return False


def _segments_cross(p1, p2, p3, p4):
    def side(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    d1, d2 = side(p3, p4, p1), side(p3, p4, p2)
    d3, d4 = side(p1, p2, p3), side(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _place_settlements(gen, field, coast, count):
    """Sites on the land, most of them within reach of the water.

    A post service in this country is a coastal service: settlements sit on the
    shore, on the islands, and only some way up the valleys behind them.
    """
    shore_y = [p[1] for p in coast]
    shore_x = [p[0] for p in coast]
    pts = []
    tries = 0
    while len(pts) < count and tries < T.SETTLEMENT_PLACEMENT_TRIES:
        tries += 1
        p = (gen.uniform(60, T.WORLD_W - 60), gen.uniform(60, T.WORLD_H - 60))
        if not field(p):
            continue
        inland = p[0] - float(np.interp(p[1], shore_y, shore_x))
        if inland > T.SETTLEMENT_COAST_BAND and gen.random() > T.SETTLEMENT_INLAND_CHANCE:
            continue
        if any(np.hypot(p[0] - q[0], p[1] - q[1]) < T.SETTLEMENT_MIN_SPACING for q in pts):
            continue
        pts.append(p)
    return pts


def _candidate_edges(points):
    """k-nearest neighbours, plus a minimum spanning tree so nothing is orphaned."""
    arr = np.asarray(points)
    n = len(arr)
    d = np.hypot(arr[:, None, 0] - arr[None, :, 0], arr[:, None, 1] - arr[None, :, 1])
    np.fill_diagonal(d, np.inf)

    pairs = set()
    for i in range(n):
        for j in np.argsort(d[i])[: T.EDGE_NEIGHBOURS]:
            if d[i, j] <= T.EDGE_MAX_LENGTH:
                pairs.add((min(i, int(j)), max(i, int(j))))

    # Prim's, so the graph is connected in autumn whatever the neighbours gave us
    reached = {0}
    while len(reached) < n:
        best = None
        for i in reached:
            for j in range(n):
                if j in reached:
                    continue
                if best is None or d[i, j] < d[best[0], best[1]]:
                    best = (i, j)
        pairs.add((min(best), max(best)))
        reached.add(best[1])
    return sorted(pairs), d


def generate(seed: int) -> WorldMap:
    gen = rng("world", seed)

    # the land is a coast: open sea to the west, mainland to the east, and a
    # scatter of smaller islands out in the water
    coast = _coastline(gen)
    land = [_mainland(coast)]
    coast_paths = [(list(coast), False)]      # (points, closed)
    island_centres = []

    wanted = int(gen.integers(*T.COAST_ISLANDS))
    for _ in range(wanted * 20):
        if len(island_centres) >= wanted:
            break
        radius = float(gen.uniform(*T.ISLAND_RADIUS))
        centre = (gen.uniform(150.0, T.WORLD_W * T.COAST_X - 120.0),
                  gen.uniform(T.WORLD_H * 0.06, T.WORLD_H * 0.94))
        island = _blob(gen, centre, radius, lobes=7, roughness=0.24)
        if any(point_in_polygon(p, land[0]) for p in island):
            continue      # an island that touches anything is not an island
        if any(np.hypot(centre[0] - c[0], centre[1] - c[1]) < radius + r + 90
               for c, r in island_centres):
            continue
        land.append(island)
        coast_paths.append((island, True))
        island_centres.append((centre, radius))

    # the mountain spine, inland and roughly parallel to the shore
    ridge = []
    for i in range(T.RIDGE_KNOTS):
        t = i / (T.RIDGE_KNOTS - 1)
        y = T.WORLD_H * (0.02 + 0.96 * t)
        shore = float(np.interp(y, [p[1] for p in coast], [p[0] for p in coast]))
        ridge.append((min(T.WORLD_W - 120.0,
                          shore + T.RIDGE_INLAND + gen.uniform(-90.0, 130.0)), y))

    field = LandField(land)
    points = _place_settlements(gen, field, coast, T.SETTLEMENTS_MAX)
    labels = name_data.settlement_names(gen, len(points))

    settlements = []
    for i, (p, name) in enumerate(zip(points, labels)):
        pop = int(gen.integers(*T.POP_RANGE))
        goods = list(("GRAIN", "FUEL", "MEDICINE", "TOOLS"))
        gen.shuffle(goods)
        surplus = tuple(goods[: 1 + int(gen.integers(0, 2))])
        settlements.append(Settlement(
            id=i, name=name, pos=p, population=pop, surplus=surplus,
            standing=float(T.STANDING_START),
        ))

    pairs, dist = _candidate_edges(points)
    edges = []
    for a, b in pairs:
        length = float(dist[a, b])
        pa, pb = points[a], points[b]
        if _crosses_water(pa, pb, field):
            terrain = "COAST"
        elif _crosses_ridge(pa, pb, ridge):
            terrain = "PASS"
        else:
            terrain = "INLAND"
        edges.append(Edge(
            id=len(edges), a=a, b=b, terrain=terrain,
            days=round(length * T.TRAVEL_DAYS_PER_UNIT, 1),
            tunnel_site=bool(gen.random() < T.TUNNEL_SITE_CHANCE and terrain != "COAST"),
        ))

    # the inversion: water that freezes hard enough to carry a sled
    def freeze(e):
        edges.append(Edge(
            id=len(edges), a=e.a, b=e.b, terrain="ICE", ice_of=e.id,
            days=round(float(dist[e.a, e.b]) * T.TRAVEL_DAYS_PER_UNIT * 0.8, 1),
        ))

    eligible = [e for e in list(edges)
                if e.terrain == "COAST" and dist[e.a, e.b] <= T.ICE_ROAD_MAX_LENGTH]
    for e in eligible:
        if gen.random() <= 0.65:
            freeze(e)
    if eligible and not any(e.terrain == "ICE" for e in edges):
        freeze(min(eligible, key=lambda e: dist[e.a, e.b]))

    # what the post already has on its chart: a connected handful, not a scatter
    for sid in _starting_cluster(points, edges, T.SETTLEMENTS_START):
        settlements[sid].known = True

    soundings = []
    for i in range(320):
        p = (gen.uniform(0, T.WORLD_W), gen.uniform(0, T.WORLD_H))
        if field(p):
            continue
        soundings.append((p[0], p[1], int(gen.integers(3, 96))))

    # a chart shows what the water is doing: inward lines behind the shore and
    # depth contours out at sea, both read off the same shapes
    coast_offsets = [[]]
    depth_lines = [[], []]
    coast_offsets[0].append(_offset_coast(coast, -34.0, smoothing=9))
    # smoothed a little more the further out they sit, but never so much that
    # they straighten: a straight line is the one mark this chart does not make
    for i, seaward in enumerate((70.0, 165.0)):
        depth_lines[i].extend(
            _open_water_runs(_offset_coast(coast, seaward, smoothing=7 + i * 4),
                             field, closed=False))
    for island, (centre, radius) in zip(land[1:], island_centres):
        coast_offsets[0].append(_offset_ring(island, centre, radius * 0.16))
        depth_lines[0].extend(
            _open_water_runs(_offset_ring(island, centre, -radius * 0.45), field))

    return WorldMap(seed=seed, settlements=settlements, edges=edges,
                    land=land, ridge=ridge, soundings=soundings,
                    coast_offsets=coast_offsets, depth_lines=depth_lines,
                    coast_paths=coast_paths)



def _starting_cluster(points, edges, count):
    """The settlements the post begins with: connected, near the middle of the map.

    The start prefers a node on water that freezes, so the seasonal inversion is
    on the player's chart from the first winter rather than found years later.
    """
    arr = np.asarray(points)
    centre = arr.mean(axis=0)
    distance = np.hypot(*(arr - centre).T)
    on_ice = {e.a for e in edges if e.terrain == "ICE"} | {e.b for e in edges
                                                           if e.terrain == "ICE"}
    if on_ice:
        start = min(on_ice, key=lambda sid: float(distance[sid]))
    else:
        start = int(np.argmin(distance))

    adjacency = {}
    for e in edges:
        adjacency.setdefault(e.a, set()).add(e.b)
        adjacency.setdefault(e.b, set()).add(e.a)

    ice_pairs = {(min(e.a, e.b), max(e.a, e.b)) for e in edges if e.terrain == "ICE"}

    def completes_ice(sid, known):
        return any((min(sid, k), max(sid, k)) in ice_pairs for k in known)

    known = [start]
    frontier = sorted(adjacency.get(start, ()))
    while len(known) < count and frontier:
        have_ice = any(completes_ice(k, [j for j in known if j != k]) for k in known)
        # nearest unknown neighbour, but an ice crossing first while there is none
        frontier.sort(key=lambda sid: (0 if not have_ice and completes_ice(sid, known)
                                       else 1, float(distance[sid])))
        sid = frontier.pop(0)
        if sid in known:
            continue
        known.append(sid)
        frontier.extend(n for n in sorted(adjacency.get(sid, ())) if n not in known)
    return known


def edge_seed(edge: Edge) -> int:
    """A line must wobble identically every frame: seeds come from identity."""
    return seed_of("edge", edge.id, edge.a, edge.b, edge.terrain)
