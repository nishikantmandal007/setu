"""Lane arrangements must follow Tables 3, 6 and 6A."""

from __future__ import annotations

import pytest

from setu.irc_code_rules.lane_arrangements import (
    CLASS_A_LANE,
    ZONE_70R,
    class_a_gap,
    count_design_lanes,
    fit_blocks_between,
    list_admissible_arrangements,
    narrowest_carriageway_that_fits,
    where_vehicle_sits_in_block,
)


@pytest.mark.parametrize(
    ("carriageway_width_m", "design_lanes"),
    [
        (4.25, 1),
        (5.29, 1),
        (5.30, 2),
        (9.59, 2),
        (9.60, 3),
        (13.09, 3),
        (13.10, 4),
        (16.60, 5),
        (20.10, 6),
        (30.00, 6),
    ],
)
def test_table_6_lane_counts(carriageway_width_m, design_lanes):
    assert count_design_lanes(carriageway_width_m) == design_lanes


def test_a_carriageway_too_narrow_to_load_carries_nothing():
    """IRC:5 Clause 104.3 - below 4.25 m no vehicle is placed at all."""
    assert list_admissible_arrangements(4.0) == []


@pytest.mark.parametrize(
    ("carriageway_width_m", "gap_m"),
    [(7.0, 1.20), (6.20, 1.20), (6.10, 1.20), (5.80, 0.90), (5.30, 0.40), (5.00, 0.40)],
)
def test_table_3_gap_between_two_class_a_vehicles(carriageway_width_m, gap_m):
    assert class_a_gap(carriageway_width_m) == pytest.approx(gap_m)


def test_two_class_a_vehicles_need_the_tabulated_width():
    """Two 2.30 m lanes, two 0.15 m kerb clearances and a 1.20 m gap = 6.10 m.

    Which is exactly the width above which Table 3 gives the full 1.20 m gap -
    the two readings of the table agree at the point where they meet.
    """
    assert narrowest_carriageway_that_fits([CLASS_A_LANE, CLASS_A_LANE]) == pytest.approx(6.10)
    assert class_a_gap(6.10) == pytest.approx(1.20)


def test_a_lone_70r_needs_only_its_own_clearances():
    """2.90 m wide plus 1.20 m either side = 5.30 m."""
    assert narrowest_carriageway_that_fits([ZONE_70R]) == pytest.approx(5.30)


def test_partly_loaded_arrangements_are_included():
    """Table 6A note (b): fewer vehicles can govern, so subsets must be searched."""
    patterns = [
        tuple(arrangement.lane_pattern) for arrangement in list_admissible_arrangements(9.0)
    ]

    assert (CLASS_A_LANE, CLASS_A_LANE) in patterns
    assert (CLASS_A_LANE,) in patterns


def test_arrangements_never_exceed_the_carriageway():
    for carriageway_width_m in (4.5, 5.3, 7.0, 9.6, 13.1, 16.6, 20.1, 24.0):
        for arrangement in list_admissible_arrangements(carriageway_width_m):
            assert arrangement.narrowest_carriageway_m <= carriageway_width_m + 1e-9
            assert arrangement.sliding_room_m >= 0.0


def test_a_70r_zone_is_wider_at_the_edge_than_between_lanes():
    at_edge = fit_blocks_between([ZONE_70R, CLASS_A_LANE], 0.0, 12.0)
    inside = fit_blocks_between([CLASS_A_LANE, ZONE_70R, CLASS_A_LANE], 0.0, 14.0)

    assert at_edge.block_widths_m[0] == pytest.approx(7.25)
    assert inside.block_widths_m[1] == pytest.approx(7.00)


def test_class_a_sits_at_the_centre_of_its_lane_but_70r_floats():
    nearest_m, furthest_m = where_vehicle_sits_in_block(CLASS_A_LANE, 2.30)
    assert nearest_m == furthest_m == pytest.approx(1.15)

    nearest_m, furthest_m = where_vehicle_sits_in_block(ZONE_70R, 7.25)
    assert nearest_m == pytest.approx(1.20 + 2.90 / 2)
    assert furthest_m > nearest_m


def test_an_arrangement_that_does_not_fit_is_refused():
    assert fit_blocks_between([CLASS_A_LANE, CLASS_A_LANE], 0.0, 4.0) is None
