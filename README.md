# The Long Post

A post service in a frozen north, played four turns a year for ten years. The
build brief is `the-long-post-spec.md`; everything visual is governed by
`the-long-post-art-direction.md`, which is binding.

## Running

```
pip install -r requirements.txt
python -m longpost            # or: python -m longpost <seed>
```

Python 3.11+, `pygame` and `numpy` only, plus the one `.ttf` in
`longpost/data/`. No build step.

```
pytest tests/
```

## Controls

| | |
|---|---|
| `space` | the season turns |
| wheel, `+` / `−` | zoom, continuously, at any time |
| drag | pan |
| right click | look at a settlement or a leg |
| `f` | fit the whole chart |
| `esc`, `q` | leave |

Debug: `F1` edge terrain, travel days, season profile and danger · `F2`
desperation and standing · `F3` reseed.

## Milestone status

Built: **A0 — Ink** and **M0 / A1 / A2 — Chart, turns, free zoom.**

* `render/ink.py` — the five primitives (wobbled line, curve, hatch, stipple,
  mark), the generated chart paper, and the one ruled line the game allows.
  Every wobble is seeded from the identity of the thing drawn, never from time.
* `world/map.py`, `world/season.py` — the generated graph, terrain, travel days
  and the season profiles, including the inversion: sea lanes that close in
  winter and ice roads that only exist while they are frozen.
* `render/chart_view.py` — continuous zoom and pan as a player verb, with
  detail arriving progressively: names, then roofs and a jetty, then the
  hand-ruled distance measure along a leg. The static document is cached and
  re-inked only when the chart changes.
* `render/panel.py`, `render/log.py` — numbers in the panel, never on the
  chart; plain declarative lines in the log.

Not built yet: cargo, carriers, couriers, desperation, theft, tunnels,
delegation, the ending. Those are M1–M6.

### Tests

`tests/test_map.py` (300 seeds: reachability, no settlement isolated in all
four seasons, ice roads never coexist with the water they cross, the starting
chart is connected and carries the inversion) · `tests/test_ink.py` (a line
wobbles identically every frame, no line is straight except the tunnel, tone is
hatching and never a fill) · `tests/test_camera.py` (zoom holds the point under
the cursor, zoom and pan persist between turns, the chart is not re-inked every
frame) · `tests/test_determinism.py` · `tests/test_tone.py` (a lint pass over
every string the game can write).

## Borrowed from map maker

Three things were taken from the `mapmaker` repo, which solves a neighbouring
problem — a hand-drawn chart that has to stay at 60 fps while it is dragged.

* **The pan-quantised layer cache.** Panning does not change the document, it
  translates it. So the chart is inked onto a bitmap larger than the chart rect
  at a camera centre rounded to a grid, and blitted back at the difference. A
  drag re-inks as it eats the margin rather than once a frame.
* **Splitting the sheet from what is on it,** and inking the expensive half a
  few milliseconds at a time across frames. The ground — sea, ice, depth lines,
  coast, stipple — changes only with the season and the view. The network —
  legs, settlements, marks — is cheap and changes constantly, including every
  frame of the season redraw, so it is always finished in one.
* **Grain above the ink, not under it,** blitted with a multiply. Real grain
  lies on top of what was drawn, so a line crossing a rough patch is broken by
  it. Its chart depth contours came over too: our coastlines are radial by
  construction, so an inward or seaward offset can be read straight off the
  shape and cannot fold at an inlet the way offsetting a polygon does.

## Decisions taken so far

* **The starting five are a connected cluster**, chosen near the middle of the
  map and biased toward a crossing that freezes, so the seasonal inversion is
  on the player's chart from the first winter rather than found in year four.
  The remaining fifteen settlements exist from generation but are undiscovered.
* **Spring is the worst season** in the profiles as specified: passes closed,
  inland mud, sea only half open.
* **Standing and desperation are carried on the settlement now** but do nothing
  until M2. Nothing hostile happens in M0, so nothing is untraceable yet.
* **No money** (§6.5, settled). Goods and standing only. Nothing in the code
  assumes a currency and nothing will.

## Open questions, at the milestone where they bite

* Numeric risk or bands (§6.2, decide at M2) — the edge carries a `danger`
  float and the panel has no risk readout yet, so either is still cheap.

## Frame budget

Measured headless at 1280 × 720, seed 3, in milliseconds per frame:

| | median | worst |
|---|---|---|
| idle, at CHART and at FOCUS | 4.7 | 5.3 |
| dragging 600 px | 12.4 | 19.8 |
| a five-notch zoom | 7.1 | 17.9 |
| the season re-ink, over its second | 12.0 | 20.7 |

Before the cache rework a drag cost about 35 ms *every* frame. The dials are
`PAN_QUANTUM` (how far the view may travel before a re-ink), `INK_SLICE_MS`
(how much ink work a frame may do), and hatch spacing.
