# THE LONG POST — build specification

*(v2. Supersedes the previous draft. Courier traits removed; desperation model, doomed settlements, and the ending added.)*

The world froze. What is left of the north is a scatter of settlements that cannot survive alone, and the only thing connecting them is you: a post service with too few people, too few animals, and a season that closes half the map for four months of the year.

You will not save it. Everyone in this world already knows that. The question is only how long the light stays on, and who is warm when it goes out.

*(Working title — rename freely.)*

This document is the build brief. Work the milestones in order. Each must run and be playable on its own. Stop for review at the end of each. The companion document `the-long-post-art-direction.md` governs everything visual and is binding.

---

## 1. Design thesis

**Three ideas.**

*A route network under season.* Settlements are nodes, routes are edges, and half of them close for a third of the year. You assign carriers, you commit, the season resolves. You never control anything in motion.

*A kind world the environment does not respect.* Nobody in this game is evil. The bandits on the eastern road are a settlement that stopped being able to feed itself. A courier who steals your grain took it to their own village, which you had not shipped to in two years. Every antagonist in the game is somebody's neighbour making an arithmetic decision under pressure the player can see.

*A managed decline.* You cannot win. The aggregate population is falling from turn one and the panel says so plainly. The game is not about preventing the end; it is about what you do with the time and what you carry on the last run.

**The spine is a graph, and every complication attaches to a specific edge in a specific season.** When a shipment is lost, the player can point at the leg and name the cause. Traceability is non-negotiable — it is the difference between this and a game where bad things simply happen.

**Failure is felt through absence, not through drama.** See §3.7. This is the most important design rule in the document and the easiest to get wrong.

### Non-negotiables

- **Turn-based by season.** Four turns per year. No real-time movement, ever.
- No combat. Bandits are a hazard with a cause, never an enemy to fight.
- No villains. Every hostile act in the game must be traceable to a material pressure the player could have relieved.
- Every loss must be traceable to a visible cause the player could have weighed beforehand.
- The player can zoom, freely, at any time. See §3.11.
- Kindness must never be secretly optimal. See §3.9.
- The game is unwinnable and says so. It does not present a survival goal it then denies.
- A full run is **10 years = 40 turns**, and should take 60–90 minutes.

### Anti-goals

No tactical combat, no base building, no tech tree, no dialogue trees, no character portraits, no morality score, no redemption arc, no twist. **No courier stat blocks** — see §3.5. If a system does not change what you ship, who ships it, or whether it arrives, it does not go in.

---

## 2. Technical constraints

- Python 3.11+, `pygame` and `numpy` only, plus one `.ttf` font file in `data/`. No build step.
- Runs as `python -m longpost` from repo root.
- Window 1280 × 720. Chart on the left, panel on the right, log along the bottom.
- Turn-based. Resolution animates over a few seconds and is skippable.
- Deterministic given a seed and an input trace. **This matters more here than in any previous project** — the player must be able to replay a disastrous year and watch it unfold identically.
- All constants and content tables in `tuning.py` and `data/`.

### Repo layout

```
longpost/
  __main__.py       window, turn loop, phases
  tuning.py         every constant
  data/
    carriers.py     carrier types
    events.py       hazard definitions
    names.py        settlement and person names
    chart.ttf       the one asset in the project
  world/
    map.py          nodes, edges, generation
    season.py       season profiles, edge availability
    settlement.py   needs, population, decline, doom, abandonment
    desperation.py  the pressure model — see 3.6
  post/
    courier.py      couriers: condition, loyalty, history
    carrier.py      animals, boats, sleds, tunnels
    assign.py       orders, standing orders, delegation
    resolve.py      season resolution — the core simulation
  render/
    ink.py          the five drawing primitives
    chart_view.py   CHART / FOCUS / VIGNETTE scales, camera
    panel.py        readouts, assignment UI
    log.py          the resolution log
  debug/
    overlay.py      edge risk, desperation values, F-keys
tests/
```

### Debug keys

`F1` edge risk and season profile · `F2` desperation values per settlement and per courier · `F3` reseed · `F4` replay last season's resolution.

---

## 3. Systems

### 3.1 The map

Generated per seed. **5 settlements at start, up to 20 discoverable.**

Each **settlement** has:
- A population, and needs per year: `GRAIN`, `FUEL`, `MEDICINE`, `TOOLS`, `POST`.
- A **surplus**: one or two goods it produces beyond its own needs. This is why the network exists — nobody has everything.
- A **standing**, 0–100: how much it trusts the post. Low standing means fewer recruits and eventually refusal to deal.
- A **desperation** value, 0–100. See §3.6. This is the most important number in the game and it drives nearly everything hostile.

Each **edge** has: length in travel days; a **season profile** (`OPEN`, `HARD`, `CLOSED` per season); a **terrain type** (`COAST`, `INLAND`, `PASS`, `TUNNEL`); and a **danger** value derived from terrain, season, and the desperation of settlements near it.

**The seasonal inversion is the map's best feature.** Some edges exist only in winter — ice roads over frozen water, fjord crossings impassable when liquid. Winter closes the sea and opens the ice. A route that is your lifeline in February does not exist in June, and the player must hold two maps in their head.

### 3.2 Seasons

| Season | Sea | Passes | Inland | Character |
|---|---|---|---|---|
| **Autumn** | open | open | open | Everything is possible. You overcommit. |
| **Winter** | closed | hard | ice roads open | Sleds and dogs. New edges appear. |
| **Spring** | opening | closed | thaw, mud | The worst season. Almost nothing moves. |
| **Summer** | open | open | good | Recovery, building, breeding. |

Needs are consumed continuously but **checked at the end of winter**. What you failed to ship in autumn kills people in February. This delay is the game's central cruelty and it must be legible: the panel always shows each settlement's projected winter shortfall against what has actually arrived.

### 3.3 Carriers

| Carrier | Capacity | Speed | Seasons | Notes |
|---|---|---|---|---|
| **Fast horse** | low | high | not deep winter | Outruns trouble. Eats grain year-round. |
| **Hardy horse** | medium | low | all but spring | Eats scrub. Caught by anything that wants to. |
| **Dog sled** | low | high | winter only | The only thing that makes deep winter routine. |
| **Small boat** | medium | medium | coast, not winter | Weather-sensitive. |
| **Deep-sea vessel** | very high | medium | open sea, not winter | Enormous capacity, ruinous to lose. |
| **Tunnel** | unlimited | instant | all | Excavated. See §3.4. |

**Breeding.** In summer you may breed horses, selecting for speed or hardiness. A foal takes three years to be useful. This is the long-horizon investment, and it should be made in year two by a player who understands the game.

### 3.4 Tunnels — the only permanent thing

Some edges have a pre-collapse tunnel or rail line, collapsed or flooded. Excavating one costs many seasons of labour, tools, fuel, and people diverted from carrying.

A completed tunnel makes that edge `OPEN` in every season, at zero danger, forever.

It is the only investment that produces permanent reliability, priced so the player can afford **one, maybe two, in ten years**. Choosing which edge deserves it is the biggest strategic decision in the game. Building the wrong one is survivable and painful.

### 3.5 Couriers — people, not stat blocks

**There are no trait tables.** A courier is a name, a condition, a loyalty, and a history. That is all.

- **Condition**, 0–100. Falls with hard seasons and consecutive runs, recovers with rest. A courier run into the ground is lost — to injury, to leaving, or to not coming back.
- **Loyalty**, 0–100. Built by rest, fair loads, and by the post serving their home settlement. Eroded by hard seasons, by repeated dangerous assignments, and by neglecting where they are from.
- **Home.** Every courier is *from* somewhere on the map. This single fact replaces the entire trait system and does more work than it did. It determines what they care about, why they might steal, and what it means when their home is the settlement you cannot save.
- **History.** A visible, accumulating record: routes run, loads delivered, loads lost, seasons served. **This is how couriers become relatable.** *Sigrid has run the Nordfjord leg eleven times* is worth more than any stat block, and it costs nothing to generate because it is simply true.

Competence is not a hidden number. A courier gets better at a route by running it — a visible count of prior runs on that leg gives a real, small bonus. The player's veterans are veterans because of what the player asked of them.

### 3.6 Desperation — the engine under everything hostile

Every settlement has a desperation value, visible on the chart as hatching density and in the panel as a plain band.

It rises with: unmet needs, deaths over winter, isolation (seasons since a delivery), and the collapse of a neighbouring settlement. It falls with: deliveries, especially in the season they were needed, and with `POST`.

Desperation drives:

- **Bandit hazard** on edges near that settlement. *Bandits are not a faction.* They are that settlement's people, and the game's log should say so plainly: *the road east of Kvitvik is being watched. Kvitvik has had nothing since spring.*
- **Recruitment** — desperate settlements offer more couriers, which is a grim source of labour and should feel like one.
- **Refusal to deal** at the extreme.

**The loop that matters most in the game:** the player's own failures raise desperation, which raises danger, which makes those settlements harder to serve, which raises desperation further. The player must be able to see this happening and recognise it as their own doing. **If the player ships to a bandit-plagued road's source settlement, the road gets safer.** This must be discoverable through play, never explained in a tutorial, and it is the moment the game's thesis lands.

### 3.7 Loss — absence, not drama

**This is the most important section in the document.**

The rule: **never dramatise the death; dramatise the absence.**

When a courier is lost:
- The vignette is two seconds and does not linger. It is not scored, not slowed, not underlined.
- The log line is one plain sentence. No adjectives. *Sigrid was lost on the Nordfjord leg in the third week of winter.*
- No music sting, no fade to black, no memorial screen.

Then, and this is where it lands:
- Her name remains in the assignment panel for the rest of the run, greyed, with her full history beside it — eleven runs on Nordfjord.
- The Nordfjord leg still needs someone next season, and the panel shows who is left.
- Her worn ink stays on that route on the chart for the remaining years. A small cross sits in the margin with the year.
- **The game never mentions her again.**

The same principle applies to a settlement. No requiem. It is struck through on the chart, its routes fade, and every subsequent season the player routes around a hole that used to be a place. The summary at the end lists it by name and year, once.

**Failure states are never accompanied by an explanation of how the player should feel.** No text ever tells the player this is sad. The game states facts plainly and lets the arithmetic do the work.

### 3.8 Theft — desperation, not character

A courier may take the cargo. It is evaluated at resolution from pressures **all visible before the assignment**:

- Their loyalty and condition.
- The desperation of their **home** settlement.
- The desperation of settlements the route passes through.
- The value of the cargo against what the settlement they are serving actually needs.

Afterwards, **the game tells the player where the grain went.** It went to their home village, three days off the route, which the player had not shipped to in two years. That village is on the chart. The player can look at it.

A courier who steals may vanish, or may return and keep working — with their home settlement's standing toward the post now higher, and the player's stores lower. There is no punishment mechanic and no forgiveness mechanic. There is only what happened and what the player does next season.

### 3.9 Doomed settlements — kindness with no payoff

Some settlements are, by arithmetic, already lost. Their population and surplus cannot carry them through the coming winter even with a full delivery, and **the panel says so plainly**, in advance, in ordinary language: *Kvitvik cannot survive this winter.*

Shipping to them is a genuine waste of capacity. It does not extend their life. It does not raise standing usefully. It produces no resource, no recruit, and no mechanical advantage of any kind.

**It must never be secretly optimal.** No hidden bonus, no delayed reward, no survivor who later turns up and repays the kindness. The moment kindness becomes a strategy it stops being kindness, and the game's entire premise collapses.

What the game does instead: it **records it**. In the log at the time, and in the end-of-run summary, plainly:

> *Kvitvik received grain in the winter it ended.*

That line is the only thing the player gets. It is enough, and it is the whole argument of the game.

**Implementation note:** this must be tested. `tests/test_kindness.py` verifies that shipping to a doomed settlement produces no measurable advantage on any run outcome. If a headless player who always serves doomed settlements outperforms one who never does, the design has failed.

### 3.10 Post — why the service exists

`POST` is a good, with a function no other good has: **delivering post reduces desperation and raises standing at both ends of the route.** It is how the network holds together socially.

It weighs nothing and it is always the first thing dropped when a load must be lightened. A player who never carries letters finds, around year four, that nobody will work for them and every road is watched.

That is the game's thesis expressed as a mechanic and never as dialogue.

### 3.11 Zoom — a first-class control

**The player can zoom freely, at any time, with the scroll wheel or `+`/`-`, and pan by dragging.** This is not restricted to cutscenes or scripted moments. It is a core verb.

Three scales, per the art direction:

- **CHART** — the whole network, schematic. The default and where most play happens.
- **FOCUS** — one edge or one settlement. Vessels become drawn hulls with wakes, the sea gains state, distance remaining is ticked off along a ruled measure. The player may sit here and watch a single shipment cross for as long as they like.
- **VIGNETTE** — a framed full-screen moment for six specific events.

**During resolution the camera auto-focuses on the most consequential leg**, but the player can override it at any time and go watch something else, and can zoom back out. The game never takes the camera away from them.

Zoom state persists between turns. A player who has been watching one vessel stays with it.

### 3.12 Turn structure

1. **Report** — what arrived, what did not, who did what, settlement states, desperation changes.
2. **Plan** — assign couriers and carriers, set cargo, adjust standing orders, commit labour to tunnels, breed in summer.
3. **Commit** — irreversible.
4. **Resolve** — legs run, hazards fire, theft evaluates, the log fills. Animated over about six seconds, skippable, freely navigable by camera.

### 3.13 Delegation — the late game

Once the network exceeds roughly eight active routes, micromanagement becomes impractical. **Standing orders** — a route, a carrier, a cargo priority, a courier or pool — run every season the route is open until changed.

Standing orders report by exception: only what went wrong, what went unusually well, and any courier whose situation changed.

**This is not an unlock.** It is available from turn one and simply becomes necessary. The player's attention shifts from people to network because the network outgrew them, which is the honest version of that transition — and it is also why a courier they had stopped reading about surfaces again when they are lost.

### 3.14 The ending

There is no victory condition. The run ends when **the network can no longer sustain itself** — fewer than three settlements remain connected — or when ten years elapse, whichever comes first. In a well-played run it will usually be the latter, and the population will still be falling.

**The last run.** When the ending triggers, the game does not cut to a summary. It offers one final assignment: one carrier, one route, and a cargo the player chooses.

There is no score attached. Nothing is calculated from it. The prompt is plain:

> *One more run. What do you carry?*

The player loads it, the resolution plays out at FOCUS scale, the last mark goes onto the chart, and the game stops.

**Summary screen**, plainly set: settlements surviving and lost by name and year, population at start and end, tunnels built, couriers who served all ten years and couriers lost with their histories intact, loads stolen and where they went, the year the network was at its largest, and every line of the form *X received grain in the winter it ended.*

The headline figure is not a score. It is: **years the post ran.**

### 3.15 Tone rules for all written text

Every line of text in the game — log, panel, summary — follows these:

- Plain declarative sentences. No adjectives of feeling. Never *tragically*, *sadly*, *heroically*.
- Never tell the player how to feel about an event.
- Never editorialise about a courier's or settlement's choices. *Ranveig took the grain to Hesthamn* — not *betrayed you*.
- Numbers where numbers are honest; words where they are not.
- No second person imperatives. The game does not instruct.

---

## 4. Milestones

**M0 — Chart and turns.** Generated graph, seasons, edge availability changing per season, turn advance, **free zoom and pan**. No cargo, no couriers. *Acceptance:* the seasonal inversion is immediately legible, and zooming around the chart is pleasant on its own.

**M1 — Shipping.** Carriers, cargo, assignment, settlement needs, the end-of-winter check, decline and abandonment. *Acceptance:* a player who under-ships in autumn watches a settlement die in February and knows exactly which deliveries they failed to make.

**M2 — Desperation gate.** The desperation model, bandit hazard driven by it, the feedback loop, and the discovery that serving a settlement calms its road. **This is the gate.** *Acceptance:* a player identifies a dangerous region as their own doing, ships to it, watches it calm, and describes this as the moment they understood the game. **If hostility reads as random rather than caused, stop and fix the pressure model before building anything on top of it.**

**M3 — Couriers and loss.** Named couriers, condition, loyalty, home, history, route familiarity, theft with full visible pressures, and the absence model of §3.7 in full. *Acceptance:* losing a veteran courier is felt in the assignment panel the following season, not in the moment it happens.

**M4 — The long game.** Tunnels, breeding, post and standing, discovery, doomed settlements and the kindness rule. *Acceptance:* a player ships to a settlement they know is lost, receives nothing for it, and does it again the next year.

**M5 — Delegation and scale.** Standing orders, exception reporting, courier history surfacing. *Acceptance:* by year five the player has stopped reading individual assignments, and a courier they had forgotten returns to their attention through a loss.

**M6 — The ending.** The last run, the summary, tuning pass. *Acceptance:* a ten-year run takes 60–90 minutes, the population trend is visibly downward throughout, and the final prompt lands without any text telling the player it should.

---

## 5. Testing

- `tests/test_map.py` — over 300 seeds, every settlement is reachable in at least one season; none is isolated in all four; ice-road edges never coexist with their open-water counterparts in the same season.
- `tests/test_needs.py` — a settlement receiving exactly its needs never declines; one receiving nothing declines on a predictable schedule.
- `tests/test_desperation.py` — desperation is monotonic in every input; sustained delivery to a settlement always reduces the danger of its adjacent edges; **no edge is ever dangerous without a traceable desperation source.**
- `tests/test_theft.py` — theft probability is monotonic in every pressure; with all pressures at minimum it never occurs; **a theft never fires without at least two pressures being visible to the player at assignment time**; the destination of stolen cargo is always a settlement on the map.
- `tests/test_kindness.py` — over 200 headless runs, a player who always ships to doomed settlements does **not** outperform one who never does, on any outcome measure. **Kindness must be mechanically neutral.**
- `tests/test_decline.py` — aggregate population is non-increasing across a full run under every scripted strategy. There is no winning line.
- `tests/test_determinism.py` — the same seed and input trace produce an identical world state and an identical log after 40 turns.
- `tests/test_tone.py` — a lint pass over all generated text strings, failing on a banned word list (*tragic*, *heroic*, *sadly*, *betrayed*, *bravely*, and similar). Blunt, but it keeps §3.15 honest over a long build.

---

## 6. Open questions

Raise at the milestone where they bite, with a recommendation.

1. Should couriers be recruitable freely, or should losing one be near-permanent? Scarcity makes every assignment heavier. Recommend scarce, with recruits arriving mainly from desperate settlements. Decide at M3.
2. Numeric risk on a route, or bands (*safe / hard / desperate*)? Bands preserve tension; numbers preserve trust. Recommend bands, with numbers in the debug overlay. Decide at M2.
3. Is ten years right? Long enough for breeding and tunnels to matter, possibly too long to hold attention. Test eight and twelve at M6.
4. Should settlements ever be *founded*? A growing map would contradict the thesis. Recommend no. Confirm at M4.
5. Money at all, or purely goods and standing? Recommend none. Decide at M1.
6. Should the player be told a settlement is doomed, or should they work it out? Telling them plainly is stronger — it removes any excuse of ignorance and makes the choice fully conscious. Recommend telling. Confirm at M4.
