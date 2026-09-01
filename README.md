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

Built: **A0 — Ink**, **M0 / A1 / A2 — Chart, turns, free zoom**, and
**M1 — Shipping.**

* `render/ink.py` — the five primitives (wobbled line, curve, hatch, stipple,
  mark), the generated chart paper, and the one ruled line the game allows.
  Every wobble is seeded from the identity of the thing drawn, never from time.
* `world/terrain.py` — one elevation field, read at several levels. The shore
  is a contour of it, the depths and the lines behind the shore are contours a
  little either side, the high ground is a contour further up, and the land
  mask every other question is answered from is the same array. A coast of this
  kind — skerries, then islands, then fjords behind them — is what happens when
  water meets rough ground, so that is how it is made rather than drawn.
* `world/map.py`, `world/season.py` — the generated graph, terrain, travel days
  and the season profiles, including the inversion: sea lanes that close in
  winter and ice roads that only exist while they are frozen.
* `world/settlement.py` — needs per head per year in loads, production of a
  settlement's surplus, continuous consumption, the end-of-winter check, and
  the plain arithmetic that says in advance which places will not survive it.
* `post/` — carrier types and the post's fleet, orders and loads, and
  `resolve.py`, where a season is decided in one deterministic pass and then
  played back over six seconds. A carrier that can make the leg twice in a
  season comes home, and comes home carrying what the place it left is short of.
* `render/chart_view.py` — continuous zoom and pan as a player verb, with
  detail arriving progressively: names, then roofs and a jetty, then the
  hand-ruled distance measure along a leg. The static document is cached and
  re-inked only when the chart changes.
* `render/panel.py`, `render/log.py` — numbers in the panel, never on the
  chart; plain declarative lines in the log.

Not built yet: desperation, couriers, theft, tunnels, delegation, the ending.
Those are M2–M6.

### Tests

`tests/test_map.py` (300 seeds: reachability, no settlement isolated in all
four seasons, ice roads never coexist with the water they cross, the starting
chart is connected and carries the inversion) · `tests/test_ink.py` (a line
wobbles identically every frame, no line is straight except the tunnel, tone is
hatching and never a fill) · `tests/test_camera.py` (zoom holds the point under
the cursor, zoom and pan persist between turns, the chart is not re-inked every
frame, a short pan is a blit) · `tests/test_needs.py` (a settlement given
exactly its needs never declines; one given nothing declines on a schedule; a
shortfall in autumn is counted in February) · `tests/test_shipping.py` (a load
is moved and never created, the hold is the limit, a closed leg is refused) ·
`tests/test_decline.py` (population never rises, under any strategy) ·
`tests/test_determinism.py` · `tests/test_tone.py` (a lint pass over every
string the game can write).

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

* **The land is a coast, and the coast is a field, not a line.** Open sea to
  the west, then a wide shelf sitting just under the waterline that breaks into
  skerries and islands, then sounds and fjords, then high ground. Settlements
  sit on the islands and along the sounds, and only some way up the valleys
  behind them — which is why most legs are sea legs, and why winter closing the
  water is the year's hinge.
* **Goods are counted in loads.** One load of grain feeds twenty people for a
  year, so a hardy horse's seven is most of a small settlement's year and a
  deep-sea vessel is several settlements at once. Cargo is always whole loads.
* **A run is a round trip where the season affords it.** A carrier that can
  make the leg twice comes home rather than stranding itself empty at the far
  end, and it brings back what the place it left is short of.
* **A settlement below twenty-six people is given up at the winter check.**
  That threshold is also what "cannot survive this winter" means in the panel:
  what the winter will take leaves too few people to hold the place. It is
  arithmetic the player can read in advance, which is the point of §3.9.
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
| idle, at CHART and at FOCUS | 7.2 | 9.0 |
| dragging 600 px | 15.1 | 22.7 |
| a five-notch zoom | 12.4 | 24.8 |
| the season re-ink, over its second | 17.2 | 29.9 |

A full re-ink of the sheet is about 90 ms of work, which is why it is never
done in one frame. The dials are `PAN_QUANTUM` (how much margin the bitmap
carries before the view eats it), `INK_SLICE_MS` (how much ink work a frame may
do), the contour decimation in `_contour_step`, and hatch spacing.
