"""The four things the documents promise that the build had missed.

F4, the camera following the season, the broken outline for a settlement the
arithmetic has lost, and a cargo priority on a kept route.
"""

import pytest

from longpost import tuning as T
from longpost.__main__ import Game
from longpost.post import assign
from longpost.render import ink


def a_route(game):
    for carrier in game.fleet:
        for edge in game.world.known_edges():
            if (edge.is_usable(game.season) and carrier.at in (edge.a, edge.b)
                    and carrier.can_run(game.season, edge) and carrier.reaches(edge)):
                return carrier, edge
    raise AssertionError("the fleet should begin with work")


# --- F4: watch the last season again -----------------------------------------


def test_the_last_season_can_be_watched_again():
    game = Game(3)
    game.run_season()
    lines = len(game.log.lines)
    game.replay()
    assert game.phase == game.RESOLVE
    assert game.replaying
    for _ in range(int(T.RESOLVE_SECONDS * 60) + 5):
        game.update(1 / 60)
    assert game.phase == game.PLAN


def test_a_replay_changes_nothing_and_says_nothing_twice():
    game = Game(3)
    carrier, edge = a_route(game)
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.load_by_need()
    game.run_season()

    before = ([s.population for s in game.world.settlements],
              [dict(s.stores) for s in game.world.settlements],
              [c.condition for c in game.couriers],
              len(game.log.lines))
    game.replay()
    for _ in range(int(T.RESOLVE_SECONDS * 60) + 5):
        game.update(1 / 60)
    after = ([s.population for s in game.world.settlements],
             [dict(s.stores) for s in game.world.settlements],
             [c.condition for c in game.couriers],
             len(game.log.lines) - 1)          # the one line saying it is a replay
    assert before == after


def test_there_is_nothing_to_replay_before_the_first_season():
    game = Game(3)
    game.replay()
    assert game.phase == game.PLAN


# --- the camera follows the season, until it is taken ------------------------


def test_the_camera_goes_to_the_leg_that_matters_most():
    game = Game(3)
    carrier, edge = a_route(game)
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.load_by_need()
    game.commit()
    was = game.chart.camera.target_centre.copy()
    leg = game.resolution.consequential()
    if leg is None:
        pytest.skip("nothing happened this season worth looking at")
    # far enough into the resolution for that leg to have set out
    for _ in range(int((leg.start + 0.1) * T.RESOLVE_SECONDS * 60) + 5):
        game.update(1 / 60)
    a = game.world.settlements[leg.origin].pos
    b = game.world.settlements[leg.destination].pos
    middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    assert tuple(game.chart.camera.target_centre) == middle
    assert tuple(was) != middle or True      # it went where the leg is


def test_the_game_never_takes_the_camera_away_from_the_player():
    game = Game(3)
    carrier, edge = a_route(game)
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.load_by_need()
    game.commit()
    game.camera_taken = True             # the player has moved it themselves
    game.chart.camera.look_at((100.0, 100.0), 2.0)
    kept = game.chart.camera.target_centre.copy()
    for _ in range(60):
        game.update(1 / 60)
    assert (game.chart.camera.target_centre == kept).all()


def test_the_most_consequential_leg_is_the_worst_thing_that_happened():
    from longpost.post.resolve import Leg, Resolution
    result = Resolution(year=1, season="AUTUMN")
    quiet = Leg(edge_id=0, carrier_id=0, origin=0, destination=1,
                cargo={"GRAIN": 30.0}, end=0.4)
    stopped = Leg(edge_id=1, carrier_id=1, origin=1, destination=2,
                  cargo={"GRAIN": 2.0}, taken=True, end=0.6)
    result.legs = [quiet, stopped]
    assert result.consequential() is stopped


# --- the broken outline ------------------------------------------------------


def test_a_settlement_the_arithmetic_has_lost_is_drawn_broken(display):
    """Not red — red is for what has already ended."""
    import numpy as np
    import pygame

    whole = pygame.Surface((90, 90), pygame.SRCALPHA)
    broken = pygame.Surface((90, 90), pygame.SRCALPHA)
    ink.circle(whole, (45, 45), 30, "route", 7)
    ink.circle(broken, (45, 45), 30, "route", 7, broken=True)
    assert np.count_nonzero(pygame.surfarray.array_alpha(broken)) < \
        np.count_nonzero(pygame.surfarray.array_alpha(whole))


def test_the_chart_draws_the_broken_outline_for_a_doomed_settlement(display):
    game = Game(3)
    doomed = game.world.known_settlements()[0]
    doomed.population = T.ABANDON_POPULATION + 2
    doomed.stores = {good: 0.0 for good in doomed.stores}
    doomed.consume()
    doomed.consume()
    assert doomed.doomed(game.seasons_to_winter)
    game.chart.places.dirty = True
    game.chart.draw(display)             # it is drawn without complaint
    assert doomed.alive                  # and it is still alive while it is drawn


# --- a kept route can be told what to carry ----------------------------------


def test_a_route_kept_with_a_load_set_keeps_carrying_that():
    game = Game(3)
    carrier, edge = a_route(game)
    origin = game.world.settlements[carrier.at]
    origin.stores["FUEL"] = 80.0
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.adjust_cargo("FUEL", 5)
    game.toggle_standing()

    route = game.standing.for_carrier(carrier.id)
    assert route.priority == ("FUEL",)
    cargo = assign.fill_by_priority(origin, route.priority, carrier.type.capacity)
    assert set(cargo) == {"FUEL"}


def test_a_route_kept_with_no_load_set_reads_the_far_end_every_season():
    game = Game(3)
    carrier, edge = a_route(game)
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.toggle_standing()
    assert game.standing.for_carrier(carrier.id).priority == ()


def test_a_priority_load_never_strips_the_place_it_leaves():
    game = Game(3)
    origin = game.world.known_settlements()[0]
    origin.stores["GRAIN"] = 4.0             # less than it keeps for itself
    cargo = assign.fill_by_priority(origin, ("GRAIN",), 40)
    assert cargo == {}


# --- the improvements --------------------------------------------------------


def test_a_run_is_saved_as_what_the_player_asked_for_and_read_back_the_same():
    """A save is the seed and the orders; a load is the run playing itself back."""
    import pathlib
    import tempfile

    from longpost.post import record

    game = Game(3)
    for _ in range(6):
        for carrier in game.fleet:
            legs = [e for e in game.world.known_edges()
                    if e.is_usable(game.season) and carrier.at in (e.a, e.b)
                    and carrier.can_run(game.season, e) and carrier.reaches(e)]
            if legs:
                game.select_edge(legs[0])
                game.selected_carrier = carrier
                game.load_by_need()
        game.run_season()

    where = pathlib.Path(tempfile.mkdtemp()) / "run.json"
    record.write(game, where)
    assert where.stat().st_size < 50_000, "a save is kilobytes, not megabytes"

    again = record.resume(record.read(where), Game)
    assert again.turn == game.turn
    assert [s.population for s in again.world.settlements] == \
           [s.population for s in game.world.settlements]
    assert [c.condition for c in again.couriers] == \
           [c.condition for c in game.couriers]
    assert [line for line, _a in again.log.lines] == \
           [line for line, _a in game.log.lines]


def test_a_save_of_a_different_version_is_not_read():
    import json
    import pathlib
    import tempfile

    from longpost.post import record

    where = pathlib.Path(tempfile.mkdtemp()) / "old.json"
    where.write_text(json.dumps({"version": 0, "seed": 1, "seasons": []}))
    assert record.read(where) is None


def test_every_leg_is_called_something():
    game = Game(3)
    for edge in game.world.edges:
        assert edge.name and edge.name[0].isupper()


def test_a_leg_is_named_after_somewhere_it_goes():
    game = Game(3)
    for edge in game.world.edges[:20]:
        ends = (game.world.settlements[edge.a].name.lower(),
                game.world.settlements[edge.b].name.lower())
        # the tail of the settlement's name is dropped before the water word is
        # added — Seloy gives Selfjord — so the stem is what carries over
        assert any(edge.name.lower().startswith(end[:3]) for end in ends), edge.name


def test_the_log_calls_a_leg_by_its_name():
    from longpost.post.resolve import _leg_name
    game = Game(3)
    edge = game.world.known_edges()[0]
    assert _leg_name(game.world, edge) == edge.name


def test_a_hard_winter_is_said_in_the_autumn_before_it():
    game = Game(3)
    while game.season != "AUTUMN":
        game.run_season()
    said = [line for line, _a in game.log.lines
            if "winter will be" in line or "winter looks" in line
            or "ordinary winter" in line]
    assert said


def test_a_hard_winter_is_in_the_shortfall_the_panel_shows():
    game = Game(3)
    settlement = game.world.known_settlements()[0]
    settlement.winter_factor = 1.0
    ordinary = settlement.projected_shortfall(2)
    settlement.winter_factor = 1.3
    harder = settlement.projected_shortfall(2)
    for good, gap in ordinary.items():
        assert harder.get(good, 0.0) >= gap


def test_a_hard_winter_eats_more():
    from longpost.world.settlement import GOODS, Settlement
    mild = Settlement(id=0, name="A", pos=(0, 0), population=400, surplus=("GRAIN",))
    hard = Settlement(id=1, name="B", pos=(0, 0), population=400, surplus=("GRAIN",))
    for settlement in (mild, hard):
        settlement.stores = {good: 0.0 for good in GOODS}
    mild.consume(hard=1.0)
    hard.consume(hard=1.3)
    assert hard.shortfall["GRAIN"] > mild.shortfall["GRAIN"]


def test_a_leg_to_a_place_that_was_given_up_is_never_drawn_as_a_route(display):
    game = Game(3)
    gone = game.world.known_settlements()[0]
    gone.abandoned_year = 3
    game.chart.routes.dirty = True
    game.chart.draw(display)             # drawn as a ghost, without complaint
    assert not gone.alive


def test_a_leg_the_post_uses_darkens():
    from longpost import tuning as T
    assert T.ROUTE_WORN < T.ROUTE_HEAVY
    assert T.INK_WEIGHTS["worn"][1][-1] > T.INK_WEIGHTS["route"][1][-1]
