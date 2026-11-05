import math

import numpy as np

from setu.irc6.irc_constants import (
    DRAG_CAMBER_INCREASE_AT_MOST,
    DRAG_INCREASE_PER_DEGREE_OF_CAMBER,
    GUST_FACTOR_BY_TERRAIN_CATEGORY,
    GUST_METHOD_UP_TO_PIER_HEIGHT_M,
    GUST_METHOD_UP_TO_SPAN_M,
    HOURLY_FACTOR_MULTIPLIER,
    HOURLY_FACTOR_ROUGHNESS_EXPONENT,
    K1_BASIC_WIND_SPEEDS_MPS,
    K1_BY_RETURN_PERIOD,
    K2_BY_TERRAIN_CATEGORY,
    K2_HOURLY_BY_TERRAIN_CATEGORY,
    K2_HEIGHTS_M,
    K3_VALLEY_OR_LEEWARD_HILL,
    K4_CYCLONE_COAST,
    K4_CYCLONE_COAST_FROM_BASIC_SPEED_MPS,
    K4_OFFSHORE,
    LIVE_LOAD_DEPTH_M,
    PLATE_GIRDERS_DRAG_BASE,
    PLATE_GIRDERS_DRAG_COEFFICIENT_MOST,
    PLATE_GIRDERS_DRAG_SPACING_DIVISOR,
    PRESSURE_PER_SPEED_SQUARED,
    ROUGHNESS_HEIGHT_M,
    SERVICE_DRAG_B_OVER_D,
    SERVICE_DRAG_COEFFICIENTS,
    SINGLE_PLATE_GIRDER_CONSTRUCTION_DRAG,
    WIND_RULES_APPLY_UP_TO_PIER_HEIGHT_M,
    WIND_RULES_APPLY_UP_TO_SPAN_M,
)

INLAND = "inland"
CYCLONE_COAST = "cyclone coast"
OFFSHORE = "offshore"
CYCLONIC_REGIONS = (INLAND, CYCLONE_COAST, OFFSHORE)
NO_TOPOGRAPHY_EFFECT = 1.0
NOT_CYCLONIC = 1.0


# 209.1: these quasi-static rules cover spans up to 200 m and piers up to 100 m
def check_scope(span_m, pier_height_m):
    if span_m > WIND_RULES_APPLY_UP_TO_SPAN_M or pier_height_m > WIND_RULES_APPLY_UP_TO_PIER_HEIGHT_M:
        raise ValueError(f"IRC:6 cl. 209.1 covers spans up to {WIND_RULES_APPLY_UP_TO_SPAN_M:.0f} m and piers up to "
                         f"{WIND_RULES_APPLY_UP_TO_PIER_HEIGHT_M:.0f} m (span {span_m} m, pier {pier_height_m} m); use Appendix 1")


# Table 1: k1 for a tabulated return period and basic wind speed zone (50 years is 1.0 for every zone)
def risk_coefficient(basic_wind_speed_mps, return_period_years):
    if return_period_years not in K1_BY_RETURN_PERIOD:
        raise ValueError(f"IRC:6 Table 1 gives k1 for return periods {sorted(K1_BY_RETURN_PERIOD)} years, got {return_period_years}")
    row = K1_BY_RETURN_PERIOD[return_period_years]
    if len(set(row)) == 1:
        return row[0]
    if basic_wind_speed_mps not in K1_BASIC_WIND_SPEEDS_MPS:
        raise ValueError(f"IRC:6 Table 1 gives k1 for basic wind speeds {K1_BASIC_WIND_SPEEDS_MPS} m/s, got {basic_wind_speed_mps}")
    return row[K1_BASIC_WIND_SPEEDS_MPS.index(basic_wind_speed_mps)]


# Table 3: k2 by height and terrain category; 'up to 10 m' below the first row, linear between rows
def terrain_height_factor(height_m, terrain_category):
    if height_m > K2_HEIGHTS_M[-1]:
        raise ValueError(f"IRC:6 Table 3 stops at {K2_HEIGHTS_M[-1]:.0f} m, got {height_m} m")
    return float(np.interp(max(height_m, K2_HEIGHTS_M[0]), K2_HEIGHTS_M, K2_BY_TERRAIN_CATEGORY[terrain_category]))


# 209.4: hourly mean speed factor k2bar from Table 4 (10-500 m, linear); below 10 m from Equation 4, 0.1423 ln(z / z0) z0^0.0706
def hourly_mean_height_factor(height_m, terrain_category):
    if height_m > K2_HEIGHTS_M[-1]:
        raise ValueError(f"IRC:6 Table 4 stops at {K2_HEIGHTS_M[-1]:.0f} m, got {height_m} m")
    if height_m >= K2_HEIGHTS_M[0]:
        return float(np.interp(height_m, K2_HEIGHTS_M, K2_HOURLY_BY_TERRAIN_CATEGORY[terrain_category]))
    z0_m = ROUGHNESS_HEIGHT_M[terrain_category]
    return HOURLY_FACTOR_MULTIPLIER * math.log(height_m / z0_m) * z0_m ** HOURLY_FACTOR_ROUGHNESS_EXPONENT


# 209.3.3: k3
def topography_factor(valley_or_leeward_hill):
    return K3_VALLEY_OR_LEEWARD_HILL if valley_or_leeward_hill else NO_TOPOGRAPHY_EFFECT


# 209.3.4: k4
def cyclonic_importance_factor(cyclonic_region, basic_wind_speed_mps):
    if cyclonic_region not in CYCLONIC_REGIONS:
        raise ValueError(f"cyclonic_region must be one of {CYCLONIC_REGIONS}, got {cyclonic_region!r}")
    if cyclonic_region == OFFSHORE:
        return K4_OFFSHORE
    if cyclonic_region == CYCLONE_COAST and basic_wind_speed_mps >= K4_CYCLONE_COAST_FROM_BASIC_SPEED_MPS:
        return K4_CYCLONE_COAST
    return NOT_CYCLONIC


# Equation 1: Vz = Vb k1 k2 k3 k4 (3 s gust)
def design_wind_speed_mps(site, height_m, return_period_years):
    return (site.basic_wind_speed_mps * risk_coefficient(site.basic_wind_speed_mps, return_period_years)
            * terrain_height_factor(height_m, site.terrain_category) * topography_factor(site.valley_or_leeward_hill)
            * cyclonic_importance_factor(site.cyclonic_region, site.basic_wind_speed_mps))


# Equation 5: hourly mean Vz,d = Vb k1 k2bar k3 k4
def hourly_mean_wind_speed_mps(site, height_m, return_period_years):
    return (site.basic_wind_speed_mps * risk_coefficient(site.basic_wind_speed_mps, return_period_years)
            * hourly_mean_height_factor(height_m, site.terrain_category) * topography_factor(site.valley_or_leeward_hill)
            * cyclonic_importance_factor(site.cyclonic_region, site.basic_wind_speed_mps))


# Equations 2 and 6: pressure in N/m2 from speed in m/s
def wind_pressure_pa(speed_mps):
    return PRESSURE_PER_SPEED_SQUARED * speed_mps ** 2


# Table 5: column 2 alone for a span up to 40 m on piers up to 20 m; otherwise the larger of columns 2 and 3, resolved by Table 6
def needs_hourly_mean_method(span_m, pier_height_m):
    return span_m > GUST_METHOD_UP_TO_SPAN_M or pier_height_m > GUST_METHOD_UP_TO_PIER_HEIGHT_M


# 209.5.2.2: gust factor for the hourly mean method
def gust_factor(terrain_category):
    return GUST_FACTOR_BY_TERRAIN_CATEGORY[terrain_category]


# Table 8 case I(ii): service-stage CD for a deck on beams by B/d, interpolated (note 1), raised 3 % per degree of camber up to 25 % (note 7)
def service_drag_coefficient(width_m, depth_m, cross_slope_deg):
    drag = float(np.interp(width_m / depth_m, SERVICE_DRAG_B_OVER_D, SERVICE_DRAG_COEFFICIENTS))
    return drag * (1.0 + min(DRAG_INCREASE_PER_DEGREE_OF_CAMBER * abs(cross_slope_deg), DRAG_CAMBER_INCREASE_AT_MOST))


# Table 8 case II(a): before the deck is cast, one plate girder 2.5, several 2(1 + c / 20d) but not more than 4
def construction_drag_coefficient(girder_count, girder_spacing_m, windward_girder_depth_m):
    if girder_count == 1:
        return SINGLE_PLATE_GIRDER_CONSTRUCTION_DRAG
    spread_out = PLATE_GIRDERS_DRAG_BASE * (1.0 + girder_spacing_m / (PLATE_GIRDERS_DRAG_SPACING_DIVISOR * windward_girder_depth_m))
    return min(spread_out, PLATE_GIRDERS_DRAG_COEFFICIENT_MOST)


# Fig. 5 / Table 7: depth for the area in elevation; road_depth_m is girder bottom to road surface
def exposed_depth_m(road_depth_m, solid_barrier_height_m, with_live_load):
    with_traffic_m = road_depth_m + LIVE_LOAD_DEPTH_M
    if solid_barrier_height_m > 0:
        solid_m = road_depth_m + solid_barrier_height_m
        return max(solid_m, with_traffic_m) if with_live_load else solid_m
    return with_traffic_m if with_live_load else road_depth_m


# Fig. 7: depth for deriving CD
def drag_depth_m(road_depth_m, solid_barrier_height_m, with_live_load):
    superstructure_m = road_depth_m + solid_barrier_height_m if solid_barrier_height_m > 0 else road_depth_m
    if superstructure_m > LIVE_LOAD_DEPTH_M or not with_live_load:
        return superstructure_m
    return LIVE_LOAD_DEPTH_M
