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
        float(world.terrain.elevation.sum()),
        [len(loop) for loop in world.coast_paths],
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
            game.run_season()
        return list(game.log.lines), fingerprint(game.world)

    assert run(9) == run(9)


def test_no_roll_in_the_game_depends_on_the_process():
    """Python randomises string hashing per process. A run that replays
    differently tomorrow is not a replay, so nothing may use hash()."""
    import pathlib
    import re

    source = pathlib.Path(__file__).resolve().parent.parent / "longpost"
    offenders = []
    for path in sorted(source.rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#") or '"""' in line:
                continue
            if re.search(r"(?<![\w.])hash\s*\(", line) and "seed_of" not in line:
                offenders.append(f"{path.name}:{number}")
    assert not offenders, offenders


def test_a_hazard_roll_is_the_same_in_every_process():
    from longpost.render.ink import seed_of
    assert seed_of("hazard", 3, 2, "WINTER", 11, 0, 0) == 3228847447


def test_the_run_is_forty_turns_and_stops_there():
    game = Game(5)
    for _ in range(T.TURNS + 10):
        game.run_season()
    assert game.turn == T.TURNS - 1
    assert game.year == T.START_YEAR + T.YEARS - 1
