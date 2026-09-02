"""The pressure model — the engine under everything hostile in this game.

Nobody here is evil. A road that is watched is watched by a settlement that
cannot feed itself, and the game says so by name. Every hostile thing that can
happen is a function of the numbers in this file, and every one of those
numbers is something the player could have seen and could have relieved.

Two rules govern the whole module:

* **Monotonic in every input.** More unmet need, more isolation, more deaths,
  more neighbours gone: never less desperate. More delivered, more post: never
  more desperate. A model that is not monotonic cannot be reasoned about by a
  player, and this one is meant to be reasoned about.
* **No danger without a source.** An edge's danger is a settlement's
  desperation seen from that edge, and the edge remembers which settlement.
  Terrain and season only scale what desperation has already caused. If every
  settlement on the map is calm, every road on the map is safe.
"""

import math

from .. import tuning as T
from .settlement import GOODS, NEED_PER_HEAD

# how far a settlement's desperation reaches down a road, in world units
WATCH_RADIUS = T.DESPERATION_WATCH_RADIUS


def hunger(settlement) -> float:
    """What share of a year's need has gone unmet since the last winter."""
    want = sum(settlement.population * NEED_PER_HEAD[g] * weight
               for g, weight in T.DESPERATION_HUNGER_GOODS.items())
    if want <= 0:
        return 0.0
    missing = sum(settlement.shortfall.get(g, 0.0) * weight
                  for g, weight in T.DESPERATION_HUNGER_GOODS.items())
    return min(1.0, missing / want)


def isolation(settlement) -> float:
    """Seasons since anything arrived, as a share of the patience there is."""
    return min(1.0, settlement.seasons_since_delivery / T.DESPERATION_ISOLATION)


def grief(settlement, year) -> float:
    """Deaths over the last two winters, against the people left."""
    recent = sum(count for when, count in settlement.deaths
                 if when >= year - 1)
    if settlement.population + recent <= 0:
        return 0.0
    return min(1.0, recent / (settlement.population + recent))


def bereavement(world, settlement) -> float:
    """Neighbours that have been given up. A settlement is not only fed by the
    network; it is held up by it."""
    neighbours = [world.other_end(e, settlement.id)
                  for e in world.edges_of(settlement.id)]
    if not neighbours:
        return 0.0
    lost = sum(1 for sid in set(neighbours) if not world.settlements[sid].alive)
    return min(1.0, lost / len(set(neighbours)))


def relief(settlement) -> float:
    """What the post has brought since the last winter, against the year's need.

    Post counts for more than its weight, which is the whole argument of §3.10:
    it is the cheapest thing to carry and the only thing that says the network
    has not forgotten this place.
    """
    want = sum(settlement.population * NEED_PER_HEAD[g] * weight
               for g, weight in T.DESPERATION_HUNGER_GOODS.items())
    if want <= 0:
        return 0.0
    brought = sum(settlement.received.get(g, 0.0) * weight
                  for g, weight in T.DESPERATION_HUNGER_GOODS.items())
    share = min(1.0, brought / want)
    letters = min(1.0, settlement.received.get("POST", 0.0)
                  / max(settlement.population * NEED_PER_HEAD["POST"], 1e-6))
    return min(1.0, share + letters * T.DESPERATION_POST_RELIEF)


def target(world, settlement, year) -> float:
    """Where this settlement's desperation is heading, 0..100."""
    if not settlement.alive:
        return 0.0
    relieved = T.DESPERATION_WEIGHTS["relief"] * relief(settlement)
    pressure = (T.DESPERATION_WEIGHTS["hunger"] * hunger(settlement)
                + T.DESPERATION_WEIGHTS["isolation"] * isolation(settlement)
                + T.DESPERATION_WEIGHTS["grief"] * grief(settlement, year)
                + T.DESPERATION_WEIGHTS["bereavement"] * bereavement(world, settlement)
                - relieved)
    return float(min(100.0, max(0.0, pressure * 100.0)))


def settle(world, year):
    """Move every settlement toward where its pressures point.

    Eased rather than set, because a settlement that has gone hungry for two
    years does not stop being desperate the week a load arrives — and because
    the player needs to see the thing move in a direction, not flicker.
    """
    for settlement in world.settlements:
        if not settlement.alive:
            settlement.desperation = 0.0
            continue
        want = target(world, settlement, year)
        if settlement.doomed(2) and want < settlement.desperation:
            continue
            # A settlement the arithmetic has already ended does not become
            # less desperate. Not because the people are ungrateful: because
            # nothing that arrives changes what is coming, and because the
            # moment it did, shipping to the dying would be a way of making the
            # roads safer — and kindness would have become a strategy. §3.9.
        ease = T.DESPERATION_RISE if want > settlement.desperation else T.DESPERATION_FALL
        settlement.desperation += (want - settlement.desperation) * ease
        settlement.desperation = float(min(100.0, max(0.0, settlement.desperation)))


# --- what that does to the roads ---------------------------------------------


def _distance_to_leg(point, a, b) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(point[0] - ax, point[1] - ay)
    t = max(0.0, min(1.0, ((point[0] - ax) * dx + (point[1] - ay) * dy)
                     / (dx * dx + dy * dy)))
    return math.hypot(point[0] - (ax + dx * t), point[1] - (ay + dy * t))


def watchers(world, edge):
    """Every settlement close enough to this leg to be watching it, with how
    much of its desperation reaches that far."""
    a = world.settlements[edge.a].pos
    b = world.settlements[edge.b].pos
    out = []
    for settlement in world.settlements:
        if not settlement.alive:
            continue
        if settlement.id in (edge.a, edge.b):
            reach = 1.0
        else:
            distance = _distance_to_leg(settlement.pos, a, b)
            if distance > WATCH_RADIUS:
                continue
            reach = 1.0 - distance / WATCH_RADIUS
        out.append((settlement, reach))
    return out


def terrain_factor(edge, season) -> float:
    """Terrain and season only scale what desperation has already caused."""
    if edge.tunnel_built:
        return 0.0
    return (T.DANGER_TERRAIN.get(edge.effective_terrain, 1.0)
            * T.DANGER_SEASON.get(season, 1.0))


def edge_danger(world, edge, season):
    """This leg's danger, 0..1, and the settlement it comes from.

    A leg is dangerous because somebody near it has nothing. Take that away and
    the leg is safe, whatever the terrain and whatever the season.
    """
    factor = terrain_factor(edge, season)
    if factor <= 0:
        return 0.0, -1
    worst, source = 0.0, -1
    for settlement, reach in watchers(world, edge):
        share = settlement.desperation / 100.0
        if share < T.DANGER_THRESHOLD:
            continue          # a settlement that is coping watches nobody
        value = (share - T.DANGER_THRESHOLD) / (1.0 - T.DANGER_THRESHOLD) * reach
        if value > worst:
            worst, source = value, settlement.id
    return min(1.0, worst * factor), source


def apply(world, season, year):
    """Settle the pressures, then read the roads off them."""
    settle(world, year)
    for edge in world.edges:
        edge.danger, edge.danger_source = edge_danger(world, edge, season)


def band(value, scale=100.0) -> str:
    """Plain words for the panel. Numbers live in the debug overlay."""
    share = value / scale
    if share < T.BAND_CALM:
        return "calm"
    if share < T.BAND_STRAINED:
        return "strained"
    return "desperate"


def road_band(danger) -> str:
    if danger < T.BAND_ROAD_SAFE:
        return "safe"
    if danger < T.BAND_ROAD_HARD:
        return "watched"
    return "dangerous"


def refuses_to_deal(settlement) -> bool:
    """At the extreme, a settlement keeps what it has. It is not hostile; it
    simply has nothing to give and no reason to trust that more is coming."""
    return settlement.desperation >= T.DESPERATION_REFUSAL
