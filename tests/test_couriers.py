"""Couriers: people, not stat blocks.

The tests the spec asks for at M3: theft is monotonic in every pressure, never
fires without at least two pressures the player could have seen, and always
sends the load to a settlement on the map; and a courier who is lost stays in
the panel with their record beside them.
"""

import pytest

from longpost import tuning as T
from longpost.__main__ import Game
from longpost.post import courier as courier_mod
from longpost.post.courier import Courier


def a_courier(game, home=None):
    home = home if home is not None else game.world.known_settlements()[0].id
    return Courier(id=0, name="Sigrid Berg", home=home, at=home)


def a_leg(game):
    return game.world.known_edges()[0]


# --- condition, rest, familiarity --------------------------------------------


def test_a_courier_is_worn_by_running_and_recovers_by_resting():
    game = Game(3)
    runner = a_courier(game)
    edge = a_leg(game)
    runner.ran(1, "AUTUMN", edge, hard=False)
    worn = runner.condition
    assert worn < 100.0
    runner.rested()
    assert runner.condition > worn


def test_consecutive_seasons_cost_more_than_the_first():
    game = Game(3)
    edge = a_leg(game)
    runner = a_courier(game)
    runner.ran(1, "AUTUMN", edge, hard=False)
    first = 100.0 - runner.condition
    before = runner.condition
    runner.ran(1, "WINTER", edge, hard=False)
    assert before - runner.condition > first


def test_a_hard_season_costs_more_than_an_open_one():
    game = Game(3)
    edge = a_leg(game)
    easy, hard = a_courier(game), a_courier(game)
    easy.ran(1, "AUTUMN", edge, hard=False)
    hard.ran(1, "WINTER", edge, hard=True)
    assert hard.condition < easy.condition


def test_a_leg_run_before_is_easier_and_the_count_is_visible():
    game = Game(3)
    edge = a_leg(game)
    runner = a_courier(game)
    assert runner.runs_on(edge.id) == 0
    for _ in range(4):
        runner.ran(1, "AUTUMN", edge, hard=False)
        runner.rested()
    assert runner.runs_on(edge.id) == 4
    assert 0 < runner.familiarity(edge.id) <= T.FAMILIARITY_CAP


def test_a_spent_courier_is_not_sent():
    game = Game(3)
    runner = a_courier(game)
    runner.condition = T.CONDITION_UNFIT - 1
    assert not runner.fit_for(a_leg(game))


def test_the_risk_of_a_run_follows_condition_and_the_road():
    game = Game(3)
    edge = a_leg(game)
    runner = a_courier(game)
    assert runner.risk_on(edge) == 0.0
    runner.condition = 40.0
    worn = runner.risk_on(edge)
    assert worn > 0.0
    edge.danger = 0.8
    assert runner.risk_on(edge) > worn


# --- theft -------------------------------------------------------------------


def pressures_with(**overrides):
    base = {"disloyalty": 0.0, "condition": 0.0, "home need": 0.0,
            "route need": 0.0, "cargo": 0.0}
    base.update(overrides)
    return base


def test_with_every_pressure_at_its_lowest_theft_never_happens():
    assert courier_mod.theft_chance(pressures_with()) == 0.0


def test_theft_never_fires_on_one_pressure_alone():
    for name in ("disloyalty", "condition", "home need", "route need", "cargo"):
        assert courier_mod.theft_chance(pressures_with(**{name: 1.0})) == 0.0


def test_theft_is_monotonic_in_every_pressure():
    for name in ("disloyalty", "condition", "home need", "route need", "cargo"):
        last = -1.0
        for value in (0.0, 0.3, 0.6, 1.0):
            # a second pressure, so the two-pressure rule is not what is being read
            chance = courier_mod.theft_chance(
                pressures_with(**{name: value, "route need": 0.9})
                if name != "route need" else pressures_with(**{name: value,
                                                               "home need": 0.9}))
            assert chance >= last, name
            last = chance


def test_every_pressure_behind_a_theft_was_on_the_panel():
    game = Game(3)
    runner = a_courier(game)
    runner.loyalty = 5.0
    runner.condition = 20.0
    game.world.settlements[runner.home].desperation = 95.0
    edge = a_leg(game)
    destination = game.world.settlements[edge.b]
    pressures = courier_mod.theft_pressures(game.world, runner, edge,
                                            {"GRAIN": 4}, destination)
    visible = courier_mod.visible_pressures(pressures)
    assert len(visible) >= T.THEFT_PRESSURES_NEEDED
    assert courier_mod.theft_chance(pressures) > 0


def test_a_stolen_load_always_goes_to_a_settlement_on_the_map():
    game = Game(3)
    world = game.world
    carrier, edge = next((c, e) for c in game.fleet for e in world.known_edges()
                         if e.is_usable(game.season) and c.at in (e.a, e.b)
                         and c.can_run(game.season, e) and c.reaches(e))
    runner = next(c for c in game.couriers if c.at in (edge.a, edge.b))
    runner.loyalty = 0.0
    runner.condition = 30.0
    world.settlements[runner.home].desperation = 100.0
    world.settlements[carrier.at].stores["GRAIN"] = 40.0

    game.select_edge(edge)
    game.selected_carrier = carrier
    game.selected_courier = runner
    game.adjust_cargo("GRAIN", 5)
    game.run_season()

    for leg in game.last_resolution.legs:
        if leg.stolen:
            assert 0 <= runner.home < len(world.settlements)
            assert world.settlements[runner.home].known
            assert any("took" in line for line, _ in game.log.lines)


# --- loss --------------------------------------------------------------------


def test_a_lost_courier_stays_in_the_panel_with_their_record():
    """§3.7. The name is never removed and the record never shortened."""
    game = Game(3)
    runner = game.couriers[0]
    edge = a_leg(game)
    for _ in range(3):
        runner.ran(2, "WINTER", edge, hard=True)
    from longpost.post.resolve import Resolution, _lose
    result = Resolution(year=2, season="WINTER")
    _lose(result, game.world, runner, edge, 2, "WINTER", 0.5)

    assert runner in game.couriers          # never taken off the list
    assert not runner.alive
    assert runner.lost_where
    assert runner.history()                 # the record is still there
    assert (2, runner.name) in edge.losses  # and the leg carries the mark
    said = [line for _at, line, _accent in result.lines]
    assert len(said) == 1, "a loss is one plain sentence and no more"
    for word in ("tragic", "sadly", "bravely", "heroic"):
        assert word not in said[0].lower()


def test_the_game_never_mentions_a_lost_courier_again():
    game = Game(7)
    for _ in range(T.TURNS):
        for carrier in game.fleet:
            legs = [e for e in game.world.known_edges()
                    if e.is_usable(game.season) and carrier.at in (e.a, e.b)
                    and carrier.can_run(game.season, e) and carrier.reaches(e)]
            if legs:
                game.select_edge(legs[0])
                game.selected_carrier = carrier
                game.load_by_need()
        game.run_season()

    for runner in game.couriers:
        if runner.alive:
            continue
        lines = [line for line, _accent in game.log.lines]
        loss = next(i for i, line in enumerate(lines)
                    if runner.name in line and ("was lost" in line
                                                or "did not come back" in line))
        after = [line for line in lines[loss + 1:] if runner.name in line]
        assert not after, f"{runner.name} is mentioned after being lost: {after}"


# --- recruitment -------------------------------------------------------------


def test_recruits_come_from_settlements_with_nothing_left_to_keep_them():
    game = Game(3)
    world = game.world
    before = len(game.couriers)
    for settlement in world.known_settlements():
        settlement.desperation = 0.0
    while game.season != "SPRING":
        game.run_season()
    game.run_season()
    assert len(game.couriers) == before, "a calm map should offer nobody"

    for settlement in world.known_settlements():
        settlement.desperation = 100.0
        settlement.standing = 80.0
    for _ in range(4):
        game.run_season()
    assert len(game.couriers) > before
    for runner in game.couriers[before:]:
        assert world.settlements[runner.home].known
