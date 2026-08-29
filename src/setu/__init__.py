# setu - the worst legal IRC:6 vehicle position on a bridge deck.
#
# Finding where traffic does the most damage normally means moving the vehicles,
# analysing, moving them again, and analysing again - tens of thousands of times. setu
# does it with one analysis per response quantity, and gets the exact answer rather than
# the best of whatever positions happened to be tried.
#
# Two ideas do the work. An influence surface, built by solving the model once with the
# response applied as an imaginary load, gives the effect of a unit load at every point of
# the deck - after that a vehicle position costs an interpolation instead of an analysis.
# Then two dynamic programs find the worst position the code actually allows: one along
# the span for the worst train of vehicles in a lane, one across the width for the worst
# arrangement of vehicles in every lane at once.
#
#     from setu import DeckCrossSection, InfluenceSolver, find_critical_position
#
#     influence = InfluenceSolver(deck)
#     surface = influence.for_girder_moment("girder 3 midspan", element)
#
#     cross_section = DeckCrossSection.from_widths({
#         "footpath_left": 1.50, "kerb_left": 0.45,
#         "carriageway_1": 4.5, "median": 0.60, "carriageway_2": 4.5,
#         "kerb_right": 0.45, "footpath_right": 1.50,
#     })
#
#     worst = find_critical_position(surface, cross_section, span_m=35.0)
#     print(worst.describe())
#
# Coordinates: x runs along the span, y is vertical and positive upwards, z runs across
# the deck from its left edge. Lengths are metres, loads kilonewtons.
#
# ('setu' is Sanskrit for bridge.)

from __future__ import annotations

__version__ = "1.0.0"

from .critical_position import find_critical_position, rank_all_positions
from .deck_cross_section import Carriageway, DeckCrossSection, DeckStrip
from .deck_model import DeckModel, GirderSection
from .errors import (
    BackendError,
    CrossSectionError,
    InfluenceSurfaceError,
    ModelAlreadyLoadedError,
    NoAdmissibleArrangementError,
    NotLinearError,
    SetuError,
    VehicleDefinitionError,
    VehicleNotFoundError,
)
from .influence_surfaces import FEBackend, InfluenceSolver, InfluenceSurface, OpenSeesBackend
from .irc_code_rules import (
    CLASS_70R_TRACKED,
    CLASS_70R_WHEELED,
    CLASS_A,
    IRC_VEHICLES,
    AxleVehicle,
    TrackedVehicle,
    Vehicle,
    count_design_lanes,
    impact_factor,
    lane_reduction_factor,
    list_admissible_arrangements,
    register_vehicle,
)
from .reporting import enable_reports
from .results import CriticalPosition, VehiclePlacement
from .sampling import DEFAULT_SAMPLING, SamplingSettings

__all__ = [
    "CLASS_70R_TRACKED",
    "CLASS_70R_WHEELED",
    "CLASS_A",
    "DEFAULT_SAMPLING",
    "IRC_VEHICLES",
    "AxleVehicle",
    "BackendError",
    "Carriageway",
    "CriticalPosition",
    "CrossSectionError",
    "DeckCrossSection",
    "DeckModel",
    "DeckStrip",
    "FEBackend",
    "GirderSection",
    "InfluenceSolver",
    "InfluenceSurface",
    "InfluenceSurfaceError",
    "ModelAlreadyLoadedError",
    "NoAdmissibleArrangementError",
    "NotLinearError",
    "OpenSeesBackend",
    "SamplingSettings",
    "SetuError",
    "TrackedVehicle",
    "Vehicle",
    "VehicleDefinitionError",
    "VehicleNotFoundError",
    "VehiclePlacement",
    "__version__",
    "count_design_lanes",
    "enable_reports",
    "find_critical_position",
    "impact_factor",
    "lane_reduction_factor",
    "list_admissible_arrangements",
    "rank_all_positions",
    "register_vehicle",
]
