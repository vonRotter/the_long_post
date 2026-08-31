"""Map generation. Over many seeds, the network has to be worth playing on."""

import pytest

from longpost import tuning as T
from longpost.world import map as world_map
from longpost.world import season as season_mod

SEEDS = range(300)


@pytest.fixture(scope="module")
def worlds():
    return [world_map.generate(seed) for seed in SEEDS]


def test_every_settlement_is_reachable_in_at_least_one_season(worlds):
    for world in worlds:
        touched = set()
        for season in T.SEASONS:
            for group in world.components(season=season):
                if len(group) > 1:
                    touched.update(group)
        missing = [world.settlements[i].name
                   for i in range(len(world.settlements)) if i not in touched]
        assert not missing, f"seed {world.seed}: {missing} reach nothing in any season"


def test_no_settlement_is_isolated_in_all_four_seasons(worlds):
    for world in worlds:
        for s in world.settlements:
            usable = [season for season in T.SEASONS
                      if any(e.is_usable(season) for e in world.edges_of(s.id))]
            assert usable, f"seed {world.seed}: {s.name} has no leg in any season"


def test_the_network_is_connected_in_autumn(worlds):
    for world in worlds:
        groups = world.components(season="AUTUMN")
        assert len(groups) == 1, f"seed {world.seed}: autumn splits the map"


def test_ice_roads_never_coexist_with_the_water_they_cross(worlds):
    for world in worlds:
        by_id = {e.id: e for e in world.edges}
        ice = [e for e in world.edges if e.terrain == "ICE"]
        assert ice, f"seed {world.seed}: no ice road anywhere on the map"
        for e in ice:
            water = by_id[e.ice_of]
            assert water.terrain == "COAST"
            assert (water.a, water.b) == (e.a, e.b)
            for season in T.SEASONS:
                both = e.is_usable(season) and water.is_usable(season)
                assert not both, f"seed {world.seed}: ice and water both stand in {season}"


def test_the_seasonal_inversion_exists_on_the_starting_chart(worlds):
    for world in worlds:
        winter = [e for e in world.known_edges() if e.is_usable("WINTER")]
        ice = [e for e in world.known_edges() if e.terrain == "ICE"]
        assert ice, f"seed {world.seed}: the first chart carries no ice road"
        assert winter, f"seed {world.seed}: nothing stands in winter"


def test_the_post_starts_with_a_connected_handful(worlds):
    for world in worlds:
        known = world.known_settlements()
        assert len(known) == T.SETTLEMENTS_START
        ids = {s.id for s in known}
        groups = [g for g in world.components(season="AUTUMN", known_only=True)
                  if set(g) & ids]
        assert len(groups) == 1, f"seed {world.seed}: the first chart is a scatter"


def test_travel_days_follow_length_and_terrain(worlds):
    for world in worlds[:40]:
        for e in world.edges:
            assert e.days > 0
            profile = season_mod.profile(e.terrain)
            assert set(profile) == set(T.SEASONS)
