import numpy as np

from setu.irc6.irc_constants import (
    FIG_16B_POSITIVE_FADES_OVER_M,
    FIG_16B_POSITIVE_KINK_C,
    FIG_16B_POSITIVE_KINK_DEPTH_FRACTION,
    FIG_16B_POSITIVE_TOP_C,
    FIG_16B_SLAB_DEPTHS_M,
    METALLIC_ABOVE_SHADE_MAX_C,
    METALLIC_BELOW_SHADE_MIN_C,
)
from setu.utils.constants import TOLERANCE_M


# clause 215.2: a steel bridge goes from shade min - 10 C up to shade max + 15 C
def effective_temperature_range(shade_max_c, shade_min_c):
    return (shade_min_c - METALLIC_BELOW_SHADE_MIN_C, shade_max_c + METALLIC_ABOVE_SHADE_MAX_C)


# Fig. 16b positive temperature difference: (depth from slab top, degrees C) points
def temperature_difference_profile(slab_thickness_m):
    thinnest_m, thickest_m = FIG_16B_SLAB_DEPTHS_M
    if not thinnest_m - TOLERANCE_M <= slab_thickness_m <= thickest_m + TOLERANCE_M:
        raise ValueError(f"Fig. 16b is drawn for slabs of {thinnest_m} to {thickest_m} m, got {slab_thickness_m} m")
    top_c = float(np.interp(slab_thickness_m, FIG_16B_SLAB_DEPTHS_M, FIG_16B_POSITIVE_TOP_C))
    kink_m = FIG_16B_POSITIVE_KINK_DEPTH_FRACTION * slab_thickness_m
    return [(0.0, top_c), (kink_m, FIG_16B_POSITIVE_KINK_C), (kink_m + FIG_16B_POSITIVE_FADES_OVER_M, 0.0)]
