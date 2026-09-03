"""Girder section properties, against hand calculation."""


import pytest

from setu.models.bridge import PlateGirderSection, girder_properties

# The section from the worked example.
SECTION = PlateGirderSection(
    top_flange_width_m=0.550,
    top_flange_thickness_m=0.025,
    bottom_flange_width_m=0.650,
    bottom_flange_thickness_m=0.040,
    web_thickness_m=0.014,
    web_height_m=2.100,
)


def test_depth_is_the_three_plates_stacked():
    assert SECTION.depth_m == pytest.approx(0.025 + 2.100 + 0.040)


def test_area_is_the_three_plates_added_up():
    expected_m2 = 0.550 * 0.025 + 0.650 * 0.040 + 0.014 * 2.100
    assert girder_properties(SECTION).area_m2 == pytest.approx(expected_m2)


def test_the_neutral_axis_sits_below_mid_depth():
    """The bottom flange is the heavier of the two, so it pulls the axis down."""
    girder = girder_properties(SECTION)
    assert 0 < girder.neutral_axis_from_bottom_m < girder.depth_m / 2


def test_the_strong_axis_is_far_stiffer_than_the_weak_one():
    """A plate girder is deep and thin, which is the whole point of it.

    Getting these two the wrong way round once handed vertical bending to a
    stiffness 42 times too small.
    """
    girder = girder_properties(SECTION)
    assert girder.strong_axis_inertia_m4 > 40 * girder.weak_axis_inertia_m4


def test_the_weak_axis_needs_no_parallel_axis_term():
    """Sideways, every plate is already centred on the girder's own centreline."""
    expected_m4 = 0.025 * 0.550**3 / 12 + 0.040 * 0.650**3 / 12 + 2.100 * 0.014**3 / 12
    assert girder_properties(SECTION).weak_axis_inertia_m4 == pytest.approx(expected_m4)


def test_torsion_is_the_sum_of_the_plates():
    expected_m4 = (0.550 * 0.025**3 + 0.650 * 0.040**3 + 2.100 * 0.014**3) / 3
    assert girder_properties(SECTION).torsion_constant_m4 == pytest.approx(expected_m4)


def test_a_symmetric_section_has_its_axis_at_mid_depth():
    symmetric = PlateGirderSection(
        top_flange_width_m=0.5,
        top_flange_thickness_m=0.03,
        bottom_flange_width_m=0.5,
        bottom_flange_thickness_m=0.03,
        web_thickness_m=0.02,
        web_height_m=1.0,
    )
    girder = girder_properties(symmetric)
    assert girder.neutral_axis_from_bottom_m == pytest.approx(girder.depth_m / 2)
