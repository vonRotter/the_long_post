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

Built: **A0 — Ink**, **M0 / A1 / A2 — Chart, turns, free zoom**,
**M1 — Shipping**, **M2 — the desperation gate**, **M3 — Couriers and loss**,
**M4 — the long game**, **M5 — delegation and scale**, and **M6 — the ending.**

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
* `world/desperation.py` — the pressure model, and the only source of anything
  hostile in the game. Desperation rises with unmet need, isolation, deaths and
  neighbours given up, and falls with deliveries and with post. A road is
  dangerous because a settlement near it has nothing, the road remembers which
  settlement, and terrain and season only scale what desperation has already
  caused: on a calm map every road is safe. A load that is taken goes to that
  settlement's stores, and if the post had never found the place, it goes onto
  the chart by that fact.
* `post/courier.py` — people, not stat blocks. A courier is a name, a
  condition, a loyalty, a home and a history, and the history is the part that
  does the work because it is simply true. Competence is not hidden either: a
  leg run before is easier, and the count of prior runs is on the panel. Theft
  is read off five pressures — their loyalty, their condition, their home's
  desperation, the desperation on the route, and how little the destination
  needs the load — every one of which is on the panel before the season is
  committed, and never fires on fewer than two of them.
* **The ending.** The run ends when the network can no longer hold itself
  together — fewer than three settlements still reachable from each other — or
  when ten years are up, and in a well-played run it is the latter with the
  population still falling. Then the game does not cut away: it offers one more
  run, one carrier, one leg, and a cargo of the player's choosing, played at
  FOCUS with the chart the only thing on screen and no way to hurry it. When it
  arrives the view pulls back to the whole chart as it now stands, and holds
  there. The summary is reached by a keypress, and its headline figure is not a
  score: it is the number of years the post ran.
* **Delegation.** A route can be kept: a carrier, a leg, and either a named
  courier or whoever is fit and standing there. It runs itself every season the
  route is open, and it reports by exception — what went wrong, what went
  unusually well, and anything that changed for the worse about a courier. The
  seasons that go as they were meant to are counted, not recited. It is
  available from the first turn and simply becomes necessary, which is the
  honest version of that transition.
* **The long game.** A collapsed line under a pass or a sound can be dug out:
  ten seasons of a courier and their team not carrying anything, and thirty
  loads of tools and twenty of fuel carried to whichever end they are standing
  at. What it buys is the only permanent thing in the game — an edge open in
  every season, at no danger, forever. Horses are bred in summer and a foal is
  three years from being any use. Letters raise standing at both ends of a
  route, and a settlement that trusts the post tells it about a neighbour it
  had not found, which is how the chart grows.
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

Not built yet: the six vignettes (A4) and the sound (§9).

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
`tests/test_desperation.py` (monotonic in every input, a calm map has no
dangerous road, serving a settlement calms the roads beside it, and no load is
ever taken on a leg the panel called safe) ·
`tests/test_ending.py` (ten years ends it, so does a network that cannot hold
itself together, the last run is not skippable, and the summary is a record
rather than a score) · `tests/test_delegation.py` (a kept route runs itself, never overrules an order
the player gave, reports a stall once and then stops repeating it, and brings a
courier who is wearing down back to the player's attention) ·
`tests/test_kindness.py` (120 headless runs: a player who always serves the
settlements the arithmetic has ended does not beat one who never does, on
population, settlements, standing, recruits, roads or desperation) ·
`tests/test_long_game.py` (a tunnel takes its seasons and its loads and then
never closes; post raises standing at both ends; a foal is three years) ·
`tests/test_couriers.py` (wear and rest, theft monotonic in every pressure and
never on fewer than two, a stolen load always goes to a settlement on the map,
and a lost courier stays in the panel with their record and is never mentioned
again) · `tests/test_determinism.py` (including a lint that fails the build if
`hash()` reappears: Python randomises string hashing per process, so a run
seeded through it would not replay) · `tests/test_tone.py` (a lint pass over
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
* **Bands, not numbers** (§6.2, settled at M2). The panel says calm, strained,
  desperate, and safe, watched, dangerous. The numbers behind them are in the
  debug overlay, which is where trust in a band is checked.
* **A settlement that stops a load goes onto the chart.** Nothing hostile is
  allowed to happen off the document: if the player is told where the grain
  went, they must be able to look at the place it went to.
* **Couriers are scarce** (§6.1, settled at M3). Four to begin with, and
  recruits arrive mainly from settlements desperate enough that the work is
  worth taking — which is a grim source of labour and reads as one. A
  settlement that has stopped trusting the post sends nobody.
* **A courier is lost by a roll the panel showed.** Condition and the road's
  danger are both bands on the panel before the season is committed, and they
  are the only two things the roll reads.
* **Ten years is right** (§6.3, settled at M6). Measured over six seeds at
  eight, ten and twelve: eight leaves the north down about half with two
  settlements gone, which shows the decline but not the thinning; twelve costs
  another two years to watch what year ten has already decided, and ends early
  more often. Ten is where the settlements actually go while the ending is
  still in doubt.
* **No settlements are ever founded** (§6.4, settled at M4). The map only ever
  loses places; the chart grows because the post finds what was already there.
* **Doom is arithmetic, not pessimism** (§3.9). A settlement is doomed when what
  this winter is already owed — the seasons it has already gone short — ends it
  whatever arrives from here on. A settlement that is merely short is not
  doomed: that one the post can still save, and saving it is the game. A doomed
  settlement's desperation never falls again, so shipping to it cannot make a
  road safer, produce a recruit, or buy anything at all. What the player gets is
  the line in the log and in the summary: *Kvitvik received grain in the winter
  it ended.*
* **A load is a caravan's load.** One load of grain is a year for ten people,
  and a carrier is a team rather than an animal: eight horses and four drivers,
  three sleds, a boat and five hands, a vessel and eighteen. The courier is who
  leads it. That is what makes overland a trickle and the sea the artery — and
  winter taking the artery away the shape of the year.

## Open questions, at the milestone where they bite

*(none open)*

## Frame budget

Measured headless at 1280 × 720, seed 3, in milliseconds per frame:

| | median | worst |
|---|---|---|
| idle, at CHART and at FOCUS | 6.0 | 8.8 |
| dragging 600 px | 14.7 | 23.4 |
| a five-notch zoom | 11.7 | 27.1 |
| the season re-ink, over its second | 14.8 | 26.8 |

A full re-ink of the sheet is about 90 ms of work, which is why it is never
done in one frame. The dials are `PAN_QUANTUM` (how much margin the bitmap
carries before the view eats it), `INK_SLICE_MS` (how much ink work a frame may
do), the contour decimation in `_contour_step`, and hatch spacing.
