"""The menu, on the same sheet as everything else.

Pressing escape used to close the window without asking, which is a poor way to
end a ten-year run. It now lifts a small card onto the chart: carry on, sound,
write the run down, take a written one up, the keys, or give the run up — and
that last one asks twice.

The card is drawn in the same hand as the chart. No shading, no highlight bar,
no rounded panel: a wobbled rule around a slightly opaque piece of the paper, a
tick in the margin against the line the player is on, and the same lettering
used everywhere else. The world does not stop being a document because the
player wants to turn the sound off.
"""

import pygame

from .. import tuning as T
from ..post import record
from . import ink, lettering

WIDTH = 470
LINE = 27


class Item:
    """One line of the card. `value` is what is set against it on the right."""

    def __init__(self, key, label, value=None, dim=False):
        self.key = key
        self.label = label
        self.value = value
        self.dim = dim


KEYS = [
    ("the chart", [
        ("drag, wheel", "move and zoom"),
        ("+ —", "zoom by a step"),
        ("f", "the whole chart"),
        ("right click", "look at a place or a leg"),
    ]),
    ("the season", [
        ("click, tab", "choose a leg"),
        ("c", "the carrier — shift for the one before"),
        ("v", "the courier — shift for the one before"),
        ("1 to 5", "load grain, fuel, medicine, tools, post"),
        ("shift 1 to 5", "take it off again"),
        ("l", "load for what is needed"),
        ("d", "dig the leg out"),
        ("b", "put a pair to breed"),
        ("s", "keep the leg as a standing route"),
        ("p", "hold the courier to that route"),
        ("x", "drop the order"),
        ("space", "commit the season"),
    ]),
    ("the record", [
        ("f5", "write the run down"),
        ("f4", "watch the last season again"),
        ("f3", "a new seed"),
        ("m", "sound"),
        ("f1, f2", "what the post can see"),
        ("esc", "this card"),
    ]),
]


class Menu:
    """Open or shut, and which line the player is on.

    Kept by the window rather than by the game, so a new seed does not close it
    and the card can outlive the run it was opened over.
    """

    def __init__(self):
        self.open = False
        self.page = "main"
        self.index = 0
        self.armed = None       # a key that has been asked for once
        self.notice = ""
        self._backing = {}

    # --- what is on the card ---

    def items(self, game):
        muted = getattr(game.sound, "muted", False)
        saved = record.path_for(game.seed).exists()
        return [
            Item("carry on", "carry on"),
            Item("sound", "sound", "off" if muted else "on"),
            Item("save", "write the run down"),
            Item("resume", "take the written run up",
                 "" if saved else "nothing written", dim=not saved),
            Item("keys", "the keys"),
            Item("quit", "give the run up",
                 "ask again to be sure" if self.armed == "quit" else ""),
        ]

    # --- opening and shutting ---

    def toggle(self):
        if self.open and self.page == "keys":
            self.page = "main"
            return
        self.open = not self.open
        self.page = "main"
        self.armed = None
        self.notice = ""

    def close(self):
        self.open = False
        self.armed = None
        self.notice = ""

    # --- the keys the card itself answers ---

    def handle(self, event, game):
        """Returns None, or what the window has to do about it."""
        if event.type == pygame.MOUSEMOTION:
            hit = self._line_at(event.pos, game)
            if hit is not None:
                self.index = hit
            return None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = self._line_at(event.pos, game)
            if hit is None:
                return None
            self.index = hit
            return self._choose(game)
        if event.type != pygame.KEYDOWN:
            return None

        if event.key == pygame.K_ESCAPE:
            self.toggle()
            return None
        if self.page == "keys":
            self.page = "main"
            return None

        items = self.items(game)
        if event.key in (pygame.K_DOWN, pygame.K_TAB):
            self.index = (self.index + 1) % len(items)
            self.armed = None
        elif event.key == pygame.K_UP:
            self.index = (self.index - 1) % len(items)
            self.armed = None
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                           pygame.K_LEFT, pygame.K_RIGHT):
            return self._choose(game)
        elif event.key == pygame.K_m:
            self._sound(game)
        return None

    def _choose(self, game):
        items = self.items(game)
        item = items[self.index % len(items)]
        if item.dim:
            return None
        if item.key != "quit":
            self.armed = None

        if item.key == "carry on":
            self.close()
        elif item.key == "sound":
            self._sound(game)
        elif item.key == "save":
            where = game.save()
            self.notice = f"written down at {where}."
        elif item.key == "resume":
            return "resume"
        elif item.key == "keys":
            self.page = "keys"
        elif item.key == "quit":
            if self.armed == "quit":
                return "quit"
            self.armed = "quit"
        return None

    def _sound(self, game):
        muted = game.sound.toggle_mute()
        record.remember_setting("muted", bool(muted))
        self.notice = "the sound is off." if muted else "the sound is on."

    # --- where the lines sit ---

    def _rect(self, game):
        rows = len(KEYS) + sum(len(k[1]) for k in KEYS) if self.page == "keys" \
            else len(self.items(game))
        height = 92 + rows * LINE
        width = 560 if self.page == "keys" else WIDTH
        rect = pygame.Rect(0, 0, width, min(height, T.WINDOW_H - 40))
        rect.center = (T.WINDOW_W // 2, T.WINDOW_H // 2)
        return rect

    def _line_at(self, pos, game):
        if not self.open or self.page != "main":
            return None
        rect = self._rect(game)
        top = rect.top + 74
        for i in range(len(self.items(game))):
            if pygame.Rect(rect.left, top + i * LINE - 6, rect.w, LINE).collidepoint(pos):
                return i
        return None

    # --- setting it on the paper ---

    def draw(self, target, game):
        if not self.open:
            return
        rect = self._rect(game)
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        layer.blit(self._backing_for(rect.size), (0, 0))

        if self.page == "keys":
            self._draw_keys(layer, rect)
        else:
            self._draw_main(layer, rect, game)
        target.blit(layer, rect.topleft)

    def _backing_for(self, size):
        """The card itself: a piece of the sheet, and a rule drawn round it.

        Cached, because the border is hand-drawn and there is no reason to draw
        it sixty times a second.
        """
        backing = self._backing.get(size)
        if backing is not None:
            return backing
        w, h = size
        backing = pygame.Surface(size, pygame.SRCALPHA)
        backing.fill((*T.PAPER_BASE, 240))
        border = [(9, 9), (w - 9, 9), (w - 9, h - 9), (9, h - 9)]
        ink.ink_paths(backing, [border], "normal", ink.seed_of("menu card", w, h),
                      closed=True)
        ink.ink_line(backing, (22, 58), (w - 22, 58), "faint",
                     ink.seed_of("menu rule", w))
        lettering.draw(backing, T.TITLE, (26, 30), size=14, alpha=225, spacing=2.0,
                       caps=True)
        self._backing[size] = backing
        return backing

    def _draw_main(self, layer, rect, game):
        items = self.items(game)
        self.index %= len(items)
        y = 74
        for i, item in enumerate(items):
            here = i == self.index
            alpha = 100 if item.dim else (230 if here else 180)
            if here and not item.dim:
                ink.mark(layer, "tick", (32, y + 7), ink.seed_of("menu tick", i),
                         scale=5.0, weight="faint")
            lettering.draw(layer, item.label, (48, y), size=13, alpha=alpha)
            if item.value:
                lettering.draw(layer, item.value, (rect.w - 28, y + 1), size=11,
                               alpha=alpha - 40, align="right")
            y += LINE
        foot = self.notice or "arrows and enter, or the mouse.  esc — carry on."
        lettering.draw(layer, foot, (26, rect.h - 30), size=10, alpha=140)

    def _draw_keys(self, layer, rect):
        y = 74
        for heading, rows in KEYS:
            lettering.draw(layer, heading, (26, y), size=11, alpha=190, spacing=1.6,
                           caps=True)
            y += LINE
            for key, what in rows:
                lettering.draw(layer, key, (200, y), size=11, alpha=205, align="right")
                lettering.draw(layer, what, (216, y), size=11, alpha=175)
                y += LINE
        lettering.draw(layer, "any key — back", (26, rect.h - 30), size=10, alpha=140)
