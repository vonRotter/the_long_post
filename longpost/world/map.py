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
from ..render.ink import rng, seed_of
from . import season as season_mod
from . import terrain as terrain_mod
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
    danger: float = 0.0           # what desperation near this leg makes of it
    danger_source: int = -1       # and whose desperation that is
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
    terrain: object       # the elevation field everything else is read from
    coast_paths: list     # the shore, as loops
    coast_offsets: list   # lines behind the shore, nearest first
    depth_lines: list     # seaward contours, the depths a chart carries
    mountains: list       # contours of the high ground
    soundings: list       # (x, y, number) — texture only, they mean nothing

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


def _crosses_water(a, b, terrain, samples=18):
    for t in np.linspace(0.08, 0.92, samples):
        p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        if not terrain.is_land(p):
            return True
    return False


def _crosses_high_ground(a, b, terrain, samples=14):
    for t in np.linspace(0.15, 0.85, samples):
        p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        if terrain.is_mountain(p):
            return True
    return False


def _segments_cross(p1, p2, p3, p4):
    def side(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    d1, d2 = side(p3, p4, p1), side(p3, p4, p2)
    d3, d4 = side(p1, p2, p3), side(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _place_settlements(gen, ground, count):
    """Sites on the land, most of them within reach of the water.

    A post service in this country is a coastal service: settlements sit on
    the islands and along the sounds, and only some way up the valleys behind
    them. Nothing is built on the tops.
    """
    pts = []
    tries = 0
    while len(pts) < count and tries < T.SETTLEMENT_PLACEMENT_TRIES:
        tries += 1
        p = (gen.uniform(60, T.WORLD_W - 60), gen.uniform(60, T.WORLD_H - 60))
        if not ground.is_land(p) or ground.is_mountain(p):
            continue
        if ground.distance_to_water(p) > T.SETTLEMENT_COAST_BAND:
            if gen.random() > T.SETTLEMENT_INLAND_CHANCE:
                continue
        if any(np.hypot(p[0] - q[0], p[1] - q[1]) < T.SETTLEMENT_MIN_SPACING
               for q in pts):
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
    ground = terrain_mod.Terrain(seed)

    # everything the chart says about land and water is one field read at
    # several levels, so none of it can disagree with itself
    # kept as arrays: the chart transforms every one of them on every re-ink
    def rings(level, minimum_points=10, least_area=0.0):
        return [np.asarray(loop) for loop in ground.contours(level, minimum_points)
                if terrain_mod.ring_area(loop) >= least_area]

    coast_paths = rings(T.SEA_LEVEL, 6, T.MIN_ISLAND_AREA)
    coast_offsets = [rings(T.SEA_LEVEL + step) for step in T.SHORE_LEVELS]
    depth_lines = [rings(T.SEA_LEVEL - step, 12) for step in T.DEPTH_LEVELS]
    mountains = rings(T.MOUNTAIN_LEVEL)

    points = _place_settlements(gen, ground, T.SETTLEMENTS_MAX)
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
        if _crosses_water(pa, pb, ground):
            terrain = "COAST"
        elif _crosses_high_ground(pa, pb, ground):
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
    for _ in range(420):
        p = (gen.uniform(0, T.WORLD_W), gen.uniform(0, T.WORLD_H))
        if ground.is_land(p):
            continue
        depth = int(round((T.SEA_LEVEL - ground.height(p)) * 260)) + int(gen.integers(2, 9))
        soundings.append((p[0], p[1], max(2, depth)))

    return WorldMap(seed=seed, settlements=settlements, edges=edges,
                    terrain=ground, coast_paths=coast_paths,
                    coast_offsets=coast_offsets, depth_lines=depth_lines,
                    mountains=mountains, soundings=soundings)


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
