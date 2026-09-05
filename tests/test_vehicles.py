"""The standard vehicles, and what happens when one is turned round."""


import numpy as np
import pytest

from setu.utils.errors import VehicleDefinitionError, VehicleNotFoundError
from setu.models.vehicles import (
    CLASS_70R_TRACKED,
    CLASS_70R_WHEELED,
    CLASS_A,
    IRC_VEHICLES,
    AxleVehicle,
    class_of,
    facing_backwards,
    find_vehicle,
    most_vehicles_that_fit,
    pitch_between_vehicles_m,
)
from setu.irc6 import (
    contact_patches_at,
    wheel_load_offsets,
    wheel_loads_at,
)


def test_class_a_is_the_tabulated_vehicle():
    assert CLASS_A.axle_loads_t == (2.7, 2.7, 11.4, 11.4, 6.8, 6.8, 6.8, 6.8)
    assert CLASS_A.total_load_t() == pytest.approx(55.4)
    assert CLASS_A.length_m() == pytest.approx(0.6 + 18.8 + 0.9)


def test_70r_wheeled_is_the_tabulated_vehicle():
    assert CLASS_70R_WHEELED.total_load_t() == pytest.approx(100.0)
    assert len(CLASS_70R_WHEELED.axle_positions_m()) == 7


def test_70r_tracked_spreads_its_load_over_its_tracks():
    expected_kpa = 35.0 * 9.81 / (4.57 * 0.84)
    assert CLASS_70R_TRACKED.contact_pressure_kpa() == pytest.approx(expected_kpa)


def test_every_axle_becomes_two_wheels():
    offsets = wheel_load_offsets(CLASS_A)

    assert len(offsets) == 2 * len(CLASS_A.axle_loads_t)
    assert offsets[:, 2].sum() == pytest.approx(CLASS_A.total_load_t() * 9.81)


def test_a_tracked_vehicle_keeps_its_total_load_however_it_is_sampled():
    for wearing_course_m in (0.0, 0.075, 0.15):
        offsets = wheel_load_offsets(CLASS_70R_TRACKED, wearing_course_m)
        assert offsets[:, 2].sum() == pytest.approx(2 * 35.0 * 9.81)


def test_the_wearing_course_spreads_the_footprint_wider():
    """Clause 204.2: load disperses at 45 degrees on its way through surfacing."""
    bare = wheel_load_offsets(CLASS_70R_TRACKED, 0.0)
    through_surfacing = wheel_load_offsets(CLASS_70R_TRACKED, 0.075)

    assert np.ptp(through_surfacing[:, 0]) > np.ptp(bare[:, 0])
    assert np.ptp(through_surfacing[:, 1]) > np.ptp(bare[:, 1])


def test_placing_a_vehicle_is_its_shape_plus_where_it_stands():
    offsets = wheel_load_offsets(CLASS_A)
    placed = wheel_loads_at(CLASS_A, x_front_m=7.25, z_centre_m=3.5)

    for (dx, dz, load), wheel in zip(offsets, placed, strict=True):
        assert wheel.x_m == pytest.approx(7.25 + dx)
        assert wheel.z_m == pytest.approx(3.5 + dz)
        assert wheel.load_kn == pytest.approx(load)


def test_a_tracked_vehicle_puts_down_two_patches():
    patches = contact_patches_at(CLASS_70R_TRACKED, x_front_m=0.0, z_centre_m=5.0)

    assert len(patches) == 2
    assert sum(patch.total_load_kn() for patch in patches) == pytest.approx(2 * 35.0 * 9.81)


def test_reversing_class_a_reverses_its_axles():
    """Clause 204.1.4 - and Class A is not symmetric, so this is a new load case."""
    backwards = facing_backwards(CLASS_A)

    assert backwards.axle_loads_t == tuple(reversed(CLASS_A.axle_loads_t))
    assert backwards.lead_clearance_m == CLASS_A.trail_clearance_m
    assert backwards.length_m() == pytest.approx(CLASS_A.length_m())
    assert backwards.total_load_t() == pytest.approx(CLASS_A.total_load_t())


def test_reversing_a_tracked_vehicle_changes_nothing():
    """A track is the same either way round."""
    assert facing_backwards(CLASS_70R_TRACKED) is CLASS_70R_TRACKED


def test_a_reversed_vehicle_is_still_its_own_class():
    """Which matters, because the impact factor is looked up by class."""
    assert class_of(facing_backwards(CLASS_A)) == "Class_A"


def test_the_pitch_is_a_whole_vehicle_plus_the_gap_behind_it():
    assert pitch_between_vehicles_m(CLASS_A) == pytest.approx(CLASS_A.length_m() + 18.5)


def test_how_many_vehicles_fit():
    pitch_m = pitch_between_vehicles_m(CLASS_A)

    assert most_vehicles_that_fit(CLASS_A, 0.0, pitch_m * 0.5) == 1
    assert most_vehicles_that_fit(CLASS_A, 0.0, pitch_m) == 2
    assert most_vehicles_that_fit(CLASS_A, 0.0, pitch_m * 2) == 3


def test_an_unknown_vehicle_says_what_it_does_know():
    with pytest.raises(VehicleNotFoundError, match="Class_A"):
        find_vehicle("Class_Z")


def test_axle_loads_and_spacings_have_to_agree():
    with pytest.raises(VehicleDefinitionError, match="spacings"):
        AxleVehicle(
            name="broken",
            axle_loads_t=(10, 10, 10),
            axle_spacing_m=(2.0,),
            transverse_gauge_m=1.8,
            lead_clearance_m=0.5,
            trail_clearance_m=0.5,
            min_nose_to_tail_m=18.5,
        )


def test_a_measurement_cannot_be_zero_or_negative():
    with pytest.raises(VehicleDefinitionError, match="greater than zero"):
        AxleVehicle(
            name="broken",
            axle_loads_t=(10, -10),
            axle_spacing_m=(2.0,),
            transverse_gauge_m=1.8,
            lead_clearance_m=0.5,
            trail_clearance_m=0.5,
            min_nose_to_tail_m=18.5,
        )


def test_the_registry_holds_the_three_standard_vehicles():
    assert set(IRC_VEHICLES) == {"Class_A", "Class_70R_Wheeled", "Class_70R_Tracked"}
    assert np.isfinite([v.total_load_t() for v in IRC_VEHICLES.values()] ).all()


def test_the_fatigue_and_special_vehicles_are_defined_but_not_placed():
    """Clause 204.6 and 204.5.1 - both exist, neither belongs in a lane arrangement.

    The special vehicle has Clause 204.5.3's own placement regime (alone on the
    carriageway, crawling, no impact) and the fatigue vehicle answers a different
    question, so neither may leak into the ordinary transverse search.
    """
    from setu.models.vehicles import (
        FATIGUE_VEHICLE,
        SPECIAL_VEHICLE,
        VEHICLES_ALLOWED_IN_BLOCK,
        VEHICLES_OUTSIDE_LANE_ARRANGEMENTS,
    )

    placeable = {name for names in VEHICLES_ALLOWED_IN_BLOCK.values() for name in names}

    assert FATIGUE_VEHICLE.name not in placeable
    assert SPECIAL_VEHICLE.name not in placeable
    assert set(VEHICLES_OUTSIDE_LANE_ARRANGEMENTS) == {"Fatigue_Vehicle", "Special_Vehicle"}
    assert set(IRC_VEHICLES).isdisjoint(VEHICLES_OUTSIDE_LANE_ARRANGEMENTS)


def test_the_special_vehicle_carries_what_clause_204_5_says():
    from setu.models.vehicles import SPECIAL_VEHICLE

    # One steering axle, two bogie axles, twenty trailer axles.
    assert len(SPECIAL_VEHICLE.axle_loads_t) == 23
    assert SPECIAL_VEHICLE.total_load_t() == pytest.approx(385.0)


def test_the_fatigue_vehicle_carries_what_clause_204_6_says():
    from setu.models.vehicles import FATIGUE_VEHICLE

    assert FATIGUE_VEHICLE.axle_loads_t == (12.0, 14.0, 14.0)
    assert FATIGUE_VEHICLE.total_load_t() == pytest.approx(40.0)
