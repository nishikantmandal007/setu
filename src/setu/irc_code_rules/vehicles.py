# Clause 204.1 - the standard IRC:6 vehicles. AxleVehicle carries its load on axles, two
# wheels per axle (Class A, Class 70R Wheeled); TrackedVehicle carries it on two continuous
# tracks, each pressing a rectangular contact patch onto the deck (Class 70R Tracked). Every
# dimension is geometric - measured from the vehicle's own front and centreline - so a
# definition says nothing about any particular bridge. Axle loads are tabulated in tonnes,
# as the code tabulates them, and become kilonewtons only when they are turned into loads.

from __future__ import annotations

from dataclasses import dataclass, replace

from ..errors import VehicleDefinitionError, VehicleNotFoundError
from .code_tables import GRAVITY_KN_PER_TONNE

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def check_axle_and_spacing_counts_match(vehicle: AxleVehicle) -> None:
    axles = len(vehicle.axle_loads_t)
    spacings = len(vehicle.axle_spacing_m)

    if axles != spacings + 1:
        raise VehicleDefinitionError(
            f"{vehicle.name}: {axles} axle loads need {axles - 1} spacings between "
            f"them, but {spacings} were given"
        )


def check_all_measurements_positive(vehicle: Vehicle) -> None:
    common = {
        "transverse_gauge_m": vehicle.transverse_gauge_m,
        "min_nose_to_tail_m": vehicle.min_nose_to_tail_m,
    }

    if isinstance(vehicle, AxleVehicle):
        specific = {
            f"axle_loads_t[{index}]": load
            for index, load in enumerate(vehicle.axle_loads_t)
        }
        specific |= {
            f"axle_spacing_m[{index}]": gap
            for index, gap in enumerate(vehicle.axle_spacing_m)
        }
    else:
        specific = {
            "load_per_track_t": vehicle.load_per_track_t,
            "track_length_m": vehicle.track_length_m,
            "track_width_m": vehicle.track_width_m,
        }

    for description, value in (common | specific).items():
        if value <= 0:
            raise VehicleDefinitionError(
                f"{vehicle.name}: {description} must be greater than zero, got {value}"
            )


@dataclass(frozen=True)
class AxleVehicle:
    # A vehicle whose load sits on axles - Class A, Class 70R Wheeled.
    name: str
    axle_loads_t: tuple[float, ...]

    # Gaps between consecutive axles, so one fewer than there are axles.
    axle_spacing_m: tuple[float, ...]

    # Wheel centreline to wheel centreline, across the vehicle.
    transverse_gauge_m: float

    # Front of the vehicle to its first axle.
    lead_clearance_m: float

    # Last axle to the back of the vehicle.
    trail_clearance_m: float

    # Smallest gap the code allows between this vehicle and the next one behind.
    min_nose_to_tail_m: float

    overall_width_m: float | None = None

    def __post_init__(self) -> None:
        check_axle_and_spacing_counts_match(self)
        check_all_measurements_positive(self)

    @property
    def length_m(self) -> float:
        # Front bumper to rear bumper, not axle to axle.
        return self.lead_clearance_m + sum(self.axle_spacing_m) + self.trail_clearance_m

    @property
    def axle_positions_m(self) -> tuple[float, ...]:
        # Each axle's distance behind the first one.
        positions = [0.0]
        for spacing_m in self.axle_spacing_m:
            positions.append(positions[-1] + spacing_m)
        return tuple(positions)

    @property
    def total_load_t(self) -> float:
        return sum(self.axle_loads_t)


@dataclass(frozen=True)
class TrackedVehicle:
    # A vehicle whose load sits on two continuous tracks - Class 70R Tracked.
    name: str
    load_per_track_t: float
    track_length_m: float
    track_width_m: float

    # Track centreline to track centreline, across the vehicle.
    transverse_gauge_m: float

    min_nose_to_tail_m: float
    lead_clearance_m: float = 0.0
    trail_clearance_m: float = 0.0

    def __post_init__(self) -> None:
        check_all_measurements_positive(self)

    @property
    def length_m(self) -> float:
        # For a tracked vehicle, overall length is the track itself.
        return self.track_length_m

    @property
    def contact_pressure_kpa(self) -> float:
        # Load per track spread evenly over that track's contact patch.
        load_kn = self.load_per_track_t * GRAVITY_KN_PER_TONNE
        return load_kn / (self.track_length_m * self.track_width_m)

    @property
    def total_load_t(self) -> float:
        return 2.0 * self.load_per_track_t


Vehicle = AxleVehicle | TrackedVehicle


# ---------------------------------------------------------------------------
# The standard vehicles
# ---------------------------------------------------------------------------

CLASS_70R_WHEELED = AxleVehicle(
    name="Class_70R_Wheeled",
    axle_loads_t=(8, 12, 12, 17, 17, 17, 17),
    axle_spacing_m=(3.95, 1.52, 2.13, 1.37, 3.05, 1.37),
    transverse_gauge_m=2.06,
    lead_clearance_m=0.81,
    trail_clearance_m=0.91,
    # Figure 1 note 1 measures the gap between 70R vehicles axle to axle, at
    # 30 m. Taking the body length back out of that leaves 28.28 m nose to tail.
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
    # Figure 2 note 1 measures the gap between Class A vehicles nose to tail.
    min_nose_to_tail_m=18.5,
    overall_width_m=2.3,
)

IRC_VEHICLES: dict[str, Vehicle] = {
    vehicle.name: vehicle for vehicle in (CLASS_70R_WHEELED, CLASS_70R_TRACKED, CLASS_A)
}


# ---------------------------------------------------------------------------
# Which vehicles may fill which kind of lane block
# ---------------------------------------------------------------------------

# Table 6A note (a): a 70R zone may hold either 70R vehicle, so both are tried and
# whichever is worse for the response being checked is the one that governs.
VEHICLES_ALLOWED_IN_BLOCK: dict[str, tuple[str, ...]] = {
    "class_a": ("Class_A",),
    "zone_70r": ("Class_70R_Wheeled", "Class_70R_Tracked"),
}

# Marks a vehicle turned round to drive the other way - Clause 204.1.4 lets it, and the
# two directions are genuinely different load cases.
REVERSED_SUFFIX = "_reversed"


def class_of(vehicle: Vehicle) -> str:
    # A reversed Class A is still a Class A as far as the code is concerned, so this is
    # the name to use when looking anything up in a code table.
    return vehicle.name.removesuffix(REVERSED_SUFFIX)


def find_vehicle(name: str, vehicles: dict[str, Vehicle] | None = None) -> Vehicle:
    known = IRC_VEHICLES if vehicles is None else vehicles

    if name not in known:
        raise VehicleNotFoundError(
            f"no vehicle named {name!r}; known vehicles are {sorted(known)}"
        )
    return known[name]


def register_vehicle(vehicle: Vehicle, vehicles: dict[str, Vehicle] | None = None) -> None:
    # The way to bring in a permit vehicle or a special vehicle without changing setu
    # itself. Mutates the module-global IRC_VEHICLES by default, which is easy to miss.
    known = IRC_VEHICLES if vehicles is None else vehicles
    known[vehicle.name] = vehicle


def facing_backwards(vehicle: Vehicle) -> Vehicle:
    # Clause 204.1.4 lets a vehicle head in either direction. Class A is not symmetric
    # front to back - its heavy axles sit forward - so the reversed vehicle is a
    # genuinely different load case, not a mirror image of one already checked.
    if isinstance(vehicle, TrackedVehicle):
        return vehicle  # a track is symmetric, so reversing it changes nothing

    return replace(
        vehicle,
        name=f"{vehicle.name}{REVERSED_SUFFIX}",
        axle_loads_t=tuple(reversed(vehicle.axle_loads_t)),
        axle_spacing_m=tuple(reversed(vehicle.axle_spacing_m)),
        lead_clearance_m=vehicle.trail_clearance_m,
        trail_clearance_m=vehicle.lead_clearance_m,
    )


def vehicles_allowed_in_each_block(
    vehicles: dict[str, Vehicle] | None, allow_reversed_vehicles: bool
) -> dict[str, list[Vehicle]]:
    # Clause 204.1.4 lets a vehicle drive in either direction, so a vehicle that is not
    # symmetric front to back is added twice, once facing each way - the two are different
    # load cases. Table 6A note (a) is why a zone_70r block gets both 70R vehicles, above.
    known = IRC_VEHICLES if vehicles is None else vehicles

    permitted: dict[str, list[Vehicle]] = {}
    for block, names in VEHICLES_ALLOWED_IN_BLOCK.items():
        choices = []
        for name in names:
            if name not in known:
                continue
            vehicle = find_vehicle(name, known)
            choices.append(vehicle)

            if allow_reversed_vehicles:
                reversed_vehicle = facing_backwards(vehicle)
                if reversed_vehicle is not vehicle:
                    choices.append(reversed_vehicle)

        if not choices:
            raise ValueError(
                f"no vehicle available for a {block!r} lane block; "
                f"expected one of {list(names)} among {sorted(known)}"
            )
        permitted[block] = choices

    return permitted


def pitch_between_vehicles_m(vehicle: Vehicle) -> float:
    # Front-to-front spacing in a train of these vehicles: one whole vehicle plus the
    # smallest gap the code allows behind it.
    return vehicle.length_m + vehicle.min_nose_to_tail_m


def most_vehicles_that_fit(vehicle: Vehicle, from_m: float, to_m: float) -> int:
    pitch_m = pitch_between_vehicles_m(vehicle)
    return max(1, int((to_m - from_m) // pitch_m) + 1)
