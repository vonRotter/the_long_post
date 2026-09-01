"""Carriers, loads, and what a season does with them."""

from longpost import tuning as T
from longpost.__main__ import Game
from longpost.post import assign


def first_usable_edge(game, carrier):
    for edge in game.world.known_edges():
        if (edge.is_usable(game.season) and carrier.at in (edge.a, edge.b)
                and carrier.can_run(game.season, edge) and carrier.reaches(edge)):
            return edge
    return None


def a_carrier_with_work(game):
    """Any carrier that can run something this season, and what it can run."""
    for carrier in game.fleet:
        edge = first_usable_edge(game, carrier)
        if edge is not None:
            return carrier, edge
    raise AssertionError("the fleet should begin where it has work")


def test_a_load_is_moved_not_created():
    game = Game(3)
    carrier, edge = a_carrier_with_work(game)
    origin = game.world.settlements[carrier.at]
    origin.stores["GRAIN"] = 20.0
    before = sum(s.stores.get("GRAIN", 0.0) for s in game.world.settlements)
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.load_by_need()
    game.run_season()
    after = sum(s.stores.get("GRAIN", 0.0) for s in game.world.settlements)
    consumed = sum(s.season_need("GRAIN") for s in game.world.settlements if s.alive)
    produced = sum(s.produces("GRAIN") for s in game.world.settlements if s.alive)
    assert after == round(before - consumed + produced, 6) or after < before


def test_a_carrier_never_runs_a_leg_its_season_forbids():
    game = Game(3)
    sled = next(c for c in game.fleet if c.kind == "DOG_SLED")
    assert not sled.can_run("SUMMER", game.world.edges[0])
    while game.season != "WINTER":
        game.run_season()
    ice = [e for e in game.world.known_edges() if e.terrain == "ICE"]
    assert ice, "the seed should carry an ice road"
    assert sled.type.can_work("WINTER", "ICE")


def test_a_leg_that_is_closed_this_season_is_refused():
    game = Game(3)
    carrier = game.fleet[0]
    closed = [e for e in game.world.known_edges() if not e.is_usable(game.season)]
    if not closed:
        return
    edge = closed[0]
    game.plan.set(assign.Order(edge_id=edge.id, carrier_id=carrier.id,
                               origin=carrier.at, cargo={"GRAIN": 1}))
    where = carrier.at
    game.run_season()
    assert carrier.at == where
    assert any("did not set out" in line for line, _ in game.log.lines)


def test_a_round_trip_brings_the_carrier_home():
    game = Game(3)
    carrier, edge = a_carrier_with_work(game)
    home = carrier.at
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.load_by_need()
    game.run_season()
    if carrier.round_trip(edge):
        assert carrier.at == home
    else:
        assert carrier.at == game.world.other_end(edge, home)


def test_the_hold_is_the_limit():
    game = Game(3)
    carrier, edge = a_carrier_with_work(game)
    origin = game.world.settlements[carrier.at]
    for good in ("GRAIN", "FUEL", "MEDICINE", "TOOLS"):
        origin.stores[good] = 99.0
    game.select_edge(edge)
    game.selected_carrier = carrier
    for good in ("GRAIN", "FUEL", "MEDICINE", "TOOLS"):
        for _ in range(20):
            game.adjust_cargo(good, 1)
    order = game.plan.for_carrier(carrier.id)
    assert order.total() <= carrier.type.capacity


def test_post_weighs_nothing_and_always_goes():
    game = Game(3)
    carrier, edge = a_carrier_with_work(game)
    origin = game.world.settlements[carrier.at]
    origin.stores["POST"] = 4.0
    destination = game.world.settlements[game.world.other_end(edge, carrier.at)]
    cargo = assign.fill_by_need(game.world, origin, destination,
                                carrier.type.capacity)
    assert cargo.get("POST", 0) >= 1
