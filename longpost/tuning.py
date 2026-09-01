"""Every constant in the game.

Nothing here is derived at runtime and nothing outside this module invents a
number. The build spec requires all tuning to live in one place.
"""

# --- window ---------------------------------------------------------------

WINDOW_W = 1280
WINDOW_H = 720
FPS = 60
TITLE = "The Long Post"

# Chart on the left, panel on the right, log along the bottom.
PANEL_W = 340
LOG_H = 140
CHART_RECT = (0, 0, WINDOW_W - PANEL_W, WINDOW_H - LOG_H)
PANEL_RECT = (WINDOW_W - PANEL_W, 0, PANEL_W, WINDOW_H)
LOG_RECT = (0, WINDOW_H - LOG_H, WINDOW_W - PANEL_W, LOG_H)

# --- paper and ink --------------------------------------------------------

PAPER_BASE = (232, 226, 212)      # warm off-white
PAPER_FIBRE = 5                   # coarse fibre amplitude
PAPER_GRAIN = 4                   # fine grain amplitude
PAPER_VIGNETTE = 0.20             # darkening toward the edges
PAPER_STAINS = (3, 5)             # count range, placed per seed

INK = (26, 28, 34)                # near-black, cold-leaning, never pure black
OXIDE = (146, 62, 48)             # the one accent, corrections and losses only

# weight -> (passes, alphas, offset spread in px)
INK_WEIGHTS = {
    "faint":      (1, (70,), 0.0),
    "normal":     (2, (95, 165), 0.5),
    # the post's own lines: legs and settlements, re-inked oftener than the
    # coast around them, and the thing the chart is actually about
    "route":      (2, (150, 215), 0.55),
    "heavy":      (3, (110, 175, 235), 0.9),
    "correction": (3, (150, 205, 250), 1.4),
}

INK_SEGMENT_PX = 8.0              # subdivision length of a stroke
INK_WOBBLE_BASE = 0.55            # px of displacement, short lines
INK_WOBBLE_PER_PX = 0.010         # extra displacement per px of length
INK_WOBBLE_MAX = 4.5
INK_ENDPOINT_WEIGHT = 1           # extra deposit passes at pen start and stop

HATCH_SPACING_MIN = 3.0           # px between hatch lines at density 1.0
HATCH_SPACING_MAX = 22.0          # px between hatch lines at density 0.0

# --- camera ---------------------------------------------------------------

ZOOM_CHART = 1.0                  # the whole network
ZOOM_FOCUS = 6.0                  # one edge or one settlement
ZOOM_MIN = 0.55
ZOOM_MAX = 9.0
ZOOM_STEP = 1.16                  # per wheel notch or +/- press
CAMERA_EASE = 0.24                # ease-out per frame toward the target
CAMERA_SNAP = 0.35                # px/zoom epsilon below which the ease ends

# Detail arrives progressively; these are the thresholds it arrives at.
DETAIL_NAMES = 0.8
DETAIL_ROOFS = 3.0
DETAIL_HULLS = 2.2
DETAIL_MEASURE = 3.4
DETAIL_HACHURE = 1.5      # below this, high ground is drawn as contours only

# --- world ----------------------------------------------------------------

WORLD_W = 2800.0
WORLD_H = 1650.0

SETTLEMENTS_START = 5
SETTLEMENTS_MAX = 20
SETTLEMENT_MIN_SPACING = 360.0
SETTLEMENT_PLACEMENT_TRIES = 9000
SETTLEMENT_COAST_BAND = 170.0     # within this of the shore is a coastal site
SETTLEMENT_INLAND_CHANCE = 0.4    # how often a site well inland is taken anyway

# Settlements are not the same size. Most of the north lives in a handful of
# towns and the rest in places of a few hundred, so the draw is skewed: the
# exponent decides how rare the big ones are.
POP_SMALLEST = 150
POP_LARGEST = 1600
POP_SKEW = 2.6
STANDING_START = 55

# --- the economy ----------------------------------------------------------

# A settlement produces its surplus goods at this multiple of its own yearly
# need for them. Nobody produces everything, which is why the network exists.
SURPLUS_RATE = 2.6
STORES_AT_START = 0.70            # fraction of a year's need already held

# What a shortfall costs, at the end of winter. Weighted by good: nobody dies
# of a tool shortage, and a winter without fuel is nearly a winter without
# grain. In head-years unsupplied.
# A settlement given nothing at all for a year loses the sum of these, as a
# share of its people. Grain is most of it; nobody dies of a tool shortage.
SHORTFALL_DEATHS = {"GRAIN": 0.100, "FUEL": 0.055, "MEDICINE": 0.025,
                    "TOOLS": 0.0, "POST": 0.0}
# Below this, at the end of a winter, a settlement is given up: too few people
# left to hold the place through another one. It is also what makes a
# settlement doomed in advance — see Settlement.doomed and the spec's §3.9.
ABANDON_POPULATION = 60

# The land is a coast: open sea to the west, and a shore of skerries, islands
# and fjords giving onto high ground in the east. All of it is one noise field
# read at several levels — see world/terrain.py.
TERRAIN_CELL = 9.0                # world units per elevation cell
SEA_LEVEL = 0.50
MOUNTAIN_LEVEL = 0.78
# How the ground rises from west to east: (across the sheet, height). The long
# middle section sits just under the waterline, which is what makes the outer
# archipelago a belt of rock and sounds rather than an edge.
COAST_PROFILE = ((0.00, 0.00), (0.22, 0.04), (0.42, 0.40), (0.60, 0.58),
                 (0.80, 0.90), (1.00, 1.00))
COAST_GRADIENT = 0.28             # how much of the height is that rise
COAST_BASE = (7, 6)               # the largest features, in cells across
COAST_STRETCH = 1.6               # features elongated east to west: fjords
COAST_ROUGHNESS = 0.66            # how much the fine octaves carry
COAST_SHELF = 0.70                # ground squeezed toward the waterline
SKERRY_AMOUNT = 0.26              # how hard the shallows break into rock
SKERRY_DEPTH = 0.055              # how far below the waterline that happens
SKERRY_BAND = 0.075               # and over what depth of water
COAST_WARP = 150.0                # world units the ground is warped before read

DEPTH_LEVELS = (0.035, 0.085)     # contours below the shore, out at sea
SHORE_LEVELS = (0.030,)           # contours above it, behind the shore
MIN_ISLAND_AREA = 900.0           # smaller loops than this are not inked

EDGE_NEIGHBOURS = 3               # k-nearest candidate edges per settlement
EDGE_MAX_LENGTH = 950.0
TRAVEL_DAYS_PER_UNIT = 0.022      # world units -> travel days
ICE_ROAD_MAX_LENGTH = 600.0       # sea crossings longer than this never freeze
TUNNEL_SITE_CHANCE = 0.22         # edges carrying a collapsed pre-collapse line

# --- desperation, and the roads it makes dangerous -----------------------

# What the pressure model weighs. All four pressures push up, relief pulls
# down, and nothing else touches it — see world/desperation.py.
DESPERATION_WEIGHTS = {
    "hunger": 0.85,
    "isolation": 0.50,
    "grief": 0.55,
    "bereavement": 0.30,
    "relief": 0.70,
}
DESPERATION_HUNGER_GOODS = {"GRAIN": 1.0, "FUEL": 0.6, "MEDICINE": 0.25}
DESPERATION_ISOLATION = 6.0       # seasons without a delivery to reach the top
DESPERATION_POST_RELIEF = 0.22    # what letters are worth, beyond their weight
DESPERATION_RISE = 0.45           # how fast it climbs toward its pressures
DESPERATION_FALL = 0.28           # and how much more slowly it comes down
DESPERATION_REFUSAL = 92.0        # at the extreme, a settlement keeps what it has
DESPERATION_WATCH_RADIUS = 500.0  # how far its desperation reaches down a road

# Terrain and season scale what desperation has already caused; they never
# create danger on their own. A finished tunnel is zero, forever.
DANGER_TERRAIN = {"INLAND": 1.0, "PASS": 1.15, "COAST": 0.5, "ICE": 0.75,
                  "TUNNEL": 0.0}
DANGER_SEASON = {"AUTUMN": 1.0, "WINTER": 1.15, "SPRING": 1.05, "SUMMER": 0.85}
DANGER_THRESHOLD = 0.30           # below this a settlement watches nobody
HAZARD_SCALE = 0.75               # chance of a load being taken, at full danger

# Bands, not numbers: the panel says calm, strained, desperate — and safe,
# watched, dangerous. The numbers behind them are in the debug overlay (§6.2,
# settled at M2: bands preserve tension, numbers preserve trust, and the
# overlay is where trust is checked).
BAND_CALM = 0.30
BAND_STRAINED = 0.62
BAND_ROAD_SAFE = 0.12
BAND_ROAD_HARD = 0.38

# --- seasons --------------------------------------------------------------

SEASONS = ("AUTUMN", "WINTER", "SPRING", "SUMMER")
YEARS = 10
TURNS = YEARS * len(SEASONS)      # a full run is 40 turns
START_YEAR = 1

OPEN, HARD, CLOSED = "OPEN", "HARD", "CLOSED"

# terrain -> availability per season
SEASON_PROFILES = {
    "COAST":  {"AUTUMN": OPEN,   "WINTER": CLOSED, "SPRING": HARD,   "SUMMER": OPEN},
    "INLAND": {"AUTUMN": OPEN,   "WINTER": HARD,   "SPRING": HARD,   "SUMMER": OPEN},
    "PASS":   {"AUTUMN": OPEN,   "WINTER": HARD,   "SPRING": CLOSED, "SUMMER": OPEN},
    "ICE":    {"AUTUMN": CLOSED, "WINTER": OPEN,   "SPRING": CLOSED, "SUMMER": CLOSED},
    "TUNNEL": {"AUTUMN": OPEN,   "WINTER": OPEN,   "SPRING": OPEN,   "SUMMER": OPEN},
}

# How far the view may pan before the cached document is re-inked.
#
# Panning does not change the chart, it translates it. So the document is
# re-inked at an offset rounded to this grid, onto a surface this much larger
# than the chart rect, and blitted back at the difference: a drag re-inks once
# every 160 px of travel instead of once a frame. Borrowed from map maker.
PAN_QUANTUM = 260

# The ground layer's re-ink is spread over frames, this many milliseconds at a
# time, so no single frame pays for the whole sheet.
INK_SLICE_MS = 7.0

# While a zoom is still easing, the cached document is scaled rather than
# re-inked, and re-inked once the camera settles.
ZOOM_SETTLE = 0.004

# --- motion ---------------------------------------------------------------

REDRAW_SECONDS = 1.0              # the season change re-inks the chart
RESOLVE_SECONDS = 6.0

# --- log ------------------------------------------------------------------

LOG_LINES_KEPT = 400
LOG_LINES_SHOWN = 7

# room kept at the foot of the panel for the key list
PANEL_KEYS_HEIGHT = 76
