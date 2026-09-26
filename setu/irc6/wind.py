import numpy as np

from setu.irc6.irc_constants import (
    FUNNELLING_TOPOGRAPHY_INCREASE,
    GUST_FACTOR,
    LIFT_COEFFICIENT,
    LIVE_LOAD_DRAG_COEFFICIENT,
    LIVE_LOAD_EXPOSED_HEIGHT_M,
    LIVE_LOAD_LONGITUDINAL_WIND_FRACTION,
    PLATE_GIRDER_LONGITUDINAL_WIND_FRACTION,
    PLATE_GIRDERS_DRAG_BASE,
    PLATE_GIRDERS_DRAG_COEFFICIENT_MOST,
    PLATE_GIRDERS_DRAG_SPACING_DIVISOR,
    SINGLE_PLATE_GIRDER_DRAG_COEFFICIENT,
    TABLE_12_BASIC_WIND_SPEED_MPS,
    TABLE_12_HEIGHTS_M,
    TABLE_12_WIND_PRESSURE_PA,
    TABLE_12_WIND_SPEED_MPS,
    WIND_RULES_APPLY_UP_TO_HEIGHT_M,
    WIND_RULES_APPLY_UP_TO_SPAN_M,
)

NO_ENHANCEMENT = 1.0


# Table 12 speed and pressure at this height, scaled to the site wind speed
def hourly_mean_wind(height_m, terrain, basic_wind_speed_mps, funnelling):
    if height_m > WIND_RULES_APPLY_UP_TO_HEIGHT_M:
        raise ValueError(f"clause 209.1 covers heights up to {WIND_RULES_APPLY_UP_TO_HEIGHT_M:.0f} m, got {height_m} m; use specialist literature")
    at_least_the_first_row_m = max(height_m, TABLE_12_HEIGHTS_M[0])
    speed_ratio = basic_wind_speed_mps / TABLE_12_BASIC_WIND_SPEED_MPS
    speed_mps = float(np.interp(at_least_the_first_row_m, TABLE_12_HEIGHTS_M, TABLE_12_WIND_SPEED_MPS[terrain])) * speed_ratio
    pressure_pa = float(np.interp(at_least_the_first_row_m, TABLE_12_HEIGHTS_M, TABLE_12_WIND_PRESSURE_PA[terrain])) * speed_ratio ** 2
    pressure_pa *= FUNNELLING_TOPOGRAPHY_INCREASE if funnelling else NO_ENHANCEMENT
    return (speed_mps, pressure_pa)


# clause 209.3.3 drag for one or several plate girders
def drag_coefficient(girder_count, girder_spacing_m, girder_depth_m):
    if girder_count == 1:
        return SINGLE_PLATE_GIRDER_DRAG_COEFFICIENT
    spread_out = PLATE_GIRDERS_DRAG_BASE * (1.0 + girder_spacing_m / (PLATE_GIRDERS_DRAG_SPACING_DIVISOR * girder_depth_m))
    return min(spread_out, PLATE_GIRDERS_DRAG_COEFFICIENT_MOST)


# the given gust factor, or IRC:6's 2.0 up to 150 m span
def gust_factor_for(span_m, gust=None):
    if gust is not None:
        return gust
    if span_m > WIND_RULES_APPLY_UP_TO_SPAN_M:
        raise ValueError(f"clause 209.1 covers spans up to {WIND_RULES_APPLY_UP_TO_SPAN_M:.0f} m, got {span_m} m; use specialist literature")
    return GUST_FACTOR


# F_T = P G C_D A
def transverse_wind_force_kn(pressure_kpa, exposed_area_m2, drag, span_m, gust=None):
    return pressure_kpa * exposed_area_m2 * gust_factor_for(span_m, gust) * drag


# F_L as a fraction of F_T for plate girders
def longitudinal_wind_force_kn(transverse_kn):
    return PLATE_GIRDER_LONGITUDINAL_WIND_FRACTION * transverse_kn


# F_V = P G C_L A_plan
def vertical_wind_force_kn(pressure_kpa, plan_area_m2, span_m, gust=None, lift=None):
    lift = LIFT_COEFFICIENT if lift is None else lift
    return pressure_kpa * plan_area_m2 * gust_factor_for(span_m, gust) * lift


# wind on the vehicles, across and along
def wind_on_live_load_kn(pressure_kpa, span_m, solid_barrier_height_m, gust=None, drag=None, exposed_area_m2=None):
    if exposed_area_m2 is None:
        exposed_area_m2 = span_m * max(LIVE_LOAD_EXPOSED_HEIGHT_M - solid_barrier_height_m, 0.0)
    drag = LIVE_LOAD_DRAG_COEFFICIENT if drag is None else drag
    transverse_kn = pressure_kpa * exposed_area_m2 * gust_factor_for(span_m, gust) * drag
    return (transverse_kn, LIVE_LOAD_LONGITUDINAL_WIND_FRACTION * transverse_kn)
