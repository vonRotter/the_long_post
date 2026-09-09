"""Plain phrasing helpers.

Tone rules, §3.15: plain declarative sentences, numbers where numbers are
honest, words where they are not, and no line telling the player how to feel.
"""


def count(n, singular, plural=None):
    plural = plural or singular + "s"
    return f"{n} {singular if n == 1 else plural}"


def band(value, bands=(("safe", 25), ("hard", 60), ("desperate", 101))):
    for label, ceiling in bands:
        if value < ceiling:
            return label
    return bands[-1][0]
