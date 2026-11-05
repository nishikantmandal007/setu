# Values from IRC:6-2017, grouped by clause.
from setu.utils.constants import (
    BASIC,
    DEAD,
    FREQUENT,
    LIVE,
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

# IRC:6-2017 Table 6A row 1: '4.25 m <= CW < 5.3 m' - narrower carries no vehicle loading
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
# Table 6 ends at 'less than 23.6 m'; wider carriageways are refused (no IRC source, decision D15)
WIDEST_TABULATED_CARRIAGEWAY_M = 23.60
MOST_70R_VEHICLES_DRAWN = 2

# Clause 205, Table 8 - reduction for several lanes loaded together
LANE_REDUCTION_BY_LANE_COUNT = {1: 1.00, 2: 1.00, 3: 0.90}
LANE_REDUCTION_FOR_FOUR_OR_MORE_LANES = 0.80

# Table 6 S.No.1 (Amendment 10) - 5 kN/m2 on the carriageway a single Class A lane leaves
RESIDUAL_UDL_KPA = 5.0
RESIDUAL_UDL_APPLIES_BELOW_M = 5.30

# Clause 206.1 and 206.3 (Amendment 10, kN/m2) - footway live load, and how it falls with span:
# P = P' up to 7.5 m; P = P' - (40L - 300)/900 up to 30 m; P = (P' - 2.6 + 48/L)(16.5 - W)/15 beyond
FOOTWAY_PEDESTRIAN_KPA = 4.0
FOOTWAY_FULL_LOAD_UP_TO_SPAN_M = 7.5
FOOTWAY_WIDTH_MATTERS_ABOVE_SPAN_M = 30.0
FOOTWAY_MEDIUM_SPAN_KPA_PER_M = 40.0
FOOTWAY_MEDIUM_SPAN_OFFSET_KPA = 300.0
FOOTWAY_MEDIUM_SPAN_DIVISOR = 900.0
FOOTWAY_LONG_SPAN_DEDUCTION_KPA = 2.6
FOOTWAY_LONG_SPAN_KPA_M = 48.0
FOOTWAY_WIDTH_FACTOR_BASE_M = 16.5
FOOTWAY_WIDTH_FACTOR_DIVISOR = 15.0
# Clause 206.2 (Amendment 10 S.No. 43): kerbs carry the footway load; 'If kerb width is less than 0.75m, no live load shall be applied'
KERB_CARRIES_FOOTWAY_LOAD_FROM_M = 0.75

# Clause 204.6 and Fig. 7 (Amendment 8, reprinted in Amendment 10 S.No. 35, kN). Fig. 7A Fatigue Load Train: the 400 kN truck
# (axles 120, 140, 140 kN at 4.5 m and 1.4 m) 'must be included'; 120 kN trucks (36, 42, 42 kN, same spacings) ahead of and behind it,
# 20 m (min) from one truck's rear axle to the next truck's front axle, 'only such number ... as can be accommodated in influence line'.
# Fig. 7B: dual tyres 310 mm wide in 710 mm pairs, 2390 mm overall (pair centres 1.68 m apart). Base cl. 204.6: single passage, worst
# position, outer tyre edge at least 150 mm off the kerb, 50 % of the clause 208 impact (Amendment 8's clause text not obtained).
FATIGUE_TRUCK_AXLE_LOADS_KN = (120.0, 140.0, 140.0)
FATIGUE_TRAIN_LIGHT_TRUCK_AXLE_LOADS_KN = (36.0, 42.0, 42.0)
FATIGUE_TRAIN_GAP_M = 20.0
FATIGUE_TRUCK_AXLE_SPACING_M = (4.5, 1.4)
FATIGUE_TRUCK_OVERALL_WIDTH_M = 2.39
FATIGUE_TRUCK_TYRE_PAIR_WIDTH_M = 0.71
FATIGUE_TRUCK_TYRE_WIDTH_M = 0.31
FATIGUE_TRUCK_KERB_CLEARANCE_M = 0.15
FATIGUE_IMPACT_SHARE = 0.5

# Amendment 10 S.No. 11, Table 1 note: 'For wet concrete the unit weights given in the table above shall be increased by 1 kN/m3'
WET_CONCRETE_EXTRA_KN_M3 = 1.0

# Clause 204.5, Class SV (IRC:6-2017 base text with Amendment 10 S.No. 4, 33, 34). Required for all new bridges except on rural,
# district and village roads (cl. 201.1, Amendment 10). Fig. 6 (Amendment 10): prime mover 60, 95, 95 kN at 3.200 and 1.370 m, then
# 5.427 m to 20 trailer axles of 180 kN at 1.500 m (3850 kN). Fig. 6A: 8 tyres per axle, tyre centres 403, 647, 1153, 1397 mm either side
# of the vehicle centreline (bogie struts at 900 mm, dual pairs 375 mm either side of a strut, tyres 244 mm apart in a pair; checks:
# 403 and 1153 - 647 = 506 as printed), contact 156 x 274 mm, 22.5 kN a tyre. 204.5.3: centreline within 300 mm of the carriageway
# centreline (Fig. 6B). 204.5.4: no other live load (footway included) on its carriageway, no impact or braking on it, no wind,
# seismic or temperature gradient with it, no fatigue; partial factor on SV 1.15 ULS basic, 1.0 SLS rare, 0.75 SLS frequent.
SPECIAL_VEHICLE_AXLE_LOADS_KN = (60.0, 95.0, 95.0) + (180.0,) * 20
SPECIAL_VEHICLE_AXLE_SPACING_M = (3.200, 1.370, 5.427) + (1.500,) * 19
SPECIAL_VEHICLE_TYRE_OFFSETS_M = (0.403, 0.647, 1.153, 1.397)
SPECIAL_VEHICLE_WIDTH_M = 3.0
SPECIAL_VEHICLE_ECCENTRICITY_M = 0.300
SPECIAL_VEHICLE_FACTORS = {"ultimate, basic": 1.15, "serviceability, rare": 1.0, "serviceability, frequent": 0.75}

# Clause 208, Figure 9 - dynamic impact allowance for a steel bridge
SHORTEST_TABULATED_SPAN_M = 3.0
LONGEST_TABULATED_SPAN_M = 45.0
SHORT_SPAN_IMPACT_FRACTION = 0.25
TRACKED_IMPACT_FRACTION_FLOOR = 0.10
SHORT_SPAN_UPPER_LIMIT_M = 9.0
TRACKED_TRANSITION_START_SPAN_M = 5.0
TRACKED_TRANSITION_SPAN_WIDTH_M = 4.0
# Amendment 10 S.No. 55, cl. 208.3 (b)(ii)(4): steel / composite wheeled 25 % up to 22.5 m, then the Fig. 9 curve
WHEELED_70R_IMPACT_CURVE_TAKES_OVER_M = 22.5


# Clause 209 as replaced by IRC:6-2017 Amendment 10 (MoRTH Notification 83, S.No. 59).
# 209.1: quasi-static rules for spans up to 200 m and pier heights (pier cap top to foundation top) up to 100 m
WIND_RULES_APPLY_UP_TO_SPAN_M = 200.0
WIND_RULES_APPLY_UP_TO_PIER_HEIGHT_M = 100.0
# 209.3.1 Table 1: risk coefficient k1 by return period (years) and basic wind speed zone (m/s); note 1: 10 years for construction
K1_BASIC_WIND_SPEEDS_MPS = (33.0, 39.0, 44.0, 47.0, 50.0, 55.0)
K1_BY_RETURN_PERIOD = {
    5: (0.82, 0.76, 0.73, 0.71, 0.70, 0.67),
    10: (0.87, 0.83, 0.81, 0.80, 0.79, 0.77),
    25: (0.94, 0.92, 0.91, 0.91, 0.90, 0.89),
    50: (1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
    100: (1.05, 1.06, 1.07, 1.07, 1.08, 1.08),
}
CONSTRUCTION_RETURN_PERIOD_YEARS = 10
# 209.3.2 Table 3: k2 by height z (m) for TC1-TC4; the first row is 'up to 10 m'; linear interpolation
K2_HEIGHTS_M = (10.0, 15.0, 20.0, 30.0, 50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 500.0)
K2_BY_TERRAIN_CATEGORY = {
    1: (1.05, 1.09, 1.12, 1.15, 1.20, 1.26, 1.30, 1.32, 1.34, 1.35, 1.35, 1.35, 1.35, 1.35),
    2: (1.00, 1.05, 1.07, 1.12, 1.17, 1.24, 1.28, 1.30, 1.32, 1.34, 1.35, 1.35, 1.35, 1.35),
    3: (0.91, 0.97, 1.01, 1.06, 1.12, 1.20, 1.24, 1.27, 1.29, 1.31, 1.32, 1.34, 1.35, 1.35),
    4: (0.80, 0.80, 0.80, 0.97, 1.10, 1.20, 1.24, 1.27, 1.28, 1.30, 1.31, 1.32, 1.33, 1.34),
}
# 209.3.2 Table 2: aerodynamic roughness height z0 (m) by terrain category, used in Equation 4
ROUGHNESS_HEIGHT_M = {1: 0.002, 2: 0.02, 3: 0.2, 4: 2.0}
# 209.4 Table 4: hourly mean factor k2bar by height (10-500 m) and terrain category; linear interpolation.
# Table A3.2 is computed from these rounded values. Below 10 m (no row) Equation 4 is used: k2bar = 0.1423 ln(z / z0) z0^0.0706
K2_HOURLY_BY_TERRAIN_CATEGORY = {
    1: (0.78, 0.82, 0.85, 0.88, 0.93, 0.99, 1.03, 1.06, 1.08, 1.09, 1.11, 1.12, 1.13, 1.14),
    2: (0.67, 0.71, 0.75, 0.79, 0.84, 0.92, 0.96, 0.99, 1.02, 1.04, 1.05, 1.07, 1.08, 1.09),
    3: (0.50, 0.55, 0.58, 0.64, 0.70, 0.79, 0.84, 0.88, 0.91, 0.93, 0.95, 0.97, 0.98, 0.99),
    4: (0.24, 0.30, 0.34, 0.40, 0.48, 0.58, 0.65, 0.69, 0.72, 0.75, 0.77, 0.79, 0.81, 0.83),
}
HOURLY_FACTOR_MULTIPLIER = 0.1423
HOURLY_FACTOR_ROUGHNESS_EXPONENT = 0.0706
# 209.3.3: k3 = 1.2 in a funnelling valley or on the leeward side of a hill, else 1.0
K3_VALLEY_OR_LEEWARD_HILL = 1.2
# 209.3.4: k4 = 1.30 within 60 km of a cyclone coast where Vb >= 50 m/s, 1.5 offshore up to 200 km, else 1.0
K4_CYCLONE_COAST = 1.30
K4_CYCLONE_COAST_FROM_BASIC_SPEED_MPS = 50.0
K4_OFFSHORE = 1.5
# 209.3.5 Equation 2 and 209.4.2 Equation 6: pressure in N/m2 = 0.6 V^2 (checked against Table A3.1)
PRESSURE_PER_SPEED_SQUARED = 0.6
# 209.5.2.1 Table 5: column 2 (peak gust, no G) for span <= 40 m with pier <= 20 m; otherwise max of column 2 and column 3
GUST_METHOD_UP_TO_SPAN_M = 40.0
GUST_METHOD_UP_TO_PIER_HEIGHT_M = 20.0
LONGITUDINAL_WIND_FRACTION = 0.25
VERTICAL_WIND_ECCENTRICITY_OF_WIDTH = 0.25
# Table 6, other spans: skew angle (deg) -> (transverse, longitudinal) coefficient
SKEW_COEFFICIENTS_OTHER_SPANS = {0: (1.00, 0.00), 15: (0.88, 0.12), 30: (0.82, 0.24), 45: (0.66, 0.32), 60: (0.34, 0.38)}
# 209.5.2.2: gust factor G by terrain category for the hourly mean method
GUST_FACTOR_BY_TERRAIN_CATEGORY = {1: 2.0, 2: 2.0, 3: 2.5, 4: 3.5}
# Table 8 case I(ii), deck on beams or box girders: CD at B/d = 1, 2, 6; interpolate (note 1); note 7 camber +3 % per degree, at most 25 %
SERVICE_DRAG_B_OVER_D = (1.0, 2.0, 6.0)
SERVICE_DRAG_COEFFICIENTS = (2.2, 1.5, 1.3)
DRAG_INCREASE_PER_DEGREE_OF_CAMBER = 0.03
DRAG_CAMBER_INCREASE_AT_MOST = 0.25
# Table 8 case II(a), before the deck is cast: single steel plate girder 2.5; two or more plate girders 2(1 + c / 20d), at most 4
SINGLE_PLATE_GIRDER_CONSTRUCTION_DRAG = 2.5
PLATE_GIRDERS_DRAG_BASE = 2.0
PLATE_GIRDERS_DRAG_SPACING_DIVISOR = 20.0
PLATE_GIRDERS_DRAG_COEFFICIENT_MOST = 4.0
# 209.5.2.2: CL = +/-0.9 for plate-girder decks
LIFT_COEFFICIENT = 0.9
# 209.5.2.3: wind on live load, CD 1.2 over 3.0 m above the roadway (areas below a solid barrier top neglected), acting 1.5 m above it
LIVE_LOAD_DRAG_COEFFICIENT = 1.2
LIVE_LOAD_EXPOSED_HEIGHT_M = 3.0
WIND_ON_LIVE_LOAD_ACTS_ABOVE_ROAD_M = 1.5
LIVE_LOAD_LONGITUDINAL_WIND_FRACTION = 0.25
# Table 7 and Fig. 5, 7: dL, the live load height above the roadway
LIVE_LOAD_DEPTH_M = 3.0

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

# Construction stage (un-propped: the bare steel carries its own weight, the wet slab, shuttering and construction live load,
# IRC:22-2015 cl. 604.1.1; loads from the construction programme, IRC:6-2017 cl. 218 'Erection Effects and Construction Loads',
# numbered 217 before Amendment 10). Factors, IRC:6-2017 Annex B Table B.2 (structural strength):
# dead load 1.35 adding / 1.0 relieving (row 1.1); construction live load 1.35 basic, 1.0 seismic (row 2.1 c);
# construction dead loads such as shuttering 1.35 basic, 1.35 seismic (row 2.4); wind during service and construction 1.5 leading,
# 0.9 accompanying (row 2.2); seismic during construction 0.75 (row 4 b). A relieving variable load is ignored (Annex B para 3 ii).
CONSTRUCTION_DEAD_FACTORS = (1.35, 1.0)
CONSTRUCTION_TEMPORARY_DEAD_FACTOR_BASIC = 1.35
CONSTRUCTION_TEMPORARY_DEAD_FACTOR_SEISMIC = 1.35
CONSTRUCTION_LIVE_LOAD_FACTOR_BASIC = 1.35
CONSTRUCTION_LIVE_LOAD_FACTOR_SEISMIC = 1.0
CONSTRUCTION_WIND_FACTORS = (1.5, 0.9)
SEISMIC_DURING_CONSTRUCTION_FACTOR = 0.75
# IRC:SP:114-2018 note under Table 4.3: 'While checking for seismic effects during construction, the importance factor of 1 should be considered'
CONSTRUCTION_IMPORTANCE_FACTOR = 1.0

# 209.5.2.4: no live load on the bridge when the design wind speed at deck level exceeds 36 m/s
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

# Clause 215.2 - effective temperature of a metallic bridge: other areas shade max + 15 C to shade min - 10 C; snowbound areas -35 C to +50 C
METALLIC_ABOVE_SHADE_MAX_C = 15.0
METALLIC_BELOW_SHADE_MIN_C = 10.0
SNOWBOUND_EFFECTIVE_RANGE_C = (-35.0, 50.0)

# Clause 215.3, Fig. 16b (IRC:6-2017 p. 58) - temperature difference across steel / composite decks, drawn for 50 mm surfacing.
# Heating: T1 at the top, 4 C at h1, 0 at h1 + h2. Cooling: T1 at the top, 0 at h1, 8 C at h1 + h2. h1 = 0.6h, h2 = 0.4 m.
# T1 by slab depth h; 'for intermediate slab thickness, T1 may be interpolated'. Used for any surfacing, as IRC:SP:120-2018
# (p. 57, 59) does with 65-90 mm surfacing (decision D13).
FIG_16B_SLAB_DEPTHS_M = (0.2, 0.3)
FIG_16B_HEATING_T1_C = (18.0, 20.5)
FIG_16B_COOLING_T1_C = (-4.4, -6.8)
FIG_16B_HEATING_AT_H1_C = 4.0
FIG_16B_COOLING_AT_H1_PLUS_H2_C = -8.0
TEMPERATURE_H1_FRACTION_OF_SLAB = 0.6
TEMPERATURE_H2_M = 0.4

# Clause 215.4 - coefficient of thermal expansion for RCC, PSC and steel
THERMAL_EXPANSION_PER_C = 12.0e-6
