"""M4: tunnels, post and standing, breeding, and finding the map.

The long-horizon things. Each of them is meant to be affordable once or twice
in ten years, and each of them costs the network something now.
"""

import pytest

from longpost import tuning as T
from longpost.__main__ import Game
from longpost.post import assign


def dig_ready(game):
    """A tunnel site the fleet can actually reach, and who would dig it."""
    for carrier in game.fleet:
        for edge in game.world.known_edges():
            if not edge.tunnel_site or edge.tunnel_built:
                continue
            if carrier.at in (edge.a, edge.b):
                return carrier, edge
    return None, None


# --- tunnels -----------------------------------------------------------------


def test_a_tunnel_takes_seasons_of_labour_and_what_is_carried_to_it():
    game = Game(3)
    world = game.world
    edge = next(e for e in world.edges if e.tunnel_site)
    edge.a = game.fleet[0].at
    carrier = game.fleet[0]
    origin = world.settlements[carrier.at]
    origin.stores["TOOLS"] = 200.0
    origin.stores["FUEL"] = 200.0

    seasons = 0
    while not edge.tunnel_built and seasons < 40:
        # the face wants tools and fuel at whichever end the team is standing
        standing = world.settlements[carrier.at]
        standing.stores["TOOLS"] = 200.0
        standing.stores["FUEL"] = 200.0
        game.select_edge(edge)
        game.selected_carrier = carrier
        runner = game._best_courier(edge)
        if runner is not None:
            game.selected_courier = runner
        game.toggle_digging()
        assert game.plan.for_carrier(carrier.id).digging
        game.run_season()
        seasons += 1

    assert edge.tunnel_built, "a tunnel should be finishable inside ten years"
    assert seasons >= T.TUNNEL_LABOUR, "and never in fewer seasons than the labour"


def test_a_finished_tunnel_is_open_in_every_season_and_never_dangerous():
    from longpost.world import desperation as pressure

    game = Game(3)
    edge = next(e for e in game.world.edges if e.tunnel_site)
    edge.tunnel_built = True
    for season in T.SEASONS:
        assert edge.is_open(season)
    for settlement in game.world.settlements:
        settlement.desperation = 100.0
    danger, source = pressure.edge_danger(game.world, edge, "WINTER")
    assert danger == 0.0 and source == -1


def test_digging_is_a_season_not_carrying():
    game = Game(3)
    carrier, edge = dig_ready(game)
    if carrier is None:
        pytest.skip("this seed's fleet begins nowhere near a collapsed line")
    delivered = carrier.delivered
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.toggle_digging()
    game.run_season()
    assert carrier.delivered == delivered


# --- post and standing -------------------------------------------------------


def test_post_raises_standing_at_both_ends():
    game = Game(3)
    world = game.world
    carrier, edge = next((c, e) for c in game.fleet for e in world.known_edges()
                         if e.is_usable(game.season) and c.at in (e.a, e.b)
                         and c.can_run(game.season, e) and c.reaches(e))
    origin = world.settlements[carrier.at]
    destination = world.settlements[world.other_end(edge, carrier.at)]
    origin.stores["POST"] = 20.0
    before = (origin.standing, destination.standing)

    game.select_edge(edge)
    game.selected_carrier = carrier
    game.adjust_cargo("POST", 3)
    game.run_season()

    assert origin.standing > before[0]
    assert destination.standing > before[1]


def test_a_post_that_carries_nothing_loses_its_standing():
    game = Game(3)
    watched = game.world.known_settlements()[0]
    before = watched.standing
    for _ in range(8):
        game.run_season()
    assert watched.standing < before


def test_a_settlement_that_trusts_the_post_puts_a_neighbour_on_the_chart():
    game = Game(3)
    world = game.world
    carrier, edge = next((c, e) for c in game.fleet for e in world.known_edges()
                         if e.is_usable(game.season) and c.at in (e.a, e.b)
                         and c.can_run(game.season, e) and c.reaches(e))
    destination = world.settlements[world.other_end(edge, carrier.at)]
    destination.standing = 100.0
    unknown = [world.other_end(e, destination.id)
               for e in world.edges_of(destination.id)
               if not world.settlements[world.other_end(e, destination.id)].known]
    if not unknown:
        pytest.skip("this seed's chart already reaches every neighbour")

    world.settlements[carrier.at].stores["POST"] = 20.0
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.adjust_cargo("POST", 2)
    game.run_season()
    assert any(world.settlements[sid].known for sid in unknown)


# --- breeding ----------------------------------------------------------------


def test_a_foal_is_three_years_from_being_any_use():
    game = Game(3)
    while game.season != T.BREED_SEASON:
        game.run_season()
    horse = next(c for c in game.fleet if c.kind in ("FAST_HORSE", "HARDY_HORSE"))
    game.selected_carrier = horse
    game.world.settlements[horse.at].stores["GRAIN"] = 100.0
    fleet = len(game.fleet)
    game.breed()
    assert game.foals and len(game.fleet) == fleet

    for _ in range(T.BREED_YEARS * 4):
        game.run_season()
    assert len(game.fleet) > fleet
    assert not game.foals


def test_horses_are_bred_in_summer_and_out_of_horses():
    game = Game(3)
    while game.season == T.BREED_SEASON:
        game.run_season()
    horse = next(c for c in game.fleet if c.kind in ("FAST_HORSE", "HARDY_HORSE"))
    game.selected_carrier = horse
    game.world.settlements[horse.at].stores["GRAIN"] = 100.0
    game.breed()
    assert not game.foals

    while game.season != T.BREED_SEASON:
        game.run_season()
    boat = next(c for c in game.fleet if c.kind == "SMALL_BOAT")
    game.selected_carrier = boat
    game.world.settlements[boat.at].stores["GRAIN"] = 100.0
    game.breed()
    assert not game.foals
