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

NO_IMPACT = 1.0


@dataclass(frozen=True)
class ResponseCurve:
    vehicle_name: str
    z_positions_m: np.ndarray
    response: np.ndarray
    x_positions_m: np.ndarray
    vehicles_in_train: np.ndarray
    train_x_front_m: list[tuple[float, ...]]
    impact_factor: float

    def read_at(self, z_m: float | np.ndarray) -> float | np.ndarray:
        return np.interp(z_m, self.z_positions_m, self.response)


@dataclass(frozen=True)
class WorstAlongSpan:
    response: np.ndarray
    x_positions_m: np.ndarray
    vehicles_in_train: np.ndarray
    train_x_front_m: list[tuple[float, ...]]


class VehicleResponses:
    def __init__(
        self,
        surface: InfluenceSurface,
        span_m: float,
        material: str = "steel",
        member_span_m: float | None = None,
        wearing_course_thickness_m: float = 0.0,
        apply_impact: bool = True,
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
        z_positions_m = np.asarray(z_positions_m, float)
        remembered = remembered_as(vehicle, z_positions_m, adverse)

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
        positions_across_the_width = response_to_one_vehicle.shape[1]

        worst_along_the_span = index_of_worst(response_to_one_vehicle, adverse, axis=0)
        every_position = np.arange(positions_across_the_width)
        where_it_stopped_m = x_positions_m[worst_along_the_span]

        return WorstAlongSpan(
            response=response_to_one_vehicle[worst_along_the_span, every_position],
            x_positions_m=where_it_stopped_m,
            vehicles_in_train=np.ones(positions_across_the_width, int),
            train_x_front_m=[(float(x_m),) for x_m in where_it_stopped_m],
        )

    def worst_train_at_each_position(
        self,
        vehicle: Vehicle,
        response_to_one_vehicle: np.ndarray,
        x_positions_m: np.ndarray,
        adverse: str,
    ) -> WorstAlongSpan:
        pitch_m = pitch_between_vehicles_m(vehicle)
        longest_train = most_vehicles_that_fit(
            vehicle, float(x_positions_m[0]), float(x_positions_m[-1])
        )

        positions_across_the_width = response_to_one_vehicle.shape[1]
        response = np.empty(positions_across_the_width)
        leading_x_m = np.empty(positions_across_the_width)
        vehicles_in_train = np.empty(positions_across_the_width, int)
        trains: list[tuple[float, ...]] = []

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
                    "no legal placement was found for even a single vehicle at one of the "
                    "positions across the width, but one vehicle should always fit"
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
        if not self.apply_impact:
            return NO_IMPACT

        span_m = self.span_m if self.member_span_m is None else float(self.member_span_m)
        return impact_factor(class_of(vehicle), span_m, self.material)


def remembered_as(vehicle: Vehicle, z_positions_m: np.ndarray, adverse: str) -> tuple:
    # Two different grids that share a length and both endpoints would collide here.
    return (
        vehicle.name,
        adverse,
        len(z_positions_m),
        float(z_positions_m[0]),
        float(z_positions_m[-1]),
    )


def positions_across_width(
    responses: VehicleResponses,
    vehicles: list[Vehicle],
    z_from_m: float,
    z_to_m: float,
    steps: int | None = None,
) -> np.ndarray:
    steps = DEFAULT_SAMPLING.positions_across_the_deck_to_try if steps is None else steps
    an_even_spread = np.linspace(z_from_m, z_to_m, steps)
    worth_sampling = [an_even_spread]

    for vehicle in vehicles:
        worth_sampling.append(
            bending_positions_across_width(
                responses.surface,
                vehicle,
                responses.wearing_course_thickness_m,
                responses.sampling,
                z_from_m,
                z_to_m,
            )
        )

    everywhere_m = np.unique(np.round(np.concatenate(worth_sampling), ROUND_TO_DECIMALS))
    is_on_the_deck = (everywhere_m >= z_from_m - TOLERANCE_M) & (
        everywhere_m <= z_to_m + TOLERANCE_M
    )
    return everywhere_m[is_on_the_deck]
