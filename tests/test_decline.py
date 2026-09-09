"""There is no winning line.

Aggregate population is non-increasing across a full run, whatever is shipped.
"""

from longpost import tuning as T
from longpost.__main__ import Game
from longpost.post import assign


def strategies():
    return {"idle": _idle, "by need": _by_need, "nearest": _nearest}


def _idle(game):
    return


def _by_need(game):
    for carrier in game.fleet:
        legs = _legs(game, carrier)
        if not legs:
            continue
        origin = game.world.settlements[carrier.at]
        legs.sort(key=lambda e: -assign.prospective_load(
            game.world, origin,
            game.world.settlements[game.world.other_end(e, carrier.at)],
            carrier.type.capacity))
        game.select_edge(legs[0])
        game.selected_carrier = carrier
        game.load_by_need()


def _nearest(game):
    for carrier in game.fleet:
        legs = _legs(game, carrier)
        if not legs:
            continue
        legs.sort(key=lambda e: e.days)
        game.select_edge(legs[0])
        game.selected_carrier = carrier
        game.load_by_need()


def _legs(game, carrier):
    return [e for e in game.world.known_edges()
            if e.is_usable(game.season) and carrier.at in (e.a, e.b)
            and carrier.can_run(game.season, e) and carrier.reaches(e)]


def population(game):
    return sum(s.population for s in game.world.settlements if s.alive)


def test_population_never_rises_under_any_strategy():
    for name, strategy in strategies().items():
        for seed in (3, 11):
            game = Game(seed)
            last = population(game)
            for _ in range(T.TURNS):
                strategy(game)
                game.run_season()
                now = population(game)
                assert now <= last, f"{name}, seed {seed}: population rose"
                last = now


def test_a_run_ends_with_fewer_people_than_it_began():
    game = Game(5)
    start = population(game)
    for _ in range(T.TURNS):
        _by_need(game)
        game.run_season()
    assert population(game) < start
