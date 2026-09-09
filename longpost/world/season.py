"""Season profiles and edge availability.

Four turns a year. The seasonal inversion is the map's best feature: winter
closes the sea and opens the ice, and the player holds two maps in their head.
"""

from .. import tuning as T

SEASONS = T.SEASONS
OPEN, HARD, CLOSED = T.OPEN, T.HARD, T.CLOSED

CHARACTER = {
    "AUTUMN": "everything is possible",
    "WINTER": "the sea is closed, the ice is open",
    "SPRING": "thaw and mud, the passes are shut",
    "SUMMER": "open water, good ground",
}


def season_of_turn(turn: int) -> str:
    return SEASONS[turn % len(SEASONS)]


def year_of_turn(turn: int) -> int:
    return T.START_YEAR + turn // len(SEASONS)


def availability(terrain: str, season: str) -> str:
    return T.SEASON_PROFILES[terrain][season]


def profile(terrain: str) -> dict:
    return dict(T.SEASON_PROFILES[terrain])


def is_usable(terrain: str, season: str) -> bool:
    return availability(terrain, season) != CLOSED
