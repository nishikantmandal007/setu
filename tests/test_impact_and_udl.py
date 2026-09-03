"""Clause 208 impact, Clause 205 lane reduction, and the area loads."""


import numpy as np
import pytest

from setu.rules.irc6 import (
    needs_residual_udl,
    response_to_area_load,
    strips_beside_class_a,
    uncovered_strips,
)
from setu.config.constants import RESIDUAL_UDL_KPA
from setu.rules.irc6 import (
    class_a_impact_fraction,
    impact_factor,
    impact_fraction,
)
from setu.rules.irc6 import lane_reduction_factor


@pytest.mark.parametrize(
    ("loaded_lanes", "factor"), [(1, 1.00), (2, 1.00), (3, 0.90), (4, 0.80), (6, 0.80)]
)
def test_table_8_lane_reduction(loaded_lanes, factor):
    assert lane_reduction_factor(loaded_lanes) == pytest.approx(factor)


def test_the_figure_9_curve_for_class_a():
    """Clause 208.2: i = 9 / (13.5 + L) for steel, 4.5 / (6 + L) for concrete."""
    assert class_a_impact_fraction(35.0, "steel") == pytest.approx(9.0 / 48.5)
    assert class_a_impact_fraction(35.0, "rc") == pytest.approx(4.5 / 41.0)


def test_the_figure_9_curve_is_held_at_its_ends():
    """It is drawn between 3 m and 45 m; outside that it is not extrapolated."""
    assert class_a_impact_fraction(1.0) == class_a_impact_fraction(3.0)
    assert class_a_impact_fraction(90.0) == class_a_impact_fraction(45.0)


@pytest.mark.parametrize("span_m", [3.0, 9.0, 20.0, 45.0])
def test_impact_factor_is_one_plus_the_fraction(span_m):
    for vehicle in ("Class_A", "Class_70R_Wheeled", "Class_70R_Tracked"):
        assert impact_factor(vehicle, span_m) == pytest.approx(
            1.0 + impact_fraction(vehicle, span_m)
        )


def test_short_spans_take_the_full_quarter():
    """Clause 208.3(a): 25 per cent below 9 m, easing off for tracked vehicles."""
    assert impact_fraction("Class_70R_Wheeled", 5.0) == pytest.approx(0.25)
    assert impact_fraction("Class_70R_Tracked", 5.0) == pytest.approx(0.25)
    assert impact_fraction("Class_70R_Tracked", 9.0) == pytest.approx(0.10)


def test_impact_never_grows_with_span():
    """A longer member is less lively, so the allowance can only fall."""
    spans_m = np.linspace(3.0, 45.0, 200)
    for vehicle in ("Class_A", "Class_70R_Wheeled", "Class_70R_Tracked"):
        fractions = [impact_fraction(vehicle, span_m) for span_m in spans_m]
        assert all(
            later <= earlier + 1e-12
            for earlier, later in zip(fractions, fractions[1:], strict=False)
        )


@pytest.mark.parametrize(
    ("carriageway_width_m", "applies"), [(4.5, True), (5.29, True), (5.30, False), (9.0, False)]
)
def test_when_the_residual_udl_applies(carriageway_width_m, applies):
    """Table 6 S.No.1 - only on a carriageway under 5.30 m."""
    assert needs_residual_udl(carriageway_width_m) is applies


def test_the_residual_udl_is_500_kg_per_square_metre():
    assert pytest.approx(500.0 * 9.81 / 1000.0) == RESIDUAL_UDL_KPA


def test_the_strips_move_with_the_vehicle():
    """The uncovered width is beside the vehicle, so it shifts as the vehicle does."""
    to_the_left, to_the_right = strips_beside_class_a(3.0, 0.5, 5.1)

    assert to_the_left == pytest.approx((0.5, 3.0 - 1.15))
    assert to_the_right == pytest.approx((3.0 + 1.15, 5.1))


def test_a_vehicle_covering_everything_leaves_no_strip():
    assert uncovered_strips([(0.0, 5.0)], 1.0, 4.0) == []


def test_only_the_adverse_area_is_loaded(sagging_surface, hogging_surface):
    """Muller-Breslau: a uniform load stands only where it hurts.

    On a surface of one sign it makes no difference; on one that changes sign it
    always makes the answer worse.
    """
    strips = [(2.0, 11.5)]

    everywhere = response_to_area_load(
        hogging_surface, strips, "minimum", adverse_area_only=False
    )
    only_where_it_hurts = response_to_area_load(
        hogging_surface, strips, "minimum", adverse_area_only=True
    )
    assert only_where_it_hurts <= everywhere + 1e-9

    one_sign = response_to_area_load(sagging_surface, strips, "maximum")
    assert one_sign > 0
