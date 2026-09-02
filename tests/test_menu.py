"""The card that escape lifts onto the chart.

Escape used to close the window without asking, which is a poor way to end a
ten-year run. What is proved here is that it no longer does, that the sound can
be turned off and stays off, and that giving the run up has to be asked for
twice.
"""

import pathlib

import pygame
import pytest

from longpost import tuning as T
from longpost.__main__ import Game, handle
from longpost.post import record
from longpost.render.menu import Menu


@pytest.fixture
def game():
    return Game(3)


@pytest.fixture
def menu():
    return Menu()


@pytest.fixture(autouse=True)
def _settings_beside_the_test(tmp_path, monkeypatch):
    """Kept out of the player's own saves directory."""
    monkeypatch.setattr(T, "SAVE_DIRECTORY", str(tmp_path / "saves"))


def key(code, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=mod, unicode="")


def choose(menu, game, label):
    labels = [item.label for item in menu.items(game)]
    menu.index = labels.index(label)
    return menu.handle(key(pygame.K_RETURN), game)


# --- escape ------------------------------------------------------------------


def test_escape_no_longer_closes_the_window(game):
    """It is the one key a player presses by reflex, and a run is ten years."""
    assert handle(key(pygame.K_ESCAPE), game) is True


def test_escape_opens_the_card_and_shuts_it_again(menu):
    menu.toggle()
    assert menu.open
    menu.toggle()
    assert not menu.open


def test_escape_backs_out_of_the_keys_before_it_shuts(menu, game):
    menu.toggle()
    choose(menu, game, "the keys")
    assert menu.page == "keys"
    menu.handle(key(pygame.K_ESCAPE), game)
    assert menu.page == "main" and menu.open


# --- the sound ---------------------------------------------------------------


def test_the_sound_can_be_turned_off_from_the_card(menu, game):
    menu.toggle()
    was = game.sound.muted
    choose(menu, game, "sound")
    assert game.sound.muted is not was


def test_the_switch_outlives_the_run(menu, game):
    """A player who turns the sound off does not want it back next launch."""
    menu.toggle()
    while not game.sound.muted:
        choose(menu, game, "sound")
    assert record.setting("muted") is True
    assert Game(4).sound.muted is True


def test_the_card_says_which_way_the_switch_is_set(menu, game):
    menu.toggle()
    set_to = lambda: next(i.value for i in menu.items(game) if i.label == "sound")
    before = set_to()
    choose(menu, game, "sound")
    assert set_to() != before
    assert {before, set_to()} == {"on", "off"}


# --- giving up ---------------------------------------------------------------


def test_giving_the_run_up_is_asked_for_twice(menu, game):
    menu.toggle()
    assert choose(menu, game, "give the run up") is None
    assert choose(menu, game, "give the run up") == "quit"


def test_moving_off_the_line_disarms_it(menu, game):
    menu.toggle()
    choose(menu, game, "give the run up")
    menu.handle(key(pygame.K_UP), game)
    assert choose(menu, game, "give the run up") is None


# --- the run itself ----------------------------------------------------------


def test_the_run_can_be_written_down_from_the_card(menu, game):
    menu.toggle()
    assert choose(menu, game, "write the run down") is None
    assert record.path_for(game.seed).exists()


def test_a_written_run_can_only_be_taken_up_when_there_is_one(menu, game):
    menu.toggle()
    written = next(i for i in menu.items(game)
                   if i.label == "take the written run up")
    assert written.dim
    assert choose(menu, game, "take the written run up") is None

    choose(menu, game, "write the run down")
    assert not next(i for i in menu.items(game)
                    if i.label == "take the written run up").dim
    assert choose(menu, game, "take the written run up") == "resume"


# --- the paper ---------------------------------------------------------------


def test_both_pages_draw(menu, game):
    surface = pygame.Surface((T.WINDOW_W, T.WINDOW_H), pygame.SRCALPHA)
    menu.toggle()
    menu.draw(surface, game)
    assert surface.get_bounding_rect().width > 0
    choose(menu, game, "the keys")
    menu.draw(surface, game)


def test_a_shut_card_puts_nothing_on_the_sheet(menu, game):
    surface = pygame.Surface((T.WINDOW_W, T.WINDOW_H), pygame.SRCALPHA)
    menu.draw(surface, game)
    assert surface.get_bounding_rect().width == 0


def test_the_mouse_finds_the_same_lines_the_arrows_do(menu, game):
    menu.toggle()
    rect = menu._rect(game)
    for i in range(len(menu.items(game))):
        y = rect.top + 74 + i * 27 + 6
        assert menu._line_at((rect.centerx, y), game) == i
    assert menu._line_at((rect.centerx, rect.top + 20), game) is None


# --- the launcher ------------------------------------------------------------


def test_the_batch_file_starts_the_game_the_documented_way():
    root = pathlib.Path(__file__).resolve().parent.parent
    bat = (root / "startgame.bat").read_bytes()
    assert b"\r\n" in bat                       # or Windows will not read it
    assert all(c < 128 for c in bat)            # cmd's code page is not utf-8
    assert b"-m longpost %*" in bat             # the seed and --resume go through
