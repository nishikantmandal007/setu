from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..sampling import DEFAULT_SAMPLING, SamplingSettings
from .code_tables import GRAVITY_KN_PER_TONNE
from .vehicles import AxleVehicle, TrackedVehicle, Vehicle, pitch_between_vehicles_m

LEFT_OF_THE_CENTRELINE = -1
RIGHT_OF_THE_CENTRELINE = +1
BOTH_SIDES = (LEFT_OF_THE_CENTRELINE, RIGHT_OF_THE_CENTRELINE)

WHEELS_PER_AXLE = 2

# Columns of the array wheel_load_offsets returns.
OFFSET_DX_M = 0
OFFSET_DZ_M = 1
OFFSET_LOAD_KN = 2


@dataclass(frozen=True)
class WheelLoad:
    x_m: float
    z_m: float
    load_kn: float


@dataclass(frozen=True)
class ContactPatch:
    x_from_m: float
    x_to_m: float
    z_from_m: float
    z_to_m: float
    pressure_kpa: float

    @property
    def total_load_kn(self) -> float:
        length_m = self.x_to_m - self.x_from_m
        width_m = self.z_to_m - self.z_from_m
        return self.pressure_kpa * length_m * width_m


@dataclass(frozen=True)
class LaneAssignment:
    vehicle: Vehicle
    x_front_m: float
    z_centre_m: float
    how_many: int = 1
    gap_m: float | None = None


def split_offsets(offsets: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return offsets[:, OFFSET_DX_M], offsets[:, OFFSET_DZ_M], offsets[:, OFFSET_LOAD_KN]


def wheel_load_offsets(
    vehicle: Vehicle,
    wearing_course_thickness_m: float = 0.0,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
) -> np.ndarray:
    # Offsets from the vehicle datum: the front of the vehicle, on its centreline.
    if isinstance(vehicle, TrackedVehicle):
        return offsets_for_tracks(vehicle, wearing_course_thickness_m, sampling)
    return offsets_for_axles(vehicle)


def offsets_for_axles(vehicle: AxleVehicle) -> np.ndarray:
    half_gauge_m = vehicle.transverse_gauge_m / 2.0

    offsets = []
    axles = zip(vehicle.axle_loads_t, vehicle.axle_positions_m, strict=True)
    for axle_load_t, dx_m in axles:
        wheel_load_kn = axle_load_t * GRAVITY_KN_PER_TONNE / WHEELS_PER_AXLE
        for side in BOTH_SIDES:
            offsets.append((dx_m, side * half_gauge_m, wheel_load_kn))

    return np.array(offsets, float)


def offsets_for_tracks(
    vehicle: TrackedVehicle,
    wearing_course_thickness_m: float,
    sampling: SamplingSettings,
) -> np.ndarray:
    # Clause 204.2 disperses the load at 45 degrees through the wearing course, so the
    # footprint grows by the surfacing thickness on every side and the total is unchanged.
    length_m = vehicle.track_length_m + 2.0 * wearing_course_thickness_m
    width_m = vehicle.track_width_m + 2.0 * wearing_course_thickness_m

    steps_along = sampling.point_loads_along_a_track
    steps_across = sampling.point_loads_across_a_track
    points_per_track = steps_along * steps_across
    load_per_point_kn = vehicle.load_per_track_t * GRAVITY_KN_PER_TONNE / points_per_track

    dx_m = (np.arange(steps_along) + 0.5) * length_m / steps_along
    dz_m = (np.arange(steps_across) + 0.5) * width_m / steps_across - width_m / 2.0
    half_gauge_m = vehicle.transverse_gauge_m / 2.0

    offsets = [
        (along_m, side * half_gauge_m + across_m, load_per_point_kn)
        for side in BOTH_SIDES
        for along_m in dx_m
        for across_m in dz_m
    ]

    return np.array(offsets, float)


def wheel_loads_at(
    vehicle: Vehicle,
    x_front_m: float,
    z_centre_m: float,
    wearing_course_thickness_m: float = 0.0,
) -> list[WheelLoad]:
    offsets = wheel_load_offsets(vehicle, wearing_course_thickness_m)

    return [
        WheelLoad(x_m=x_front_m + dx_m, z_m=z_centre_m + dz_m, load_kn=load_kn)
        for dx_m, dz_m, load_kn in offsets
    ]


def contact_patches_at(
    vehicle: TrackedVehicle, x_front_m: float, z_centre_m: float
) -> list[ContactPatch]:
    half_gauge_m = vehicle.transverse_gauge_m / 2.0
    half_track_m = vehicle.track_width_m / 2.0
    pressure_kpa = vehicle.contact_pressure_kpa

    patches = []
    for side in BOTH_SIDES:
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


def train_at(
    vehicle: Vehicle,
    x_front_of_leader_m: float,
    z_centre_m: float,
    how_many: int = 1,
    gap_m: float | None = None,
) -> tuple[list[WheelLoad], list[ContactPatch]]:
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
