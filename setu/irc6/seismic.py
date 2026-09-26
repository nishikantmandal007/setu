import itertools

from setu.irc6.irc_constants import (
    MINIMUM_HORIZONTAL_SEISMIC_COEFFICIENT,
    OTHER_DIRECTIONS_FRACTION,
    SA_OVER_G_WITHOUT_A_PERIOD,
    SPECTRUM_BY_SOIL,
    SPECTRUM_PLATEAU,
    SPECTRUM_TAIL_STARTS_S,
    VERTICAL_ZONE_FACTOR_FRACTION,
    ZONE_FACTOR_DIVISOR,
    ZONE_FACTORS,
)
from setu.utils.constants import BOTH_WAYS


# Z for the zone, Table 4.2
def zone_factor(zone):
    return ZONE_FACTORS[zone]


# lowest Ah allowed for the zone, Table 5.2
def minimum_horizontal_coefficient(zone):
    return MINIMUM_HORIZONTAL_SEISMIC_COEFFICIENT[zone]


# Sa/g off the Fig. 5.1 spectrum for this period and soil
def spectral_acceleration(period_s, soil):
    plateau_ends_s, falls_as_over_t, tail = SPECTRUM_BY_SOIL[soil]
    if period_s <= plateau_ends_s:
        return SPECTRUM_PLATEAU
    if period_s <= SPECTRUM_TAIL_STARTS_S:
        return falls_as_over_t / period_s
    return tail


# Ah = Z/2 x I/R x Sa/g, never below the Table 5.2 minimum
def horizontal_seismic_coefficient(site):
    elastic = zone_factor(site.zone) / ZONE_FACTOR_DIVISOR * site.importance_factor / site.response_reduction
    return max(elastic * spectral_acceleration(site.period_s, site.soil), minimum_horizontal_coefficient(site.zone))


# Av with 2/3 of Z; OsdagBridge gives no vertical period, so Sa/g is the Fig. 5.1 note's 2.5
def vertical_seismic_coefficient(site):
    vertical_zone_factor = VERTICAL_ZONE_FACTOR_FRACTION * zone_factor(site.zone)
    return vertical_zone_factor / ZONE_FACTOR_DIVISOR * site.importance_factor / site.response_reduction * SA_OVER_G_WITHOUT_A_PERIOD


# clause 4.2.2: each direction in full plus 30% of the others, every sign
def combine_directions(r1, r2, r3=None):
    responses = [r1, r2] if r3 is None else [r1, r2, r3]
    combined = []
    for full in range(len(responses)):
        scaled = [response if k == full else OTHER_DIRECTIONS_FRACTION * response for k, response in enumerate(responses)]
        for signs in itertools.product(BOTH_WAYS, repeat=len(scaled)):
            combined.append(sum(sign * value for sign, value in zip(signs, scaled, strict=True)))
    return combined
