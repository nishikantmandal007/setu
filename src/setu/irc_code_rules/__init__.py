"""The IRC:6-2017 rules: which vehicles exist, how they may be arranged, and what
the code adds on top. Nothing in here knows anything about finite elements."""

from .carriageway_udl import footway_response, needs_residual_udl, response_to_area_load
from .code_tables import GRAVITY_KN_PER_TONNE, TOLERANCE_M
from .impact_factor import impact_factor, impact_fraction
from .lane_arrangements import (
    CLASS_A_LANE,
    ZONE_70R,
    LaneArrangement,
    count_design_lanes,
    fit_blocks_between,
    list_admissible_arrangements,
)
from .lane_reduction import lane_reduction_factor
from .vehicles import (
    CLASS_70R_TRACKED,
    CLASS_70R_WHEELED,
    CLASS_A,
    IRC_VEHICLES,
    AxleVehicle,
    TrackedVehicle,
    Vehicle,
    facing_backwards,
    find_vehicle,
    most_vehicles_that_fit,
    pitch_between_vehicles_m,
    register_vehicle,
)
from .wheel_loads import (
    ContactPatch,
    LaneAssignment,
    WheelLoad,
    contact_patches_at,
    loads_for_lanes,
    train_at,
    wheel_load_offsets,
    wheel_loads_at,
)

__all__ = [
    "CLASS_70R_TRACKED",
    "CLASS_70R_WHEELED",
    "CLASS_A",
    "CLASS_A_LANE",
    "GRAVITY_KN_PER_TONNE",
    "IRC_VEHICLES",
    "TOLERANCE_M",
    "ZONE_70R",
    "AxleVehicle",
    "ContactPatch",
    "LaneArrangement",
    "LaneAssignment",
    "TrackedVehicle",
    "Vehicle",
    "WheelLoad",
    "contact_patches_at",
    "count_design_lanes",
    "facing_backwards",
    "find_vehicle",
    "fit_blocks_between",
    "footway_response",
    "impact_factor",
    "impact_fraction",
    "lane_reduction_factor",
    "list_admissible_arrangements",
    "loads_for_lanes",
    "most_vehicles_that_fit",
    "needs_residual_udl",
    "pitch_between_vehicles_m",
    "register_vehicle",
    "response_to_area_load",
    "train_at",
    "wheel_load_offsets",
    "wheel_loads_at",
]
