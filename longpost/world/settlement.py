"""Settlements: what they hold, what they need, what they produce.

Decline, doom and abandonment attach here at M1 and M4. At M0 a settlement is
a population, a set of needs, a surplus, a standing and a desperation value.
"""

from dataclasses import dataclass, field

from .. import tuning as T

GOODS = ("GRAIN", "FUEL", "MEDICINE", "TOOLS", "POST")

# Per head, per year, in loads. A load is a real cargo — a load of grain is a
# year for ten people — and the holds in data/carriers.py are caravans rather
# than animals: a horse team is several horses and their drivers, a sled team
# several sleds, a boat its crew. The courier is who leads it.
#
# That sets the shape of the whole game: overland is a trickle, the sea is the
# artery, and winter takes the artery away.
NEED_PER_HEAD = {
    "GRAIN": 0.100,
    "FUEL": 0.060,
    "MEDICINE": 0.012,
    "TOOLS": 0.020,
    "POST": 0.008,
}


@dataclass
class Settlement:
    id: int
    name: str
    pos: tuple            # world coordinates
    population: int
    surplus: tuple        # one or two goods produced beyond its own needs
    standing: float = 55.0
    desperation: float = 0.0
    known: bool = False   # discovered by the post
    abandoned_year: int = 0
    stores: dict = field(default_factory=dict)
    shortfall: dict = field(default_factory=dict)   # since the last winter
    received: dict = field(default_factory=dict)    # from the post, this year
    deaths: list = field(default_factory=list)      # (year, count)
    seasons_since_delivery: int = 0

    def __post_init__(self):
        if not self.stores:
            self.stores = {g: round(self.population * per * T.STORES_AT_START, 2)
                           for g, per in NEED_PER_HEAD.items()}
        for good in GOODS:
            self.shortfall.setdefault(good, 0.0)
            self.received.setdefault(good, 0.0)

    def needs(self) -> dict:
        """What this settlement consumes in a year."""
        return {g: round(self.population * per, 2) for g, per in NEED_PER_HEAD.items()}

    def season_need(self, good) -> float:
        return self.population * NEED_PER_HEAD[good] / 4.0

    def produces(self, good) -> float:
        """What it makes in a season. Only its surplus goods, and only above
        what it eats itself."""
        if good not in self.surplus:
            return 0.0
        return self.population * NEED_PER_HEAD[good] * T.SURPLUS_RATE / 4.0

    def spare(self, good) -> float:
        """What the post may take without leaving the place short this year.

        A settlement at the extreme gives up nothing. It is not hostile: it has
        nothing to spare and no reason to believe more is coming.
        """
        if not self.alive or self.desperation >= T.DESPERATION_REFUSAL:
            return 0.0
        keep = self.population * NEED_PER_HEAD[good] * 0.5
        return max(0.0, self.stores.get(good, 0.0) - keep)

    # --- the season ---
    def produce(self):
        for good in self.surplus:
            self.stores[good] = self.stores.get(good, 0.0) + self.produces(good)

    def consume(self):
        """Needs are consumed continuously; what is missing is remembered."""
        missing = {}
        for good in GOODS:
            want = self.season_need(good)
            have = self.stores.get(good, 0.0)
            taken = min(want, have)
            self.stores[good] = have - taken
            if want - taken > 1e-9:
                self.shortfall[good] += want - taken
                missing[good] = want - taken
        return missing

    def projected_shortfall(self, seasons_left) -> dict:
        """What will be missing by the end of winter if nothing more arrives.

        The panel shows this every season, because the delay between a load
        that was not sent in autumn and the deaths in February is the game's
        central cruelty and it has to be legible.
        """
        out = {}
        for good in GOODS:
            want = self.season_need(good) * seasons_left
            gap = want - self.stores.get(good, 0.0) + self.shortfall[good]
            if gap > 0.01:
                out[good] = round(gap, 1)
        return out

    def received_anything(self) -> bool:
        return any(value > 0 for value in self.received.values())

    def winter_check(self, year) -> int:
        """The end of winter. What was not shipped is counted here."""
        toll = 0.0
        for good, weight in T.SHORTFALL_DEATHS.items():
            if weight <= 0 or self.shortfall[good] <= 0:
                continue
            head_years = self.shortfall[good] / NEED_PER_HEAD[good]
            toll += head_years * weight
        deaths = min(self.population, int(round(toll)))
        if deaths:
            self.population -= deaths
            self.deaths.append((year, deaths))
        for good in GOODS:
            self.shortfall[good] = 0.0
            self.received[good] = 0.0
        return deaths

    def projected_deaths(self, seasons_left=1) -> int:
        """What the winter check will cost if nothing more arrives."""
        gap = self.projected_shortfall(seasons_left)
        toll = sum(gap.get(g, 0.0) / NEED_PER_HEAD[g] * w
                   for g, w in T.SHORTFALL_DEATHS.items() if w > 0)
        return min(self.population, int(round(toll)))

    def unavoidable_deaths(self) -> int:
        """What this winter will take whatever arrives from here on.

        The seasons already gone short are already counted. A load that comes
        now cannot un-miss them, which is what makes a settlement's end
        arithmetic rather than a matter of effort.
        """
        toll = sum(self.shortfall.get(g, 0.0) / NEED_PER_HEAD[g] * w
                   for g, w in T.SHORTFALL_DEATHS.items() if w > 0)
        return min(self.population, int(round(toll)))

    def doomed(self, seasons_left=1) -> bool:
        """True when the arithmetic has already ended this place.

        Not "will die if nothing arrives" — that is a settlement the post can
        still save, and saving it is the game. This is the other one: what the
        winter will take is already owed, and a full delivery from here on
        leaves too few people to hold the place. Shipping to it is a genuine
        waste of capacity and stays one. See §3.9 and tests/test_kindness.py.
        """
        if not self.alive:
            return False
        return self.population - self.unavoidable_deaths() <= T.ABANDON_POPULATION

    @property
    def alive(self) -> bool:
        return self.abandoned_year == 0 and self.population > 0

    def radius(self) -> float:
        """Chart radius, scaled to population. The largest town on the chart is
        about twice the circle of the smallest, not ten times it."""
        return 4.0 + (self.population ** 0.55) * 0.50
