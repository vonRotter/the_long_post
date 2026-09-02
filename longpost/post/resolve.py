"""Season resolution — the core simulation.

Everything that happens in a season is decided here, in one deterministic pass,
and then played back over about six seconds. The animation shows what was
already decided; it never decides anything.
"""

from dataclasses import dataclass, field

import numpy as np

from .. import tuning as T
from ..data import names as name_data
from ..render import ink
from ..world import desperation as pressure
from ..world.settlement import GOODS
from . import assign
from . import courier as courier_mod


@dataclass
class Leg:
    """One run, as it is drawn and as it turned out."""
    edge_id: int
    carrier_id: int
    origin: int
    destination: int
    cargo: dict
    courier_id: int = -1
    arrived: bool = True
    taken: bool = False           # the load was taken on the road
    stolen: bool = False          # the courier took it somewhere of their own
    reason: str = ""              # why it did not, in plain words
    start: float = 0.0            # when it sets out, 0..1 of the resolution
    end: float = 1.0
    returning: bool = False       # the second half of a round trip


@dataclass
class Resolution:
    year: int
    season: str
    legs: list = field(default_factory=list)
    lines: list = field(default_factory=list)     # (at, text, accent)
    duration: float = T.RESOLVE_SECONDS

    def lines_before(self, t):
        return [(text, accent) for at, text, accent in self.lines if at <= t]


def _hazard(world, edge, carrier, year, season, index):
    """Whether this run is stopped on the road, and by whom.

    Deterministic in the seed, the year, the season, the leg and the carrier,
    so a disastrous year replays identically. Nothing is rolled that the
    player could not have weighed: the danger was on the leg in the panel
    before the season was committed.
    """
    if edge.danger <= 0 or edge.danger_source < 0:
        return None
    # seed_of, never hash(): Python randomises string hashing per process, and
    # a run that replays differently tomorrow is not a replay
    seed = ink.seed_of("hazard", world.seed, year, season, edge.id, carrier.id, index)
    roll = float(np.random.default_rng(seed).random())
    if roll >= edge.danger * T.HAZARD_SCALE:
        return None
    return world.settlements[edge.danger_source]


def _goods_phrase(cargo) -> str:
    parts = [f"{int(round(v))} {g.lower()}" for g, v in sorted(cargo.items()) if v > 0]
    if not parts:
        return "nothing"
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


WEEKS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh",
         "eighth", "ninth", "tenth", "eleventh", "twelfth")


def _lose(result, world, runner, edge, year, season, at, gone=False):
    """A courier is lost. One plain sentence, and then nothing.

    §3.7 is the most important section in the specification and the easiest to
    get wrong. There is no adjective here, no second sentence, and the game
    never mentions them again. What is left is the panel next season, where
    their name still is, and a cross in the margin of this leg on the chart.
    """
    runner.lost_year = year
    runner.lost_where = _leg_name(world, edge)
    week = WEEKS[ink.seed_of("week", year, season, runner.id) % len(WEEKS)]
    edge.losses.append((year, runner.name))
    verb = "did not come back from" if gone else "was lost on"
    result.lines.append((
        at, f"{runner.name} {verb} the {_leg_name(world, edge)} in the {week}"
            f" week of {season.lower()}.", True))


def _leg_name(world, edge) -> str:
    return (f"{world.settlements[edge.a].name.lower()} — "
            f"{world.settlements[edge.b].name.lower()} leg")


def _discover(result, settlement, at):
    """A settlement the post did not have on its chart, learned the hard way.

    Everything hostile has to be traceable to a place the player can look at,
    so a settlement that takes a load is put on the chart by that fact. It is
    the plainest possible answer to "where did the grain go".
    """
    if settlement.known:
        return False
    settlement.known = True
    result.lines.append((at, f"{settlement.name} was not on this chart. It is now.",
                         False))
    return True


def _why_watched(settlement) -> str:
    """The cause, in one plain sentence, every time it happens."""
    seasons = settlement.seasons_since_delivery
    if seasons >= T.DESPERATION_ISOLATION:
        return f"{settlement.name} had had nothing for {seasons} seasons."
    missing = [g.lower() for g, v in sorted(settlement.shortfall.items()) if v > 0.5]
    if missing:
        return f"{settlement.name} is short of {', '.join(missing)}."
    return f"{settlement.name} lost people last winter."


def resolve(world, fleet, couriers, plan, turn, year, season) -> Resolution:
    """Run the season. Applies every effect, and returns what to show."""
    result = Resolution(year=year, season=season)
    orders = list(plan)

    # --- the runs ---
    for index, order in enumerate(orders):
        edge = world.edges[order.edge_id]
        carrier = fleet[order.carrier_id]
        origin = world.settlements[order.origin]
        destination = world.settlements[world.other_end(edge, order.origin)]
        runner = couriers[order.courier_id] if 0 <= order.courier_id < len(couriers) \
            else None

        spacing = 0.45 / max(len(orders), 1)
        out_start = index * spacing
        out_end = min(0.94, out_start + 0.42)
        leg = Leg(edge_id=edge.id, carrier_id=carrier.id, origin=origin.id,
                  destination=destination.id, cargo={},
                  courier_id=runner.id if runner else -1,
                  start=out_start, end=out_end)

        if order.digging:
            _dig(result, world, edge, origin, runner, carrier, year, season,
                 out_start)
            continue

        if runner is None or not runner.alive:
            leg.arrived = False
            leg.reason = "there was no one to send"
        elif not runner.fit_for(edge):
            leg.arrived = False
            leg.reason = f"{runner.name} is in no condition to run it"
        elif not edge.is_usable(season):
            leg.arrived = False
            leg.reason = "the leg is closed this season"
        elif not carrier.can_run(season, edge):
            leg.arrived = False
            leg.reason = f"a {carrier.type.name} does not work this leg in {season.lower()}"
        elif not carrier.reaches(edge):
            leg.arrived = False
            leg.reason = (f"{edge.days:g} days is beyond a {carrier.type.name}"
                          f" in one season")

        if not leg.arrived:
            result.legs.append(leg)
            result.lines.append((leg.start, f"{carrier.name} did not set out: {leg.reason}.",
                                 False))
            continue

        hard = edge.availability(season) == T.HARD

        # load what is actually there, up to the hold
        room = carrier.type.capacity
        loaded = {}
        for good, amount in sorted(order.cargo.items()):
            take = min(room, int(amount), int(origin.stores.get(good, 0.0)))
            if take <= 0:
                continue
            origin.stores[good] = origin.stores.get(good, 0.0) - take
            loaded[good] = float(take)
            room -= take
        leg.cargo = loaded

        pressures = courier_mod.theft_pressures(world, runner, edge, loaded, destination)
        chance = courier_mod.theft_chance(pressures)
        seed = ink.seed_of("theft", world.seed, year, season, edge.id, runner.id)
        if loaded and chance > 0 and float(np.random.default_rng(seed).random()) < chance:
            home = world.settlements[runner.home]
            leg.stolen = True
            for good, amount in loaded.items():
                home.stores[good] = home.stores.get(good, 0.0) + amount
            home.seasons_since_delivery = 0
            home.standing = min(100.0, home.standing + T.STANDING_TOOK_IT_HOME)
            runner.took.append((year, edge.id, home.id))
            runner.ran(year, season, edge, hard)
            carrier.at = destination.id
            carrier.runs += 1
            edge.runs += 1
            result.legs.append(leg)
            result.lines.append((
                leg.end,
                f"{runner.name} took {_goods_phrase(loaded)} to {home.name}.", False))
            result.lines.append((
                leg.end,
                f"{home.name} is where {runner.name.split()[0]} is from."
                + (f" It has had nothing for {home.seasons_since_delivery} seasons."
                   if home.seasons_since_delivery else ""), False))
            _discover(result, home, leg.end)
            # they may keep working, or they may not come back. Either way the
            # game does not judge it, and the loss is the last word said about
            # them — there is nothing after it.
            stays = float(np.random.default_rng(seed + 1).random()) < runner.loyalty / 100.0
            if stays:
                runner.at = destination.id
            else:
                _lose(result, world, runner, edge, year, season, leg.end, gone=True)
            continue

        watcher = _hazard(world, edge, carrier, year, season, 0) if loaded else None
        if watcher is not None:
            # The load is taken by the people whose road this is. It is not a
            # faction and it is not an ambush: it is a settlement with nothing,
            # and the game says which one and how long it has had nothing.
            leg.taken = True
            for good, amount in loaded.items():
                watcher.stores[good] = watcher.stores.get(good, 0.0) + amount
            watcher.seasons_since_delivery = 0
            carrier.at = destination.id
            carrier.runs += 1
            carrier.history.append((year, season, edge.id))
            edge.runs += 1
            result.legs.append(leg)
            result.lines.append((
                leg.end,
                f"{carrier.name} was stopped on the {_leg_name(world, edge)}."
                f" {_goods_phrase(loaded)} went to {watcher.name}.", True))
            if not _discover(result, watcher, leg.end):
                result.lines.append((leg.end, _why_watched(watcher), False))
            continue

        destination_was = destination.projected_shortfall(2)
        for good, amount in loaded.items():
            destination.stores[good] = destination.stores.get(good, 0.0) + amount
            destination.received[good] = destination.received.get(good, 0.0) + amount

        carrier.at = destination.id
        carrier.runs += 1
        carrier.delivered += int(round(sum(loaded.values())))
        carrier.history.append((year, season, edge.id))
        edge.runs += 1
        if loaded:
            destination.seasons_since_delivery = 0

        runner.ran(year, season, edge, hard)
        runner.at = destination.id
        runner.delivered += int(round(sum(loaded.values())))
        risk = runner.risk_on(edge)
        if risk > 0:
            seed = ink.seed_of("loss", world.seed, year, season, edge.id, runner.id)
            if float(np.random.default_rng(seed).random()) < risk:
                _lose(result, world, runner, edge, year, season, leg.end)

        result.legs.append(leg)
        if loaded:
            result.lines.append((
                leg.end,
                f"{carrier.name} carried {_goods_phrase(loaded)} to {destination.name}.",
                False))
        else:
            result.lines.append((
                leg.end, f"{carrier.name} went empty to {destination.name}.", False))
        if loaded and destination_was:
            still = destination.projected_shortfall(2)
            closed = [g for g in destination_was if g not in still]
            if closed:
                result.lines.append((leg.end, f"{destination.name} is no longer short of "
                                              f"{', '.join(g.lower() for g in closed)}.",
                                     False))

        # the season affords the leg both ways: the carrier comes home, and it
        # comes home with whatever the place it left is short of
        if not carrier.round_trip(edge):
            continue
        home_cargo = assign.fill_by_need(world, destination, origin,
                                         carrier.type.capacity)
        back = Leg(edge_id=edge.id, carrier_id=carrier.id, origin=destination.id,
                   destination=origin.id, cargo={}, returning=True,
                   start=out_end, end=min(1.0, out_end + 0.42))
        room = carrier.type.capacity
        lifted = {}
        for good, amount in sorted(home_cargo.items()):
            take = min(room, int(amount), int(destination.stores.get(good, 0.0)))
            if take <= 0:
                continue
            destination.stores[good] = destination.stores.get(good, 0.0) - take
            lifted[good] = float(take)
            room -= take

        watcher = _hazard(world, edge, carrier, year, season, 1) if lifted else None
        if watcher is not None:
            back.taken = True
            for good, amount in lifted.items():
                watcher.stores[good] = watcher.stores.get(good, 0.0) + amount
            watcher.seasons_since_delivery = 0
            carrier.at = origin.id
            edge.runs += 1
            result.legs.append(back)
            result.lines.append((
                back.end,
                f"{carrier.name} was stopped coming back over the"
                f" {_leg_name(world, edge)}. {_goods_phrase(lifted)} went to"
                f" {watcher.name}.", True))
            if not _discover(result, watcher, back.end):
                result.lines.append((back.end, _why_watched(watcher), False))
            continue

        for good, amount in lifted.items():
            origin.stores[good] = origin.stores.get(good, 0.0) + amount
            origin.received[good] = origin.received.get(good, 0.0) + amount
            back.cargo[good] = amount
        carrier.at = origin.id
        edge.runs += 1
        if back.cargo:
            origin.seasons_since_delivery = 0
            result.lines.append((
                back.end,
                f"{carrier.name} brought {_goods_phrase(back.cargo)} back to"
                f" {origin.name}.", False))
        result.legs.append(back)

    # --- the season itself ---
    for settlement in world.settlements:
        if not settlement.alive:
            continue
        settlement.produce()
        settlement.consume()
        if not any(leg.destination == settlement.id and leg.cargo and leg.arrived
                   for leg in result.legs):
            settlement.seasons_since_delivery += 1

    # --- the end of winter, where what was not shipped is counted ---
    if season == "WINTER":
        world.settlement_received = {
            s.id: {g: v for g, v in s.received.items() if v > 0}
            for s in world.settlements}
        for settlement in world.settlements:
            if not settlement.alive:
                continue
            deaths = settlement.winter_check(year)
            if deaths and settlement.known:
                result.lines.append((
                    0.9, f"{settlement.name} lost {deaths} over the winter."
                         f" {settlement.population} remain.", False))
            if settlement.population <= T.ABANDON_POPULATION and settlement.alive:
                had = world.settlement_received[settlement.id]
                settlement.abandoned_year = year
                if settlement.known:
                    result.lines.append((0.95, f"{settlement.name} was given up in"
                                               f" year {year}.", True))
                    if had:
                        # The whole of what the player gets for it, and it is
                        # recorded rather than rewarded. §3.9.
                        result.lines.append((
                            0.96, f"{settlement.name} received"
                                  f" {_goods_phrase(had)} in the winter it ended.",
                            False))
                        world.kindnesses.append((year, settlement.name, dict(had)))

    # --- what the post is for: letters, standing, and the news they carry ---
    for leg in result.legs:
        if not (leg.arrived and leg.cargo) or leg.taken or leg.stolen:
            continue
        both = (world.settlements[leg.origin], world.settlements[leg.destination])
        gain = (T.STANDING_POST if leg.cargo.get("POST") else 0.0) + T.STANDING_GOODS
        for settlement in both:
            settlement.standing = min(100.0, settlement.standing + gain)
        if leg.cargo.get("POST"):
            _news(result, world, world.settlements[leg.destination], at=leg.end)
    for settlement in world.settlements:
        if settlement.alive and not any(
                leg.destination == settlement.id and leg.cargo and leg.arrived
                for leg in result.legs):
            settlement.standing = max(0.0, settlement.standing - T.STANDING_DECAY)

    # --- the people ---
    ran = {leg.courier_id for leg in result.legs if leg.courier_id >= 0}
    for runner in couriers:
        if not runner.alive:
            continue
        if runner.id not in ran:
            runner.rested()
        home = world.settlements[runner.home]
        if home.alive:
            share = min(1.0, sum(home.received.values())
                        / max(sum(home.needs().values()), 1e-6))
            if share > 0.05:
                runner.home_served(share)
            elif season == "WINTER":
                runner.home_neglected()

    if season == "SPRING":
        _recruit(result, world, couriers, year)

    # --- and then the pressures, which is where the next season's roads
    # come from. Nothing here is random: it is arithmetic on what the player
    # did and did not ship.
    watched_before = {e.id: e.danger for e in world.edges}
    pressure.apply(world, season, year)
    for edge in world.known_edges():
        before = pressure.road_band(watched_before.get(edge.id, 0.0))
        now = pressure.road_band(edge.danger)
        if now == before or edge.danger_source < 0:
            continue
        source = world.settlements[edge.danger_source]
        if not source.known:
            continue
        if now == "safe":
            result.lines.append((
                1.0, f"the {_leg_name(world, edge)} is quiet again.", False))
        else:
            result.lines.append((
                1.0, f"the {_leg_name(world, edge)} is {now}. "
                     f"{_why_watched(source)}", False))

    return result


def _news(result, world, settlement, at):
    """A settlement that trusts the post tells it about a neighbour.

    Letters are how the network learns the shape of itself, which is why a post
    that carries none finds the chart stops growing along with everything else.
    """
    if settlement.standing < T.STANDING_NEWS:
        return
    for edge in world.edges_of(settlement.id):
        other = world.settlements[world.other_end(edge, settlement.id)]
        if other.known or not other.alive:
            continue
        other.known = True
        result.lines.append((
            at, f"{settlement.name} has people at {other.name}."
                f" It is on the chart now.", False))
        return


def _dig(result, world, edge, origin, runner, carrier, year, season, at):
    """A season spent excavating instead of carrying.

    The people are the cost. A courier and their team digging at a collapsed
    line is a courier and a team not on the water, in a season the network
    could have used them, and the panel says how many seasons are left.
    """
    if runner is None or not runner.alive or not edge.tunnel_site or edge.tunnel_built:
        return
    edge.tunnel_labour += T.TUNNEL_PER_SEASON
    for good, held in (("TOOLS", edge.tunnel_tools), ("FUEL", edge.tunnel_fuel)):
        want = (T.TUNNEL_TOOLS if good == "TOOLS" else T.TUNNEL_FUEL) - held
        take = min(max(0.0, want), origin.stores.get(good, 0.0),
                   carrier.type.capacity)
        if take <= 0:
            continue
        origin.stores[good] = origin.stores.get(good, 0.0) - take
        if good == "TOOLS":
            edge.tunnel_tools += take
        else:
            edge.tunnel_fuel += take
    runner.ran(year, season, edge, hard=False)
    runner.at = origin.id

    if edge.tunnel_share >= 1.0:
        edge.tunnel_built = True
        edge.danger, edge.danger_source = 0.0, -1
        result.lines.append((
            at, f"the {_leg_name(world, edge)} is open. It will not close again.",
            False))
    else:
        left = max(0, T.TUNNEL_LABOUR - int(edge.tunnel_labour))
        wants = []
        if edge.tunnel_tools < T.TUNNEL_TOOLS:
            wants.append(f"{int(T.TUNNEL_TOOLS - edge.tunnel_tools)} tools")
        if edge.tunnel_fuel < T.TUNNEL_FUEL:
            wants.append(f"{int(T.TUNNEL_FUEL - edge.tunnel_fuel)} fuel")
        result.lines.append((
            at, f"{runner.name} dug at the {_leg_name(world, edge)}."
                f" {words_left(left)}"
                + (f" It wants {' and '.join(wants)} at {origin.name}."
                   if wants else ""), False))


def words_left(seasons) -> str:
    if seasons <= 0:
        return "the labour is done; what it wants now is carried."
    return f"{seasons} more {'season' if seasons == 1 else 'seasons'} of labour."


def _recruit(result, world, couriers, year):
    """Who comes to the post looking for work.

    Mostly people from settlements with nothing left to keep them, which is a
    grim source of labour and is meant to read as one. A settlement that has
    stopped trusting the post sends nobody at all.
    """
    for settlement in world.settlements:
        if not (settlement.known and settlement.alive):
            continue
        if settlement.desperation < T.RECRUIT_DESPERATION:
            continue
        if settlement.doomed(2):
            continue        # nobody is taking work from a place that is ending
        if settlement.standing < T.RECRUIT_STANDING:
            continue
        gen = np.random.default_rng(
            ink.seed_of("recruit", world.seed, year, settlement.id))
        if gen.random() > T.RECRUIT_CHANCE:
            continue
        taken = {c.name for c in couriers}
        name = name_data.person_name(gen)
        for _ in range(12):
            if name not in taken:
                break
            name = name_data.person_name(gen)
        couriers.append(courier_mod.Courier(
            id=len(couriers), name=name, home=settlement.id, at=settlement.id,
            joined_year=year))
        result.lines.append((
            0.98, f"{name} of {settlement.name} has taken work with the post.",
            False))


def plan_is_runnable(world, fleet, plan, season):
    """Orders that cannot run, for the panel to say so before the commit."""
    trouble = []
    for order in plan:
        edge = world.edges[order.edge_id]
        carrier = fleet[order.carrier_id]
        if not edge.is_usable(season):
            trouble.append((order, "the leg is closed"))
        elif not carrier.can_run(season, edge):
            trouble.append((order, "not this carrier, this season"))
        elif not carrier.reaches(edge):
            trouble.append((order, "beyond its reach in one season"))
    return trouble
