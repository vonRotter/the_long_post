"""Couriers: people, not stat blocks.

There are no trait tables here and there will not be. A courier is a name, a
condition, a loyalty, a home, and a history — and the history is the part that
does the work, because it is simply true. *Sigrid has run the Nordfjord leg
eleven times* is worth more than any stat block and costs nothing to generate.

Competence is not hidden either. A courier gets better at a leg by running it,
and the count of prior runs on that leg is on the panel where the player can
see it. The player's veterans are veterans because of what the player asked of
them.
"""

from dataclasses import dataclass, field

from .. import tuning as T
from ..world.settlement import NEED_PER_HEAD


@dataclass
class Courier:
    id: int
    name: str
    home: int                      # the settlement they are from
    condition: float = 100.0       # falls with hard seasons, recovers with rest
    loyalty: float = 72.0
    at: int = 0                    # where they are standing
    joined_year: int = 1
    lost_year: int = 0
    lost_where: str = ""           # the leg, in plain words
    seasons_served: int = 0
    seasons_rested: int = 0
    consecutive: int = 0           # seasons run without a season off
    runs: list = field(default_factory=list)     # (year, season, edge id)
    delivered: int = 0
    lost_loads: int = 0
    took: list = field(default_factory=list)     # (year, edge id, settlement id)

    # --- state ---
    @property
    def alive(self) -> bool:
        return self.lost_year == 0

    def runs_on(self, edge_id) -> int:
        return sum(1 for _year, _season, leg in self.runs if leg == edge_id)

    def familiarity(self, edge_id) -> float:
        """A real, small bonus for a leg run before. Visible, never hidden."""
        return min(T.FAMILIARITY_CAP,
                   self.runs_on(edge_id) * T.FAMILIARITY_PER_RUN)

    def fit_for(self, edge) -> bool:
        """Below this the post does not send them, and the panel says why."""
        return self.condition >= T.CONDITION_UNFIT

    def risk_on(self, edge) -> float:
        """The chance this run does not come back.

        Read off their condition and the road, both of which the panel shows in
        bands before the season is committed. Nothing else feeds it.
        """
        worn = max(0.0, 1.0 - self.condition / 100.0) ** 2
        return min(0.9, T.LOSS_FROM_CONDITION * worn
                   + T.LOSS_FROM_DANGER * max(0.0, edge.danger))

    # --- the season ---
    def ran(self, year, season, edge, hard):
        self.runs.append((year, season, edge.id))
        self.seasons_served += 1
        self.seasons_rested = 0
        self.consecutive += 1
        wear = T.CONDITION_WEAR_RUN + (T.CONDITION_WEAR_HARD if hard else 0.0)
        wear += edge.days * T.CONDITION_WEAR_PER_DAY
        # consecutive seasons are what break a courier, not any single leg
        wear *= 1.0 + T.CONDITION_WEAR_CONSECUTIVE * max(0, self.consecutive - 1)
        wear *= 1.0 - self.familiarity(edge.id)
        self.condition = max(0.0, self.condition - wear)
        self.loyalty = max(0.0, self.loyalty - T.LOYALTY_WEAR_RUN
                           - (T.LOYALTY_WEAR_HARD if hard else 0.0))

    def rested(self):
        self.seasons_rested += 1
        self.consecutive = 0
        self.condition = min(100.0, self.condition + T.CONDITION_REST)
        self.loyalty = min(100.0, self.loyalty + T.LOYALTY_REST)

    def home_served(self, share):
        """Loyalty is built by the post serving where they are from."""
        self.loyalty = min(100.0, self.loyalty + T.LOYALTY_HOME * share)

    def home_neglected(self):
        self.loyalty = max(0.0, self.loyalty - T.LOYALTY_HOME_NEGLECT)

    # --- what the panel shows ---
    def history(self) -> str:
        """The record, in one plain line. It is never shortened."""
        if not self.runs:
            return "no runs yet"
        legs = {}
        for _year, _season, edge_id in self.runs:
            legs[edge_id] = legs.get(edge_id, 0) + 1
        most, count = max(legs.items(), key=lambda item: (item[1], -item[0]))
        return (f"{len(self.runs)} runs, {self.delivered} delivered"
                + (f", {self.lost_loads} lost" if self.lost_loads else ""))

    def worst_leg(self):
        legs = {}
        for _year, _season, edge_id in self.runs:
            legs[edge_id] = legs.get(edge_id, 0) + 1
        if not legs:
            return None, 0
        return max(legs.items(), key=lambda item: (item[1], -item[0]))


# --- theft: desperation, not character --------------------------------------


def theft_pressures(world, courier, edge, cargo, destination) -> dict:
    """The pressures on a courier carrying this load down this leg.

    Every one of them is on the panel before the assignment is committed, and
    the model reads no other number. A courier does not have a hidden dishonest
    streak; they have a home, and it is on the chart.
    """
    home = world.settlements[courier.home]
    passed = [world.settlements[sid] for sid in (edge.a, edge.b)]

    loads = sum(cargo.values())
    wanted = sum(destination.projected_shortfall(2).values())

    return {
        "disloyalty": max(0.0, 1.0 - courier.loyalty / 100.0),
        "condition": max(0.0, 1.0 - courier.condition / 100.0),
        "home need": home.desperation / 100.0 if home.alive else 0.0,
        "route need": max((s.desperation / 100.0 for s in passed), default=0.0),
        # a load the destination barely needs, carried past a place that does
        "cargo": 0.0 if wanted >= loads
                 else min(0.6, 0.6 * (1.0 - wanted / max(loads, 1e-6))),
    }


def theft_chance(pressures) -> float:
    """Zero unless at least two pressures are really there.

    The rule is the spec's: a theft never fires without at least two pressures
    the player could have seen at assignment time.
    """
    real = [name for name, value in pressures.items() if value >= T.THEFT_FLOOR]
    if len(real) < T.THEFT_PRESSURES_NEEDED:
        return 0.0
    weighted = sum(T.THEFT_WEIGHTS[name] * pressures[name] for name in pressures)
    total = sum(T.THEFT_WEIGHTS.values())
    return max(0.0, min(1.0, weighted / total)) * T.THEFT_SCALE


def visible_pressures(pressures) -> list:
    """The ones worth setting in the panel, heaviest first."""
    return sorted(((name, value) for name, value in pressures.items()
                   if value >= T.THEFT_FLOOR),
                  key=lambda item: -item[1])
