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

    def total(self) -> int:
        return int(round(sum(self.cargo.values())))

    def loaded(self) -> dict:
        return {g: v for g, v in self.cargo.items() if v > 0}


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
