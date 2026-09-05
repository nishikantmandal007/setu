from setu.irc6.constants import (
    SHORTEST_TABULATED_SPAN_M,
    LONGEST_TABULATED_SPAN_M,
    SHORT_SPAN_UPPER_LIMIT_M,
    SHORT_SPAN_IMPACT_FRACTION,
    TRACKED_TRANSITION_START_SPAN_M,
    TRACKED_IMPACT_FRACTION_FLOOR,
    TRACKED_TRANSITION_SPAN_WIDTH_M,
    TRACKED_RC_IMPACT_PLATEAU_LIMIT_M,
    WHEELED_70R_IMPACT_CURVE_TAKES_OVER_STEEL_M,
    WHEELED_70R_IMPACT_CURVE_TAKES_OVER_RC_M,
)


def is_steel(material):
    return material == 'steel'

def is_tracked(vehicle_name):
    return 'Tracked' in vehicle_name

def is_class_a(vehicle_name):
    return vehicle_name == 'Class_A'

def class_a_impact_fraction(span_m, material='steel'):
    span_m = min(max(float(span_m), SHORTEST_TABULATED_SPAN_M), LONGEST_TABULATED_SPAN_M)
    if is_steel(material):
        return 9.0 / (13.5 + span_m)
    return 4.5 / (6.0 + span_m)

def impact_fraction(vehicle_name, span_m, material='steel'):
    span_m = float(span_m)
    if is_class_a(vehicle_name):
        return class_a_impact_fraction(span_m, material)
    if span_m < SHORT_SPAN_UPPER_LIMIT_M:
        return short_span_impact_fraction(span_m, is_tracked(vehicle_name))
    return long_span_impact_fraction(span_m, is_tracked(vehicle_name), material)

def short_span_impact_fraction(span_m, vehicle_is_tracked):
    if not vehicle_is_tracked:
        return SHORT_SPAN_IMPACT_FRACTION
    if span_m <= TRACKED_TRANSITION_START_SPAN_M:
        return SHORT_SPAN_IMPACT_FRACTION
    fall = TRACKED_IMPACT_FRACTION_FLOOR - SHORT_SPAN_IMPACT_FRACTION
    into_the_band_m = span_m - TRACKED_TRANSITION_START_SPAN_M
    fallen_so_far = fall * into_the_band_m / TRACKED_TRANSITION_SPAN_WIDTH_M
    return SHORT_SPAN_IMPACT_FRACTION + fallen_so_far

def long_span_impact_fraction(span_m, vehicle_is_tracked, material):
    if vehicle_is_tracked:
        return tracked_long_span_impact_fraction(span_m, material)
    return wheeled_70r_long_span_impact_fraction(span_m, material)

def tracked_long_span_impact_fraction(span_m, material):
    if is_steel(material):
        return TRACKED_IMPACT_FRACTION_FLOOR
    if span_m <= TRACKED_RC_IMPACT_PLATEAU_LIMIT_M:
        return TRACKED_IMPACT_FRACTION_FLOOR
    return class_a_impact_fraction(span_m, 'rc')

def wheeled_70r_long_span_impact_fraction(span_m, material):
    if is_steel(material):
        curve_takes_over_above_m = WHEELED_70R_IMPACT_CURVE_TAKES_OVER_STEEL_M
    else:
        curve_takes_over_above_m = WHEELED_70R_IMPACT_CURVE_TAKES_OVER_RC_M
    if span_m <= curve_takes_over_above_m:
        return SHORT_SPAN_IMPACT_FRACTION
    return class_a_impact_fraction(span_m, material)

def impact_factor(vehicle_name, span_m, material='steel'):
    return 1.0 + impact_fraction(vehicle_name, span_m, material)
