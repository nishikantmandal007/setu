# Constants shared by more than one module. Values taken from a design code live in
# setu/irc6/irc_constants.py; a constant only one module uses stays in that module.

# ── Units (materials, lanes, wind_loads, irc_constants) ─────────────────────────
GRAVITY_KN_PER_TONNE = 9.81
KPA_PER_KG_M2 = GRAVITY_KN_PER_TONNE / 1000.0
KPA_PER_MPA = 1000.0
KPA_PER_PA = 1e-3

# ── Numerical conventions (deck, lanes, mesh, temperature, influence_surface, along_span) ──
TOLERANCE_M = 1e-9
ROUND_TO_DECIMALS = 9
NOTHING_THERE_M = 1e-12
OFF_THE_DECK = 0.0

# ── Which way a response is adverse (helpers, analysis, design_values, cli) ──────
BIGGER_IS_WORSE = "maximum"
SMALLER_IS_WORSE = "minimum"
BOTH_WAYS = (1.0, -1.0)

# ── Deck strips, recognised by the start of their name (dead_loads, lanes) ───────
KERB_PREFIX = "kerb"
MEDIAN_PREFIX = "median"
CRASH_BARRIER_PREFIX = "crash_barrier"

# ── Lanes and vehicles (lanes, along_span, critical_position, resultant_centring) ──
CLASS_A_LANE = "class_a"
ZONE_70R = "zone_70r"
NO_LANE_REDUCTION = 1.0
REVERSED_SUFFIX = "_reversed"
# columns of a wheel offset row: where the wheel sits from the vehicle's front and centreline, and its load
OFFSET_DX_M = 0
OFFSET_DZ_M = 1
OFFSET_LOAD_KN = 2

# ── How long a load stays on - sets the concrete's modular ratio (materials, assembly, girder_response) ──
SHORT_TERM = "short_term"
LONG_TERM = "long_term"

# ── A 3D beam element's 12 end forces: node i then node j, each N, Vy, Vz, T, My, Mz (girder_response, influence_surface) ──
N_I, VY_I, VZ_I, T_I, MY_I, MZ_I = range(0, 6)
N_J, VY_J, VZ_J, T_J, MY_J, MZ_J = range(6, 12)
END_I_FORCE_TO_INTERNAL_FORCE = -1.0

# ── OpenSees tags for a load case's pattern and time series (load_cases, girder_response) ──
LOAD_CASE_PATTERN_BASE = 100

# ── Load groups IRC:6 Annex B combines, and its limit states (combinations, design_values, cli) ──
DEAD = "dead"
SURFACING = "surfacing"
LIVE = "live"
WIND = "wind"
THERMAL = "thermal"
SEISMIC = "seismic"
BASIC = "ultimate, basic"
SEISMIC_COMBINATION = "ultimate, seismic"
RARE = "serviceability, rare"
FREQUENT = "serviceability, frequent"
QUASI_PERMANENT = "serviceability, quasi-permanent"

# ── Custom loads from OsdagBridge (custom_load, custom_loads) ────────────────────
POINT = "point"
LINE = "line"
AREA = "area"
# OsdagBridge's custom load groups, and the IRC:6 Annex B group each one is combined as
CUSTOM_LOAD_GROUPS = {"DL": DEAD, "SIDL": DEAD, "DW": SURFACING, "LL": LIVE, "EL": SEISMIC, "WL": WIND, "TL": THERMAL}

# ── Terrain around the bridge for wind, IRC:6 Table 12 (site, wind, cli) ─────────
PLAIN_TERRAIN = "plain"
OBSTRUCTED_TERRAIN = "obstructed"

# ── Girder responses setu gives design values for (design_values, cli) ───────────
MIDSPAN_MOMENT = "midspan composite moment"
SUPPORT_SHEAR = "support shear"
RESPONSES = (MIDSPAN_MOMENT, SUPPORT_SHEAR)
SUPPORT = 0

# ── Printing (results, cli) ──────────────────────────────────────────────────────
RULE = "─" * 86
