"""Lane arrangements must follow Tables 3, 6 and 6A."""


import pytest

from src.utils.code_rules import (
    CLASS_A_LANE,
    ZONE_70R,
    class_a_gap,
    count_design_lanes,
    fit_blocks_between,
    fits_in_carriageway,
    is_70r_placed_as_the_code_draws_it,
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


def test_a_lone_70r_is_searched_wherever_it_fits():
    """A 70R needs 5.30 m, so any carriageway that wide must consider one.

    It once did not. Arrangements were built by taking the fully loaded case and
    stripping vehicles off it, and on a 9.60 m carriageway every fully loaded
    case containing a 70R needs 9.70 m and was thrown away - taking the lone 70R
    that fits perfectly well down with it. The same happened to a pair of them
    between 16.60 m and 16.70 m.
    """
    for carriageway_width_m in (5.30, 7.00, 9.60, 9.65, 12.00, 16.60, 16.65, 20.00):
        patterns = [
            tuple(arrangement.lane_pattern)
            for arrangement in list_admissible_arrangements(carriageway_width_m)
        ]
        assert (ZONE_70R,) in patterns, f"no lone 70R searched on {carriageway_width_m} m"


def test_two_70r_vehicles_are_searched_wherever_they_fit():
    for carriageway_width_m in (14.50, 16.60, 18.00, 22.00):
        patterns = [
            tuple(arrangement.lane_pattern)
            for arrangement in list_admissible_arrangements(carriageway_width_m)
        ]
        assert (ZONE_70R, ZONE_70R) in patterns


@pytest.mark.parametrize(
    "carriageway_width_m", [4.25, 5.30, 6.10, 7.50, 9.60, 11.0, 13.10, 16.60, 20.10, 23.60]
)
def test_nothing_that_fits_is_left_out(carriageway_width_m):
    """With the placement rule lifted, everything that fits must be searched.

    Anything that fits between the kerbs and uses no more lanes than Table 6
    allows is a position someone could legally drive into.
    """
    from itertools import product

    searched = {
        tuple(arrangement.lane_pattern)
        for arrangement in list_admissible_arrangements(
            carriageway_width_m, follow_combination_drawings=False
        )
    }

    design_lanes = count_design_lanes(carriageway_width_m)
    everything_that_fits = set()
    for blocks in range(1, design_lanes + 1):
        for pattern in product((CLASS_A_LANE, ZONE_70R), repeat=blocks):
            lanes_used = sum(2 if block == ZONE_70R else 1 for block in pattern)
            if lanes_used <= design_lanes and fits_in_carriageway(
                list(pattern), carriageway_width_m
            ):
                everything_that_fits.add(pattern)

    assert searched == everything_that_fits


@pytest.mark.parametrize(
    "carriageway_width_m", [4.25, 5.30, 9.60, 13.10, 16.60, 20.10, 23.60]
)
def test_by_default_a_70r_is_never_boxed_in(carriageway_width_m):
    """A 70R must reach a kerb through 70R zones only, as the drawings place them."""
    for arrangement in list_admissible_arrangements(carriageway_width_m):
        assert is_70r_placed_as_the_code_draws_it(arrangement.lane_pattern)


def test_the_placement_rule_is_what_rules_a_boxed_in_70r_out():
    assert not is_70r_placed_as_the_code_draws_it([CLASS_A_LANE, ZONE_70R, CLASS_A_LANE])
    assert not is_70r_placed_as_the_code_draws_it(
        [CLASS_A_LANE, ZONE_70R, ZONE_70R, CLASS_A_LANE]
    )

    assert is_70r_placed_as_the_code_draws_it([ZONE_70R])
    assert is_70r_placed_as_the_code_draws_it([CLASS_A_LANE, ZONE_70R])
    assert is_70r_placed_as_the_code_draws_it([CLASS_A_LANE, ZONE_70R, ZONE_70R])
    assert is_70r_placed_as_the_code_draws_it([ZONE_70R, CLASS_A_LANE, ZONE_70R])
    assert is_70r_placed_as_the_code_draws_it([ZONE_70R, CLASS_A_LANE, CLASS_A_LANE, ZONE_70R])


def test_lifting_the_rule_only_ever_adds_cases():
    for step in range(425, 2400, 5):
        carriageway_width_m = step / 100.0
        strict = {
            tuple(a.lane_pattern) for a in list_admissible_arrangements(carriageway_width_m)
        }
        open_ = {
            tuple(a.lane_pattern)
            for a in list_admissible_arrangements(
                carriageway_width_m, follow_combination_drawings=False
            )
        }
        assert strict <= open_


# Every band and every case of the standard combination document, as drawn.
# (Class A count, 70R count) for the cases that fill every design lane.
COMBINATION_DOCUMENT = [
    (4.25, 5.30, {(1, 0)}),
    (5.30, 9.60, {(2, 0), (0, 1)}),
    (9.60, 9.70, {(3, 0)}),
    (9.70, 13.10, {(3, 0), (1, 1)}),
    (13.10, 13.20, {(4, 0)}),
    (13.20, 14.50, {(4, 0), (2, 1)}),
    (14.50, 16.60, {(4, 0), (2, 1), (0, 2)}),
    (16.60, 16.70, {(5, 0)}),
    (16.70, 16.80, {(5, 0), (3, 1), (1, 2)}),
    (16.80, 20.10, {(5, 0), (3, 1), (1, 2)}),
    (20.10, 20.20, {(6, 0)}),
    (20.20, 20.30, {(6, 0), (4, 1), (2, 2)}),
    (20.30, 23.60, {(6, 0), (4, 1), (2, 2)}),
]


@pytest.mark.parametrize(("band_from_m", "band_to_m", "expected"), COMBINATION_DOCUMENT)
def test_matches_the_combination_document(band_from_m, band_to_m, expected):
    """The fully loaded cases must be exactly those the document draws."""
    from collections import Counter

    for carriageway_width_m in (band_from_m + 0.005, (band_from_m + band_to_m) / 2):
        counted = {
            (Counter(a.lane_pattern)[CLASS_A_LANE], Counter(a.lane_pattern)[ZONE_70R])
            for a in list_admissible_arrangements(carriageway_width_m)
            if a.is_fully_loaded
        }
        assert counted == expected, f"at {carriageway_width_m} m"


@pytest.mark.parametrize(
    ("carriageway_width_m", "pattern", "should_be_searched"),
    [
        # S.No.9 draws Class A + two 70R from 16.70 m, but the arrangement with
        # a Class A between the two 70R needs 16.80 m and only appears there.
        (16.75, (CLASS_A_LANE, ZONE_70R, ZONE_70R), True),
        (16.75, (ZONE_70R, CLASS_A_LANE, ZONE_70R), False),
        (16.85, (ZONE_70R, CLASS_A_LANE, ZONE_70R), True),
        # The same distinction again at six lanes, S.No.12 against S.No.13.
        (20.25, (CLASS_A_LANE, CLASS_A_LANE, ZONE_70R, ZONE_70R), True),
        (20.25, (ZONE_70R, CLASS_A_LANE, CLASS_A_LANE, ZONE_70R), False),
        (20.35, (ZONE_70R, CLASS_A_LANE, CLASS_A_LANE, ZONE_70R), True),
    ],
)
def test_the_document_distinguishes_orderings(
    carriageway_width_m, pattern, should_be_searched
):
    searched = {
        tuple(a.lane_pattern) for a in list_admissible_arrangements(carriageway_width_m)
    }
    assert (pattern in searched) is should_be_searched


def test_a_fully_loaded_case_uses_every_lane():
    for arrangement in list_admissible_arrangements(13.10):
        if arrangement.is_fully_loaded:
            assert arrangement.design_lanes == count_design_lanes(13.10)
