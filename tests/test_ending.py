"""M6: the ending, the last run, and the summary.

There is no victory condition and no score. The run ends when the network can
no longer hold itself together or when ten years are up, and the headline
figure is the number of years the post ran.
"""

import pytest

from longpost import tuning as T
from longpost.__main__ import Game
from longpost.post import summary as summary_mod


def play_to_the_end(seed=3, limit=T.TURNS + 6):
    game = Game(seed)
    for _ in range(limit):
        if game.phase == game.LAST_RUN:
            break
        game.run_season()
    return game


# --- when it ends ------------------------------------------------------------


def test_ten_years_ends_the_run():
    game = play_to_the_end()
    assert game.phase == game.LAST_RUN
    assert game.ending_reason == "ten years"
    assert game.year == T.START_YEAR + T.YEARS - 1


def test_a_network_that_cannot_hold_itself_together_ends_the_run_early():
    game = Game(3)
    for settlement in game.world.known_settlements()[2:]:
        settlement.abandoned_year = 2
    assert game.connected < T.CONNECTED_MINIMUM
    game.run_season()
    assert game.phase == game.LAST_RUN
    assert "hold itself together" in game.ending_reason


def test_the_run_is_never_offered_a_victory():
    game = play_to_the_end()
    lines = [line for line, _accent in game.log.lines]
    for word in ("won", "victory", "congratulations", "score"):
        assert not any(word in line.lower() for line in lines)


# --- the last run ------------------------------------------------------------


def test_the_ending_offers_one_more_run_and_asks_what_it_carries():
    game = play_to_the_end()
    assert any("one more run" in line for line, _accent in game.log.lines)
    assert len(game.standing) == 0, "the kept routes are stood down for it"
    assert len(game.plan) == 0


def test_the_last_run_plays_at_its_own_length_and_is_not_skippable():
    game = play_to_the_end()
    if game.selected_edge is None or game.selected_carrier is None:
        pytest.skip("this seed ends with nothing left that can move")
    game.load_by_need()
    game.commit_last_run()
    assert game.resolution.duration == T.LAST_RUN_SECONDS
    assert game.last_run

    game.skip_resolution()
    assert game.phase == game.RESOLVE, "the last run is not hurried"


def test_the_view_pulls_back_and_the_summary_waits_for_a_keypress():
    game = play_to_the_end()
    if game.selected_edge is None or game.selected_carrier is None:
        pytest.skip("this seed ends with nothing left that can move")
    game.load_by_need()
    game.commit_last_run()
    for _ in range(int(T.LAST_RUN_SECONDS * 60) + 5):
        game.update(1 / 60)
    assert game.phase == game.PULL_BACK
    for _ in range(int(T.PULL_BACK_SECONDS * 60) + 5):
        game.update(1 / 60)
    assert game.phase == game.SUMMARY


# --- the summary -------------------------------------------------------------


def test_the_summary_is_a_record_and_not_a_score():
    game = play_to_the_end()
    summary = summary_mod.build(game)
    assert summary.years == T.YEARS
    assert summary.population_at_end < summary.population_at_start
    assert summary.reason
    assert not hasattr(summary, "score")


def test_the_summary_names_what_was_lost_and_when():
    game = play_to_the_end(seed=7)
    summary = summary_mod.build(game)
    for name, year in summary.lost:
        assert isinstance(name, str) and T.START_YEAR <= year <= T.START_YEAR + T.YEARS


def test_the_summary_keeps_the_histories_of_the_lost_intact():
    game = play_to_the_end(seed=7)
    summary = summary_mod.build(game)
    for name, where, year, history in summary.fallen:
        assert where and history          # never shortened, never archived


def test_what_a_settlement_received_in_the_winter_it_ended_is_in_the_summary():
    game = Game(3)
    subject = game.world.known_settlements()[0]
    subject.population = T.ABANDON_POPULATION - 5
    subject.received["GRAIN"] = 6.0
    while game.season != "WINTER":
        game.run_season()
    game.run_season()
    summary = summary_mod.build(game)
    assert any(subject.name in line and "in the winter it ended" in line
               for line in summary.kindnesses)
