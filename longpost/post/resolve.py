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
    lines: list = field(default_factory=list)     # (at, text, accent, routine)
    vignettes: list = field(default_factory=list)  # (at, kind, subject)
    duration: float = T.RESOLVE_SECONDS

    def consequential(self):
        """The leg worth watching, if any.

        A run that does not come back outranks one that is stopped, which
        outranks one that is stolen, which outranks the largest load moving.
        Nothing here decides anything; it only says where to look.
        """
        if not self.legs:
            return None

        def weight(leg):
            lost = any(kind in ("storm", "ice", "avalanche")
                       for _at, kind, _subject in self.vignettes
                       if abs(_at - leg.end) < 1e-6)
            return (3 if lost else 0) + (2 if leg.taken else 0) \
                + (2 if leg.stolen else 0) + min(1.0, sum(leg.cargo.values()) / 40.0)

        best = max(self.legs, key=weight)
        return best if weight(best) > 0 else None

    def frame(self, at, kind, subject=""):
        """A glance at something. Six kinds, and rare because they are rare
        events — the queue shows one at most, and the world does not stop."""
        self.vignettes.append((at, kind, subject))

    def say(self, at, text, accent=False, routine=False):
        self.lines.append((at, text, accent, routine))

    def lines_before(self, t, exceptions_only=False):
        """What has been written by this point in the resolution.

        With standing orders running, most of a season is routine and the
        player has stopped reading it. Exception reporting means the log keeps
        what went wrong, what went unusually well, and anything that changed
        about a courier — and counts the rest.
        """
        out = []
        routine = 0
        for at, text, accent, is_routine in self.lines:
            if at > t:
                continue
            if exceptions_only and is_routine:
                routine += 1
                continue
            out.append((text, accent))
        if routine:
            out.append((f"{routine} runs went as they were meant to.", False))
        return out


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


def _standing_of(runner):
    """A courier's state in the words the panel uses, and how bad it is."""
    if runner.condition >= 75:
        wear, wear_rank = "fit", 0
    elif runner.condition >= T.CONDITION_UNFIT:
        wear, wear_rank = "worn", 1
    else:
        wear, wear_rank = "spent", 2
    if runner.loyalty >= 70:
        return wear, wear_rank
    mood = "restless" if runner.loyalty >= 40 else "done with it"
    return f"{wear} and {mood}", wear_rank + (1 if mood == "restless" else 2)


def _lose(result, world, runner, edge, year, season, at, gone=False):
    """A courier is lost. One plain sentence, and then nothing.

    §3.7 is the most important section in the specification and the easiest to
    get wrong. There is no adjective here, no second sentence, and the game
    never mentions them again. What is left is the panel next season, where
    their name still is, and a cross in the margin of this leg on the chart.
    """
    runner.lost_year = year
    runner.lost_where = _leg_name(world, edge)
    terrain = edge.effective_terrain
    result.frame(at, {"COAST": "storm", "ICE": "ice", "PASS": "avalanche"}.get(
        terrain, "avalanche"), runner.name)
    week = WEEKS[ink.seed_of("week", year, season, runner.id) % len(WEEKS)]
    edge.losses.append((year, runner.name))
    verb = "did not come back from" if gone else "was lost on"
    result.say(at, f"{runner.name} {verb} the {_leg_name(world, edge)} in the"
                   f" {week} week of {season.lower()}.", accent=True)


def _leg_name(world, edge) -> str:
    """What the leg is called. A chart names its waters."""
    if edge.name:
        return edge.name
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
    result.say(at, f"{settlement.name} was not on this chart. It is now.")
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


@dataclass
class Season:
    """What a phase of the resolution needs to do its work.

    The season is resolved in phases — the runs, the consumption, the winter
    check, the standing and the news, the people, the pressures — and each of
    them is a function that takes this. It is a plain holder and owns nothing.
    """
    world: object
    fleet: list
    couriers: list
    year: int
    season: str
    result: Resolution

    def courier(self, courier_id):
        if 0 <= courier_id < len(self.couriers):
            return self.couriers[courier_id]
        return None

    def other_end(self, edge, settlement_id):
        return self.world.settlements[self.world.other_end(edge, settlement_id)]


def resolve(world, fleet, couriers, plan, turn, year, season) -> Resolution:
    """Run the season, in the order the world runs it.

    Every effect is applied here, once, deterministically, and the animation
    plays back what this decided. The phases are in the order they happen in:
    the runs go out, what is left is eaten, the winter counts what was not
    shipped, letters do their work, the people are worn or rested, and the
    pressures settle into the roads of the season after.
    """
    result = Resolution(year=year, season=season)
    context = Season(world=world, fleet=fleet, couriers=couriers, year=year,
                     season=season, result=result)
    # how everyone stood before the season took anything out of them
    bands_before = {c.id: _standing_of(c) for c in couriers}

    _run_orders(context, list(plan))
    _eat(context)
    if season == "WINTER":
        _count_the_winter(context)
    _letters_and_standing(context)
    _the_people(context, bands_before)
    if season == "SPRING":
        _recruit(result, world, couriers, year)
    _settle_the_pressures(context)
    return result


# --- the runs ---------------------------------------------------------------


def _run_orders(context, orders):
    for index, order in enumerate(orders):
        _run_one(context, order, index, len(orders))


def _run_one(context, order, index, total):
    world, result = context.world, context.result
    edge = world.edges[order.edge_id]
    carrier = context.fleet[order.carrier_id]
    origin = world.settlements[order.origin]
    destination = context.other_end(edge, order.origin)
    runner = context.courier(order.courier_id)

    spacing = 0.45 / max(total, 1)
    out_start = index * spacing
    out_end = min(0.94, out_start + 0.42)
    leg = Leg(edge_id=edge.id, carrier_id=carrier.id, origin=origin.id,
              destination=destination.id, cargo={},
              courier_id=runner.id if runner else -1,
              start=out_start, end=out_end)

    if order.digging:
        _dig(result, world, edge, origin, runner, carrier, context.year,
             context.season, out_start)
        return

    leg.reason = _why_not(context, edge, carrier, runner)
    if leg.reason:
        leg.arrived = False
        result.legs.append(leg)
        result.say(leg.start, f"{carrier.name} did not set out: {leg.reason}.")
        return

    hard = edge.availability(context.season) == T.HARD
    leg.cargo = _load(origin, order.cargo, carrier.type.capacity)

    if _taken_by_the_courier(context, leg, edge, carrier, runner, hard):
        return
    if _taken_on_the_road(context, leg, edge, carrier, index=0):
        return

    _arrive(context, leg, edge, carrier, runner, origin, destination, hard, order)
    _come_back(context, leg, edge, carrier, origin, destination, order, out_end)


def _why_not(context, edge, carrier, runner) -> str:
    """Why this run does not set out, in plain words, or nothing."""
    season = context.season
    if runner is None or not runner.alive:
        return "there was no one to send"
    if not runner.fit_for(edge):
        return f"{runner.name} is in no condition to run it"
    if not edge.is_usable(season):
        return "the leg is closed this season"
    if not carrier.can_run(season, edge):
        return f"a {carrier.type.name} does not work this leg in {season.lower()}"
    if not carrier.reaches(edge):
        return f"{edge.days:g} days is beyond a {carrier.type.name} in one season"
    return ""


def _load(origin, wanted, capacity) -> dict:
    """What is actually there, up to the hold."""
    room = capacity
    loaded = {}
    for good, amount in sorted(wanted.items()):
        take = min(room, int(amount), int(origin.stores.get(good, 0.0)))
        if take <= 0:
            continue
        origin.stores[good] = origin.stores.get(good, 0.0) - take
        loaded[good] = float(take)
        room -= take
    return loaded


def _taken_by_the_courier(context, leg, edge, carrier, runner, hard) -> bool:
    """Theft, from pressures the panel showed before the season was committed."""
    world, result = context.world, context.result
    destination = world.settlements[leg.destination]
    if not leg.cargo:
        return False
    pressures = courier_mod.theft_pressures(world, runner, edge, leg.cargo, destination)
    chance = courier_mod.theft_chance(pressures)
    if chance <= 0:
        return False
    seed = ink.seed_of("theft", world.seed, context.year, context.season, edge.id,
                       runner.id)
    if float(np.random.default_rng(seed).random()) >= chance:
        return False

    home = world.settlements[runner.home]
    leg.stolen = True
    for good, amount in leg.cargo.items():
        home.stores[good] = home.stores.get(good, 0.0) + amount
    home.seasons_since_delivery = 0
    home.standing = min(100.0, home.standing + T.STANDING_TOOK_IT_HOME)
    runner.took.append((context.year, edge.id, home.id))
    runner.ran(context.year, context.season, edge, hard)
    carrier.at = leg.destination
    carrier.runs += 1
    edge.runs += 1
    edge.thefts.append((context.year, runner.name, home.name))
    result.legs.append(leg)
    result.say(leg.end, f"{runner.name} took {_goods_phrase(leg.cargo)} to"
                        f" {home.name}.")
    result.say(leg.end,
               f"{home.name} is where {runner.name.split()[0]} is from."
               + (f" It has had nothing for {home.seasons_since_delivery} seasons."
                  if home.seasons_since_delivery else ""))
    _discover(result, home, leg.end)
    # they may keep working, or they may not come back. Either way the game does
    # not judge it, and the loss is the last word said about them.
    stays = float(np.random.default_rng(seed + 1).random()) < runner.loyalty / 100.0
    if stays:
        runner.at = leg.destination
    else:
        _lose(result, world, runner, edge, context.year, context.season, leg.end,
              gone=True)
    return True


def _taken_on_the_road(context, leg, edge, carrier, index) -> bool:
    """The people whose road this is take the load.

    Not a faction and not an ambush: a settlement with nothing. The game says
    which one, and how long it has had nothing.
    """
    world, result = context.world, context.result
    if not leg.cargo:
        return False
    watcher = _hazard(world, edge, carrier, context.year, context.season, index)
    if watcher is None:
        return False

    leg.taken = True
    for good, amount in leg.cargo.items():
        watcher.stores[good] = watcher.stores.get(good, 0.0) + amount
    watcher.seasons_since_delivery = 0
    carrier.at = leg.destination
    carrier.runs += 1
    carrier.history.append((context.year, context.season, edge.id))
    edge.runs += 1
    edge.thefts.append((context.year, "", watcher.name))
    result.legs.append(leg)
    result.frame(leg.end, "bandits", watcher.name)
    coming_back = " coming back over the" if leg.returning else " on the"
    result.say(leg.end,
               f"{carrier.name} was stopped{coming_back} {_leg_name(world, edge)}."
               f" {_goods_phrase(leg.cargo)} went to {watcher.name}.", accent=True)
    if not _discover(result, watcher, leg.end):
        result.say(leg.end, _why_watched(watcher))
    return True


def _arrive(context, leg, edge, carrier, runner, origin, destination, hard, order):
    """The load is put down, and the run is written into everything it touched."""
    world, result = context.world, context.result
    was_short = destination.projected_shortfall(2)
    for good, amount in leg.cargo.items():
        destination.stores[good] = destination.stores.get(good, 0.0) + amount
        destination.received[good] = destination.received.get(good, 0.0) + amount

    carrier.at = destination.id
    carrier.runs += 1
    carrier.delivered += int(round(sum(leg.cargo.values())))
    carrier.history.append((context.year, context.season, edge.id))
    edge.runs += 1
    if leg.cargo:
        destination.seasons_since_delivery = 0

    runner.ran(context.year, context.season, edge, hard)
    runner.at = destination.id
    runner.delivered += int(round(sum(leg.cargo.values())))
    _may_not_come_back(context, leg, edge, runner)

    result.legs.append(leg)
    if leg.cargo:
        result.say(leg.end, f"{carrier.name} carried {_goods_phrase(leg.cargo)} to"
                            f" {destination.name}.", routine=order.standing)
    else:
        result.say(leg.end, f"{carrier.name} went empty to {destination.name}.")

    if not (leg.cargo and was_short):
        return
    still = destination.projected_shortfall(2)
    closed = [g for g in was_short if g not in still]
    if not closed:
        return
    # the counterweight, tied to the pressure model: an arrival is worth framing
    # when the place needed it, not when the load happened to be large
    if destination.desperation >= T.BAND_CALM * 100:
        result.frame(leg.end, "arrival", destination.name)
    # what went unusually well is never routine, however it was ordered
    result.say(leg.end, f"{destination.name} is no longer short of "
                        f"{', '.join(g.lower() for g in closed)}.")


def _may_not_come_back(context, leg, edge, runner):
    """The risk the panel showed: how worn they are, and how bad the road is."""
    risk = runner.risk_on(edge)
    if risk <= 0:
        return
    seed = ink.seed_of("loss", context.world.seed, context.year, context.season,
                       edge.id, runner.id)
    if float(np.random.default_rng(seed).random()) < risk:
        _lose(context.result, context.world, runner, edge, context.year,
              context.season, leg.end)


def _come_back(context, leg, edge, carrier, origin, destination, order, out_end):
    """The season affords the leg both ways, so the carrier comes home — and it
    comes home with whatever the place it left is short of."""
    world, result = context.world, context.result
    if not carrier.round_trip(edge):
        return
    wanted = assign.fill_by_need(world, destination, origin, carrier.type.capacity)
    back = Leg(edge_id=edge.id, carrier_id=carrier.id, origin=destination.id,
               destination=origin.id, cargo={}, returning=True,
               start=out_end, end=min(1.0, out_end + 0.42))
    back.cargo = _load(destination, wanted, carrier.type.capacity)

    if _taken_on_the_road(context, back, edge, carrier, index=1):
        carrier.at = origin.id
        return

    lifted = back.cargo
    for good, amount in lifted.items():
        origin.stores[good] = origin.stores.get(good, 0.0) + amount
        origin.received[good] = origin.received.get(good, 0.0) + amount
    carrier.at = origin.id
    edge.runs += 1
    if lifted:
        origin.seasons_since_delivery = 0
        result.say(back.end, f"{carrier.name} brought {_goods_phrase(lifted)} back to"
                             f" {origin.name}.", routine=order.standing)
    result.legs.append(back)


# --- the season itself ------------------------------------------------------


def _eat(context):
    """What is produced is produced, and what is there is eaten."""
    for settlement in context.world.settlements:
        if not settlement.alive:
            continue
        settlement.produce()
        settlement.consume(hard=context.world.winters.get(context.year, 1.0)
                           if context.season == "WINTER" else 1.0)
        if not any(leg.destination == settlement.id and leg.cargo and leg.arrived
                   for leg in context.result.legs):
            settlement.seasons_since_delivery += 1


def _count_the_winter(context):
    """The end of winter, where what was not shipped in autumn is counted."""
    world, result, year = context.world, context.result, context.year
    world.settlement_received = {
        s.id: {g: v for g, v in s.received.items() if v > 0}
        for s in world.settlements}

    for settlement in world.settlements:
        if not settlement.alive:
            continue
        deaths = settlement.winter_check(year)
        if deaths and settlement.known:
            result.say(0.9, f"{settlement.name} lost {deaths} over the winter."
                            f" {settlement.population} remain.")
        if settlement.population > T.ABANDON_POPULATION or not settlement.alive:
            continue

        had = world.settlement_received[settlement.id]
        settlement.abandoned_year = year
        if not settlement.known:
            continue
        result.frame(0.95, "abandonment", settlement.name)
        result.say(0.95, f"{settlement.name} was given up in year {year}.",
                   accent=True)
        if had:
            # The whole of what the player gets for it, and it is recorded
            # rather than rewarded. §3.9.
            result.say(0.96, f"{settlement.name} received {_goods_phrase(had)}"
                             f" in the winter it ended.")
            world.kindnesses.append((year, settlement.name, dict(had)))


def _letters_and_standing(context):
    """What the post is for: letters, standing, and the news they carry."""
    world, result = context.world, context.result
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


def _the_people(context, bands_before):
    """Rest, home, and anything that changed for the worse."""
    result = context.result
    ran = {leg.courier_id for leg in result.legs if leg.courier_id >= 0}
    for runner in context.couriers:
        if not runner.alive:
            continue
        if runner.id not in ran:
            runner.rested()
        home = context.world.settlements[runner.home]
        if home.alive:
            share = min(1.0, sum(home.received.values())
                        / max(sum(home.needs().values()), 1e-6))
            if share > 0.05:
                runner.home_served(share)
            elif context.season == "WINTER":
                runner.home_neglected()

        now, rank = _standing_of(runner)
        was, was_rank = bands_before.get(runner.id, (now, rank))
        # §3.13: exception reporting keeps anything that changed about a
        # courier, which is how somebody the player had stopped reading about
        # comes back to their attention before they are lost rather than after.
        # Only a change for the worse: a courier coming back to themselves after
        # a season off is not news, and news that repeats is wallpaper.
        if now != was and rank > was_rank:
            result.say(0.97, f"{runner.name} is {now}.")


def _settle_the_pressures(context):
    """Where the next season's roads come from.

    Nothing here is random. It is arithmetic on what the player did and did not
    ship, and the roads are read straight off it.
    """
    world, result = context.world, context.result
    before = {e.id: e.danger for e in world.edges}
    pressure.apply(world, context.season, context.year)
    for edge in world.known_edges():
        was = pressure.road_band(before.get(edge.id, 0.0))
        now = pressure.road_band(edge.danger)
        if now == was or edge.danger_source < 0:
            continue
        source = world.settlements[edge.danger_source]
        if not source.known:
            continue
        if now == "safe":
            result.say(1.0, f"the {_leg_name(world, edge)} is quiet again.")
        else:
            result.say(1.0, f"the {_leg_name(world, edge)} is {now}."
                            f" {_why_watched(source)}")


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
        result.say(at, f"{settlement.name} has people at {other.name}."
                       f" It is on the chart now.")
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
        result.say(at, f"the {_leg_name(world, edge)} is open. It will not close"
                       f" again.")
    else:
        left = max(0, T.TUNNEL_LABOUR - int(edge.tunnel_labour))
        wants = []
        if edge.tunnel_tools < T.TUNNEL_TOOLS:
            wants.append(f"{int(T.TUNNEL_TOOLS - edge.tunnel_tools)} tools")
        if edge.tunnel_fuel < T.TUNNEL_FUEL:
            wants.append(f"{int(T.TUNNEL_FUEL - edge.tunnel_fuel)} fuel")
        result.say(at, f"{runner.name} dug at the {_leg_name(world, edge)}."
                       f" {words_left(left)}"
                       + (f" It wants {' and '.join(wants)} at {origin.name}."
                          if wants else ""), routine=True)


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
        result.say(0.98, f"{name} of {settlement.name} has taken work with the"
                         f" post.")


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
