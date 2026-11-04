import numpy as np

from setu.irc6.irc_constants import (
    FIG_16B_COOLING_AT_H1_PLUS_H2_C,
    FIG_16B_COOLING_T1_C,
    FIG_16B_HEATING_AT_H1_C,
    FIG_16B_HEATING_T1_C,
    FIG_16B_SLAB_DEPTHS_M,
    METALLIC_ABOVE_SHADE_MAX_C,
    METALLIC_BELOW_SHADE_MIN_C,
    SNOWBOUND_EFFECTIVE_RANGE_C,
    TEMPERATURE_H1_FRACTION_OF_SLAB,
    TEMPERATURE_H2_M,
)
from setu.utils.constants import TOLERANCE_M

HEATING = "positive difference"
COOLING = "reverse difference"


# clause 215.2: a steel bridge goes from shade min - 10 C up to shade max + 15 C, or -35 C to +50 C in snowbound areas
def effective_temperature_range(shade_max_c, shade_min_c, snowbound=False):
    if snowbound:
        return SNOWBOUND_EFFECTIVE_RANGE_C
    return (shade_min_c - METALLIC_BELOW_SHADE_MIN_C, shade_max_c + METALLIC_ABOVE_SHADE_MAX_C)


# Fig. 16b heating and cooling profiles as (depth from slab top, degrees C) points, T1 interpolated on slab depth
def temperature_difference_profiles(slab_thickness_m):
    within_the_figure(slab_thickness_m)
    h1_m = TEMPERATURE_H1_FRACTION_OF_SLAB * slab_thickness_m
    heating_t1_c = float(np.interp(slab_thickness_m, FIG_16B_SLAB_DEPTHS_M, FIG_16B_HEATING_T1_C))
    cooling_t1_c = float(np.interp(slab_thickness_m, FIG_16B_SLAB_DEPTHS_M, FIG_16B_COOLING_T1_C))
    return {
        HEATING: [(0.0, heating_t1_c), (h1_m, FIG_16B_HEATING_AT_H1_C), (h1_m + TEMPERATURE_H2_M, 0.0)],
        COOLING: [(0.0, cooling_t1_c), (h1_m, 0.0), (h1_m + TEMPERATURE_H2_M, FIG_16B_COOLING_AT_H1_PLUS_H2_C)],
    }


# refuse a slab depth Fig. 16b does not give, rather than extrapolate (the figure allows interpolation only)
def within_the_figure(slab_thickness_m):
    smallest_m, largest_m = FIG_16B_SLAB_DEPTHS_M
    if not smallest_m - TOLERANCE_M <= slab_thickness_m <= largest_m + TOLERANCE_M:
        raise ValueError(f"IRC:6 Fig. 16b gives the slab depth from {smallest_m} to {largest_m} m, got {slab_thickness_m} m")
