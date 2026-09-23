import itertools

from setu.irc6.irc_constants import (
    IMPORTANCE_FACTORS,
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

BOTH_WAYS = (1.0, -1.0)


def zone_factor(zone):
    return ZONE_FACTORS[zone]


def importance_factor(importance):
    return IMPORTANCE_FACTORS[importance] if isinstance(importance, str) else float(importance)


def minimum_horizontal_coefficient(zone):
    return MINIMUM_HORIZONTAL_SEISMIC_COEFFICIENT[zone]


def spectral_acceleration(period_s, soil):
    if period_s is None:
        return SA_OVER_G_WITHOUT_A_PERIOD
    plateau_ends_s, falls_as_over_t, tail = SPECTRUM_BY_SOIL[soil]
    if period_s <= plateau_ends_s:
        return SPECTRUM_PLATEAU
    if period_s <= SPECTRUM_TAIL_STARTS_S:
        return falls_as_over_t / period_s
    return tail


def horizontal_seismic_coefficient(site):
    elastic = zone_factor(site.zone) / ZONE_FACTOR_DIVISOR * importance_factor(site.importance) / site.response_reduction
    return max(elastic * spectral_acceleration(site.period_s, site.soil), minimum_horizontal_coefficient(site.zone))


def vertical_seismic_coefficient(site):
    vertical_zone_factor = VERTICAL_ZONE_FACTOR_FRACTION * zone_factor(site.zone)
    elastic = vertical_zone_factor / ZONE_FACTOR_DIVISOR * importance_factor(site.importance) / site.response_reduction
    return elastic * spectral_acceleration(site.vertical_period_s, site.soil)


def combine_directions(r1, r2, r3=None):
    responses = [r1, r2] if r3 is None else [r1, r2, r3]
    combined = []
    for full in range(len(responses)):
        scaled = [response if k == full else OTHER_DIRECTIONS_FRACTION * response for k, response in enumerate(responses)]
        for signs in itertools.product(BOTH_WAYS, repeat=len(scaled)):
            combined.append(sum(sign * value for sign, value in zip(signs, scaled, strict=True)))
    return combined
