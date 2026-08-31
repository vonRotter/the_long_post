"""Zoom and pan are player verbs, and the chart is not re-inked every frame."""

import numpy as np

from longpost import tuning as T
from longpost.__main__ import Game


def settle(game, frames=60):
    for _ in range(frames):
        game.chart.update(1 / 60)


def test_zoom_holds_the_point_under_the_cursor():
    game = Game(3)
    camera = game.chart.camera
    anchor = (300, 250)
    before = camera.screen_to_world(anchor)
    camera.zoom_by(T.ZOOM_STEP ** 4, anchor)
    settle(game)
    after = camera.screen_to_world(anchor)
    assert np.allclose(before, after, atol=2.0)


def test_zoom_is_clamped_at_both_ends():
    game = Game(3)
    camera = game.chart.camera
    for _ in range(60):
        camera.zoom_by(T.ZOOM_STEP, None)
    settle(game)
    assert camera.zoom <= T.ZOOM_MAX
    for _ in range(120):
        camera.zoom_by(1 / T.ZOOM_STEP, None)
    settle(game)
    assert camera.zoom >= T.ZOOM_MIN


def test_pan_responds_on_the_frame_the_input_arrives():
    game = Game(3)
    camera = game.chart.camera
    before = camera.centre.copy()
    camera.pan_screen(-40, 0)
    assert camera.centre[0] > before[0]


def test_zoom_and_pan_persist_between_turns():
    game = Game(3)
    game.chart.camera.look_at((400, 400), 4.0)
    settle(game)
    kept = (game.chart.camera.centre.copy(), game.chart.camera.zoom)
    game.advance()
    settle(game)
    assert np.allclose(game.chart.camera.centre, kept[0])
    assert game.chart.camera.zoom == kept[1]


def test_the_chart_is_not_re_inked_every_frame(display):
    game = Game(3)
    settle(game)
    game.chart.draw(display)
    before = game.chart._rebuilds
    for _ in range(30):
        game.chart.update(1 / 60)
        game.chart.draw(display)
    assert game.chart._rebuilds == before, "the chart is being re-inked every frame"


def test_a_season_change_re_inks_the_chart(display):
    game = Game(3)
    settle(game)
    game.chart.draw(display)
    before = game.chart._rebuilds
    game.advance()
    game.chart.update(1 / 60)
    game.chart.draw(display)
    assert game.chart._rebuilds > before
    assert game.chart.redraw_t < 1.0          # the hand is still revising it


def test_detail_arrives_progressively_rather_than_as_a_mode_switch():
    assert T.ZOOM_MIN < T.DETAIL_NAMES < T.DETAIL_HULLS < T.DETAIL_ROOFS < T.ZOOM_MAX
    assert T.ZOOM_CHART < T.ZOOM_FOCUS < T.ZOOM_MAX


def test_a_short_pan_does_not_re_ink_the_chart(display):
    """Panning translates the document; it does not change it."""
    game = Game(3)
    settle(game)
    for _ in range(4):
        game.chart.draw(display)
    before = game.chart.ground.rebuilds
    for _ in range(10):
        game.chart.camera.pan_screen(-6, -2)
        game.chart.update(1 / 60)
        game.chart.draw(display)
    assert game.chart.ground.rebuilds == before


def test_a_long_pan_re_inks_once_it_runs_off_the_margin(display):
    game = Game(3)
    settle(game)
    for _ in range(4):
        game.chart.draw(display)
    before = game.chart.ground.rebuilds
    travelled = 0
    while travelled < 600:
        game.chart.camera.pan_screen(-10, 0)
        travelled += 10
        game.chart.update(1 / 60)
        game.chart.draw(display)
    # the document is re-inked as the pan eats the bitmap's margin, not per frame
    re_inks = game.chart.ground.rebuilds - before
    assert 1 <= re_inks <= 6


def test_the_ground_is_inked_across_several_frames(display):
    """No single frame pays for the whole sheet."""
    game = Game(3)
    game.chart.draw(display)                  # the first bitmap must finish at once
    settle(game)
    game.chart.ground.dirty = True
    game.chart.update(1 / 60)
    game.chart.draw(display)
    assert game.chart.ground.pending is not None
    for _ in range(30):
        game.chart.update(1 / 60)
        game.chart.draw(display)
    assert game.chart.ground.pending is None


def test_a_zoom_in_flight_does_not_re_ink_every_frame(display):
    game = Game(3)
    settle(game)
    game.chart.draw(display)
    before = game.chart.ground.rebuilds
    game.chart.camera.zoom_by(T.ZOOM_STEP ** 5, (400, 300))
    for _ in range(10):
        game.chart.update(1 / 60)
        game.chart.draw(display)
        assert not game.chart.camera.settled
    assert game.chart.ground.rebuilds == before
    # and zooming in never invalidates a bitmap: it already holds more world
    assert game.chart.ground.slack(game.chart.camera, game.chart.rect) > 0
