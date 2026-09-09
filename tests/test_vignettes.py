"""A4: the six vignettes, and the restraint rule that governs them.

The art direction is unusually explicit here, because this is where §3.7 is
most easily broken: a vignette is a glance, not an elegy. If one feels like the
game asking for a reaction, it is too long.
"""

import pygame
import pytest

from longpost import tuning as T
from longpost.__main__ import Game
from longpost.render import vignette


def test_there_are_six_and_only_six():
    assert len(vignette.KINDS) == 6
    assert set(vignette.KINDS) == {"avalanche", "storm", "ice", "bandits",
                                   "arrival", "abandonment"}


def test_a_loss_vignette_holds_for_two_seconds_and_no_longer():
    for kind in vignette.KINDS:
        if kind == "arrival":
            continue
        assert vignette.Vignette(kind, 1).duration <= 2.0


def test_the_counterweight_is_allowed_a_little_longer_and_no_more():
    arrival = vignette.Vignette("arrival", 1).duration
    assert arrival <= 2.5
    assert arrival >= vignette.Vignette("storm", 1).duration


def test_any_key_dismisses_it_immediately():
    queue = vignette.Vignettes()
    queue.show("storm", 1)
    assert queue.current is not None
    queue.dismiss()
    assert queue.current is None


def test_the_world_does_not_stop_twice_in_one_season():
    queue = vignette.Vignettes()
    queue.show("storm", 1)
    queue.show("avalanche", 1)
    assert queue.current.kind == "storm"


def test_it_is_over_when_its_two_seconds_are():
    queue = vignette.Vignettes()
    queue.show("ice", 1)
    for _ in range(int(T.VIGNETTE_SECONDS * 60) + 2):
        queue.update(1 / 60)
    assert queue.current is None


def test_no_text_appears_inside_a_vignette_ever():
    """The rule is absolute, so it is checked at the source."""
    import inspect
    source = inspect.getsource(vignette)
    for banned in ("lettering", "font(", ".render_to", "Font("):
        assert banned not in source, banned


def test_every_kind_draws_something_and_none_of_it_is_filled(display):
    """Tone is hatching here as everywhere: ink never fills the frame."""
    import numpy as np
    for kind in vignette.KINDS:
        drawn = vignette.Vignette(kind, 3)._render()
        pixels = pygame.surfarray.array3d(drawn).astype(int).sum(axis=2)
        paper = int(np.median(pixels))
        inked = pixels < paper - 60
        assert inked.any(), kind
        assert np.count_nonzero(inked) < inked.size * 0.5, kind


def test_the_frame_is_smaller_than_the_chart_it_is_pasted_onto():
    assert T.VIGNETTE_SIZE[0] < T.WINDOW_W and T.VIGNETTE_SIZE[1] < T.WINDOW_H


# --- what earns one -----------------------------------------------------------


def test_a_load_taken_on_the_road_earns_a_bandits_frame():
    game = Game(3)
    world = game.world
    stranger = next(s for s in world.settlements if not s.known)
    stranger.desperation = 100.0
    for edge in world.edges:
        edge.danger, edge.danger_source = 1.0, stranger.id
    carrier, edge = next((c, e) for c in game.fleet for e in world.known_edges()
                         if e.is_usable(game.season) and c.at in (e.a, e.b)
                         and c.can_run(game.season, e) and c.reaches(e))
    world.settlements[carrier.at].stores["GRAIN"] = 40.0
    game.select_edge(edge)
    game.selected_carrier = carrier
    game.adjust_cargo("GRAIN", 4)
    game.run_season()
    kinds = [kind for _at, kind, _subject in game.last_resolution.vignettes]
    assert "bandits" in kinds


def test_a_courier_lost_at_sea_earns_the_storm_and_not_the_avalanche():
    from longpost.post.resolve import Resolution, _lose
    game = Game(3)
    edge = next(e for e in game.world.edges if e.terrain == "COAST")
    result = Resolution(year=2, season="AUTUMN")
    _lose(result, game.world, game.couriers[0], edge, 2, "AUTUMN", 0.5)
    kinds = [kind for _at, kind, _subject in result.vignettes]
    assert kinds == ["storm"]


def test_a_settlement_given_up_earns_the_abandonment():
    game = Game(3)
    subject = game.world.known_settlements()[0]
    subject.population = T.ABANDON_POPULATION - 5
    while game.season != "WINTER":
        game.run_season()
    game.run_season()
    kinds = [kind for _at, kind, _subject in game.last_resolution.vignettes]
    assert "abandonment" in kinds
