"""§3.15. A lint pass over the text the game can produce.

Blunt, but it keeps the tone rules honest over a long build.
"""

import ast
import pathlib

from longpost import tuning as T
from longpost.__main__ import Game

BANNED = (
    "tragic", "tragically", "heroic", "heroically", "bravely", "brave",
    "sadly", "sad", "betray", "betrayed", "betrayal", "cruel", "noble",
    "valiant", "hero", "villain", "evil", "wicked", "glorious", "triumphant",
    "devastating", "heartbreaking", "poor ", "sacrifice", "beloved",
)

# the game does not instruct: no second person imperatives in game-facing text
BANNED_ADDRESS = ("you must", "you should", "your duty", "don't forget")

SOURCE = pathlib.Path(__file__).resolve().parent.parent / "longpost"


def game_facing_strings():
    """Every string literal in the game's own modules, minus docstrings."""
    found = []
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    docstrings.add(doc)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in docstrings:
                    continue
                found.append((path.name, node.value))
    return found


def offending(text):
    lowered = text.lower()
    return [word for word in BANNED + BANNED_ADDRESS
            if word in lowered.split() or (" " in word and word in lowered)]


def test_no_source_string_carries_a_word_of_feeling():
    bad = [(name, text) for name, text in game_facing_strings() if offending(text)]
    assert not bad, bad


def test_a_full_run_writes_nothing_that_tells_the_player_how_to_feel():
    game = Game(11)
    for _ in range(T.TURNS):
        game.run_season()
    bad = [line for line, _accent in game.log.lines if offending(line)]
    assert not bad, bad


def test_log_lines_are_plain_and_lower_key():
    game = Game(2)
    for _ in range(8):
        game.run_season()
    for line, _accent in game.log.lines:
        assert "!" not in line
        assert not line.isupper()
