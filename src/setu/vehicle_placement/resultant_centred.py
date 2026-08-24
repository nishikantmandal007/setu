"""The other transverse position the code asks for: resultant at mid-width.

Two transverse conditions are to be checked. One is the swept position - the
vehicles put wherever, within their clearances, they do the most damage. The
other is the resultant-centred position: the same vehicles slid across until the
resultant of their loads sits on the centreline of the carriageway.

The second can never be worse than the first. It is one position inside the set
the sweep already searches, so the sweep either finds it or finds something
worse. It is computed and reported because the code asks for both, and because
the gap between them is worth seeing - relying on the centred position alone
under-predicts, and by a margin that is not always small.

Everything moves together. Each vehicle slides from where the arrangement packs
it hard left to where it packs hard right, all by the same fraction of the room
available. The resultant moves linearly with that fraction, so the fraction that
centres it is solved for directly rather than searched.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from ..deck_cross_section import Carriageway
from ..irc_code_rules.code_tables import GRAVITY_KN_PER_TONNE, TOLERANCE_M
from ..irc_code_rules.lane_arrangements import (
    CLASS_A_LANE,
    fit_blocks_between,
    list_admissible_arrangements,
    where_vehicle_sits_in_block,
)
from ..irc_code_rules.lane_reduction import lane_reduction_factor
from ..irc_code_rules.vehicles import CLASS_70R_WHEELED, CLASS_A, Vehicle


@dataclass(frozen=True)
class ResultantCentredPlacement:
    """One arrangement, slid until its load resultant sits at mid-width."""

    lane_pattern: list[str]
    design_lanes: int
    vehicle_centres_m: list[float]
    response_before_reduction: float
    lane_reduction: float
    response: float
    is_exactly_centred: bool
    """False when clearances stopped the resultant reaching the centreline."""


def weight_of(vehicle: Vehicle) -> float:
    """Returns the vehicle's total unfactored load, in kilonewtons."""
    return vehicle.total_load_t * GRAVITY_KN_PER_TONNE


def centre_the_resultant(
    carriageways: Sequence[Carriageway],
    response_curves: Sequence[Mapping[str, Callable]],
    adverse: str = "maximum",
    apply_lane_reduction: bool = True,
    follow_combination_drawings: bool = True,
) -> list[ResultantCentredPlacement]:
    """Returns the worst resultant-centred placement on each carriageway.

    One per carriageway, each the worst of that carriageway's arrangements.
    """
    worst_on_each = []

    for carriageway, curves in zip(carriageways, response_curves, strict=True):
        worst = None

        for arrangement in list_admissible_arrangements(
            carriageway.width_m, follow_combination_drawings
        ):
            placed = _centre_one_arrangement(
                carriageway, arrangement, curves, adverse, apply_lane_reduction
            )
            if placed is None:
                continue
            if worst is None or _is_worse(placed.response, worst.response, adverse):
                worst = placed

        if worst is not None:
            worst_on_each.append(worst)

    return worst_on_each


def _centre_one_arrangement(
    carriageway: Carriageway,
    arrangement,
    curves: Mapping[str, Callable],
    adverse: str,
    apply_lane_reduction: bool,
) -> ResultantCentredPlacement | None:
    """Slides one arrangement across until its resultant sits at mid-width."""
    layout = fit_blocks_between(
        arrangement.lane_pattern, carriageway.left_m, carriageway.right_m
    )
    if layout is None:
        return None

    packed_left_m, packed_right_m = _how_far_each_vehicle_can_go(arrangement, layout)
    weights_kn = [
        weight_of(_representative_vehicle(block)) for block in arrangement.lane_pattern
    ]

    fraction, is_exact = _fraction_that_centres_the_resultant(
        packed_left_m, packed_right_m, weights_kn,
        target_m=0.5 * (carriageway.left_m + carriageway.right_m),
    )

    centres_m = [
        left_m + fraction * (right_m - left_m)
        for left_m, right_m in zip(packed_left_m, packed_right_m, strict=True)
    ]

    before_reduction = sum(
        float(curves[block](np.asarray(z_m)))
        for block, z_m in zip(arrangement.lane_pattern, centres_m, strict=True)
    )
    reduction = (
        lane_reduction_factor(arrangement.design_lanes) if apply_lane_reduction else 1.0
    )

    return ResultantCentredPlacement(
        lane_pattern=list(arrangement.lane_pattern),
        design_lanes=arrangement.design_lanes,
        vehicle_centres_m=centres_m,
        response_before_reduction=before_reduction,
        lane_reduction=reduction,
        response=before_reduction * reduction,
        is_exactly_centred=is_exact,
    )


def _how_far_each_vehicle_can_go(arrangement, layout) -> tuple[list[float], list[float]]:
    """Returns each vehicle's centreline packed hard left, and packed hard right."""
    packed_left_m, packed_right_m = [], []

    for block, width_m, edge_m in zip(
        arrangement.lane_pattern, layout.block_widths_m, layout.packed_left_edges_m,
        strict=True,
    ):
        nearest_m, furthest_m = where_vehicle_sits_in_block(block, width_m)
        packed_left_m.append(edge_m + nearest_m)
        packed_right_m.append(edge_m + layout.sliding_room_m + furthest_m)

    return packed_left_m, packed_right_m


def _fraction_that_centres_the_resultant(
    packed_left_m: Sequence[float],
    packed_right_m: Sequence[float],
    weights_kn: Sequence[float],
    target_m: float,
) -> tuple[float, bool]:
    """Returns how far across to slide everything, as a fraction of the room.

    The resultant moves linearly with that fraction, so the answer is one
    division. A fraction outside 0 to 1 means the clearances will not let the
    resultant reach the centreline, and it is clamped to as close as it goes.
    """
    total_kn = float(sum(weights_kn))
    if total_kn <= 0:
        raise ValueError("this arrangement carries no load, so it has no resultant")

    resultant_packed_left_m = (
        sum(w * z for w, z in zip(weights_kn, packed_left_m, strict=True)) / total_kn
    )
    how_far_it_can_move_m = (
        sum(w * (right - left)
            for w, left, right in zip(weights_kn, packed_left_m, packed_right_m, strict=True))
        / total_kn
    )

    if abs(how_far_it_can_move_m) < TOLERANCE_M:
        return 0.0, abs(resultant_packed_left_m - target_m) < 1e-6

    fraction = (target_m - resultant_packed_left_m) / how_far_it_can_move_m
    return min(max(fraction, 0.0), 1.0), 0.0 - 1e-9 <= fraction <= 1.0 + 1e-9


def _representative_vehicle(block: str) -> Vehicle:
    """The vehicle whose weight stands for this kind of lane block."""
    return CLASS_A if block == CLASS_A_LANE else CLASS_70R_WHEELED


def _is_worse(candidate: float, best: float, adverse: str) -> bool:
    return candidate > best if adverse == "maximum" else candidate < best
