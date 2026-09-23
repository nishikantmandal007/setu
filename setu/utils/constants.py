# Constants shared by more than one module. Values taken from a design code live in
# setu/irc6/irc_constants.py; a constant only one module uses stays in that module.

# Units
GRAVITY_KN_PER_TONNE = 9.81
KPA_PER_KG_M2 = GRAVITY_KN_PER_TONNE / 1000.0
KPA_PER_GPA = 1e6

# Numerical conventions
TOLERANCE_M = 1e-9
ROUND_TO_DECIMALS = 9
NOTHING_THERE_M = 1e-12

# Which way a response is adverse
BIGGER_IS_WORSE = "maximum"
SMALLER_IS_WORSE = "minimum"

# Strips of the deck cross-section, recognised by the start of their name
KERB_PREFIX = "kerb"
MEDIAN_PREFIX = "median"
CRASH_BARRIER_PREFIX = "crash_barrier"

# Blocks a carriageway is loaded in
CLASS_A_LANE = "class_a"
ZONE_70R = "zone_70r"
NO_LANE_REDUCTION = 1.0

# A vehicle turned round to face the other way
REVERSED_SUFFIX = "_reversed"

# Columns of a wheel offset row: where the wheel sits from the vehicle's front and centreline, and its load
OFFSET_DX_M = 0
OFFSET_DZ_M = 1
OFFSET_LOAD_KN = 2

# How long a load stays on - sets the concrete's modular ratio
SHORT_TERM = "short_term"
LONG_TERM = "long_term"

# How the slab was cast
UNPROPPED = "unpropped"
PROPPED = "propped"

# A 3D beam element's 12 end forces: node i then node j, each N, Vy, Vz, T, My, Mz
N_I, VY_I, VZ_I, T_I, MY_I, MZ_I = range(0, 6)
N_J, VY_J, VZ_J, T_J, MY_J, MZ_J = range(6, 12)
END_I_FORCE_TO_INTERNAL_FORCE = -1.0

# OpenSees tags for a load case's pattern and time series
LOAD_CASE_PATTERN_BASE = 100

# Load groups IRC:6 Annex B combines, and the limit states it combines them for
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

# Terrain around the bridge for wind (IRC:6 Table 12)
PLAIN_TERRAIN = "plain"
OBSTRUCTED_TERRAIN = "obstructed"

# OsdagBridge's custom load groups, and the IRC:6 Annex B group each one is combined as
CUSTOM_LOAD_GROUPS = {"DL": DEAD, "SIDL": DEAD, "DW": SURFACING, "LL": LIVE, "EL": SEISMIC, "WL": WIND, "TL": THERMAL}
