"""Orders: what runs where, carrying what.

An order is one carrier, one leg, one load, for one season. Standing orders and
delegation arrive at M5; the shape here is meant to carry them.
"""

from dataclasses import dataclass, field

from ..world.settlement import GOODS, NEED_PER_HEAD


@dataclass
class Order:
    edge_id: int
    carrier_id: int
    origin: int                   # settlement the run leaves from
    cargo: dict = field(default_factory=dict)
    courier_id: int = -1          # who runs it
    digging: bool = False         # or who is not running it, and digging
    standing: bool = False        # raised by a route the post keeps

    def total(self) -> int:
        return int(round(sum(self.cargo.values())))

    def loaded(self) -> dict:
        return {g: v for g, v in self.cargo.items() if v > 0}


@dataclass
class StandingOrder:
    """A route the post keeps, until the post stops keeping it.

    Not an unlock: it is available from the first turn and simply becomes
    necessary, because past eight or nine active routes there is no longer time
    to look at every one of them. What it costs is attention — a standing order
    reports by exception, so the seasons it goes well are seasons the player
    does not read about.
    """
    edge_id: int
    carrier_id: int
    courier_id: int = -1          # -1: whoever is fit and standing there
    started_year: int = 1
    runs: int = 0
    idle: int = 0                 # seasons it could not send anything

    def label(self, world, fleet, couriers) -> str:
        edge = world.edges[self.edge_id]
        a, b = world.settlements[edge.a], world.settlements[edge.b]
        who = ("the pool" if self.courier_id < 0
               else couriers[self.courier_id].name)
        return f"{a.name.lower()} — {b.name.lower()}, {fleet[self.carrier_id].name}, {who}"


class Standing:
    """The routes the post keeps. One per carrier, like an order."""

    def __init__(self):
        self.routes = {}          # carrier id -> StandingOrder

    def __iter__(self):
        return iter(sorted(self.routes.values(), key=lambda r: r.carrier_id))

    def __len__(self):
        return len(self.routes)

    def for_carrier(self, carrier_id):
        return self.routes.get(carrier_id)

    def on_edge(self, edge_id):
        return [r for r in self if r.edge_id == edge_id]

    def set(self, route: StandingOrder):
        self.routes[route.carrier_id] = route

    def clear_carrier(self, carrier_id):
        self.routes.pop(carrier_id, None)


class Plan:
    """The orders standing for this season. One carrier, one order."""

    def __init__(self):
        self.orders = {}          # carrier id -> Order

    def __iter__(self):
        return iter(sorted(self.orders.values(), key=lambda o: o.carrier_id))

    def __len__(self):
        return len(self.orders)

    def for_carrier(self, carrier_id):
        return self.orders.get(carrier_id)

    def on_edge(self, edge_id):
        return [o for o in self if o.edge_id == edge_id]

    def set(self, order: Order):
        self.orders[order.carrier_id] = order

    def clear_carrier(self, carrier_id):
        self.orders.pop(carrier_id, None)

    def clear(self):
        self.orders.clear()


def standing_orders(world, fleet, couriers, standing, season, plan):
    """This season's orders from the routes the post keeps.

    A carrier the player has already given an order to this season is left
    alone: a standing order is what happens when nobody is watching, not
    something that overrules the person watching.
    """
    made, notices = [], []
    for route in standing:
        if plan.for_carrier(route.carrier_id) is not None:
            continue
        edge = world.edges[route.edge_id]
        carrier = fleet[route.carrier_id]
        legs = f"{world.settlements[edge.a].name.lower()} — " \
               f"{world.settlements[edge.b].name.lower()} leg"

        if not (edge.is_usable(season) and carrier.can_run(season, edge)
                and carrier.reaches(edge)):
            continue                      # the season, not a fault: say nothing
        if carrier.at not in (edge.a, edge.b):
            notices.append(_idle(route, f"{carrier.name} is not on the {legs}."))
            continue
        runner = _pick_runner(couriers, route, edge)
        if runner is None:
            notices.append(_idle(route, f"the {legs} had nobody to send."))
            continue
        origin = world.settlements[carrier.at]
        destination = world.settlements[world.other_end(edge, carrier.at)]
        cargo = fill_by_need(world, origin, destination, carrier.type.capacity)
        if not cargo:
            notices.append(_idle(route,
                                 f"the {legs} had nothing to carry from"
                                 f" {origin.name}."))
            continue
        order = Order(edge_id=edge.id, carrier_id=carrier.id, origin=origin.id,
                      cargo=cargo, courier_id=runner.id)
        order.standing = True
        plan.set(order)
        route.runs += 1
        route.idle = 0
        made.append(order)
    return made, [text for text in notices if text]


def _idle(route, text):
    """A kept route that sent nothing says so — but not every season.

    Exception reporting is worth nothing if the exceptions repeat until they
    are wallpaper, so a route reports the first season it stalls and then every
    fourth after that.
    """
    route.idle += 1
    if route.idle == 1 or route.idle % 4 == 0:
        seasons = "" if route.idle == 1 else f" It has been {route.idle} seasons."
        return text + seasons
    return ""


def _pick_runner(couriers, route, edge):
    if route.courier_id >= 0:
        runner = couriers[route.courier_id]
        return runner if (runner.alive and runner.fit_for(edge)
                          and runner.at in (edge.a, edge.b)) else None
    able = couriers_for(couriers, edge, None)
    if not able:
        return None
    # the freshest hand who knows the leg, which is what a clerk would do
    return max(able, key=lambda c: (c.condition + c.familiarity(edge.id) * 100.0, -c.id))


def couriers_for(couriers, edge, at):
    """Who could run this leg: the people standing at either end and fit."""
    return [c for c in couriers
            if c.alive and c.at in (edge.a, edge.b) and c.fit_for(edge)]


def candidates(world, fleet, edge, season):
    """The carriers that could run this leg this season, and from which end."""
    out = []
    for carrier in fleet:
        if not carrier.can_run(season, edge) or not carrier.reaches(edge):
            continue
        if carrier.at in (edge.a, edge.b):
            out.append(carrier)
    return out


def prospective_load(world, origin, destination, capacity) -> int:
    """How much a run from here to there could actually carry. Used to choose
    between legs without committing to one."""
    return int(round(sum(fill_by_need(world, origin, destination, capacity).values())))


def fill_by_need(world, origin, destination, capacity) -> dict:
    """A load made of what the destination is shortest of and the origin can
    spare, heaviest need first. Post weighs nothing and always goes."""
    cargo = {g: 0.0 for g in GOODS}
    room = capacity

    # a year ahead, not to the next check: the post ships before it is asked
    gaps = destination.projected_shortfall(4)
    order = sorted((g for g in GOODS if g != "POST"),
                   key=lambda g: -gaps.get(g, 0.0) / max(NEED_PER_HEAD[g], 1e-6))
    for good in order:
        if room <= 0:
            break
        want = gaps.get(good, 0.0)
        if want <= 0:
            continue
        take = min(room, int(round(min(want, origin.spare(good)))))
        if take <= 0:
            continue
        cargo[good] = take
        room -= take

    if origin.stores.get("POST", 0.0) >= 1:
        cargo["POST"] = 1.0       # it weighs nothing, and it is the whole point
    return {g: v for g, v in cargo.items() if v > 0}
