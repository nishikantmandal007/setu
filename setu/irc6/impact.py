from setu.irc6.irc_constants import (
    SHORTEST_TABULATED_SPAN_M,
    LONGEST_TABULATED_SPAN_M,
    SHORT_SPAN_UPPER_LIMIT_M,
    SHORT_SPAN_IMPACT_FRACTION,
    TRACKED_TRANSITION_START_SPAN_M,
    TRACKED_IMPACT_FRACTION_FLOOR,
    TRACKED_TRANSITION_SPAN_WIDTH_M,
    WHEELED_70R_IMPACT_CURVE_TAKES_OVER_M,
)


# 70R tracked vehicle?
def is_tracked(vehicle_name):
    return 'Tracked' in vehicle_name

# Class A train?
def is_class_a(vehicle_name):
    return vehicle_name == 'Class_A'

# clause 208.2 impact for Class A on a steel bridge: 9 / (13.5 + L)
def class_a_impact_fraction(span_m):
    span_m = min(max(float(span_m), SHORTEST_TABULATED_SPAN_M), LONGEST_TABULATED_SPAN_M)
    return 9.0 / (13.5 + span_m)

# clause 208 impact fraction for this vehicle and span, steel bridge
def impact_fraction(vehicle_name, span_m):
    span_m = float(span_m)
    if is_class_a(vehicle_name):
        return class_a_impact_fraction(span_m)
    if span_m < SHORT_SPAN_UPPER_LIMIT_M:
        return short_span_impact_fraction(span_m, is_tracked(vehicle_name))
    if is_tracked(vehicle_name):
        return TRACKED_IMPACT_FRACTION_FLOOR
    return wheeled_70r_long_span_impact_fraction(span_m)

# 70R under 9 m: 25%, tracked tapering to 10%
def short_span_impact_fraction(span_m, vehicle_is_tracked):
    if not vehicle_is_tracked:
        return SHORT_SPAN_IMPACT_FRACTION
    if span_m <= TRACKED_TRANSITION_START_SPAN_M:
        return SHORT_SPAN_IMPACT_FRACTION
    fall = TRACKED_IMPACT_FRACTION_FLOOR - SHORT_SPAN_IMPACT_FRACTION
    into_the_band_m = span_m - TRACKED_TRANSITION_START_SPAN_M
    fallen_so_far = fall * into_the_band_m / TRACKED_TRANSITION_SPAN_WIDTH_M
    return SHORT_SPAN_IMPACT_FRACTION + fallen_so_far

# 70R wheeled from 9 m: 25% up to 23 m, then the Class A curve
def wheeled_70r_long_span_impact_fraction(span_m):
    if span_m <= WHEELED_70R_IMPACT_CURVE_TAKES_OVER_M:
        return SHORT_SPAN_IMPACT_FRACTION
    return class_a_impact_fraction(span_m)

# 1 + impact fraction
def impact_factor(vehicle_name, span_m):
    return 1.0 + impact_fraction(vehicle_name, span_m)
