"""What one vehicle does to a response, from every position across the deck.

This is the bridge between the influence surface and the two searches. For each
position across the width it answers one question: put this vehicle here, slide
it along the span until it does the most damage it can, and how much is that?

    curve(z) = impact factor * worst over x of  sum over wheels  load * influence_at(x, z)

Two things make the answer exact rather than merely finely sampled.

Along the span, the only positions tried are those that put some wheel exactly
on a mesh station. The influence surface is flat-faceted between its stations,
so the worst position is always one of those - checking more would find nothing.

Across the width, the same reasoning gives the positions where the curve bends,
and the searches are handed those so they can bend their grids to match.

Impact is applied here, per vehicle, rather than once over a whole load case.
Clause 208.5 asks for the effective span of the member being checked, and a
mixed arrangement of Class A and 70R vehicles does not share one impact factor -
using a single blanket value can be out by five per cent.
"""

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


@dataclass(frozen=True)
class ResponseCurve:
    """One vehicle's worst response at each position across the deck."""

    vehicle_name: str
    z_positions_m: np.ndarray
    response: np.ndarray
    """The worst response at each position across the deck, impact included."""

    x_positions_m: np.ndarray
    """Where the leading vehicle's front sat to cause it, at each position."""

    vehicles_in_train: np.ndarray
    """How many vehicles were in the lane to cause it, at each position."""

    train_x_front_m: list[tuple[float, ...]]
    """Where every vehicle in that lane sat, at each position."""

    impact_factor: float

    def read_at(self, z_m):
        """Reads the curve at any position across the deck.

        Linear between samples, which is exact - the samples were taken at every
        position where this curve can bend.
        """
        return np.interp(z_m, self.z_positions_m, self.response)


class VehicleResponses:
    """Builds response curves for one influence surface.

    Reads as what it does::

        responses = VehicleResponses(surface, span_m=35.0)
        curve = responses.for_vehicle(CLASS_A, z_positions_m, adverse="maximum")
    """

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
        """The effective span of the member being checked, when it is not the
        span of the bridge. Clause 208.5."""

        self.wearing_course_thickness_m = float(wearing_course_thickness_m)
        self.apply_impact = apply_impact
        self.allow_trains = allow_trains
        """Whether one lane may carry more than one vehicle at a time."""

        self.sampling = sampling
        self._already_built: dict[tuple, ResponseCurve] = {}

    def for_vehicle(
        self, vehicle: Vehicle, z_positions_m: np.ndarray, adverse: str = "maximum"
    ) -> ResponseCurve:
        """Returns this vehicle's worst response at each position across the deck."""
        z_positions_m = np.asarray(z_positions_m, float)
        remembered = (
            vehicle.name,
            adverse,
            len(z_positions_m),
            float(z_positions_m[0]),
            float(z_positions_m[-1]),
        )
        if remembered not in self._already_built:
            self._already_built[remembered] = self._build_curve(vehicle, z_positions_m, adverse)
        return self._already_built[remembered]

    def _build_curve(
        self, vehicle: Vehicle, z_positions_m: np.ndarray, adverse: str
    ) -> ResponseCurve:
        wheel_offsets = wheel_load_offsets(
            vehicle, self.wearing_course_thickness_m, self.sampling
        )
        x_positions_m = self.positions_along_span(wheel_offsets)
        response_to_one_vehicle = self._response_to_one_vehicle_everywhere(
            wheel_offsets, x_positions_m, z_positions_m
        )

        if self.allow_trains:
            response, x_m, vehicles, trains = self._worst_train_at_each_position(
                vehicle, response_to_one_vehicle, x_positions_m, adverse
            )
        else:
            response, x_m, vehicles, trains = self._worst_single_vehicle_at_each_position(
                response_to_one_vehicle, x_positions_m, adverse
            )

        factor = self.impact_factor_for(vehicle)
        return ResponseCurve(
            vehicle_name=vehicle.name,
            z_positions_m=z_positions_m,
            response=factor * response,
            x_positions_m=x_m,
            vehicles_in_train=vehicles,
            train_x_front_m=trains,
            impact_factor=factor,
        )

    def positions_along_span(self, wheel_offsets: np.ndarray) -> np.ndarray:
        """Returns every position along the span worth trying for these wheels.

        A position is worth trying when it puts some wheel exactly on a mesh
        station, because that is where the surface bends. The range starts far
        enough back for the vehicle to be part-way onto the bridge, which is a
        real load case and often the worst one near a support.
        """
        stations_m = self.surface.length_mesh_m
        wheel_dx_m = np.asarray(wheel_offsets, float)[:, 0]

        candidates_m = np.unique((stations_m[None, :] - wheel_dx_m[:, None]).ravel())
        first_m = -wheel_dx_m.max()
        last_m = stations_m[-1]
        return candidates_m[
            (candidates_m >= first_m - TOLERANCE_M) & (candidates_m <= last_m + TOLERANCE_M)
        ]

    def _response_to_one_vehicle_everywhere(
        self, wheel_offsets: np.ndarray, x_positions_m: np.ndarray, z_positions_m: np.ndarray
    ) -> np.ndarray:
        """Returns the response to one vehicle at every (along span, across width) pair.

        Built a chunk of longitudinal positions at a time, because the full
        wheel-by-wheel tensor would be large enough to matter on a fine mesh.
        """
        responses = np.empty((len(x_positions_m), len(z_positions_m)))
        chunk = self.sampling.positions_per_chunk

        for start in range(0, len(x_positions_m), chunk):
            some_x_m = x_positions_m[start : start + chunk]
            responses[start : start + len(some_x_m)] = self._sum_over_wheels(
                wheel_offsets, some_x_m, z_positions_m
            )

        return responses

    def _sum_over_wheels(
        self, wheel_offsets: np.ndarray, x_positions_m: np.ndarray, z_positions_m: np.ndarray
    ) -> np.ndarray:
        """Returns sum over wheels of load times influence, for every position pair."""
        offsets = np.asarray(wheel_offsets, float)
        wheel_dx_m, wheel_dz_m, wheel_loads_kn = offsets[:, 0], offsets[:, 1], offsets[:, 2]

        wheel_x_m = np.asarray(x_positions_m, float)[:, None, None] + wheel_dx_m[None, None, :]
        wheel_z_m = np.asarray(z_positions_m, float)[None, :, None] + wheel_dz_m[None, None, :]

        return (self.surface.influence_at(wheel_x_m, wheel_z_m) * wheel_loads_kn).sum(axis=-1)

    def _worst_single_vehicle_at_each_position(
        self, response_to_one_vehicle: np.ndarray, x_positions_m: np.ndarray, adverse: str
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[tuple[float, ...]]]:
        """Puts one vehicle in the lane, at whichever spot along the span is worst."""
        worst_at = index_of_worst(
            response_to_one_vehicle, adverse, axis=0
        )
        across = np.arange(response_to_one_vehicle.shape[1])
        where_it_stopped_m = x_positions_m[worst_at]

        return (
            response_to_one_vehicle[worst_at, across],
            where_it_stopped_m,
            np.ones(response_to_one_vehicle.shape[1], int),
            [(float(x),) for x in where_it_stopped_m],
        )

    def _worst_train_at_each_position(
        self,
        vehicle: Vehicle,
        response_to_one_vehicle: np.ndarray,
        x_positions_m: np.ndarray,
        adverse: str,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[tuple[float, ...]]]:
        """Fills the lane with as many vehicles as help, at whichever spots are worst.

        One lane may legally carry several vehicles nose to tail, and on a long
        or continuous span that is what governs. Every train length from one
        vehicle upwards is tried, because a shorter train can be worse when the
        extra vehicle would land where the influence surface changes sign.
        """
        pitch_m = pitch_between_vehicles_m(vehicle)
        longest_train = most_vehicles_that_fit(
            vehicle, float(x_positions_m[0]), float(x_positions_m[-1])
        )

        positions_across = response_to_one_vehicle.shape[1]
        response = np.empty(positions_across)
        leading_x_m = np.empty(positions_across)
        vehicles_in_train = np.empty(positions_across, int)
        trains: list[tuple[float, ...]] = []

        for across in range(positions_across):
            worst = find_worst_train(
                response_to_one_vehicle[:, across],
                x_positions_m,
                pitch_m,
                longest_train,
                adverse,
            )
            assert worst is not None, "a single vehicle always fits"
            response[across] = worst.response
            leading_x_m[across] = worst.positions_m[0]
            vehicles_in_train[across] = worst.vehicles_in_train
            trains.append(worst.positions_m)

        return response, leading_x_m, vehicles_in_train, trains

    def impact_factor_for(self, vehicle: Vehicle) -> float:
        """Returns the Clause 208 factor for this vehicle on the member being checked."""
        if not self.apply_impact:
            return 1.0

        span_m = self.span_m if self.member_span_m is None else float(self.member_span_m)
        return impact_factor(class_of(vehicle), span_m, self.material)

    def bending_positions_across_width(
        self, vehicle: Vehicle, z_from_m: float, z_to_m: float
    ) -> np.ndarray:
        """Returns the positions across the deck where this vehicle's curve bends.

        The curve bends when a wheel crosses a mesh station, so these are the
        stations shifted back by each wheel's offset. Sampling a curve here makes
        it exactly piecewise linear rather than approximately so.
        """
        wheel_offsets = wheel_load_offsets(
            vehicle, self.wearing_course_thickness_m, self.sampling
        )
        wheel_dz_m = np.asarray(wheel_offsets, float)[:, 1]
        stations_m = self.surface.width_mesh_m

        bends_m = np.unique(
            np.concatenate(
                [
                    (stations_m[None, :] - wheel_dz_m[:, None]).ravel(),
                    np.array([z_from_m, z_to_m], float),
                ]
            )
        )
        return bends_m[(bends_m >= z_from_m - TOLERANCE_M) & (bends_m <= z_to_m + TOLERANCE_M)]


def positions_across_width(
    responses: VehicleResponses,
    vehicles: list[Vehicle],
    z_from_m: float,
    z_to_m: float,
    steps: int | None = None,
) -> np.ndarray:
    """Returns the positions across the deck to sample every curve at.

    The bends of every vehicle that might be placed, plus an even fill. The fill
    is belt and braces: it catches the places where one vehicle's curve overtakes
    another's, which is a bend in the envelope even though neither curve bends
    there.
    """
    steps = DEFAULT_SAMPLING.transverse_steps if steps is None else steps
    positions = [np.linspace(z_from_m, z_to_m, steps)]

    for vehicle in vehicles:
        positions.append(responses.bending_positions_across_width(vehicle, z_from_m, z_to_m))

    everywhere_m = np.unique(np.round(np.concatenate(positions), ROUND_TO_DECIMALS))
    return everywhere_m[
        (everywhere_m >= z_from_m - TOLERANCE_M) & (everywhere_m <= z_to_m + TOLERANCE_M)
    ]
