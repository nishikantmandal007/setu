# The worst any permitted vehicle can do in one kind of lane block, at every position
# across the deck.
#
# A 70R zone may hold a wheeled or a tracked vehicle, and a Class A lane may hold a vehicle
# facing either way. Which of them is worse changes along the deck, so all of them are
# worked out and the worst is taken at each position. BlockEnvelope is callable, so the
# transverse search (see across_carriageway.py) can read it as a response curve.

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

# ---------------------------------------------------------------------------
# Block Envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BlockEnvelope:
    z_positions_m: np.ndarray
    response: np.ndarray

    # Which vehicle was worst at each position across the deck.
    winner: list[str]

    def __call__(self, z_m: np.ndarray) -> np.ndarray:
        return np.interp(z_m, self.z_positions_m, self.response)

    def winner_at(self, z_m: float) -> str:
        # Read by nearest position, not interpolated: which vehicle wins is a choice
        # between two of them, and there is nothing in between.
        nearest = int(np.abs(self.z_positions_m - float(z_m)).argmin())
        return self.winner[nearest]


# ---------------------------------------------------------------------------
# Building The Envelopes
# ---------------------------------------------------------------------------


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
    # Returns one enveloped response curve per kind of lane block, for one carriageway.
    envelopes = {}

    for block, choices in permitted.items():
        curves = [responses.for_vehicle(vehicle, z_positions_m, adverse) for vehicle in choices]
        stacked = np.vstack([curve.response for curve in curves])

        worst = index_of_worst(stacked, adverse, axis=0)
        response = stacked[worst, np.arange(len(z_positions_m))]

        # Table 6 S.No.1: on a narrow carriageway the strip the vehicle does not cover
        # carries 500 kg/m2, and that strip moves with the vehicle - so it rides along with
        # the Class A curve rather than being added at the end.
        if (
            block == CLASS_A_LANE
            and apply_residual_udl
            and needs_residual_udl(carriageway.width_m)
        ):
            response = response + residual_udl_curve(
                surface, z_positions_m, carriageway, adverse, sampling
            )

        envelopes[block] = BlockEnvelope(
            z_positions_m=z_positions_m,
            response=response,
            winner=[choices[which].name for which in worst],
        )

    return envelopes


def residual_udl_curve(
    surface: InfluenceSurface,
    z_positions_m: np.ndarray,
    carriageway: Carriageway,
    adverse: str,
    sampling: SamplingSettings,
) -> np.ndarray:
    # Returns what the residual UDL adds at each position a Class A vehicle could sit.
    return np.array(
        [
            response_to_area_load(
                surface,
                strips_beside_class_a(float(z_m), carriageway.left_m, carriageway.right_m),
                adverse,
                sampling=sampling,
            )
            for z_m in z_positions_m
        ]
    )
