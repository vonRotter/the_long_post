"""§9: sound, briefly.

Procedural only, in the same restrained register as everything else — and
silence is a valid state, because a machine with no audio should run the game
exactly as it ran before.
"""

import numpy as np
import pytest

from longpost import sound as sound_mod
from longpost import tuning as T
from longpost.__main__ import Game


@pytest.fixture(scope="module")
def made():
    return sound_mod.Sound(seed=3)


# --- what it is made of ------------------------------------------------------


def test_there_are_no_sound_files_in_this_project():
    """Every sound is a few seconds of numpy. The one asset is the typeface."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    for pattern in ("*.wav", "*.ogg", "*.mp3", "*.flac"):
        assert not list(root.rglob(pattern)), pattern


def test_the_wind_loops_without_a_click():
    gen = np.random.default_rng(3)
    wave = sound_mod._wind(gen, seconds=4.0)
    # the ends have been crossfaded into each other, so the seam is small
    seam = abs(float(wave[0]) - float(wave[-1]))
    assert seam < 0.25, seam


def test_the_pen_is_a_pen_and_not_a_hiss():
    """A nib is a narrow band with a very fast attack."""
    gen = np.random.default_rng(3)
    wave = sound_mod._scratch(gen)
    assert len(wave) == int(sound_mod.RATE * 0.13)
    peak_at = int(np.argmax(np.abs(wave))) / sound_mod.RATE
    assert peak_at < 0.03, peak_at
    spectrum = np.abs(np.fft.rfft(wave))
    frequencies = np.fft.rfftfreq(len(wave), 1.0 / sound_mod.RATE)
    centroid = float((spectrum * frequencies).sum() / spectrum.sum())
    assert 1200 < centroid < 8000, centroid


def test_the_tones_sit_where_they_are_meant_to():
    """Low for a shortfall, lower for a loss, warm for an arrival."""
    def pitch(wave):
        spectrum = np.abs(np.fft.rfft(wave))
        frequencies = np.fft.rfftfreq(len(wave), 1.0 / sound_mod.RATE)
        return float(frequencies[int(np.argmax(spectrum))])

    shortfall = sound_mod._tone(1.4, 88.0, attack=0.08, decay=0.9)
    loss = sound_mod._tone(2.0, 62.0, attack=0.05, decay=1.3)
    arrival = sound_mod._tone(1.1, 294.0, attack=0.03, decay=0.55)
    assert pitch(loss) < pitch(shortfall) < pitch(arrival)


def test_nothing_clips():
    gen = np.random.default_rng(3)
    for wave in (sound_mod._wind(gen, 2.0), sound_mod._scratch(gen),
                 sound_mod._tone(1.0, 200.0)):
        assert np.max(np.abs(wave)) <= 1.0 + 1e-9


def test_it_is_quiet():
    """Nothing in the register is loud, and the bed is the quietest of all."""
    assert T.SOUND_WIND <= 0.2
    for level in (T.SOUND_SCRATCH, T.SOUND_SHORTFALL, T.SOUND_LOSS,
                  T.SOUND_ARRIVAL):
        assert level <= 0.3
    assert T.SOUND_WIND < T.SOUND_SCRATCH, "the pen sits above the wind"


def test_the_bed_thickens_through_winter():
    wind = T.SOUND_SEASON_WIND
    assert wind["WINTER"] > wind["SPRING"] > wind["AUTUMN"] > wind["SUMMER"]


# --- what it does ------------------------------------------------------------


def test_silence_is_a_valid_state():
    """A machine with no audio runs the game exactly as it ran before."""
    quiet = sound_mod.Sound.__new__(sound_mod.Sound)
    quiet.enabled = False
    quiet.muted = False
    quiet.season = None
    quiet._scratches = []
    quiet._wind_channel = None
    quiet.set_season("WINTER")
    quiet.scratch()
    quiet.loss_tone()
    quiet.arrival_tone()
    quiet.shortfall_tone()
    quiet.stop()


def test_the_player_can_turn_it_off(made):
    was = made.muted
    assert made.toggle_mute() is not was
    made.toggle_mute()


def test_a_season_of_play_makes_sound_without_touching_the_simulation():
    """Sound is downstream of everything. It never decides anything."""
    def run(muted):
        game = Game(3)
        game.sound.muted = muted
        for _ in range(6):
            game.run_season()
        return [line for line, _accent in game.log.lines], [
            s.population for s in game.world.settlements]

    assert run(True) == run(False)
