"""Saving a run, and picking it up again.

A run is a seed and the orders that were committed against it. Nothing else is
written down, because nothing else is needed: the world is generated from the
seed and every season is decided deterministically from the orders, so a save
is a few kilobytes of what the player asked for and a load is the game playing
itself back at once.

That is only true because §2's determinism rule has been kept honestly. This
file is the reason to keep keeping it — and the thing that would catch it if it
were ever broken, since a save that no longer replays is a save that is wrong.
"""

import json
import pathlib
import time

from .. import tuning as T

VERSION = 1


def path_for(seed) -> pathlib.Path:
    directory = pathlib.Path(T.SAVE_DIRECTORY).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"seed-{seed}.json"


def _season_record(game) -> dict:
    """What was committed this season, as the player asked for it."""
    return {
        "turn": game.turn,
        "orders": [
            {"edge": order.edge_id, "carrier": order.carrier_id,
             "courier": order.courier_id, "origin": order.origin,
             "cargo": {good: int(amount) for good, amount in order.cargo.items()},
             "digging": bool(order.digging)}
            for order in sorted(game.plan_at_commit.values(),
                                key=lambda o: o.carrier_id)
        ],
        "standing": [
            {"edge": route.edge_id, "carrier": route.carrier_id,
             "courier": route.courier_id, "priority": list(route.priority)}
            for route in game.standing
        ],
        "foals": [[born, kind, where] for born, kind, where in game.foals],
    }


def remember(game):
    """Called at every commit. The trace is the save."""
    game.trace.append(_season_record(game))


def write(game, where=None) -> pathlib.Path:
    where = pathlib.Path(where) if where else path_for(game.seed)
    where.parent.mkdir(parents=True, exist_ok=True)
    where.write_text(json.dumps({
        "version": VERSION,
        "seed": game.seed,
        "turn": game.turn,
        "written": time.strftime("%Y-%m-%d %H:%M"),
        "seasons": game.trace,
    }, indent=1), encoding="utf-8")
    return where


def read(where):
    where = pathlib.Path(where)
    if not where.exists():
        return None
    saved = json.loads(where.read_text(encoding="utf-8"))
    if saved.get("version") != VERSION:
        return None
    return saved


def resume(saved, make_game):
    """Play the run back at once, and hand back where it got to.

    Every season is replayed through the same commit the player used, so a
    resumed run is not a restored snapshot of the world — it is the same run,
    arrived at the same way. If that ever produces a different world, the
    determinism the whole game rests on has been broken, and this is where it
    shows.
    """
    from . import assign

    game = make_game(saved["seed"])
    for season in saved["seasons"]:
        game.standing.routes.clear()
        for route in season.get("standing", []):
            game.standing.set(assign.StandingOrder(
                edge_id=route["edge"], carrier_id=route["carrier"],
                courier_id=route.get("courier", -1),
                priority=tuple(route.get("priority", ()))))
        game.foals = [(born, kind, where) for born, kind, where
                      in season.get("foals", [])]
        game.plan.clear()
        for order in season["orders"]:
            game.plan.set(assign.Order(
                edge_id=order["edge"], carrier_id=order["carrier"],
                origin=order["origin"],
                cargo={good: float(amount) for good, amount in order["cargo"].items()},
                courier_id=order.get("courier", -1),
                digging=bool(order.get("digging", False))))
        game.run_season()
        if game.phase == game.LAST_RUN:
            break
    return game


# --- what the player set, rather than what they did -------------------------
#
# Not part of the run. A save is the seed and the orders; whether the sound is
# on is a property of the machine the game is being played on, so it is kept
# beside the saves and read at startup.

def settings_path() -> pathlib.Path:
    directory = pathlib.Path(T.SAVE_DIRECTORY).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "settings.json"


def settings() -> dict:
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def setting(name, fallback=None):
    return settings().get(name, fallback)


def remember_setting(name, value):
    """Best effort. A read-only disk is not a reason to stop the game."""
    kept = settings()
    kept[name] = value
    try:
        settings_path().write_text(json.dumps(kept, indent=1), encoding="utf-8")
    except Exception:
        pass
    return kept
