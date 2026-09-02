"""Sound, briefly.

Procedural only, in the same restrained register as everything else: a wind bed
thickening through winter, pen-scratch as marks are inked during resolution, a
low tone on shortfall, a heavier one on a loss, and one warm note on an arrival
in need.

The pen scratch is the important one. It reinforces that everything the player
is seeing is being written down — that the chart is a document somebody is
keeping, not a display. Everything else sits under it.

Nothing here is a file. There are no assets in this project beyond the one
typeface, and there will not be. Every sound is a few seconds of numpy, made
once at startup from the world's seed, and the module fails silent: if the
mixer will not start, the game runs exactly as it did before.
"""

import numpy as np

try:
    import pygame
except ImportError:                       # pragma: no cover - pygame is required
    pygame = None

from . import tuning as T

RATE = 44100


# --- making the sounds ------------------------------------------------------


def _noise(gen, seconds, tilt=1.0):
    """Noise with a spectral tilt: 0 is white, 1 pink, 2 brown.

    Shaped in the frequency domain, because a one-pole filter over four hundred
    thousand samples in Python is not something to do at startup.
    """
    count = int(RATE * seconds)
    white = gen.standard_normal(count)
    spectrum = np.fft.rfft(white)
    frequencies = np.fft.rfftfreq(count, 1.0 / RATE)
    shape = np.ones_like(frequencies)
    shape[1:] = 1.0 / (frequencies[1:] ** (tilt / 2.0))
    shaped = np.fft.irfft(spectrum * shape, n=count)
    peak = np.max(np.abs(shaped)) or 1.0
    return shaped / peak


def _band(signal, low, high):
    """Keep a band of it. Same reason as above: done in the spectrum."""
    spectrum = np.fft.rfft(signal)
    frequencies = np.fft.rfftfreq(len(signal), 1.0 / RATE)
    spectrum[(frequencies < low) | (frequencies > high)] = 0.0
    return np.fft.irfft(spectrum, n=len(signal))


def _envelope(count, attack, decay, hold=0.0):
    """Attack, hold, exponential decay — in seconds."""
    out = np.ones(count)
    rise = max(1, int(attack * RATE))
    out[:rise] = np.linspace(0.0, 1.0, rise) ** 1.5
    held = rise + int(hold * RATE)
    fall = count - held
    if fall > 0:
        out[held:] = np.exp(-np.linspace(0.0, 5.0, fall) * (0.6 / max(decay, 1e-3)))
    return out


def _tone(seconds, root, partials=(1.0, 2.0), weights=(1.0, 0.3), attack=0.02,
          decay=0.5, hold=0.05, breath=0.0, gen=None):
    """A note. Sine partials, a soft envelope, and a little breath if asked."""
    count = int(RATE * seconds)
    t = np.arange(count) / RATE
    wave = np.zeros(count)
    for partial, weight in zip(partials, weights):
        wave += weight * np.sin(2 * np.pi * root * partial * t)
    if breath and gen is not None:
        wave += breath * _band(_noise(gen, seconds, tilt=1.0), root * 0.5, root * 4)
    wave *= _envelope(count, attack, decay, hold)
    peak = np.max(np.abs(wave)) or 1.0
    return wave / peak


def _scratch(gen, seconds=0.13):
    """One mark going onto the paper.

    A nib is a narrow band of noise with a very fast attack and a rough
    amplitude — the roughness is what makes it a pen rather than a hiss.
    """
    count = int(RATE * seconds)
    grain = _band(_noise(gen, seconds, tilt=0.6), 1400.0, 7000.0)
    rough = 1.0 + 0.55 * np.sin(2 * np.pi * gen.uniform(70, 160)
                                * np.arange(count) / RATE)
    wave = grain[:count] * rough * _envelope(count, 0.004, 0.14)
    peak = np.max(np.abs(wave)) or 1.0
    return wave / peak


def _wind(gen, seconds=8.0):
    """The bed. Brown noise, slowly breathing, and made to loop seamlessly."""
    count = int(RATE * seconds)
    body = _band(_noise(gen, seconds, tilt=2.0), 40.0, 900.0)[:count]
    t = np.arange(count) / RATE
    breathing = 1.0 + 0.35 * np.sin(2 * np.pi * t / seconds * 3.0) \
        + 0.20 * np.sin(2 * np.pi * t / seconds * 7.0 + 1.1)
    wave = body * breathing
    # crossfade the ends into each other, or the loop clicks every eight seconds
    fade = int(RATE * 0.6)
    ramp = np.linspace(0.0, 1.0, fade)
    wave[:fade] = wave[:fade] * ramp + wave[-fade:] * (1.0 - ramp)
    wave = wave[:-fade]
    peak = np.max(np.abs(wave)) or 1.0
    return wave / peak


def _to_sound(wave, volume):
    """A waveform as the mixer actually wants it.

    Whoever initialised the mixer decides how many channels it has — pygame.init
    may have got there first with its own defaults — so the shape is taken from
    the mixer rather than assumed.
    """
    samples = np.clip(wave * volume, -1.0, 1.0)
    samples = (samples * 32767).astype(np.int16)
    init = pygame.mixer.get_init()
    if init and init[2] > 1:
        samples = np.repeat(samples[:, None], init[2], axis=1)
    return pygame.sndarray.make_sound(np.ascontiguousarray(samples))


# --- the register the game plays in -----------------------------------------


class Sound:
    """Every sound the game makes, made once and kept.

    Silence is a valid state: on a machine with no audio, or with the mixer
    taken by something else, `enabled` is False and every method does nothing.
    """

    def __init__(self, seed=0, muted=False):
        self.enabled = False
        self.muted = muted
        self.season = None
        self._scratches = []
        self._wind_channel = None
        if pygame is None:
            return
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=RATE, size=-16, channels=1, buffer=1024)
            pygame.mixer.set_num_channels(T.SOUND_CHANNELS)
        except Exception:
            return

        gen = np.random.default_rng(seed)
        try:
            self.wind = _to_sound(_wind(gen), T.SOUND_WIND)
            self._scratches = [_to_sound(_scratch(gen), T.SOUND_SCRATCH)
                               for _ in range(6)]
            self.shortfall = _to_sound(
                _tone(1.4, 88.0, (1.0, 2.0, 3.0), (1.0, 0.22, 0.08),
                      attack=0.08, decay=0.9, hold=0.15), T.SOUND_SHORTFALL)
            self.loss = _to_sound(
                _tone(2.0, 62.0, (1.0, 1.5, 2.0), (1.0, 0.18, 0.12),
                      attack=0.05, decay=1.3, hold=0.2, breath=0.12, gen=gen),
                T.SOUND_LOSS)
            self.arrival = _to_sound(
                _tone(1.1, 294.0, (1.0, 2.0, 3.0), (1.0, 0.35, 0.12),
                      attack=0.03, decay=0.55, hold=0.08), T.SOUND_ARRIVAL)
        except Exception:
            return
        self.enabled = True
        self._gen = gen

    # --- the bed ---
    def set_season(self, season):
        """The wind thickens through winter and thins again by summer."""
        if not self.enabled:
            return
        self.season = season
        if self._wind_channel is None:
            self._wind_channel = self.wind.play(loops=-1)
            if self._wind_channel is None:
                return
        self._wind_channel.set_volume(0.0 if self.muted
                                      else T.SOUND_SEASON_WIND.get(season, 0.5))

    # --- the marks ---
    def scratch(self):
        """A mark going onto the paper, during resolution."""
        if not self.enabled or self.muted or not self._scratches:
            return
        self._scratches[int(self._gen.integers(len(self._scratches)))].play()

    def shortfall_tone(self):
        self._play(getattr(self, "shortfall", None))

    def loss_tone(self):
        self._play(getattr(self, "loss", None))

    def arrival_tone(self):
        self._play(getattr(self, "arrival", None))

    def _play(self, sound):
        if self.enabled and not self.muted and sound is not None:
            sound.play()

    # --- the player's own switch ---
    def toggle_mute(self):
        self.muted = not self.muted
        if self.enabled and self._wind_channel is not None:
            self._wind_channel.set_volume(
                0.0 if self.muted else T.SOUND_SEASON_WIND.get(self.season, 0.5))
        return self.muted

    def stop(self):
        if self.enabled:
            try:
                pygame.mixer.stop()
            except Exception:
                pass
