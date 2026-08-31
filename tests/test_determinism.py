"""The same seed and the same input trace produce the same run.

This matters more here than in any previous project: the player must be able to
replay a disastrous year and watch it unfold identically.
"""

from longpost import tuning as T
from longpost.__main__ import Game
from longpost.world import map as world_map


def fingerprint(world):
    return (
        [(s.id, s.name, tuple(round(c, 6) for c in s.pos), s.population,
          s.surplus, s.known) for s in world.settlements],
        [(e.id, e.a, e.b, e.terrain, e.days, e.ice_of, e.tunnel_site)
         for e in world.edges],
        [tuple(round(c, 6) for c in p) for poly in world.land for p in poly],
        world.soundings,
    )


def test_a_seed_makes_one_world():
    for seed in (0, 1, 17, 404):
        assert fingerprint(world_map.generate(seed)) == fingerprint(world_map.generate(seed))


def test_different_seeds_make_different_worlds():
    assert fingerprint(world_map.generate(1)) != fingerprint(world_map.generate(2))


def test_forty_turns_replay_identically():
    def run(seed):
        game = Game(seed)
        for _ in range(T.TURNS + 2):
            game.advance()
        return list(game.log.lines), fingerprint(game.world)

    assert run(9) == run(9)


def test_the_run_is_forty_turns_and_stops_there():
    game = Game(5)
    for _ in range(T.TURNS + 10):
        game.advance()
    assert game.turn == T.TURNS - 1
    assert game.year == T.START_YEAR + T.YEARS - 1
