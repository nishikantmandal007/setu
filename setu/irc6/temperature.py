import numpy as np

from setu.irc6.irc_constants import (
    FIG_16B_POSITIVE_FADES_OVER_M,
    FIG_16B_POSITIVE_KINK_C,
    FIG_16B_POSITIVE_KINK_DEPTH_FRACTION,
    FIG_16B_POSITIVE_TOP_C,
    FIG_16B_REVERSE_BOTTOM_C,
    FIG_16B_REVERSE_TOP_C,
    FIG_16B_SLAB_DEPTHS_M,
    METALLIC_ABOVE_SHADE_MAX_C,
    METALLIC_BELOW_SHADE_MIN_C,
    SNOWBOUND_METALLIC_RANGE_C,
    TABLE_15_SWING_NARROW_C,
    TABLE_15_SWING_WIDE_C,
    TABLE_15_WIDE_SHADE_RANGE_C,
)
from setu.utils.constants import TOLERANCE_M


def effective_temperature_range(shade_max_c, shade_min_c, metallic=True, snowbound=False):
    if metallic:
        if snowbound:
            return SNOWBOUND_METALLIC_RANGE_C
        return (shade_min_c - METALLIC_BELOW_SHADE_MIN_C, shade_max_c + METALLIC_ABOVE_SHADE_MAX_C)
    mean_c = (shade_max_c + shade_min_c) / 2
    swing_c = TABLE_15_SWING_WIDE_C if shade_max_c - shade_min_c >= TABLE_15_WIDE_SHADE_RANGE_C else TABLE_15_SWING_NARROW_C
    return (mean_c - swing_c, mean_c + swing_c)


def temperature_difference_profile(slab_thickness_m, positive=True, reverse_depths_m=None):
    thinnest_m, thickest_m = FIG_16B_SLAB_DEPTHS_M
    if not thinnest_m - TOLERANCE_M <= slab_thickness_m <= thickest_m + TOLERANCE_M:
        raise ValueError(f"Fig. 16b is drawn for slabs of {thinnest_m} to {thickest_m} m, got {slab_thickness_m} m")
    if positive:
        top_c = float(np.interp(slab_thickness_m, FIG_16B_SLAB_DEPTHS_M, FIG_16B_POSITIVE_TOP_C))
        kink_m = FIG_16B_POSITIVE_KINK_DEPTH_FRACTION * slab_thickness_m
        return [(0.0, top_c), (kink_m, FIG_16B_POSITIVE_KINK_C), (kink_m + FIG_16B_POSITIVE_FADES_OVER_M, 0.0)]
    if reverse_depths_m is None:
        raise ValueError("Fig. 16b does not give the depths h1 and h2 of the reverse profile; pass reverse_depths_m=(h1, h2)")
    first_m, second_m = reverse_depths_m
    top_c = float(np.interp(slab_thickness_m, FIG_16B_SLAB_DEPTHS_M, FIG_16B_REVERSE_TOP_C))
    return [(0.0, -top_c), (first_m, 0.0), (first_m + second_m, -FIG_16B_REVERSE_BOTTOM_C)]
