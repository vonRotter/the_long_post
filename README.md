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

## Decisions taken so far

* **The starting five are a connected cluster**, chosen near the middle of the
  map and biased toward a crossing that freezes, so the seasonal inversion is
  on the player's chart from the first winter rather than found in year four.
  The remaining fifteen settlements exist from generation but are undiscovered.
* **Spring is the worst season** in the profiles as specified: passes closed,
  inland mud, sea only half open.
* **Standing and desperation are carried on the settlement now** but do nothing
  until M2. Nothing hostile happens in M0, so nothing is untraceable yet.

## Open questions, at the milestone where they bite

* Numeric risk or bands (§6.2, decide at M2) — the edge carries a `danger`
  float and the panel has no risk readout yet, so either is still cheap.
* Money at all (§6.5, decide at M1) — nothing in the current code assumes it.

## Known tuning debt

Re-inking the whole chart costs roughly 35 ms, so a drag runs near 30 fps while
an idle chart runs at 60. The cost is almost entirely the sea tone; if it
becomes annoying at FOCUS, hatch spacing is the dial.
