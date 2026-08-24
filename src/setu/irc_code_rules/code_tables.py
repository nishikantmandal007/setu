"""Every number setu takes from IRC:6-2017, transcribed once.

This module is the single source of truth for tabulated code values. Nothing
here depends on anything else in setu, and no other module may hard-code a
number that belongs in the code.

Sampling knobs we chose ourselves live in `setu/settings.py` instead - the two
kinds of number are kept apart on purpose, because one of them is negotiable
and the other is not.

All lengths are in metres, loads in kilonewtons.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Clause 204.3, Table 3 - transverse placement geometry
# ---------------------------------------------------------------------------

CLASS_A_LANE_WIDTH_M = 2.30
"""Width of the lane block one Class A vehicle occupies."""

CLASS_A_KERB_CLEARANCE_M = 0.15
"""Clearance Table 3 requires between a Class A vehicle and the kerb or deck edge."""

CLASS_A_VEHICLE_GAP_M = 1.20
"""Clearance Table 3 requires between two adjacent Class A vehicles."""

VEHICLE_70R_WIDTH_M = 2.90
"""Width a 70R vehicle occupies - track gauge plus the wheels themselves."""

VEHICLE_70R_CLEARANCE_M = 1.20
"""Clearance a 70R vehicle keeps from both boundaries of its exclusive zone."""

ZONE_70R_AT_EDGE_M = 7.25
"""Width of the exclusive 70R zone when it sits at the edge of the carriageway."""

ZONE_70R_INSIDE_M = 7.00
"""Width of the exclusive 70R zone when it sits between other lanes."""

ZONE_70R_ALONE_M = VEHICLE_70R_WIDTH_M + 2 * VEHICLE_70R_CLEARANCE_M
"""Width of a 70R zone with nothing beside it: the vehicle plus its two clearances."""

# The narrow band where Table 3 reduces the gap between two Class A vehicles.
# Below 5.30 m the carriageway is single lane; above 6.10 m the gap is the full
# 1.20 m. In between it opens up linearly, which is what `class_a_gap` computes.
CLASS_A_GAP_OPENS_UP_BELOW_M = 6.10
SMALLEST_CLASS_A_GAP_M = 0.40


# ---------------------------------------------------------------------------
# IRC:5-2015 Clause 104.3 - when a carriageway is too narrow to load at all
# ---------------------------------------------------------------------------

NARROWEST_LOADED_CARRIAGEWAY_M = 4.25
"""A carriageway narrower than this carries no vehicle loading."""


# ---------------------------------------------------------------------------
# Table 6 - how many design lanes a carriageway of a given width has
# ---------------------------------------------------------------------------

DESIGN_LANES_BY_WIDTH = (
    # (width from, width up to but excluding, design lanes)
    (0.00, 5.30, 1),
    (5.30, 9.60, 2),
    (9.60, 13.10, 3),
    (13.10, 16.60, 4),
    (16.60, 20.10, 5),
    (20.10, 23.60, 6),
)

WIDEST_TABULATED_CARRIAGEWAY_M = 23.60
"""Table 6 stops here. Anything wider is read as six design lanes."""

MOST_DESIGN_LANES = 6

MOST_70R_VEHICLES_DRAWN = 2
"""The combination drawings never put a third 70R on a carriageway.

Six design lanes would hold three of them, and 21.50 m of carriageway is enough
- but the drawings stop at two, and there is no band boundary at 21.50 m where a
third would first become possible. Every other case has one.
"""


# ---------------------------------------------------------------------------
# Clause 205, Table 8 - reduction for several lanes loaded together
# ---------------------------------------------------------------------------

LANE_REDUCTION_BY_LANE_COUNT = {1: 1.00, 2: 1.00, 3: 0.90}
LANE_REDUCTION_FOR_FOUR_OR_MORE_LANES = 0.80


# ---------------------------------------------------------------------------
# Table 6 S.No.1 - the residual load on carriageway a vehicle does not cover
# ---------------------------------------------------------------------------

RESIDUAL_UDL_KPA = 500.0 * 9.81 / 1000.0
"""500 kg/m2, expressed in kN/m2."""

RESIDUAL_UDL_APPLIES_BELOW_M = 5.30
"""Carriageways narrower than this carry the residual UDL beside the vehicle."""


# ---------------------------------------------------------------------------
# Clause 206 - footway and cycle track loading
# ---------------------------------------------------------------------------

FOOTWAY_UDL_KPA = 5.0
CYCLE_TRACK_UDL_KPA = 2.5


# ---------------------------------------------------------------------------
# Units and numerical conventions
# ---------------------------------------------------------------------------

GRAVITY_KN_PER_TONNE = 9.81
"""Vehicle axle loads are tabulated in tonnes; responses are in kilonewtons."""

TOLERANCE_M = 1e-9
"""Two lengths closer than this are the same length."""

ROUND_TO_DECIMALS = 9
"""Decimal places kept when rounding a coordinate, so grids compare equal."""
