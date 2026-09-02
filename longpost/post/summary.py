"""The end of the run, set plainly.

Not a score. The headline figure is the number of years the post ran, and
everything under it is a record of what happened rather than an assessment of
it. The lines about settlements that received something in the winter they
ended are the whole of what the player gets for that, and they are here for the
same reason they are in the log: because it happened.
"""

from dataclasses import dataclass, field

from .. import tuning as T


@dataclass
class Summary:
    years: int
    reason: str                                  # why the run ended, plainly
    population_at_start: int = 0
    population_at_end: int = 0
    surviving: list = field(default_factory=list)     # (name, population)
    lost: list = field(default_factory=list)          # (name, year)
    tunnels: list = field(default_factory=list)       # leg names
    veterans: list = field(default_factory=list)      # couriers who served it all
    fallen: list = field(default_factory=list)        # (name, where, year, history)
    thefts: list = field(default_factory=list)        # (name, what, where)
    kindnesses: list = field(default_factory=list)    # the winter-it-ended lines
    largest_year: int = 0
    largest_count: int = 0
    loads: int = 0
    on_chart: int = 0
    on_chart_population: int = 0


def build(game) -> Summary:
    world = game.world
    alive = [s for s in world.settlements if s.alive]
    summary = Summary(
        years=game.year - T.START_YEAR + (1 if game.turn + 1 >= T.TURNS else 0),
        reason=game.ending_reason,
        population_at_start=game.population_at_start,
        population_at_end=sum(s.population for s in alive),
        surviving=sorted(((s.name, s.population) for s in alive if s.known),
                         key=lambda item: -item[1]),
        lost=sorted(((s.name, s.abandoned_year) for s in world.settlements
                     if not s.alive and s.known), key=lambda item: item[1]),
        tunnels=[e.name or f"{world.settlements[e.a].name.lower()} — "
                 f"{world.settlements[e.b].name.lower()}"
                 for e in world.edges if e.tunnel_built],
        loads=sum(c.delivered for c in game.fleet),
        largest_year=game.largest_year,
        largest_count=game.largest_count,
        on_chart=len([s for s in alive if s.known]),
        on_chart_population=sum(s.population for s in alive if s.known),
        kindnesses=[f"{name} received "
                    + _goods(what) + f" in the winter it ended."
                    for _year, name, what in world.kindnesses],
    )

    for runner in game.couriers:
        if runner.alive and runner.joined_year == T.START_YEAR:
            summary.veterans.append((runner.name, runner.history()))
        elif not runner.alive:
            summary.fallen.append((runner.name, runner.lost_where, runner.lost_year,
                                   runner.history()))
        for year, _edge_id, home in runner.took:
            summary.thefts.append((runner.name, world.settlements[home].name, year))
    return summary


def _goods(what) -> str:
    parts = [f"{int(round(v))} {g.lower()}" for g, v in sorted(what.items()) if v > 0]
    if not parts:
        return "nothing"
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]
