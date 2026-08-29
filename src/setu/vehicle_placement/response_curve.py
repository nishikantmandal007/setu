# What one vehicle does to a response, from every position across the deck.
#
# This is the bridge between the influence surface and the two searches. For each position
# across the width it answers one question: put this vehicle here, slide it along the span
# until it does the most damage it can, and how much is that?
#
#     curve(z) = impact factor * worst over x of  sum over wheels  load * influence_at(x, z)
#
# The "sum over wheels" and "worst over x" machinery, and why the search only ever needs to
# try positions that put a wheel exactly on a mesh station, live in wheels_on_the_surface.py.
#
# Impact is applied here, per vehicle, rather than once over a whole load case. Clause 208.5
# asks for the effective span of the member being checked, and a mixed arrangement of Class A
# and 70R vehicles does not share one impact factor - using a single blanket value can be out
# by five per cent.

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..adverse_direction import index_of_worst
from ..influence_surfaces.surface import InfluenceSurface
from ..irc_code_rules.code_tables import ROUND_TO_DECIMALS, TOLERANCE_M
from ..irc_code_rules.impact_factor import impact_factor
from ..irc_code_rules.vehicles import (
    Vehicle,
    class_of,
    most_vehicles_that_fit,
    pitch_between_vehicles_m,
)
from ..irc_code_rules.wheel_loads import wheel_load_offsets
from ..sampling import DEFAULT_SAMPLING, SamplingSettings
from .along_span import find_worst_train
from .wheels_on_the_surface import (
    bending_positions_across_width,
    positions_along_span,
    response_to_one_vehicle_everywhere,
)

# ---------------------------------------------------------------------------
# Response Curve
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResponseCurve:
    # One vehicle's worst response at each position across the deck.
    vehicle_name: str
    z_positions_m: np.ndarray

    # The worst response at each position across the deck, impact included.
    response: np.ndarray

    # Where the leading vehicle's front sat to cause it, at each position.
    x_positions_m: np.ndarray

    # How many vehicles were in the lane to cause it, at each position.
    vehicles_in_train: np.ndarray

    # Where every vehicle in that lane sat, at each position.
    train_x_front_m: list[tuple[float, ...]]

    impact_factor: float

    def read_at(self, z_m: float | np.ndarray) -> float | np.ndarray:
        # Linear between samples, which is exact - the samples were taken at every
        # position where this curve can bend.
        return np.interp(z_m, self.z_positions_m, self.response)


# ---------------------------------------------------------------------------
# Vehicle Responses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorstAlongSpan:
    # The worst response along the span, and how it was achieved, at each position across
    # the width.
    response: np.ndarray

    # Where the leading (or only) vehicle's front sat to cause it.
    x_positions_m: np.ndarray

    # How many vehicles were in the train.
    vehicles_in_train: np.ndarray

    # Where every vehicle in that train sat.
    train_x_front_m: list[tuple[float, ...]]


class VehicleResponses:
    # Builds response curves for one influence surface.

    def __init__(
        self,
        surface: InfluenceSurface,
        span_m: float,
        material: str = "steel",
        member_span_m: float | None = None,
        # The effective span of the member being checked, when it is not the span of the
        # bridge. Clause 208.5.
        wearing_course_thickness_m: float = 0.0,
        apply_impact: bool = True,
        # Whether one lane may carry more than one vehicle at a time.
        allow_trains: bool = True,
        sampling: SamplingSettings = DEFAULT_SAMPLING,
    ) -> None:
        self.surface = surface
        self.span_m = float(span_m)
        self.material = material
        self.member_span_m = member_span_m
        self.wearing_course_thickness_m = float(wearing_course_thickness_m)
        self.apply_impact = apply_impact
        self.allow_trains = allow_trains
        self.sampling = sampling
        self._already_built: dict[tuple, ResponseCurve] = {}

    def for_vehicle(
        self, vehicle: Vehicle, z_positions_m: np.ndarray, adverse: str = "maximum"
    ) -> ResponseCurve:
        # Returns this vehicle's worst response at each position across the deck.
        z_positions_m = np.asarray(z_positions_m, float)
        # The cache key. Assumes that two different non-uniform z-grids never share both a
        # length and their two endpoints - true of every grid positions_across_width can
        # produce, since it is always sorted and deduplicated, but nothing here enforces it,
        # so a hand-built grid that happened to collide would silently return the wrong
        # cached curve.
        remembered = (
            vehicle.name,
            adverse,
            len(z_positions_m),
            float(z_positions_m[0]),
            float(z_positions_m[-1]),
        )
        if remembered not in self._already_built:
            self._already_built[remembered] = self.build_curve(vehicle, z_positions_m, adverse)
        return self._already_built[remembered]

    def build_curve(
        self, vehicle: Vehicle, z_positions_m: np.ndarray, adverse: str
    ) -> ResponseCurve:
        wheel_offsets = wheel_load_offsets(
            vehicle, self.wearing_course_thickness_m, self.sampling
        )
        x_positions_m = positions_along_span(self.surface, wheel_offsets)
        response_to_one_vehicle = response_to_one_vehicle_everywhere(
            self.surface, wheel_offsets, x_positions_m, z_positions_m, self.sampling
        )

        if self.allow_trains:
            worst = self.worst_train_at_each_position(
                vehicle, response_to_one_vehicle, x_positions_m, adverse
            )
        else:
            worst = self.worst_single_vehicle_at_each_position(
                response_to_one_vehicle, x_positions_m, adverse
            )

        factor = self.impact_factor_for(vehicle)
        return ResponseCurve(
            vehicle_name=vehicle.name,
            z_positions_m=z_positions_m,
            response=factor * worst.response,
            x_positions_m=worst.x_positions_m,
            vehicles_in_train=worst.vehicles_in_train,
            train_x_front_m=worst.train_x_front_m,
            impact_factor=factor,
        )

    def worst_single_vehicle_at_each_position(
        self, response_to_one_vehicle: np.ndarray, x_positions_m: np.ndarray, adverse: str
    ) -> WorstAlongSpan:
        # Puts one vehicle in the lane, at whichever spot along the span is worst.
        worst_at = index_of_worst(response_to_one_vehicle, adverse, axis=0)
        z_index = np.arange(response_to_one_vehicle.shape[1])
        where_it_stopped_m = x_positions_m[worst_at]

        return WorstAlongSpan(
            response=response_to_one_vehicle[worst_at, z_index],
            x_positions_m=where_it_stopped_m,
            vehicles_in_train=np.ones(response_to_one_vehicle.shape[1], int),
            train_x_front_m=[(float(x_m),) for x_m in where_it_stopped_m],
        )

    def worst_train_at_each_position(
        self,
        vehicle: Vehicle,
        response_to_one_vehicle: np.ndarray,
        x_positions_m: np.ndarray,
        adverse: str,
    ) -> WorstAlongSpan:
        # Fills the lane with as many vehicles as help, at whichever spots are worst.
        #
        # One lane may legally carry several vehicles nose to tail, and on a long or
        # continuous span that is what governs. Every train length from one vehicle upwards
        # is tried, because a shorter train can be worse when the extra vehicle would land
        # where the influence surface changes sign.
        pitch_m = pitch_between_vehicles_m(vehicle)
        longest_train = most_vehicles_that_fit(
            vehicle, float(x_positions_m[0]), float(x_positions_m[-1])
        )

        positions_across_the_width = response_to_one_vehicle.shape[1]
        response = np.empty(positions_across_the_width)
        leading_x_m = np.empty(positions_across_the_width)
        vehicles_in_train = np.empty(positions_across_the_width, int)
        trains: list[tuple[float, ...]] = []

        # One search per position across the width - z_index counts positions, not metres.
        for z_index in range(positions_across_the_width):
            worst = find_worst_train(
                response_to_one_vehicle[:, z_index],
                x_positions_m,
                pitch_m,
                longest_train,
                adverse,
            )
            if worst is None:
                raise RuntimeError(
                    "find_worst_train found no legal placement for even a single vehicle "
                    "at one of the positions across the width - a single vehicle should "
                    "always fit somewhere on x_positions_m"
                )
            response[z_index] = worst.response
            leading_x_m[z_index] = worst.positions_m[0]
            vehicles_in_train[z_index] = worst.vehicles_in_train
            trains.append(worst.positions_m)

        return WorstAlongSpan(
            response=response,
            x_positions_m=leading_x_m,
            vehicles_in_train=vehicles_in_train,
            train_x_front_m=trains,
        )

    def impact_factor_for(self, vehicle: Vehicle) -> float:
        # Returns the Clause 208 factor for this vehicle on the member being checked.
        if not self.apply_impact:
            return 1.0

        span_m = self.span_m if self.member_span_m is None else float(self.member_span_m)
        return impact_factor(class_of(vehicle), span_m, self.material)


# ---------------------------------------------------------------------------
# Positions Across The Width
# ---------------------------------------------------------------------------


def positions_across_width(
    responses: VehicleResponses,
    vehicles: list[Vehicle],
    z_from_m: float,
    z_to_m: float,
    steps: int | None = None,
) -> np.ndarray:
    # Returns the positions across the deck to sample every curve at.
    #
    # The bends of every vehicle that might be placed, plus an even fill. The fill is belt
    # and braces: it catches the places where one vehicle's curve overtakes another's, which
    # is a bend in the envelope even though neither curve bends there.
    steps = DEFAULT_SAMPLING.transverse_steps if steps is None else steps
    positions = [np.linspace(z_from_m, z_to_m, steps)]

    for vehicle in vehicles:
        positions.append(
            bending_positions_across_width(
                responses.surface,
                vehicle,
                responses.wearing_course_thickness_m,
                responses.sampling,
                z_from_m,
                z_to_m,
            )
        )

    everywhere_m = np.unique(np.round(np.concatenate(positions), ROUND_TO_DECIMALS))
    return everywhere_m[
        (everywhere_m >= z_from_m - TOLERANCE_M) & (everywhere_m <= z_to_m + TOLERANCE_M)
    ]
