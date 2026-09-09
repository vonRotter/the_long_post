"""M5: standing orders, and reporting by exception.

Delegation is not an unlock. It is available from the first turn and becomes
necessary, which is the honest version of that transition: the network outgrows
the player's attention rather than granting them something.
"""

import pytest

from longpost import tuning as T
from longpost.__main__ import Game
from longpost.post import assign


def a_route(game):
    for carrier in game.fleet:
        for edge in game.world.known_edges():
            if (edge.is_usable(game.season) and carrier.at in (edge.a, edge.b)
                    and carrier.can_run(game.season, edge) and carrier.reaches(edge)):
                return carrier, edge
    raise AssertionError("the fleet should begin with work")


def keep_everything(game):
    for carrier in game.fleet:
        legs = [e for e in game.world.known_edges()
                if carrier.at in (e.a, e.b) and carrier.reaches(e)]
        if not legs:
            continue
        game.select_edge(legs[0])
        game.selected_carrier = carrier
        game.toggle_standing()


# --- keeping a route ---------------------------------------------------------


def test_a_kept_route_runs_itself_season_after_season():
    game = Game(3)
    carrier, edge = a_route(game)
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.toggle_standing()
    assert len(game.standing) == 1

    for _ in range(8):
        game.run_season()
    assert game.standing.for_carrier(carrier.id).runs > 0
    assert carrier.runs > 0


def test_keeping_a_route_is_available_from_the_first_turn():
    game = Game(3)
    assert game.turn == 0
    carrier, edge = a_route(game)
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.toggle_standing()
    assert len(game.standing) == 1


def test_a_route_is_dropped_as_easily_as_it_is_kept():
    game = Game(3)
    carrier, edge = a_route(game)
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.toggle_standing()
    game.toggle_standing()
    assert len(game.standing) == 0


def test_an_order_the_player_gave_is_never_overruled_by_a_kept_route():
    game = Game(3)
    carrier, edge = a_route(game)
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.toggle_standing()

    other = next((e for e in game.world.known_edges()
                  if e is not edge and e.is_usable(game.season)
                  and carrier.at in (e.a, e.b) and carrier.can_run(game.season, e)
                  and carrier.reaches(e)), None)
    if other is None:
        pytest.skip("this seed gives the carrier only one leg to work")
    game.select_edge(other)
    game.selected_carrier = carrier
    game.load_by_need()
    game.commit()
    assert game.plan_at_commit[carrier.id].edge_id == other.id


def test_a_kept_route_takes_whoever_is_fit_unless_a_courier_is_named():
    game = Game(3)
    carrier, edge = a_route(game)
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.toggle_standing()
    assert game.standing.for_carrier(carrier.id).courier_id == -1

    game.toggle_standing()
    game.pin_courier = True
    game.selected_courier = game._best_courier(edge)
    game.toggle_standing()
    assert game.standing.for_carrier(carrier.id).courier_id >= 0


# --- reporting by exception --------------------------------------------------


def test_a_season_of_routine_runs_is_counted_rather_than_recited():
    game = Game(3)
    keep_everything(game)
    game.run_season()
    lines = [line for line, _accent in game.log.lines]
    assert any("went as they were meant to" in line for line in lines), lines
    assert not any("carried" in line and "went as they" not in line
                   for line in lines[-4:])


def test_what_went_wrong_is_never_collapsed():
    game = Game(7)
    keep_everything(game)
    seen = False
    for _ in range(T.TURNS):
        game.run_season()
        for line, _accent in game.log.lines:
            if "was stopped" in line or "was lost" in line or "took" in line:
                seen = True
    assert seen, "ten years of kept routes should throw up something"


def test_a_kept_route_that_can_send_nothing_says_so_and_then_stops_saying_it():
    game = Game(3)
    carrier, edge = a_route(game)
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.toggle_standing()
    # nothing anywhere to carry
    for settlement in game.world.settlements:
        settlement.stores = {g: 0.0 for g in settlement.stores}

    said = []
    for _ in range(6):
        before = len(game.log.lines)
        game.run_season()
        said.append(any("nothing to carry" in line or "nobody to send" in line
                        or "is not on the" in line
                        for line, _ in game.log.lines[before:]))
    assert said[0], "a stalled route should report the first season"
    assert not all(said), "and not every season after it"


def test_a_courier_who_is_wearing_down_is_reported_without_being_asked_for():
    """The line that brings somebody back to the player's attention."""
    game = Game(3)
    carrier, edge = a_route(game)
    game.select_edge(edge)
    game.selected_carrier = carrier
    runner = game._best_courier(edge)
    game.pin_courier = True
    game.selected_courier = runner
    game.toggle_standing()

    for _ in range(T.TURNS):
        runner.condition = min(runner.condition, 90.0)
        game.run_season()
        if any(f"{runner.name} is worn" in line or f"{runner.name} is spent" in line
               for line, _accent in game.log.lines):
            return
    raise AssertionError(f"{runner.name} wore down and nobody said so")


def test_a_courier_coming_back_to_themselves_is_not_news():
    game = Game(3)
    carrier, edge = a_route(game)
    runner = game._best_courier(edge)
    runner.condition = 40.0
    for _ in range(6):
        game.run_season()
    said = [line for line, _accent in game.log.lines if f"{runner.name} is fit" in line]
    assert not said, said
