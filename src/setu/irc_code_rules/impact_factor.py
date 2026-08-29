# Clause 208 - the dynamic allowance that amplifies a static wheel load. The factor
# depends on the vehicle, whether the deck is steel or concrete, and the effective span
# of the *member* being checked, which is not always the span of the bridge (Clause
# 208.5). So the factor is applied per member, inside each response, rather than once
# as a blanket multiplier on a whole load case.

from __future__ import annotations

from .code_tables import (
    LONGEST_TABULATED_SPAN_M,
    SHORT_SPAN_IMPACT_FRACTION,
    SHORT_SPAN_UPPER_LIMIT_M,
    SHORTEST_TABULATED_SPAN_M,
    TRACKED_IMPACT_FRACTION_FLOOR,
    TRACKED_RC_IMPACT_PLATEAU_LIMIT_M,
    TRACKED_TRANSITION_SPAN_WIDTH_M,
    TRACKED_TRANSITION_START_SPAN_M,
    WHEELED_70R_IMPACT_CURVE_TAKES_OVER_RC_M,
    WHEELED_70R_IMPACT_CURVE_TAKES_OVER_STEEL_M,
)


def class_a_impact_fraction(span_m: float, material: str = "steel") -> float:
    # Clause 208.2, the Figure 9 curve. Anything not exactly "steel" is treated as RC.
    span_m = min(max(float(span_m), SHORTEST_TABULATED_SPAN_M), LONGEST_TABULATED_SPAN_M)

    # The two Figure 9 curves, written the way the code writes them. Naming the four
    # coefficients only made the formula harder to read than the standard it came from.
    if material == "steel":
        return 9.0 / (13.5 + span_m)
    return 4.5 / (6.0 + span_m)


def impact_fraction(vehicle_name: str, span_m: float, material: str = "steel") -> float:
    # Class A follows the Figure 9 curve. The 70R vehicles have their own flat and
    # transition values, Clause 208.3.
    span_m = float(span_m)

    if vehicle_name == "Class_A":
        return class_a_impact_fraction(span_m, material)

    is_tracked = "Tracked" in vehicle_name

    if span_m < SHORT_SPAN_UPPER_LIMIT_M:
        return short_span_impact_fraction(span_m, is_tracked)

    return long_span_impact_fraction(span_m, is_tracked, material)


def short_span_impact_fraction(span_m: float, is_tracked: bool) -> float:
    # Clause 208.3(a) - spans below 9 m.
    if not is_tracked:
        return SHORT_SPAN_IMPACT_FRACTION

    if span_m <= TRACKED_TRANSITION_START_SPAN_M:
        return SHORT_SPAN_IMPACT_FRACTION

    # Tracked vehicles fall linearly from 25% at 5 m to 10% at 9 m.
    fall = TRACKED_IMPACT_FRACTION_FLOOR - SHORT_SPAN_IMPACT_FRACTION
    into_the_band_m = span_m - TRACKED_TRANSITION_START_SPAN_M
    return SHORT_SPAN_IMPACT_FRACTION + fall * into_the_band_m / TRACKED_TRANSITION_SPAN_WIDTH_M


def long_span_impact_fraction(span_m: float, is_tracked: bool, material: str) -> float:
    # Clause 208.3(b) - spans of 9 m and above. Each vehicle holds a flat value until the
    # Figure 9 curve drops below it; the thresholds below are those crossing points.
    if is_tracked:
        if material == "steel":
            return TRACKED_IMPACT_FRACTION_FLOOR
        return (
            TRACKED_IMPACT_FRACTION_FLOOR
            if span_m <= TRACKED_RC_IMPACT_PLATEAU_LIMIT_M
            else class_a_impact_fraction(span_m, "rc")
        )

    curve_takes_over_above_m = (
        WHEELED_70R_IMPACT_CURVE_TAKES_OVER_STEEL_M
        if material == "steel"
        else WHEELED_70R_IMPACT_CURVE_TAKES_OVER_RC_M
    )
    if span_m <= curve_takes_over_above_m:
        return SHORT_SPAN_IMPACT_FRACTION
    return class_a_impact_fraction(span_m, material)


def impact_factor(vehicle_name: str, span_m: float, material: str = "steel") -> float:
    # (1 + i): multiply a static response by this to allow for impact.
    return 1.0 + impact_fraction(vehicle_name, span_m, material)
