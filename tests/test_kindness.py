"""Kindness must be mechanically neutral.

The spec's §3.9, and the test it asks for. A player who always ships to
settlements the arithmetic has already ended must not outperform one who never
does, on any measure. If this test ever passes only by luck, the design has
failed and the premise of the game with it.
"""

import pytest

from longpost import tuning as T
from longpost.__main__ import Game
from longpost.post import assign

SEEDS = range(60)          # 60 seeds, two strategies: 120 headless runs


def legs_for(game, carrier):
    return [e for e in game.world.known_edges()
            if e.is_usable(game.season) and carrier.at in (e.a, e.b)
            and carrier.can_run(game.season, e) and carrier.reaches(e)]


def play(seed, serve_the_doomed):
    """The same player twice, differing only in whether they serve the dying."""
    game = Game(seed)
    for _ in range(T.TURNS):
        for carrier in game.fleet:
            legs = legs_for(game, carrier)
            if not legs:
                continue
            origin = game.world.settlements[carrier.at]
            seasons_left = game.seasons_to_winter

            def score(edge):
                other = game.world.settlements[
                    game.world.other_end(edge, carrier.at)]
                load = assign.prospective_load(game.world, origin, other,
                                               carrier.type.capacity)
                doomed = other.doomed(seasons_left)
                if serve_the_doomed and doomed:
                    return -(load + 1000)        # always, and first
                if not serve_the_doomed and doomed:
                    return 1000                  # never
                return -load

            legs.sort(key=score)
            best = legs[0]
            other = game.world.settlements[game.world.other_end(best, carrier.at)]
            if not serve_the_doomed and other.doomed(seasons_left):
                continue                          # would only serve the dying
            game.select_edge(best)
            game.selected_carrier = carrier
            game.load_by_need()
        game.run_season()
    return outcome(game)


def outcome(game):
    world = game.world
    alive = [s for s in world.settlements if s.alive]
    return {
        "population": sum(s.population for s in alive),
        "settlements": len(alive),
        "known standing": sum(s.standing for s in world.known_settlements()),
        "couriers": len([c for c in game.couriers if c.alive]),
        "couriers lost": len([c for c in game.couriers if not c.alive]),
        "delivered": sum(c.delivered for c in game.fleet),
        "worst road": max((e.danger for e in world.known_edges()), default=0.0),
        "desperation": sum(s.desperation for s in world.known_settlements()),
    }


@pytest.fixture(scope="module")
def runs():
    return [(play(seed, True), play(seed, False)) for seed in SEEDS]


def test_kindness_buys_no_population(runs):
    kind = sum(a["population"] for a, _ in runs)
    cold = sum(b["population"] for _, b in runs)
    assert kind <= cold * 1.02, (kind, cold)


def test_kindness_saves_no_settlements(runs):
    kind = sum(a["settlements"] for a, _ in runs)
    cold = sum(b["settlements"] for _, b in runs)
    assert kind <= cold, (kind, cold)


def test_kindness_makes_no_road_safer(runs):
    kind = sum(a["worst road"] for a, _ in runs)
    cold = sum(b["worst road"] for _, b in runs)
    assert kind >= cold * 0.98, (kind, cold)


def test_kindness_calms_nothing(runs):
    kind = sum(a["desperation"] for a, _ in runs)
    cold = sum(b["desperation"] for _, b in runs)
    assert kind >= cold * 0.98, (kind, cold)


def test_kindness_recruits_nobody(runs):
    kind = sum(a["couriers"] for a, _ in runs)
    cold = sum(b["couriers"] for _, b in runs)
    assert kind <= cold * 1.02, (kind, cold)


def test_a_settlement_that_is_ending_is_never_made_calmer_by_a_delivery():
    """The rule itself, where it is enforced."""
    from longpost.world import desperation as pressure
    from longpost.world.settlement import GOODS, NEED_PER_HEAD

    game = Game(3)
    world = game.world
    subject = world.known_settlements()[0]
    subject.population = T.ABANDON_POPULATION + 5
    subject.stores = {g: 0.0 for g in GOODS}
    subject.shortfall = {g: subject.population * NEED_PER_HEAD[g] for g in GOODS}
    assert subject.doomed(2)

    for _ in range(6):
        pressure.settle(world, 2)
    hard = subject.desperation
    assert hard > 0

    # then give it everything, season after season
    for _ in range(6):
        for good in GOODS:
            subject.received[good] = subject.population * NEED_PER_HEAD[good] * 2
            subject.stores[good] = subject.population * NEED_PER_HEAD[good]
        subject.seasons_since_delivery = 0
        pressure.settle(world, 2)
    assert subject.desperation >= hard


def test_a_settlement_that_can_still_be_saved_is_not_called_doomed():
    """The other half of the rule: doom is arithmetic, not pessimism."""
    from longpost.world.settlement import GOODS, NEED_PER_HEAD

    game = Game(3)
    subject = game.world.known_settlements()[0]
    subject.population = 400
    subject.stores = {g: 0.0 for g in GOODS}
    assert not subject.doomed(4)          # short of everything, and still savable
    assert subject.projected_deaths(4) > 0


def test_what_arrived_in_the_last_winter_is_recorded_by_name():
    game = Game(3)
    world = game.world
    subject = world.known_settlements()[0]
    subject.population = T.ABANDON_POPULATION - 5
    subject.received["GRAIN"] = 4.0
    while game.season != "WINTER":
        game.run_season()
    game.run_season()

    assert not subject.alive
    assert any(subject.name in line and "in the winter it ended" in line
               for line, _ in game.log.lines)
    assert any(name == subject.name for _year, name, _what in world.kindnesses)
