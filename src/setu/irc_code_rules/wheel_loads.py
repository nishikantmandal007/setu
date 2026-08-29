# Turning a vehicle into the loads it puts on a deck: wheel_load_offsets gives the shape of
# a vehicle's loads relative to its own datum - the front of the vehicle, on its centreline
# - for the searches that slide one vehicle over thousands of positions; wheel_loads_at and
# friends place that shape absolutely, for reporting a result or applying it to the model. A
# placed load is always an offset plus the datum.

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..sampling import DEFAULT_SAMPLING, SamplingSettings
from .code_tables import GRAVITY_KN_PER_TONNE
from .vehicles import AxleVehicle, TrackedVehicle, Vehicle, pitch_between_vehicles_m

# ---------------------------------------------------------------------------
# Loads On The Deck
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WheelLoad:
    # One concentrated load sitting somewhere on the deck.
    x_m: float  # along the span
    z_m: float  # across the deck width
    load_kn: float


@dataclass(frozen=True)
class ContactPatch:
    # One rectangle of uniform pressure - a tracked vehicle's footprint.
    x_from_m: float
    x_to_m: float
    z_from_m: float
    z_to_m: float
    pressure_kpa: float

    @property
    def total_load_kn(self) -> float:
        return self.pressure_kpa * (self.x_to_m - self.x_from_m) * (self.z_to_m - self.z_from_m)


@dataclass(frozen=True)
class LaneAssignment:
    # One lane's worth of traffic: which vehicle, where, and how many of them.
    vehicle: Vehicle
    x_front_m: float
    z_centre_m: float
    how_many: int = 1
    gap_m: float | None = None  # nose-to-tail gap; None means the smallest the code allows


# ---------------------------------------------------------------------------
# Columns Of The Offsets Array
# ---------------------------------------------------------------------------

# Columns of the offsets array returned by wheel_load_offsets: distance along the span
# from the vehicle's front, distance across the width from its centreline, and the load
# in kilonewtons.
OFFSET_DX_M = 0
OFFSET_DZ_M = 1
OFFSET_LOAD_KN = 2


def split_offsets(offsets: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # dx along the span, dz across the width, load in kN
    return offsets[:, OFFSET_DX_M], offsets[:, OFFSET_DZ_M], offsets[:, OFFSET_LOAD_KN]


# ---------------------------------------------------------------------------
# The Shape Of A Vehicle's Loads
# ---------------------------------------------------------------------------


def wheel_load_offsets(
    vehicle: Vehicle,
    wearing_course_thickness_m: float = 0.0,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
) -> np.ndarray:
    # An (n, 3) array of offsets from the vehicle datum - the front of the vehicle, on its
    # centreline. See OFFSET_DX_M, OFFSET_DZ_M and OFFSET_LOAD_KN for the columns.
    if isinstance(vehicle, TrackedVehicle):
        return offsets_for_tracks(vehicle, wearing_course_thickness_m, sampling)
    return offsets_for_axles(vehicle)


def offsets_for_axles(vehicle: AxleVehicle) -> np.ndarray:
    # Each axle load splits into two wheels, half the gauge either side of the centreline.
    half_gauge_m = vehicle.transverse_gauge_m / 2.0

    offsets = []
    for axle_load_t, dx_m in zip(vehicle.axle_loads_t, vehicle.axle_positions_m, strict=True):
        wheel_load_kn = axle_load_t * GRAVITY_KN_PER_TONNE / 2.0
        offsets.append((dx_m, -half_gauge_m, wheel_load_kn))
        offsets.append((dx_m, +half_gauge_m, wheel_load_kn))

    return np.array(offsets, float)


def offsets_for_tracks(
    vehicle: TrackedVehicle,
    wearing_course_thickness_m: float,
    sampling: SamplingSettings,
) -> np.ndarray:
    # Each track's contact patch is spread into an even grid of point loads, whose density
    # comes from SamplingSettings. Clause 204.2 disperses a load through the wearing course
    # at 45 degrees on its way down, so the footprint grows by the surfacing thickness on
    # every side; the total load is unchanged, only spread over a larger area.
    length_m = vehicle.track_length_m + 2.0 * wearing_course_thickness_m
    width_m = vehicle.track_width_m + 2.0 * wearing_course_thickness_m

    steps_along = sampling.patch_steps_along_span
    steps_across = sampling.patch_steps_across_width
    load_per_point_kn = (
        vehicle.load_per_track_t * GRAVITY_KN_PER_TONNE / (steps_along * steps_across)
    )

    dx_m = (np.arange(steps_along) + 0.5) * length_m / steps_along
    dz_m = (np.arange(steps_across) + 0.5) * width_m / steps_across - width_m / 2.0
    half_gauge_m = vehicle.transverse_gauge_m / 2.0

    # side in (-1, +1): the two tracks, either side of the vehicle's centreline. Nested in
    # this order - side, then along, then across - so the row order matches exactly.
    offsets = [
        (along_m, side * half_gauge_m + across_m, load_per_point_kn)
        for side in (-1, +1)
        for along_m in dx_m
        for across_m in dz_m
    ]

    return np.array(offsets, float)


# ---------------------------------------------------------------------------
# Placing A Vehicle On The Deck
# ---------------------------------------------------------------------------


def wheel_loads_at(
    vehicle: Vehicle,
    x_front_m: float,
    z_centre_m: float,
    wearing_course_thickness_m: float = 0.0,
) -> list[WheelLoad]:
    # The wheel loads of one vehicle placed with its front at x_front_m.
    offsets = wheel_load_offsets(vehicle, wearing_course_thickness_m)

    return [
        WheelLoad(x_m=x_front_m + dx_m, z_m=z_centre_m + dz_m, load_kn=load_kn)
        for dx_m, dz_m, load_kn in offsets
    ]


def contact_patches_at(
    vehicle: TrackedVehicle, x_front_m: float, z_centre_m: float
) -> list[ContactPatch]:
    # The two rectangular footprints of a tracked vehicle placed here.
    half_gauge_m = vehicle.transverse_gauge_m / 2.0
    half_track_m = vehicle.track_width_m / 2.0
    pressure_kpa = vehicle.contact_pressure_kpa

    patches = []
    for side in (-1, +1):  # the two tracks, either side of the vehicle's centreline
        track_centre_m = z_centre_m + side * half_gauge_m
        patches.append(
            ContactPatch(
                x_from_m=x_front_m,
                x_to_m=x_front_m + vehicle.track_length_m,
                z_from_m=track_centre_m - half_track_m,
                z_to_m=track_centre_m + half_track_m,
                pressure_kpa=pressure_kpa,
            )
        )

    return patches


# ---------------------------------------------------------------------------
# Trains And Multi-Lane Load Cases
# ---------------------------------------------------------------------------


def train_at(
    vehicle: Vehicle,
    x_front_of_leader_m: float,
    z_centre_m: float,
    how_many: int = 1,
    gap_m: float | None = None,
) -> tuple[list[WheelLoad], list[ContactPatch]]:
    # The loads of several of the same vehicle, nose to tail in one lane.
    if gap_m is None:
        gap_m = vehicle.min_nose_to_tail_m

    pitch_m = vehicle.length_m + gap_m
    wheel_loads: list[WheelLoad] = []
    patches: list[ContactPatch] = []

    for position_in_train in range(how_many):
        x_front_m = x_front_of_leader_m + position_in_train * pitch_m

        if isinstance(vehicle, TrackedVehicle):
            patches.extend(contact_patches_at(vehicle, x_front_m, z_centre_m))
        else:
            wheel_loads.extend(wheel_loads_at(vehicle, x_front_m, z_centre_m))

    return wheel_loads, patches


def loads_for_lanes(
    lanes: list[LaneAssignment],
) -> tuple[list[WheelLoad], list[ContactPatch]]:
    # Every lane at once, one complete load case - Class A in one lane and a 70R in another,
    # present on the deck together, as Table 6A intends.
    all_wheel_loads: list[WheelLoad] = []
    all_patches: list[ContactPatch] = []

    for lane in lanes:
        wheel_loads, patches = train_at(
            lane.vehicle, lane.x_front_m, lane.z_centre_m, lane.how_many, lane.gap_m
        )
        all_wheel_loads.extend(wheel_loads)
        all_patches.extend(patches)

    return all_wheel_loads, all_patches


__all__ = [
    "OFFSET_DX_M",
    "OFFSET_DZ_M",
    "OFFSET_LOAD_KN",
    "ContactPatch",
    "LaneAssignment",
    "WheelLoad",
    "contact_patches_at",
    "loads_for_lanes",
    "pitch_between_vehicles_m",
    "split_offsets",
    "train_at",
    "wheel_load_offsets",
    "wheel_loads_at",
]
