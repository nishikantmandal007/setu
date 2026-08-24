"""Clause 208 - the dynamic allowance that amplifies a static wheel load.

The factor depends on three things: which vehicle it is, whether the deck is
steel or concrete, and the effective span of the *member* being checked.

That last one matters more than it looks. Clause 208.5 asks for the effective
span of the member, which is not always the span of the bridge - a deck slab
panel has its own. So the factor is applied per member, inside each response,
rather than once as a blanket multiplier on a whole load case.
"""

from __future__ import annotations

SHORTEST_TABULATED_SPAN_M = 3.0
LONGEST_TABULATED_SPAN_M = 45.0


def class_a_impact_fraction(span_m: float, material: str = "steel") -> float:
    """Returns the Clause 208.2 impact fraction for Class A, from the Figure 9 curve.

    Figure 9 is drawn between 3 m and 45 m. Outside that range the curve is held
    at its end value rather than extrapolated, because extrapolating a fitted
    curve past its data is not something the code authorises.
    """
    span_m = min(max(float(span_m), SHORTEST_TABULATED_SPAN_M), LONGEST_TABULATED_SPAN_M)

    if material == "steel":
        return 9.0 / (13.5 + span_m)
    return 4.5 / (6.0 + span_m)


def impact_fraction(vehicle_name: str, span_m: float, material: str = "steel") -> float:
    """Returns the impact fraction for one vehicle on a member of this effective span.

    Class A follows the Figure 9 curve. The 70R vehicles have their own flat and
    transition values in Clause 208.3.
    """
    span_m = float(span_m)

    if vehicle_name == "Class_A":
        return class_a_impact_fraction(span_m, material)

    is_tracked = "Tracked" in vehicle_name

    if span_m < 9.0:
        return _short_span_impact_fraction(span_m, is_tracked)

    return _long_span_impact_fraction(span_m, is_tracked, material)


def _short_span_impact_fraction(span_m: float, is_tracked: bool) -> float:
    """Clause 208.3(a) - spans below 9 m."""
    if not is_tracked:
        return 0.25

    if span_m <= 5.0:
        return 0.25

    # Tracked vehicles fall linearly from 25% at 5 m to 10% at 9 m.
    return 0.25 + (0.10 - 0.25) * (span_m - 5.0) / 4.0


def _long_span_impact_fraction(span_m: float, is_tracked: bool, material: str) -> float:
    """Clause 208.3(b) - spans of 9 m and above.

    Each vehicle holds a flat value until the Figure 9 curve drops below it, and
    follows the curve from there. The thresholds below are those crossing points.
    """
    if is_tracked:
        if material == "steel":
            return 0.10
        return 0.10 if span_m <= 40.0 else class_a_impact_fraction(span_m, "rc")

    curve_takes_over_above_m = 23.0 if material == "steel" else 12.0
    if span_m <= curve_takes_over_above_m:
        return 0.25
    return class_a_impact_fraction(span_m, material)


def impact_factor(vehicle_name: str, span_m: float, material: str = "steel") -> float:
    """Returns (1 + i): multiply a static response by this to allow for impact."""
    return 1.0 + impact_fraction(vehicle_name, span_m, material)
