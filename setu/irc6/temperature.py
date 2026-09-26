import numpy as np

from setu.irc6.irc_constants import (
    METALLIC_ABOVE_SHADE_MAX_C,
    METALLIC_BELOW_SHADE_MIN_C,
    TABLE_15B_COOLING_DT1_C,
    TABLE_15B_COOLING_DT2_C,
    TABLE_15B_HEATING_DT1_C,
    TABLE_15B_HEATING_DT2_C,
    TABLE_15B_SLAB_DEPTHS_M,
    TABLE_15B_SURFACINGS_M,
    TEMPERATURE_H1_FRACTION_OF_SLAB,
    TEMPERATURE_H2_M,
)
from setu.utils.constants import TOLERANCE_M

HEATING = "positive difference"
COOLING = "reverse difference"


# clause 215.2: a steel bridge goes from shade min - 10 C up to shade max + 15 C
def effective_temperature_range(shade_max_c, shade_min_c):
    return (shade_min_c - METALLIC_BELOW_SHADE_MIN_C, shade_max_c + METALLIC_ABOVE_SHADE_MAX_C)


# Fig. 17b heating and cooling profiles as (depth from slab top, degrees C) points, dT1 interpolated on slab depth and surfacing
def temperature_difference_profiles(slab_thickness_m, surfacing_m):
    within_the_table(slab_thickness_m, TABLE_15B_SLAB_DEPTHS_M, "slab depth")
    within_the_table(surfacing_m, TABLE_15B_SURFACINGS_M, "surfacing thickness")
    h1_m = TEMPERATURE_H1_FRACTION_OF_SLAB * slab_thickness_m
    heating_dt1_c = read_table_15b(TABLE_15B_HEATING_DT1_C, slab_thickness_m, surfacing_m)
    cooling_dt1_c = read_table_15b(TABLE_15B_COOLING_DT1_C, slab_thickness_m, surfacing_m)
    return {
        HEATING: [(0.0, heating_dt1_c), (h1_m, TABLE_15B_HEATING_DT2_C), (h1_m + TEMPERATURE_H2_M, 0.0)],
        COOLING: [(0.0, cooling_dt1_c), (h1_m, 0.0), (h1_m + TEMPERATURE_H2_M, TABLE_15B_COOLING_DT2_C)],
    }


# refuse a value outside what Table 15B gives, rather than extrapolate
def within_the_table(value_m, table_m, what):
    smallest_m, largest_m = table_m
    if not smallest_m - TOLERANCE_M <= value_m <= largest_m + TOLERANCE_M:
        raise ValueError(f"Table 15B gives the {what} from {smallest_m} to {largest_m} m, got {value_m} m")


# dT1 between the Table 15B rows (slab depth) and columns (surfacing)
def read_table_15b(table_c, slab_thickness_m, surfacing_m):
    by_depth_c = [float(np.interp(surfacing_m, TABLE_15B_SURFACINGS_M, row)) for row in table_c]
    return float(np.interp(slab_thickness_m, TABLE_15B_SLAB_DEPTHS_M, by_depth_c))
