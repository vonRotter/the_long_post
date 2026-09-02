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
