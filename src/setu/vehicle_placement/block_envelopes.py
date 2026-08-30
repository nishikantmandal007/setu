from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..adverse_direction import index_of_worst
from ..deck_cross_section import Carriageway
from ..influence_surfaces.surface import InfluenceSurface
from ..irc_code_rules.area_loads import (
    needs_residual_udl,
    response_to_area_load,
    strips_beside_class_a,
)
from ..irc_code_rules.lane_arrangements import CLASS_A_LANE
from ..irc_code_rules.vehicles import Vehicle
from ..sampling import SamplingSettings
from .response_curve import VehicleResponses


@dataclass(frozen=True)
class BlockEnvelope:
    z_positions_m: np.ndarray
    response: np.ndarray
    winner: list[str]

    def __call__(self, z_m: np.ndarray) -> np.ndarray:
        return np.interp(z_m, self.z_positions_m, self.response)

    def winner_at(self, z_m: float) -> str:
        distance_away_m = np.abs(self.z_positions_m - float(z_m))
        nearest = int(distance_away_m.argmin())
        return self.winner[nearest]


def envelope_every_block(
    responses: VehicleResponses,
    permitted: dict[str, list[Vehicle]],
    z_positions_m: np.ndarray,
    adverse: str,
    carriageway: Carriageway,
    surface: InfluenceSurface,
    apply_residual_udl: bool,
    sampling: SamplingSettings,
) -> dict[str, BlockEnvelope]:
    envelopes = {}

    for block, choices in permitted.items():
        response, winner = worst_of_the_permitted_vehicles(
            responses, choices, z_positions_m, adverse
        )

        if carries_a_residual_udl(block, carriageway, apply_residual_udl):
            response = response + residual_udl_curve(
                surface, z_positions_m, carriageway, adverse, sampling
            )

        envelopes[block] = BlockEnvelope(
            z_positions_m=z_positions_m, response=response, winner=winner
        )

    return envelopes


def worst_of_the_permitted_vehicles(
    responses: VehicleResponses,
    choices: list[Vehicle],
    z_positions_m: np.ndarray,
    adverse: str,
) -> tuple[np.ndarray, list[str]]:
    curves = [responses.for_vehicle(vehicle, z_positions_m, adverse) for vehicle in choices]
    one_row_per_vehicle = np.vstack([curve.response for curve in curves])

    worst_vehicle = index_of_worst(one_row_per_vehicle, adverse, axis=0)
    every_position = np.arange(len(z_positions_m))

    response = one_row_per_vehicle[worst_vehicle, every_position]
    winner = [choices[which].name for which in worst_vehicle]
    return response, winner


def carries_a_residual_udl(
    block: str, carriageway: Carriageway, apply_residual_udl: bool
) -> bool:
    if block != CLASS_A_LANE or not apply_residual_udl:
        return False
    return needs_residual_udl(carriageway.width_m)


def residual_udl_curve(
    surface: InfluenceSurface,
    z_positions_m: np.ndarray,
    carriageway: Carriageway,
    adverse: str,
    sampling: SamplingSettings,
) -> np.ndarray:
    # Table 6 S.No.1: the uncovered strip moves with the vehicle, so it rides along with
    # the Class A curve rather than being added once at the end.
    added_at_each_position = [
        response_to_area_load(
            surface,
            strips_beside_class_a(float(z_m), carriageway.left_m, carriageway.right_m),
            adverse,
            sampling=sampling,
        )
        for z_m in z_positions_m
    ]
    return np.array(added_at_each_position)
