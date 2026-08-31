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

# --- world ----------------------------------------------------------------

WORLD_W = 2400.0
WORLD_H = 1400.0

SETTLEMENTS_START = 5
SETTLEMENTS_MAX = 20
SETTLEMENT_MIN_SPACING = 255.0
SETTLEMENT_PLACEMENT_TRIES = 9000
SETTLEMENT_COAST_BAND = 150.0     # within this of the shore is a coastal site
SETTLEMENT_INLAND_CHANCE = 0.4    # how often a site well inland is taken anyway

POP_RANGE = (40, 260)
STANDING_START = 55

# The land is a coast, not an island: open sea to the west, mainland to the
# east, and a scatter of smaller islands out in the water.
COAST_X = 0.50                    # where the shore sits, as a fraction of width
COAST_WANDER = 90.0              # how far the shore drifts from that line
COAST_FJORDS = (3, 6)             # water cutting inland
FJORD_DEPTH = (170.0, 460.0)
COAST_ISLANDS = (3, 7)
ISLAND_RADIUS = (55.0, 150.0)
RIDGE_KNOTS = 7                   # control points of the mountain spine
RIDGE_INLAND = 320.0              # how far behind the shore the spine runs

EDGE_NEIGHBOURS = 3               # k-nearest candidate edges per settlement
EDGE_MAX_LENGTH = 820.0
TRAVEL_DAYS_PER_UNIT = 0.026      # world units -> travel days
ICE_ROAD_MAX_LENGTH = 520.0       # sea crossings longer than this never freeze
TUNNEL_SITE_CHANCE = 0.22         # edges carrying a collapsed pre-collapse line

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
PAN_QUANTUM = 160

# The ground layer's re-ink is spread over frames, this many milliseconds at a
# time, so no single frame pays for the whole sheet.
INK_SLICE_MS = 6.0

# While a zoom is still easing, the cached document is scaled rather than
# re-inked, and re-inked once the camera settles.
ZOOM_SETTLE = 0.004

# --- motion ---------------------------------------------------------------

REDRAW_SECONDS = 1.0              # the season change re-inks the chart
RESOLVE_SECONDS = 6.0

# --- log ------------------------------------------------------------------

LOG_LINES_KEPT = 400
LOG_LINES_SHOWN = 7
