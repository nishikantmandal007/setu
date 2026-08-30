from __future__ import annotations

from dataclasses import dataclass, replace

from ..errors import VehicleDefinitionError, VehicleNotFoundError
from .code_tables import GRAVITY_KN_PER_TONNE


def check_axle_and_spacing_counts_match(vehicle: AxleVehicle) -> None:
    axles = len(vehicle.axle_loads_t)
    spacings = len(vehicle.axle_spacing_m)

    if axles != spacings + 1:
        raise VehicleDefinitionError(
            f"{vehicle.name}: {axles} axle loads need {axles - 1} spacings between "
            f"them, but {spacings} were given"
        )


def every_measurement_of(vehicle: Vehicle) -> list[tuple[str, float]]:
    measurements = [
        ("transverse_gauge_m", vehicle.transverse_gauge_m),
        ("min_nose_to_tail_m", vehicle.min_nose_to_tail_m),
    ]

    if isinstance(vehicle, AxleVehicle):
        for index, axle_load_t in enumerate(vehicle.axle_loads_t):
            measurements.append((f"axle_loads_t[{index}]", axle_load_t))
        for index, spacing_m in enumerate(vehicle.axle_spacing_m):
            measurements.append((f"axle_spacing_m[{index}]", spacing_m))
    else:
        measurements.append(("load_per_track_t", vehicle.load_per_track_t))
        measurements.append(("track_length_m", vehicle.track_length_m))
        measurements.append(("track_width_m", vehicle.track_width_m))

    return measurements


def check_all_measurements_positive(vehicle: Vehicle) -> None:
    for description, value in every_measurement_of(vehicle):
        if value <= 0:
            raise VehicleDefinitionError(
                f"{vehicle.name}: {description} must be greater than zero, got {value}"
            )


@dataclass(frozen=True)
class AxleVehicle:
    name: str
    axle_loads_t: tuple[float, ...]
    axle_spacing_m: tuple[float, ...]
    transverse_gauge_m: float
    lead_clearance_m: float
    trail_clearance_m: float
    min_nose_to_tail_m: float
    overall_width_m: float | None = None

    def __post_init__(self) -> None:
        check_axle_and_spacing_counts_match(self)
        check_all_measurements_positive(self)

    @property
    def length_m(self) -> float:
        return self.lead_clearance_m + sum(self.axle_spacing_m) + self.trail_clearance_m

    @property
    def axle_positions_m(self) -> tuple[float, ...]:
        behind_the_first_axle_m = [0.0]
        for spacing_m in self.axle_spacing_m:
            behind_the_first_axle_m.append(behind_the_first_axle_m[-1] + spacing_m)
        return tuple(behind_the_first_axle_m)

    @property
    def total_load_t(self) -> float:
        return sum(self.axle_loads_t)


@dataclass(frozen=True)
class TrackedVehicle:
    name: str
    load_per_track_t: float
    track_length_m: float
    track_width_m: float
    transverse_gauge_m: float
    min_nose_to_tail_m: float
    lead_clearance_m: float = 0.0
    trail_clearance_m: float = 0.0

    def __post_init__(self) -> None:
        check_all_measurements_positive(self)

    @property
    def length_m(self) -> float:
        return self.track_length_m

    @property
    def contact_pressure_kpa(self) -> float:
        load_kn = self.load_per_track_t * GRAVITY_KN_PER_TONNE
        contact_area_m2 = self.track_length_m * self.track_width_m
        return load_kn / contact_area_m2

    @property
    def total_load_t(self) -> float:
        return 2.0 * self.load_per_track_t


Vehicle = AxleVehicle | TrackedVehicle


# Clause 204.1, with the nose-to-tail gaps from Figure 1 note 1 and Figure 2 note 1.

CLASS_70R_WHEELED = AxleVehicle(
    name="Class_70R_Wheeled",
    axle_loads_t=(8, 12, 12, 17, 17, 17, 17),
    axle_spacing_m=(3.96, 1.52, 2.13, 1.37, 3.05, 1.37),
    transverse_gauge_m=2.06,
    lead_clearance_m=0.81,
    trail_clearance_m=0.91,
    min_nose_to_tail_m=28.28,
)

CLASS_70R_TRACKED = TrackedVehicle(
    name="Class_70R_Tracked",
    load_per_track_t=35.0,
    track_length_m=4.57,
    track_width_m=0.84,
    transverse_gauge_m=2.06,
    min_nose_to_tail_m=90.0,
)

CLASS_A = AxleVehicle(
    name="Class_A",
    axle_loads_t=(2.7, 2.7, 11.4, 11.4, 6.8, 6.8, 6.8, 6.8),
    axle_spacing_m=(1.1, 3.2, 1.2, 4.3, 3.0, 3.0, 3.0),
    transverse_gauge_m=1.8,
    lead_clearance_m=0.6,
    trail_clearance_m=0.9,
    min_nose_to_tail_m=18.5,
    overall_width_m=2.3,
)

IRC_VEHICLES: dict[str, Vehicle] = {
    vehicle.name: vehicle for vehicle in (CLASS_70R_WHEELED, CLASS_70R_TRACKED, CLASS_A)
}


# A gap wider than any span setu will see, so a train of these can never form by accident.
NEVER_FORMS_A_TRAIN_M = 1000.0

# Clause 204.6 - checked on its own, not as part of a lane arrangement.
FATIGUE_VEHICLE = AxleVehicle(
    name="Fatigue_Vehicle",
    axle_loads_t=(12.0, 14.0, 14.0),
    axle_spacing_m=(4.50, 1.40),
    transverse_gauge_m=1.68,
    lead_clearance_m=0.0,
    trail_clearance_m=0.0,
    min_nose_to_tail_m=NEVER_FORMS_A_TRAIN_M,
)

# Clause 204.5.1 - a prime mover and a twenty-axle trailer, 385 t in all. Clause 204.5.3
# gives it a placement regime of its own, which setu does not implement yet.
SPECIAL_VEHICLE = AxleVehicle(
    name="Special_Vehicle",
    axle_loads_t=(6.0, 9.5, 9.5) + (18.0,) * 20,
    axle_spacing_m=(3.200, 1.370, 5.389) + (1.500,) * 19,
    transverse_gauge_m=1.8,
    lead_clearance_m=0.0,
    trail_clearance_m=0.0,
    min_nose_to_tail_m=NEVER_FORMS_A_TRAIN_M,
)

VEHICLES_OUTSIDE_LANE_ARRANGEMENTS: dict[str, Vehicle] = {
    vehicle.name: vehicle for vehicle in (FATIGUE_VEHICLE, SPECIAL_VEHICLE)
}


# Table 6A note (a): a 70R zone may hold either 70R vehicle, so both are tried.
VEHICLES_ALLOWED_IN_BLOCK: dict[str, tuple[str, ...]] = {
    "class_a": ("Class_A",),
    "zone_70r": ("Class_70R_Wheeled", "Class_70R_Tracked"),
}

REVERSED_SUFFIX = "_reversed"


def class_of(vehicle: Vehicle) -> str:
    return vehicle.name.removesuffix(REVERSED_SUFFIX)


def find_vehicle(name: str, vehicles: dict[str, Vehicle] | None = None) -> Vehicle:
    known = IRC_VEHICLES if vehicles is None else vehicles

    if name not in known:
        raise VehicleNotFoundError(
            f"no vehicle named {name!r}; known vehicles are {sorted(known)}"
        )
    return known[name]


def register_vehicle(vehicle: Vehicle, vehicles: dict[str, Vehicle] | None = None) -> None:
    known = IRC_VEHICLES if vehicles is None else vehicles
    known[vehicle.name] = vehicle


def facing_backwards(vehicle: Vehicle) -> Vehicle:
    # Clause 204.1.4. A track is symmetric, so reversing it changes nothing.
    if isinstance(vehicle, TrackedVehicle):
        return vehicle

    return replace(
        vehicle,
        name=f"{vehicle.name}{REVERSED_SUFFIX}",
        axle_loads_t=tuple(reversed(vehicle.axle_loads_t)),
        axle_spacing_m=tuple(reversed(vehicle.axle_spacing_m)),
        lead_clearance_m=vehicle.trail_clearance_m,
        trail_clearance_m=vehicle.lead_clearance_m,
    )


def find_vehicle_or_its_reverse(name: str) -> Vehicle:
    if name in IRC_VEHICLES:
        return IRC_VEHICLES[name]

    facing_forwards = name.removesuffix(REVERSED_SUFFIX)
    if facing_forwards in IRC_VEHICLES:
        return facing_backwards(IRC_VEHICLES[facing_forwards])

    return find_vehicle(name)


def both_directions_of(vehicle: Vehicle, allow_reversed_vehicles: bool) -> list[Vehicle]:
    if not allow_reversed_vehicles:
        return [vehicle]

    reversed_vehicle = facing_backwards(vehicle)
    if reversed_vehicle is vehicle:
        return [vehicle]
    return [vehicle, reversed_vehicle]


def vehicles_allowed_in_each_block(
    vehicles: dict[str, Vehicle] | None, allow_reversed_vehicles: bool
) -> dict[str, list[Vehicle]]:
    known = IRC_VEHICLES if vehicles is None else vehicles
    permitted: dict[str, list[Vehicle]] = {}

    for block, names in VEHICLES_ALLOWED_IN_BLOCK.items():
        choices = []
        for name in names:
            if name not in known:
                continue
            vehicle = find_vehicle(name, known)
            choices.extend(both_directions_of(vehicle, allow_reversed_vehicles))

        if not choices:
            raise ValueError(
                f"no vehicle available for a {block!r} lane block; "
                f"expected one of {list(names)} among {sorted(known)}"
            )
        permitted[block] = choices

    return permitted


def pitch_between_vehicles_m(vehicle: Vehicle) -> float:
    return vehicle.length_m + vehicle.min_nose_to_tail_m


def most_vehicles_that_fit(vehicle: Vehicle, from_m: float, to_m: float) -> int:
    pitch_m = pitch_between_vehicles_m(vehicle)
    return max(1, int((to_m - from_m) // pitch_m) + 1)
