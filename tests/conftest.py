"""Tests run headless: no window, no sound."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def display():
    pygame.init()
    surface = pygame.display.set_mode((1280, 720))
    yield surface
    pygame.quit()
