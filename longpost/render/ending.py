"""The last run and the summary, as they are set on the sheet.

Nothing here is embellished. Same ink, same paper, same hand. The weight comes
entirely from the chart being a record of what the player did, which is why
every accumulation rule exists — and why this screen adds nothing to it.
"""

import pygame

from .. import tuning as T
from . import ink, lettering, words


def draw_prompt(target, game):
    """One more run. What do you carry?

    Set plainly on the chart, with the leg and the load beside it. There is no
    score attached and nothing is calculated from it.
    """
    rect = pygame.Rect(T.LOG_RECT)
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    ink.ink_line(layer, (14, 3), (rect.w - 14, 3), "faint", ink.seed_of("last rule"))
    lettering.draw(layer, "one more run. what do you carry?", (18, 22), size=15,
                   alpha=225, spacing=1.2)
    if game.selected_edge is not None and game.selected_carrier is not None:
        edge = game.selected_edge
        order = game.order_for_selection()
        load = ", ".join(f"{int(v)} {g.lower()}"
                         for g, v in sorted((order.loaded() if order else {}).items()))
        who = game.selected_courier.name if game.selected_courier else "no one"
        lettering.draw(layer,
                       f"{game.world.settlements[edge.a].name.lower()} — "
                       f"{game.world.settlements[edge.b].name.lower()},"
                       f" {game.selected_carrier.name}, {who}", (18, 52), size=11,
                       alpha=175)
        lettering.draw(layer, load or "nothing yet", (18, 70), size=11, alpha=175)
    target.blit(layer, rect.topleft)


def draw_summary(target, game):
    """The record, set plainly. The headline is not a score.

    It is the number of years the post ran, and everything under it is what
    happened rather than a judgement of it.
    """
    summary = game.summary
    if summary is None:
        return
    layer = pygame.Surface((T.WINDOW_W, T.WINDOW_H), pygame.SRCALPHA)
    left, right = 90, T.WINDOW_W // 2 + 40
    y = 70

    lettering.draw(layer, "years the post ran", (left, y), size=13, alpha=190,
                   spacing=2.0, caps=True)
    lettering.draw(layer, str(summary.years), (left + 330, y - 14), size=44, alpha=235)
    y += 44
    ink.ink_line(layer, (left, y), (T.WINDOW_W - left, y), "faint",
                 ink.seed_of("summary rule"))
    y += 18
    lettering.draw(layer, summary.reason + ".", (left, y), size=11, alpha=165)
    y += 26

    column = y
    y = _block(layer, left, y, "the north", [
        f"{summary.population_at_start} at the first turn",
        f"{summary.population_at_end} at the last",
    ])
    y = _block(layer, left, y, "the post", [
        f"{words.count(summary.loads, 'load')} carried",
        f"{words.count(summary.on_chart, 'settlement')} on the chart at the end,"
        f" {summary.on_chart_population} people",
        f"the network was largest in year {summary.largest_year}, at"
        f" {words.count(summary.largest_count, 'settlement')}",
    ])
    y = _block(layer, left, y, "on the chart at the end",
               [f"{name}, {people}" for name, people in summary.surviving] or ["none"])
    y = _block(layer, left, y, "given up",
               [f"{name}, year {when}" for name, when in summary.lost] or ["none"])

    y = column
    y = _block(layer, right, y, "tunnels", summary.tunnels or ["none"])
    y = _block(layer, right, y, "who served the whole of it",
               [f"{name} — {history}" for name, history in summary.veterans] or ["none"])
    y = _block(layer, right, y, "lost", [
        f"{name}, {where}, year {when}" for name, where, when, _history in summary.fallen
    ] or ["none"])
    y = _block(layer, right, y, "loads that went elsewhere", [
        f"{name} took a load to {where}, year {when}" for name, where, when in summary.thefts
    ] or ["none"])
    if summary.kindnesses:
        _block(layer, right, y, "", summary.kindnesses)

    lettering.draw(layer, "esc", (T.WINDOW_W - 90, T.WINDOW_H - 40), size=10, alpha=120)
    target.blit(layer, (0, 0))


def _block(layer, x, y, heading, lines, limit=9):
    if heading:
        lettering.draw(layer, heading, (x, y), size=11, alpha=185, spacing=1.6,
                       caps=True)
        y += 18
    for line in lines[:limit]:
        lettering.draw(layer, line, (x + 10, y), size=11, alpha=200)
        y += 16
    if len(lines) > limit:
        lettering.draw(layer, f"and {len(lines) - limit} more", (x + 10, y), size=10,
                       alpha=140)
        y += 16
    return y + 14
