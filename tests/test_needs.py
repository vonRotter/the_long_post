"""Needs, and what happens when they are not met.

The delay is the point: what is not shipped in autumn is counted in February.
"""

import pytest

from longpost import tuning as T
from longpost.world.settlement import GOODS, NEED_PER_HEAD, Settlement


def settlement(pop=120, surplus=("GRAIN",)):
    return Settlement(id=0, name="Test", pos=(0.0, 0.0), population=pop,
                      surplus=surplus)


def supply(s, share=1.0):
    """Give it exactly a season's needs, or a share of them."""
    for good in GOODS:
        s.stores[good] = s.stores.get(good, 0.0) + s.season_need(good) * share


# a supply year runs to the winter check, which is the season it is counted in
SUPPLY_YEAR = ("SPRING", "SUMMER", "AUTUMN", "WINTER")


def year(s, share=1.0, year_number=1):
    deaths = 0
    for season in SUPPLY_YEAR:
        supply(s, share)
        s.consume()
        if season == "WINTER":
            deaths += s.winter_check(year_number)
    return deaths


def test_a_settlement_given_exactly_its_needs_never_declines():
    s = settlement()
    start = s.population
    for i in range(10):
        assert year(s, 1.0, i + 1) == 0
    assert s.population == start


def test_a_settlement_given_nothing_declines_on_a_schedule():
    s = settlement()
    s.stores = {g: 0.0 for g in GOODS}
    tolls = [year(s, 0.0, i + 1) for i in range(4)]
    assert all(t > 0 for t in tolls)
    expected = sum(T.SHORTFALL_DEATHS.values())
    assert 0.6 * expected < tolls[0] / 120 < 1.4 * expected
    assert tolls == sorted(tolls, reverse=True)      # fewer left to lose


def test_a_shortfall_in_autumn_is_counted_in_winter():
    s = settlement()
    s.stores = {g: 0.0 for g in GOODS}
    s.consume()                                   # autumn: nothing to eat
    assert s.population == 120                    # and nobody has died yet
    assert s.shortfall["GRAIN"] > 0
    s.consume()                                   # winter
    assert s.winter_check(1) > 0
    assert s.population < 120


def test_the_winter_check_clears_the_slate():
    s = settlement()
    s.stores = {g: 0.0 for g in GOODS}
    for _ in T.SEASONS:
        s.consume()
    s.winter_check(1)
    assert all(v == 0 for v in s.shortfall.values())


def test_a_doomed_settlement_is_known_to_be_doomed_in_advance():
    """Doomed means the winter leaves too few people to go on with."""
    small = settlement(pop=T.ABANDON_POPULATION + 4)
    small.stores = {g: 0.0 for g in GOODS}
    assert small.doomed(4)

    large = settlement(pop=200)
    large.stores = {g: 0.0 for g in GOODS}
    assert not large.doomed(4)          # it loses people; it does not end

    supplied = settlement(pop=T.ABANDON_POPULATION + 4)
    supply(supplied, 8.0)
    assert not supplied.doomed(4)


def test_only_a_surplus_is_produced():
    s = settlement(surplus=("FUEL",))
    assert s.produces("FUEL") > 0
    assert s.produces("GRAIN") == 0
    assert s.produces("FUEL") > s.season_need("FUEL")


def test_the_post_may_not_strip_a_settlement_bare():
    s = settlement()
    s.stores["GRAIN"] = s.population * NEED_PER_HEAD["GRAIN"]
    assert s.spare("GRAIN") == pytest.approx(s.population * NEED_PER_HEAD["GRAIN"] * 0.5)
    s.stores["GRAIN"] = 0.1
    assert s.spare("GRAIN") == 0.0
