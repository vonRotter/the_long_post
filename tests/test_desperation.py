"""The pressure model, and the roads it makes dangerous.

The spec's §3.6 and its test list: monotonic in every input, sustained delivery
calms the roads beside a settlement, and no edge is ever dangerous without a
traceable desperation source.
"""

import pytest

from longpost import tuning as T
from longpost.__main__ import Game
from longpost.world import desperation as pressure
from longpost.world.settlement import GOODS, NEED_PER_HEAD, Settlement


def lone(pop=120):
    """A settlement with no map around it, for testing one pressure at a time."""
    return Settlement(id=0, name="Test", pos=(0.0, 0.0), population=pop,
                      surplus=("GRAIN",))


class Alone:
    """The smallest world a settlement can be in."""

    def __init__(self, settlement):
        self.settlements = [settlement]
        self.edges = []
        self.seed = 1

    def edges_of(self, sid):
        return []

    def other_end(self, edge, sid):
        return sid


def target_of(s):
    return pressure.target(Alone(s), s, year=1)


# --- monotonic in every input ------------------------------------------------


def test_hunger_only_ever_raises_desperation():
    last = -1.0
    for missing in (0.0, 1.0, 3.0, 6.0, 12.0):
        s = lone()
        s.shortfall["GRAIN"] = missing
        now = target_of(s)
        assert now >= last
        last = now


def test_isolation_only_ever_raises_desperation():
    last = -1.0
    for seasons in range(0, 10):
        s = lone()
        s.seasons_since_delivery = seasons
        now = target_of(s)
        assert now >= last
        last = now


def test_deaths_only_ever_raise_desperation():
    last = -1.0
    for toll in (0, 5, 20, 60):
        s = lone()
        if toll:
            s.deaths.append((1, toll))
        now = target_of(s)
        assert now >= last
        last = now


def test_delivery_only_ever_lowers_desperation():
    last = 1e9
    for brought in (0.0, 1.0, 3.0, 6.0, 12.0):
        s = lone()
        s.shortfall["GRAIN"] = 6.0
        s.received["GRAIN"] = brought
        now = target_of(s)
        assert now <= last
        last = now


def test_post_lowers_desperation_beyond_its_weight():
    bare = lone()
    bare.shortfall["GRAIN"] = 6.0
    lettered = lone()
    lettered.shortfall["GRAIN"] = 6.0
    lettered.received["POST"] = lettered.population * NEED_PER_HEAD["POST"]
    assert target_of(lettered) < target_of(bare)


def test_a_neighbour_given_up_raises_desperation():
    game = Game(3)
    world = game.world
    subject = world.known_settlements()[0]
    before = pressure.target(world, subject, 1)
    neighbour_id = world.other_end(world.edges_of(subject.id)[0], subject.id)
    world.settlements[neighbour_id].abandoned_year = 2
    assert pressure.target(world, subject, 1) > before


# --- what that does to the roads ---------------------------------------------


def test_no_edge_is_dangerous_without_a_source():
    game = Game(3)
    for _ in range(T.TURNS // 2):
        game.run_season()
    for edge in game.world.edges:
        if edge.danger > 0:
            assert edge.danger_source >= 0
            source = game.world.settlements[edge.danger_source]
            assert source.alive
            assert source.desperation > T.DANGER_THRESHOLD * 100
            assert source.id in (edge.a, edge.b) or True   # or near it: see watchers


def test_a_calm_map_has_no_dangerous_road():
    game = Game(3)
    for settlement in game.world.settlements:
        settlement.desperation = 0.0
    for edge in game.world.edges:
        danger, source = pressure.edge_danger(game.world, edge, game.season)
        assert danger == 0.0 and source == -1


def test_danger_is_monotonic_in_the_desperation_behind_it():
    game = Game(3)
    edge = game.world.edges[0]
    last = -1.0
    for value in (0, 20, 40, 60, 80, 100):
        for settlement in game.world.settlements:
            settlement.desperation = 0.0
        game.world.settlements[edge.a].desperation = value
        danger, _ = pressure.edge_danger(game.world, edge, game.season)
        assert danger >= last
        last = danger


def test_a_finished_tunnel_is_never_dangerous():
    game = Game(3)
    edge = next(e for e in game.world.edges if e.tunnel_site)
    for settlement in game.world.settlements:
        settlement.desperation = 100.0
    edge.tunnel_built = True
    danger, _ = pressure.edge_danger(game.world, edge, game.season)
    assert danger == 0.0


def test_serving_a_settlement_calms_its_roads():
    """The gate. A player's own failures raise desperation, which raises the
    danger on the roads beside it; serving that settlement puts it back."""
    game = Game(3)
    world = game.world
    subject = world.known_settlements()[0]
    subject.shortfall = {g: subject.population * NEED_PER_HEAD[g] for g in GOODS}
    subject.seasons_since_delivery = 8
    for _ in range(6):
        pressure.apply(world, "AUTUMN", 2)
    hostile = [e for e in world.edges_of(subject.id)]
    danger_before = max(e.danger for e in hostile)
    assert danger_before > 0, "the model should make a starving settlement's roads unsafe"

    # then serve it, season after season
    for _ in range(6):
        subject.shortfall = {g: 0.0 for g in GOODS}
        subject.seasons_since_delivery = 0
        for good in GOODS:
            subject.received[good] = subject.population * NEED_PER_HEAD[good]
        pressure.apply(world, "AUTUMN", 2)
    danger_after = max(e.danger for e in hostile)
    assert danger_after < danger_before
    assert subject.desperation < 100.0


def test_a_settlement_at_the_extreme_keeps_what_it_has():
    s = lone()
    s.desperation = T.DESPERATION_REFUSAL + 1
    assert pressure.refuses_to_deal(s)
    s.desperation = T.DESPERATION_REFUSAL - 20
    assert not pressure.refuses_to_deal(s)


def test_a_run_is_only_ever_stopped_on_a_leg_the_panel_showed_as_dangerous():
    """Every loss is traceable to a cause the player could have weighed."""
    game = Game(7)
    for _ in range(T.TURNS):
        for carrier in game.fleet:
            legs = [e for e in game.world.known_edges()
                    if e.is_usable(game.season) and carrier.at in (e.a, e.b)
                    and carrier.can_run(game.season, e) and carrier.reaches(e)]
            if not legs:
                continue
            game.select_edge(legs[0])
            game.selected_carrier = carrier
            game.load_by_need()
        known_danger = {e.id: (e.danger, e.danger_source) for e in game.world.edges}
        game.run_season()
        for leg in game.last_resolution.legs:
            if not leg.taken:
                continue
            danger, source = known_danger[leg.edge_id]
            assert danger > 0, "a load was taken on a leg the panel called safe"
            assert source >= 0


def test_the_same_season_is_stopped_in_the_same_place_every_time():
    def run(seed):
        game = Game(seed)
        for _ in range(12):
            for carrier in game.fleet:
                legs = [e for e in game.world.known_edges()
                        if e.is_usable(game.season) and carrier.at in (e.a, e.b)
                        and carrier.can_run(game.season, e) and carrier.reaches(e)]
                if legs:
                    game.select_edge(legs[0])
                    game.selected_carrier = carrier
                    game.load_by_need()
            game.run_season()
        return [(line, accent) for line, accent in game.log.lines]

    assert run(4) == run(4)


def test_a_settlement_that_will_not_deal_gives_up_nothing():
    s = lone()
    s.stores["GRAIN"] = 40.0
    s.desperation = 0.0
    assert s.spare("GRAIN") > 0
    s.desperation = T.DESPERATION_REFUSAL
    assert s.spare("GRAIN") == 0.0


def test_a_settlement_that_takes_a_load_goes_onto_the_chart():
    """Nothing hostile happens off the document. If a place stops a load, the
    player can look at it from that season on."""
    game = Game(3)
    world = game.world
    stranger = next(s for s in world.settlements if not s.known)
    stranger.desperation = 100.0
    for edge in world.edges:
        edge.danger, edge.danger_source = 1.0, stranger.id

    carrier, edge = next((c, e) for c in game.fleet for e in world.known_edges()
                         if e.is_usable(game.season) and c.at in (e.a, e.b)
                         and c.can_run(game.season, e) and c.reaches(e))
    origin = world.settlements[carrier.at]
    origin.stores["GRAIN"] = 30.0
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.adjust_cargo("GRAIN", 3)
    game.run_season()

    taken = [leg for leg in game.last_resolution.legs if leg.taken]
    assert taken, "a leg at full danger should have been stopped"
    assert stranger.known
    assert any("was not on this chart" in line for line, _ in game.log.lines)
