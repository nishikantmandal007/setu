"""The standard vehicles, and what happens when one is turned round."""


import numpy as np
import pytest

from setu.errors import VehicleDefinitionError, VehicleNotFoundError
from setu.irc6.vehicles import (
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
from setu.helpers import DEFAULT_SAMPLING
from setu.irc6.wheel_loads import wheel_load_offsets


def test_class_a_is_the_tabulated_vehicle():
    assert CLASS_A.axle_loads_t == (2.7, 2.7, 11.4, 11.4, 6.8, 6.8, 6.8, 6.8)
    assert CLASS_A.total_load_t() == pytest.approx(55.4)
    assert CLASS_A.length_m() == pytest.approx(0.6 + 18.8 + 0.9)


def test_70r_wheeled_is_the_tabulated_vehicle():
    assert CLASS_70R_WHEELED.total_load_t() == pytest.approx(100.0)
    assert len(CLASS_70R_WHEELED.axle_positions_m()) == 7


def test_70r_wheel_lines_are_centred_on_their_tyre_groups():
    """IRC:6-2017 Fig. 1: 2.79 m over the tyres, 0.86 m tyre groups; 2.90 m over 0.84 m tracks."""
    assert CLASS_70R_WHEELED.transverse_gauge_m == pytest.approx(2.79 - 0.86)
    assert CLASS_70R_TRACKED.transverse_gauge_m == pytest.approx(2.90 - 0.84)


def test_every_axle_becomes_two_wheels():
    offsets = wheel_load_offsets(CLASS_A, 0.0, DEFAULT_SAMPLING)

    assert len(offsets) == 2 * len(CLASS_A.axle_loads_t)
    assert offsets[:, 2].sum() == pytest.approx(CLASS_A.total_load_t() * 9.81)


def test_a_tracked_vehicle_keeps_its_total_load_however_it_is_sampled():
    for wearing_course_m in (0.0, 0.075, 0.15):
        offsets = wheel_load_offsets(CLASS_70R_TRACKED, wearing_course_m, DEFAULT_SAMPLING)
        assert offsets[:, 2].sum() == pytest.approx(2 * 35.0 * 9.81)


def test_the_wearing_course_spreads_the_footprint_wider():
    """Clause 204.2: load disperses at 45 degrees on its way through surfacing."""
    bare = wheel_load_offsets(CLASS_70R_TRACKED, 0.0, DEFAULT_SAMPLING)
    through_surfacing = wheel_load_offsets(CLASS_70R_TRACKED, 0.075, DEFAULT_SAMPLING)

    assert np.ptp(through_surfacing[:, 0]) > np.ptp(bare[:, 0])
    assert np.ptp(through_surfacing[:, 1]) > np.ptp(bare[:, 1])


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
