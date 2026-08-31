"""The five primitives.

A line must wobble identically every frame or the chart crawls, and no line
drawn by hand is ever straight.
"""

import numpy as np
import pygame

from longpost import tuning as T
from longpost.render import ink


def test_a_line_wobbles_identically_every_frame():
    first = ink.wobble_polyline((10, 10), (400, 220), seed=ink.seed_of("edge", 7))
    second = ink.wobble_polyline((10, 10), (400, 220), seed=ink.seed_of("edge", 7))
    assert first == second


def test_two_lines_do_not_share_a_wobble():
    a = ink.wobble_polyline((10, 10), (400, 220), seed=ink.seed_of("edge", 7))
    b = ink.wobble_polyline((10, 10), (400, 220), seed=ink.seed_of("edge", 8))
    assert a != b


def test_seeds_do_not_depend_on_the_process():
    # zlib.crc32, never hash(): otherwise the chart differs between runs
    assert ink.seed_of("edge", 7, "COAST") == 3158511709


def test_no_line_is_straight():
    a, b = (20.0, 20.0), (600.0, 180.0)
    pts = np.asarray(ink.wobble_polyline(a, b, seed=3))
    t = np.linspace(0, 1, len(pts))
    straight = np.stack([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], axis=1)
    drift = np.hypot(*(pts - straight).T)
    assert drift.max() > 0.5
    assert drift[0] == 0 and drift[-1] == 0     # the pen starts and stops on the mark


def test_wobble_grows_with_length():
    short = np.asarray(ink.wobble_polyline((0, 0), (40, 0), seed=1))
    long = np.asarray(ink.wobble_polyline((0, 0), (900, 0), seed=1))
    assert np.abs(long[:, 1]).max() > np.abs(short[:, 1]).max()


def test_paper_is_generated_per_seed_and_is_stable():
    a = pygame.surfarray.array3d(ink.make_paper((160, 120), 4))
    b = pygame.surfarray.array3d(ink.make_paper((160, 120), 4))
    c = pygame.surfarray.array3d(ink.make_paper((160, 120), 5))
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    assert a.std() > 1.0                        # the sheet is uneven, not flat


def test_hatch_density_is_the_continuous_variable():
    region = [(10, 10), (190, 10), (190, 190), (10, 190)]

    def inked(density):
        surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        ink.hatch(surf, region, density, 0.6, seed=2)
        return np.count_nonzero(pygame.surfarray.array_alpha(surf))

    light, heavy = inked(0.2), inked(0.9)
    assert heavy > light * 1.5
    assert inked(0.0) == 0


def test_nothing_is_filled():
    """Tone is hatching. A hatched region leaves most of the paper showing."""
    surf = pygame.Surface((200, 200), pygame.SRCALPHA)
    ink.hatch(surf, [(0, 0), (200, 0), (200, 200), (0, 200)], 1.0, 0.4, seed=1)
    covered = np.count_nonzero(pygame.surfarray.array_alpha(surf))
    assert covered < 200 * 200 * 0.6


def test_marks_are_drawn_where_they_are_asked_for():
    for kind in ("cross", "circled_dot", "tick", "query", "strike", "dot"):
        surf = pygame.Surface((60, 60), pygame.SRCALPHA)
        ink.mark(surf, kind, (30, 30), seed=1, scale=9)
        alpha = pygame.surfarray.array_alpha(surf)
        assert alpha.any(), kind
        ys, xs = np.nonzero(alpha)
        assert 10 <= ys.mean() <= 50 and 10 <= xs.mean() <= 50, kind


def test_the_only_straight_line_in_the_game_is_the_tunnel():
    surf = pygame.Surface((200, 40), pygame.SRCALPHA)
    ink.ruled_line(surf, (10, 20), (190, 20), "normal")
    alpha = pygame.surfarray.array_alpha(surf)
    rows = np.nonzero(alpha.any(axis=0))[0]
    assert rows.max() - rows.min() <= 1


def test_ink_is_never_pure_black_and_the_accent_is_the_only_colour():
    assert T.INK != (0, 0, 0)
    assert T.INK[2] > T.INK[0]                  # cold-leaning
    assert T.OXIDE[0] > T.OXIDE[1] > T.OXIDE[2]
