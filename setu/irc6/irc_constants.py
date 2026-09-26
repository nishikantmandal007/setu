# Values from IRC:6-2017, grouped by clause.
from setu.utils.constants import (
    BASIC,
    DEAD,
    FREQUENT,
    KPA_PER_KG_M2,
    LIVE,
    OBSTRUCTED_TERRAIN,
    PLAIN_TERRAIN,
    QUASI_PERMANENT,
    RARE,
    SEISMIC,
    SEISMIC_COMBINATION,
    SURFACING,
    THERMAL,
    WIND,
)

# Clause 204.3, Table 3 - transverse placement geometry
CLASS_A_LANE_WIDTH_M = 2.30
CLASS_A_KERB_CLEARANCE_M = 0.15
CLASS_A_VEHICLE_GAP_M = 1.20
VEHICLE_70R_WIDTH_M = 2.90
VEHICLE_70R_CLEARANCE_M = 1.20
ZONE_70R_AT_EDGE_M = 7.25
ZONE_70R_INSIDE_M = 7.00
ZONE_70R_ALONE_M = VEHICLE_70R_WIDTH_M + 2 * VEHICLE_70R_CLEARANCE_M

CLASS_A_GAP_OPENS_UP_BELOW_M = 6.10
SMALLEST_CLASS_A_GAP_M = 0.40

TWO_CLASS_A_LANES_AND_KERB_CLEARANCES_M = 4.90

# IRC:5-2015 Clause 104.3 - narrower than this carries no vehicle loading
NARROWEST_LOADED_CARRIAGEWAY_M = 4.25

# Table 6 - design lanes by carriageway width
DESIGN_LANES_BY_WIDTH = (
    (0.00, 5.30, 1),
    (5.30, 9.60, 2),
    (9.60, 13.10, 3),
    (13.10, 16.60, 4),
    (16.60, 20.10, 5),
    (20.10, 23.60, 6),
)
WIDEST_TABULATED_CARRIAGEWAY_M = 23.60
MOST_DESIGN_LANES = 6
MOST_70R_VEHICLES_DRAWN = 2

# Clause 205, Table 8 - reduction for several lanes loaded together
LANE_REDUCTION_BY_LANE_COUNT = {1: 1.00, 2: 1.00, 3: 0.90}
LANE_REDUCTION_FOR_FOUR_OR_MORE_LANES = 0.80

# Table 6 S.No.1 - 500 kg/m2 residual load
RESIDUAL_UDL_KG_M2 = 500.0
RESIDUAL_UDL_KPA = RESIDUAL_UDL_KG_M2 * KPA_PER_KG_M2
RESIDUAL_UDL_APPLIES_BELOW_M = 5.30

# Clause 206.1 and 206.3 - footway live load, and how it falls with span
FOOTWAY_PEDESTRIAN_KG_M2 = 400.0
FOOTWAY_FULL_LOAD_UP_TO_SPAN_M = 7.5
FOOTWAY_WIDTH_MATTERS_ABOVE_SPAN_M = 30.0
FOOTWAY_MEDIUM_SPAN_KG_M2_PER_M = 40.0
FOOTWAY_MEDIUM_SPAN_OFFSET_KG_M2 = 300.0
FOOTWAY_MEDIUM_SPAN_DIVISOR = 9.0
FOOTWAY_LONG_SPAN_DEDUCTION_KG_M2 = 260.0
FOOTWAY_LONG_SPAN_KG_M2_M = 4800.0
FOOTWAY_WIDTH_FACTOR_BASE_M = 16.5
FOOTWAY_WIDTH_FACTOR_DIVISOR = 15.0

# Clause 204.6, Fig. 7 - the 40 t fatigue truck: axles 12, 14, 14 t at 4.5 m and 1.4 m; dual tyres 310 mm wide in 710 mm pairs,
# 2390 mm overall so the pair centres are 1.68 m apart; one truck, single passage, outer tyre edge at least 150 mm off the kerb;
# 50% of the clause 208 impact
FATIGUE_TRUCK_AXLE_LOADS_T = (12.0, 14.0, 14.0)
FATIGUE_TRUCK_AXLE_SPACING_M = (4.5, 1.4)
FATIGUE_TRUCK_OVERALL_WIDTH_M = 2.39
FATIGUE_TRUCK_TYRE_PAIR_WIDTH_M = 0.71
FATIGUE_TRUCK_TYRE_WIDTH_M = 0.31
FATIGUE_TRUCK_KERB_CLEARANCE_M = 0.15
FATIGUE_IMPACT_SHARE = 0.5

# Clause 208, Figure 9 - dynamic impact allowance for a steel bridge
SHORTEST_TABULATED_SPAN_M = 3.0
LONGEST_TABULATED_SPAN_M = 45.0
SHORT_SPAN_IMPACT_FRACTION = 0.25
TRACKED_IMPACT_FRACTION_FLOOR = 0.10
SHORT_SPAN_UPPER_LIMIT_M = 9.0
TRACKED_TRANSITION_START_SPAN_M = 5.0
TRACKED_TRANSITION_SPAN_WIDTH_M = 4.0
WHEELED_70R_IMPACT_CURVE_TAKES_OVER_M = 23.0


# Clause 209.1 - where these wind rules apply
WIND_RULES_APPLY_UP_TO_SPAN_M = 150.0
WIND_RULES_APPLY_UP_TO_HEIGHT_M = 100.0

# Clause 209.2, Table 12 - hourly mean wind speed (m/s) and pressure (N/m2) at a basic wind speed of 33 m/s
TABLE_12_HEIGHTS_M = (10.0, 15.0, 20.0, 30.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0)
TABLE_12_WIND_SPEED_MPS = {
    PLAIN_TERRAIN: (27.80, 29.20, 30.30, 31.40, 33.10, 33.60, 34.00, 34.40, 34.90, 35.30),
    OBSTRUCTED_TERRAIN: (17.80, 19.60, 21.00, 22.80, 24.90, 25.60, 26.20, 26.90, 27.50, 28.20),
}
TABLE_12_WIND_PRESSURE_PA = {
    PLAIN_TERRAIN: (463.70, 512.50, 550.60, 590.20, 659.20, 676.30, 693.60, 711.20, 729.00, 747.00),
    OBSTRUCTED_TERRAIN: (190.50, 230.50, 265.30, 312.20, 373.40, 392.90, 412.80, 433.30, 454.20, 475.60),
}
TABLE_12_BASIC_WIND_SPEED_MPS = 33.0
FUNNELLING_TOPOGRAPHY_INCREASE = 1.2

# Clause 209.3.3 - transverse wind on the superstructure
GUST_FACTOR = 2.0
SINGLE_PLATE_GIRDER_DRAG_COEFFICIENT = 2.2
PLATE_GIRDERS_DRAG_BASE = 2.0
PLATE_GIRDERS_DRAG_SPACING_DIVISOR = 20.0
PLATE_GIRDERS_DRAG_COEFFICIENT_MOST = 4.0

# Clause 209.3.4 - longitudinal wind on a beam, box or plate girder superstructure
PLATE_GIRDER_LONGITUDINAL_WIND_FRACTION = 0.25

# Clause 209.3.5 - vertical wind
LIFT_COEFFICIENT = 0.75

# Clause 209.3.6 - wind on the live load
LIVE_LOAD_DRAG_COEFFICIENT = 1.2
LIVE_LOAD_EXPOSED_HEIGHT_M = 3.0
WIND_ON_LIVE_LOAD_ACTS_ABOVE_ROAD_M = 1.5
LIVE_LOAD_LONGITUDINAL_WIND_FRACTION = 0.25

# Annex B, Tables B.2 and B.3 - partial safety factors.
# Permanent loads: (adding, relieving). Variable loads: (leading, accompanying);
# a variable load that relieves the effect is ignored (Annex B para 3 ii).
PERMANENT_LOAD_FACTORS = {
    BASIC: {DEAD: (1.35, 1.0), SURFACING: (1.75, 1.0)},
    SEISMIC_COMBINATION: {DEAD: (1.35, 1.0), SURFACING: (1.75, 1.0)},
    RARE: {DEAD: (1.0, 1.0), SURFACING: (1.2, 1.0)},
    FREQUENT: {DEAD: (1.0, 1.0), SURFACING: (1.2, 1.0)},
    QUASI_PERMANENT: {DEAD: (1.0, 1.0), SURFACING: (1.2, 1.0)},
}
VARIABLE_LOAD_FACTORS = {
    BASIC: {LIVE: (1.5, 1.15), WIND: (1.5, 0.9), THERMAL: (1.5, 0.9)},
    SEISMIC_COMBINATION: {LIVE: (None, 0.2), THERMAL: (None, 0.5), SEISMIC: (1.5, None)},
    RARE: {LIVE: (1.0, 0.75), WIND: (1.0, 0.6), THERMAL: (1.0, 0.6)},
    FREQUENT: {LIVE: (0.75, 0.2), WIND: (0.6, 0.5), THERMAL: (0.6, 0.5)},
    QUASI_PERMANENT: {LIVE: (None, 0.0), WIND: (None, 0.0), THERMAL: (None, 0.5)},
}
EACH_VARIABLE_LOAD_LEADS_IN = (BASIC, RARE, FREQUENT)

# Clause 209.3.7 - no live load on the bridge above this wind speed at deck level
LIVE_LOAD_OFF_ABOVE_WIND_SPEED_MPS = 36.0

# Clause 211.2 and 211.3 - braking
BRAKING_FIRST_TRAIN_FRACTION = 0.20
BRAKING_FOLLOWING_TRAINS_FRACTION = 0.10
BRAKING_LANES_BEYOND_TWO_FRACTION = 0.05
BRAKING_LANES_COUNTED_AS_ONE = 2
BRAKING_ACTS_ABOVE_ROAD_M = 1.2

# IRC:SP:114-2018 - seismic design of road bridges (replaces IRC:6-2017 clause 218)
# Table 4.2 zone factors, Table 5.2 minimum design horizontal coefficient
ZONE_FACTORS = {"II": 0.10, "III": 0.16, "IV": 0.24, "V": 0.36}
MINIMUM_HORIZONTAL_SEISMIC_COEFFICIENT = {"II": 0.011, "III": 0.017, "IV": 0.025, "V": 0.038}
# Clause 5.2.1 - Ah = (Z / 2) (I / R) (Sa / g)
ZONE_FACTOR_DIVISOR = 2.0
# Fig. 5.1(a), IS 1893:2016 - seismic coefficient method spectrum at 5 % damping, by soil type:
# (end of the 2.5 plateau in s, numerator of the 1/T branch, value past 4 s)
SPECTRUM_PLATEAU = 2.5
SPECTRUM_BY_SOIL = {"I": (0.40, 1.00, 0.25), "II": (0.55, 1.36, 0.34), "III": (0.67, 1.67, 0.42)}
SPECTRUM_TAIL_STARTS_S = 4.0
# Note under Fig. 5.1 - Sa/g when the period is not worked out
SA_OVER_G_WITHOUT_A_PERIOD = 2.5
# Clause 4.2.1 and 4.2.3 - vertical motion
VERTICAL_ZONE_FACTOR_FRACTION = 2.0 / 3.0
VERTICAL_ALWAYS_IN_ZONES = ("IV", "V")
# Clause 4.2.2 - combining the three directions
OTHER_DIRECTIONS_FRACTION = 0.3
# Clause 4.6 - live load in the seismic mass (impact excluded)
LIVE_LOAD_SEISMIC_FRACTION = 0.2

# Clause 215.2 - effective temperature of a metallic bridge
METALLIC_ABOVE_SHADE_MAX_C = 15.0
METALLIC_BELOW_SHADE_MIN_C = 10.0

# Clause 215.3, Fig. 17b / Table 15B (same as EN 1991-1-5 Fig. 6.2b) - temperature difference across a steel/concrete composite deck.
# Heating: dT1 at the top, dT2 at h1, 0 at h1 + h2. Cooling: dT1 at the top, 0 at h1, dT2 at h1 + h2. h1 = 0.6h, h2 = 0.4 m in both.
# Rows are slab depth h, columns surfacing thickness; the published figure gives 50 mm, Table 15B of the draft amendment adds 100 mm.
TABLE_15B_SLAB_DEPTHS_M = (0.2, 0.3)
TABLE_15B_SURFACINGS_M = (0.05, 0.10)
TABLE_15B_HEATING_DT1_C = ((18.0, 13.0), (20.5, 16.0))
TABLE_15B_COOLING_DT1_C = ((-4.4, -3.5), (-6.8, -5.0))
TABLE_15B_HEATING_DT2_C = 4.0
TABLE_15B_COOLING_DT2_C = -8.0
TEMPERATURE_H1_FRACTION_OF_SLAB = 0.6
TEMPERATURE_H2_M = 0.4

# Clause 215.4 - coefficient of thermal expansion for RCC, PSC and steel
THERMAL_EXPANSION_PER_C = 12.0e-6
