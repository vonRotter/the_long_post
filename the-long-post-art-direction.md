# THE LONG POST — art direction

Companion to the build specification. This document governs everything the player sees. It is binding: where this document and a rendering convenience disagree, this document wins.

---

## 1. The conceit

**The game is a working sea chart, maintained by hand, by someone in the world.**

Not a map of the world — a document *about* the world, kept up to date by the post service itself. It is drawn in ink on chart paper. It has soundings, hatched shoals, coastal profiles, and marginal notes. It has corrections, because the coast changed when the ice came and someone had to redraw it.

Two consequences follow, and both are load-bearing:

**Events are marks on the document.** When a settlement is abandoned it is not deleted — it is ruled through, in a heavier hand, and the strike stays there for the rest of the run. When an ice road opens, it is sketched in. When a courier is lost, a small mark goes in the margin beside that leg. By year eight the chart is dense with the player's history, and none of it was authored — it accumulated.

**Nothing needs to be illustrated.** Charts are functional documents made of lines, hatching, stipple, and type. Every one of those is cheap to generate and none of it requires an artist.

---

## 2. The materials

**Chart paper.** Warm off-white, slightly uneven. Generated once at startup with layered numpy noise: coarse fibre, fine grain, a soft vignette toward the edges, and three or four faint irregular stains placed per seed. Cached as a surface and blitted every frame. Zero per-frame cost.

**Ink.** Near-black, cold-leaning, never pure `#000`. Applied at four weights:

| Weight | Use |
|---|---|
| **Faint** | Graticule, soundings, the sea itself, anything ambient |
| **Normal** | Coastline, route lines, settlement circles, ordinary annotation |
| **Heavy** | Anything urgent — danger hatching, active shipments, shortfall warnings |
| **Correction** | Strikethroughs, abandonment, losses. The heaviest mark on the chart, and permanent |

**One accent colour.** A faded oxide red, used **only** for corrections and losses. Nothing else in the game is ever coloured. The first time the player sees red, they should already know it is bad.

---

## 3. Core rendering primitives

These five functions are the entire visual system. Build them first, in `render/ink.py`, and test them in isolation before drawing anything else.

### 3.1 `ink_line(a, b, weight, seed)` — the most important function in the project

**Never draw a straight line.** Subdivide every line into segments of roughly 6–10 px, displace each interior vertex perpendicular to the line by a small amount from smooth noise, and stroke the resulting polyline **two or three times** at slightly different offsets and alphas.

- Displacement amplitude scales with line length — long lines wander more.
- The `seed` argument must be derived from the line's identity, not from time. **A line must wobble identically every frame** or the chart will crawl and look like a bug.
- Slightly heavier deposit at the endpoints, mimicking where a pen starts and stops.

This one function is most of the difference between "programmer graphics" and "hand-drawn". Budget real time on it.

### 3.2 `ink_curve(points, weight, seed)`

The same treatment applied to a Catmull-Rom spline through control points. Used for coastline, route lines that follow terrain, and the wake behind a vessel.

### 3.3 `hatch(region, density, angle, seed)`

Parallel ink lines filling a region, at a given angle and spacing. This is how all tone is produced. **There are no filled areas anywhere in this game.**

Used for: sea state, danger on a route, ice, shoals, storm, avalanche mass, and the interior of a vignette.

Density is the game's primary continuous visual variable. A dangerous edge is not a different colour — it is more densely hatched. That reads instantly and needs no legend.

### 3.4 `stipple(region, density, seed)`

Random dots at controlled density. Snowfield, ice, and the soft edge where hatching fades out. Cheap and effective.

### 3.5 `mark(kind, position, seed)`

Small hand-drawn annotation glyphs: a cross, a circled dot, a tick, a query, a strike. These are the vocabulary of the chart's marginalia and the way small events leave a trace.

**Performance rule.** Everything static — paper, coastline, graticule, soundings, settlement glyphs — is rendered once to a cached surface and redrawn only when the chart actually changes (a season turns, a settlement dies, a route is built). Only moving things are drawn per frame. If the chart is being re-inked every frame, that is a bug, not a performance issue.

---

## 4. Three scales

The game moves between three levels of magnification. They share one visual language and differ only in what is resolved.

**Zoom is a player verb, not a scripted effect.** Scroll wheel or `+`/`-` to zoom, drag to pan, freely, at any time, including mid-resolution. The scale is continuous — CHART and FOCUS are ends of a range, not two modes, and detail is added progressively as the player draws in. During resolution the camera auto-focuses on the most consequential leg, but the player may override it at any moment and go watch something else. **The game never takes the camera away from the player.** Zoom and pan state persist between turns; a player who has been watching one vessel stays with it.

### 4.1 CHART — the default

The whole network at once. Schematic and calm.

- Settlements are **circles**, radius scaled to population, with the name set beside them in small type.
- Routes are **lines** between them: solid for open this season, dashed for hard, absent for closed. Length on screen roughly proportional to travel days, not to geography — this is a chart of *the network*, not of the coast.
- The sea between is faintly hatched. Land masses carry a sketched coastline and very light stipple.
- Soundings — small numerals scattered over the water — exist purely as texture and are generated once. They mean nothing. They are there because charts have them.
- Cargo in transit is a **single small dot** moving along its line.

This is where the player spends most of the game and it should feel like reading rather than watching.

### 4.2 FOCUS — tension

Reached by zooming in, by clicking a leg, or automatically when a shipment is in danger during resolution. Detail arrives progressively as the player draws in, so there is no visible switch between modes. At full FOCUS:

- The dot becomes a small drawn **hull** or **sledge** or **horse team** — six or seven lines, no more — with a wake or track sketched behind it.
- The sea gains real state: hatching thickens and its angle shifts with the weather.
- The destination settlement resolves from a circle into a small sketched cluster of roofs and a jetty.
- Distance remaining is shown as a hand-ruled measure along the edge, ticked off as it closes.

This is where the dot-that-must-get-home moment lives. It works because of the scale change and the ticking measure, not because of detail.

**The player may sit here as long as they like.** Nothing hurries them out, nothing dismisses the view, and no timer runs. A player watching their deep-sea vessel cross the last leg to harbour, with a storm's hatching thickening behind it, should be able to stay with that vessel until it arrives or does not. Making that possible is the entire reason the zoom is a player verb rather than a cutscene.

### 4.3 VIGNETTE — disaster

Reserved for a small number of events. Full-screen, framed with a ruled border as though pasted onto the chart, held for two to three seconds, then dismissed by any key.

**The restraint rule, and it governs this whole section.** The spec's §3.7 requires that loss be felt through absence rather than drama, and the vignettes are where that principle is most easily broken. So:

- A loss vignette holds for **two seconds and no longer**, and is dismissible immediately.
- No slow motion, no fade to black, no hold on a final frame, no music sting, no screen darkening.
- The chart is still visible behind the frame. The world does not stop for this.
- No text appears inside a vignette. Ever. The log line is one plain sentence and it belongs in the log.

A vignette is a glance, not an elegy. The weight arrives next season, in the assignment panel, when the player sees who is left.

Built from the same five primitives. **Six vignettes total, reused all run** — that is enough, because they are rare:

1. **Avalanche** — a mass of heavy hatching sweeping down over a thin line of a sledge and team.
2. **Storm at sea** — a small hull, heavy sea hatching at a steep angle, the horizon lost.
3. **Ice failure** — a jagged strike across a flat stippled plane, the track ending at it.
4. **Bandits** — figures as simple upright strokes at the edge of a track, and cargo marks scattered.
5. **Arrival** — the counterweight. A jetty, a small crowd of strokes, a hull alongside. Used when a shipment reaches a settlement in genuine need.
6. **Abandonment** — a settlement drawn in full, then struck through in oxide red as the vignette holds.

The arrival vignette matters as much as the disasters. A game that only frames its catastrophes teaches the player that success is invisible.

---

## 5. Marks that accumulate

The chart is a record, so it must show wear.

- A **route the player has used heavily** darkens over the run, as though re-inked many times. Your habitual network becomes visibly worn into the paper.
- A **leg where a courier was lost** gets a small cross in the margin beside it, permanent, with the year in tiny type.
- An **abandoned settlement** is struck through in oxide red and its routes fade to faint. It is never removed.
- A **built tunnel** is drawn as a firm double line — the only perfectly straight, un-wobbled line in the entire game. It should look like something engineered dropped onto a hand-drawn document, because that is exactly what it is.
- **Seasonal edges** — ice roads — are drawn in a lighter, sketchier hand, because they are provisional. They are erased in spring, leaving a faint ghost.

- A **settlement the arithmetic has already lost** is drawn with its circle in a broken outline, the way a chart marks something no longer to be relied on. It is not red — red is for what has already ended. This is a settlement still alive, still receiving post, and known to be finished.
- A **lost courier's name** stays in the assignment panel, set in faint ink, with their full history beside it. It is never removed and never greyed out further. The panel does not shorten.

By year ten the chart should be legible as a story without reading a single word of the log.

**The panel accumulates too.** The assignment panel is the game's other document, and it lengthens over the run: veterans with long records, faint names of the dead, settlements struck through. A player scrolling that panel in year nine is reading a decade of their own decisions. Do not compact it, do not archive it, do not offer a filter that hides the dead.

---

## 6. Typography

One typeface file in the repo — not an install, just a `.ttf` sitting in `data/`. A plain grotesque or a typewriter face. No decorative or blackletter type anywhere; this is a working document, not a fantasy map.

- Settlement names: small caps, letter-spaced, set beside the circle.
- Soundings and marginalia: very small, faint.
- The log and panels: the same face, plainly set.
- Numbers are set in the panel, never on the chart. **The chart carries no HUD.**

---

## 7. Motion

The game is turn-based, so motion is scarce and therefore meaningful.

- Resolution plays over roughly six seconds: dots move along their legs, hazards fire, the log fills line by line. Skippable with a key.
- Season change: the chart **redraws**. Closed edges are erased, new edges are inked in over about a second. This should feel like a hand revising the document, and it is the game's signature animation.
- Zoom and pan are smoothed but immediate — they respond on the frame the input arrives, with a short ease-out. Never a scripted camera move the player has to wait through.
- Nothing else animates. No idle motion, no pulsing, no drifting.

---

## 8. The last run

The ending has its own visual treatment and it is the only place in the game where the presentation changes.

When the run ends, the game does not cut away. It offers one final assignment — one carrier, one route, one cargo of the player's choosing — with the prompt set plainly on the chart:

> *One more run. What do you carry?*

Once loaded, the camera moves to FOCUS on that leg and stays. The resolution plays at that scale, uninterrupted, at normal speed. There is no log line, no panel, no readout — for this one run the chart is all there is.

When the carrier arrives, the last mark is inked onto the chart: the delivery, drawn like every delivery before it. Then the view pulls slowly back to CHART, far enough to show the whole network as it now stands — the strikethroughs, the worn routes, the margin crosses, the ghost edges, ten years of accumulated marks.

It holds there. No fade, no card, no music swell. The summary is reached by a keypress, not by a timer.

**Nothing in this sequence is embellished.** Same ink, same paper, same hand. The weight comes entirely from the chart being a record of what the player did, which is why every accumulation rule in §5 exists.

---

## 9. Sound, briefly

Procedural only, in the same restrained register: a wind bed thickening through winter, pen-scratch as marks are inked during resolution, a low tone on shortfall, a heavier one on a loss, and one warm note on an arrival in need. The pen scratch is the important one — it reinforces that everything the player is seeing is being written down.

---

## 10. Milestones

Fold into the build spec's milestones rather than running separately.

**A0 — Ink.** The five primitives, exercised on a test screen: wobbly lines, curves, hatching at varying density, stipple, marks, on generated paper. *Acceptance:* a page of these primitives alone looks hand-drawn, and nothing crawls between frames.

**A1 — Chart.** Full network at CHART scale, with the seasonal redraw. *Acceptance:* the seasonal inversion is beautiful and instantly readable — winter erases the sea lanes and inks in the ice roads.

**A2 — Focus and free zoom.** Continuous zoom and pan as a player control, progressive detail, vessels and teams, the ruled distance measure, sea state. *Acceptance:* watching a dot cross a dangerous leg at FOCUS scale is tense with no text on screen, and zooming around the chart is pleasant enough that a player does it for no reason.

**A3 — Accumulation.** Wear, margin crosses, strikethroughs, tunnel double-lines, ghost edges. *Acceptance:* a chart at year eight looks meaningfully different from one at year one, and the difference tells the truth about the run.

**A4 — Vignettes.** All six, under the restraint rule. *Acceptance:* they read as part of the same document rather than as an interruption, and a loss vignette is over before the player has finished reacting to it. **If a vignette feels like the game asking for a reaction, it is too long.**

**A5 — The last run.** The final assignment prompt, the uninterrupted FOCUS run, the pull-back to the finished chart. *Acceptance:* the final pull-back lands with no music, no text, and nothing added — purely on the accumulated marks.

---

## 11. What not to do

- No colour beyond ink and the single oxide accent.
- No filled shapes. Tone is hatching, always.
- No straight lines except the tunnel.
- No icons in a modern UI idiom. Every glyph is something a chart would plausibly carry.
- No AI-generated images, no photographs, no raster art of any kind. A single inconsistent image would make every drawn moment in the game look poorer than it is.
- No numbers on the chart. The panel is for numbers.
- No screen shake, no particles, no glow, no bloom.
- **No visual sentimentality.** No fade to black on a loss, no slow motion, no lingering hold, no darkening of the screen, no candle guttering out, no vignette that outlasts two seconds. The game does not ask the player to feel something; it shows what happened and moves to the next season.
- No text inside a vignette, ever.
- No memorial screen, no roll of the dead, no epitaph. The record in the panel is the memorial, and it is a working document rather than a monument.
- Never remove a lost courier's name or an abandoned settlement from where the player is used to seeing it. Absence is only felt where presence used to be.
