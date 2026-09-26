import numpy as np

from setu.irc6.impact import impact_fraction
from setu.irc6.irc_constants import (
    FATIGUE_IMPACT_SHARE,
    FATIGUE_TRUCK_AXLE_LOADS_T,
    FATIGUE_TRUCK_AXLE_SPACING_M,
    FATIGUE_TRUCK_KERB_CLEARANCE_M,
    FATIGUE_TRUCK_OVERALL_WIDTH_M,
    FATIGUE_TRUCK_TYRE_PAIR_WIDTH_M,
    FATIGUE_TRUCK_TYRE_WIDTH_M,
)
from setu.utils.constants import GRAVITY_KN_PER_TONNE

TYRES_PER_AXLE = 4
# the clause 204.6 truck is an ordinary wheeled lorry, so its clause 208 impact is read off the Class A curve
IMPACT_READ_AS = "Class_A"


# every tyre of the fatigue truck as (dx behind the front axle, dz from the truck centreline, load kN)
def fatigue_truck_offsets():
    axle_positions_m = np.concatenate([[0.0], np.cumsum(FATIGUE_TRUCK_AXLE_SPACING_M)])
    pair_centre_m = (FATIGUE_TRUCK_OVERALL_WIDTH_M - FATIGUE_TRUCK_TYRE_PAIR_WIDTH_M) / 2
    tyre_from_pair_centre_m = (FATIGUE_TRUCK_TYRE_PAIR_WIDTH_M - FATIGUE_TRUCK_TYRE_WIDTH_M) / 2
    tyres_dz_m = [side * pair_centre_m + inner * tyre_from_pair_centre_m for side in (-1, 1) for inner in (-1, 1)]
    return np.array([(dx_m, dz_m, axle_t * GRAVITY_KN_PER_TONNE / TYRES_PER_AXLE)
                     for dx_m, axle_t in zip(axle_positions_m, FATIGUE_TRUCK_AXLE_LOADS_T, strict=True) for dz_m in tyres_dz_m])


# the band a truck centreline can take on a carriageway, keeping the outer tyre edges 150 mm off the kerbs
def centreline_band_m(carriageway):
    half_width_m = FATIGUE_TRUCK_OVERALL_WIDTH_M / 2 + FATIGUE_TRUCK_KERB_CLEARANCE_M
    return carriageway.left_m + half_width_m, carriageway.right_m - half_width_m


# 1 + half the clause 208 impact fraction
def fatigue_impact_factor(span_m):
    return 1.0 + FATIGUE_IMPACT_SHARE * impact_fraction(IMPACT_READ_AS, span_m)
