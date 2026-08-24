"""Where across the width the vehicles do the most damage.

Every design lane of every carriageway carries a vehicle at the same time, and
they all have to be positioned together, because the code fixes how close they
may come to each other and to the kerb.

The trick that makes this searchable is to stop thinking in absolute positions.
Push the whole arrangement as far left as the clearances allow, and then let
each block slide right by some amount. Two blocks keep their clearance exactly
when the left one does not slide further than the right one - so the whole
tangle of clearance rules collapses into one rule: the sliding amounts never
decrease from left to right.

That turns the search into a dynamic program. Reading the blocks left to right,
the best arrangement up to a block is that block's own contribution plus the
best arrangement of everything to its left that has not slid past it. Each block
is visited once instead of every combination of block positions being tried, so
the cost grows with the number of blocks rather than exploding with it.

The answer is exact rather than sampled, because the sliding positions tried
include every offset at which any block's response curve bends. Between those
offsets the total is linear, so nothing can hide in the gaps.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from ..deck_cross_section import Carriageway
from ..errors import NoAdmissibleArrangementError
from ..irc_code_rules.code_tables import ROUND_TO_DECIMALS, TOLERANCE_M
from ..irc_code_rules.lane_arrangements import (
    LaneArrangement,
    fit_blocks_between,
    list_admissible_arrangements,
    where_vehicle_sits_in_block,
)
from ..irc_code_rules.lane_reduction import lane_reduction_factor
from ..settings import DEFAULT_SAMPLING, SamplingSettings
from .best_prefix import best_so_far

ResponseCurves = Mapping[str, Callable[[np.ndarray], np.ndarray]]
"""One curve per kind of lane block. Each returns the response of one vehicle of
that kind, centred at a given position across the deck."""


@dataclass(frozen=True)
class CarriagewayCase:
    """One arrangement, placed at its worst, on one carriageway."""

    lane_pattern: list[str]
    design_lanes: int
    sliding_room_m: float
    vehicle_centres_m: list[float]
    """Where each vehicle's centreline ended up, left to right."""

    response_before_reduction: float
    lane_reduction: float
    response: float


@dataclass(frozen=True)
class TransversePlacement:
    """One way of loading every carriageway at once, and what it does."""

    response: float
    response_before_reduction: float
    lane_reduction: float
    design_lanes: int
    """Design lanes loaded across the whole deck."""

    per_carriageway: list[CarriagewayCase]


def place_vehicles(
    block_curves: Sequence[np.ndarray], adverse: str = "maximum"
) -> tuple[float, list[int]]:
    """Returns the worst total over sliding offsets that never decrease left to right.

    `block_curves[b][s]` is what block b contributes when it slides by offset s.
    Returns the worst total and the offset each block ended up at.
    """
    adverse_sign = _adverse_sign(adverse)

    best_total = adverse_sign * np.asarray(block_curves[0], float)
    where_the_block_to_the_left_sat: list[np.ndarray | None] = [None]

    for block in range(1, len(block_curves)):
        best_to_the_left, came_from = best_so_far(best_total)
        best_total = adverse_sign * np.asarray(block_curves[block], float) + best_to_the_left
        where_the_block_to_the_left_sat.append(came_from)

    chosen = _walk_back_through_the_blocks(best_total, where_the_block_to_the_left_sat)
    worst = sum(float(np.asarray(block_curves[b])[chosen[b]]) for b in range(len(block_curves)))
    return worst, chosen


def find_worst_placement(
    carriageways: Sequence[Carriageway],
    response_curves: Sequence[ResponseCurves],
    adverse: str = "maximum",
    apply_lane_reduction: bool = True,
    curve_breakpoints_m: np.ndarray | None = None,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
) -> list[TransversePlacement]:
    """Returns every way of loading the deck, worst first.

    One `ResponseCurves` mapping per carriageway, because a narrow carriageway
    carries its own residual UDL and so has its own curves.

    Pass `curve_breakpoints_m` - the positions the curves were sampled at - to
    make the answer exact rather than merely finely sampled.
    """
    _check_one_set_of_curves_per_carriageway(carriageways, response_curves)

    cases_per_carriageway = [
        _cases_for_one_carriageway(
            carriageway, curves, adverse, apply_lane_reduction, curve_breakpoints_m, sampling
        )
        for carriageway, curves in zip(carriageways, response_curves, strict=True)
    ]

    if any(not cases for cases in cases_per_carriageway):
        raise NoAdmissibleArrangementError(
            "no IRC:6 lane arrangement fits this cross-section; carriageway widths are "
            f"{[round(c.width_m, 3) for c in carriageways]} m"
        )

    return _combine_across_carriageways(cases_per_carriageway, adverse, apply_lane_reduction)


def _cases_for_one_carriageway(
    carriageway: Carriageway,
    curves: ResponseCurves,
    adverse: str,
    apply_lane_reduction: bool,
    curve_breakpoints_m: np.ndarray | None,
    sampling: SamplingSettings,
) -> list[CarriagewayCase]:
    """Places every admissible arrangement on one carriageway at its worst."""
    cases = []

    for arrangement in list_admissible_arrangements(carriageway.width_m):
        layout = fit_blocks_between(
            arrangement.lane_pattern, carriageway.left_m, carriageway.right_m
        )
        if layout is None:
            continue

        offsets_m = _sliding_offsets(arrangement, layout, curve_breakpoints_m, sampling)

        contributions = []
        centres_m = []
        for block, width_m, packed_left_m in zip(
            arrangement.lane_pattern,
            layout.block_widths_m,
            layout.packed_left_edges_m,
            strict=True,
        ):
            values, positions = _block_contribution(
                block,
                width_m,
                packed_left_m,
                offsets_m,
                curves,
                adverse,
                curve_breakpoints_m,
                sampling,
            )
            contributions.append(values)
            centres_m.append(positions)

        response, chosen = place_vehicles(contributions, adverse)
        reduction = (
            lane_reduction_factor(arrangement.design_lanes) if apply_lane_reduction else 1.0
        )

        cases.append(
            CarriagewayCase(
                lane_pattern=list(arrangement.lane_pattern),
                design_lanes=arrangement.design_lanes,
                sliding_room_m=layout.sliding_room_m,
                vehicle_centres_m=[
                    float(centres_m[b][chosen[b]]) for b in range(len(contributions))
                ],
                response_before_reduction=response,
                lane_reduction=reduction,
                response=response * reduction,
            )
        )

    return cases


def _sliding_offsets(
    arrangement: LaneArrangement,
    layout,
    curve_breakpoints_m: np.ndarray | None,
    sampling: SamplingSettings,
) -> np.ndarray:
    """Returns every sliding offset worth trying for this arrangement.

    An even spread across the sliding room, plus - and this is what makes the
    answer exact - every offset that puts some vehicle exactly on a bend in its
    response curve. Between two such offsets the total varies linearly, so the
    worst case is always at one of them.
    """
    room_m = layout.sliding_room_m
    steps = 1 if room_m < TOLERANCE_M else sampling.sliding_steps
    offsets = [np.linspace(0.0, room_m, steps)]

    if curve_breakpoints_m is not None and room_m >= TOLERANCE_M:
        breakpoints_m = np.asarray(curve_breakpoints_m, float)

        for block, width_m, packed_left_m in zip(
            arrangement.lane_pattern,
            layout.block_widths_m,
            layout.packed_left_edges_m,
            strict=True,
        ):
            for where_in_block_m in set(where_vehicle_sits_in_block(block, width_m)):
                lands_on_a_bend = breakpoints_m - packed_left_m - where_in_block_m
                offsets.append(
                    lands_on_a_bend[
                        (lands_on_a_bend >= -TOLERANCE_M)
                        & (lands_on_a_bend <= room_m + TOLERANCE_M)
                    ]
                )

    return np.unique(np.round(np.concatenate(offsets), ROUND_TO_DECIMALS))


def _block_contribution(
    block: str,
    block_width_m: float,
    packed_left_m: float,
    offsets_m: np.ndarray,
    curves: ResponseCurves,
    adverse: str,
    curve_breakpoints_m: np.ndarray | None,
    sampling: SamplingSettings,
) -> tuple[np.ndarray, np.ndarray]:
    """Returns what one block contributes at each sliding offset, and where its vehicle sits.

    A Class A vehicle is pinned to the centre of its lane block, so its position
    follows the sliding offset directly. A 70R vehicle also floats inside its
    zone, so it is re-positioned at every offset to whichever spot inside the
    zone is worse.
    """
    nearest_m, furthest_m = where_vehicle_sits_in_block(block, block_width_m)

    if nearest_m == furthest_m:
        centres_m = packed_left_m + offsets_m + nearest_m
        return _read_curve(curves[block], centres_m), centres_m

    pick_worst = np.argmax if adverse == "maximum" else np.argmin
    from_m = packed_left_m + offsets_m + nearest_m
    to_m = packed_left_m + offsets_m + furthest_m

    values = np.empty(len(offsets_m))
    centres_m = np.empty(len(offsets_m))

    for offset in range(len(offsets_m)):
        inside_the_zone_m = _positions_inside_zone(
            from_m[offset], to_m[offset], curve_breakpoints_m, sampling
        )
        responses = _read_curve(curves[block], inside_the_zone_m)
        worst = int(pick_worst(responses))
        values[offset] = responses[worst]
        centres_m[offset] = inside_the_zone_m[worst]

    return values, centres_m


def _positions_inside_zone(
    from_m: float,
    to_m: float,
    curve_breakpoints_m: np.ndarray | None,
    sampling: SamplingSettings,
) -> np.ndarray:
    """Returns where a floating vehicle is worth trying inside its zone."""
    positions = [
        np.array([from_m, to_m], float),
        np.linspace(from_m, to_m, sampling.float_steps),
    ]

    if curve_breakpoints_m is not None:
        breakpoints_m = np.asarray(curve_breakpoints_m, float)
        positions.append(
            breakpoints_m[
                (breakpoints_m >= from_m - TOLERANCE_M) & (breakpoints_m <= to_m + TOLERANCE_M)
            ]
        )

    return np.unique(np.round(np.concatenate(positions), ROUND_TO_DECIMALS))


def _read_curve(curve: Callable, positions_m: np.ndarray) -> np.ndarray:
    """Reads a response curve at several positions at once.

    Falls back to reading them one at a time for a curve that only accepts a
    single position, which hand-written curves in tests often do.
    """
    positions_m = np.asarray(positions_m, float)
    try:
        responses = np.asarray(curve(positions_m), float)
        if responses.shape == positions_m.shape:
            return responses
    except (TypeError, ValueError):
        pass

    return np.array([float(curve(position)) for position in positions_m])


def _combine_across_carriageways(
    cases_per_carriageway: Sequence[list[CarriagewayCase]],
    adverse: str,
    apply_lane_reduction: bool,
) -> list[TransversePlacement]:
    """Puts one case from each carriageway together, and ranks the combinations.

    Table 8 asks for the reduction on the total number of lanes loaded across the
    whole deck, not on each carriageway separately, so it is worked out again
    here on the combined lane count.
    """
    combinations = []

    for picks in itertools.product(*[range(len(cases)) for cases in cases_per_carriageway]):
        chosen = [
            cases_per_carriageway[carriageway][pick] for carriageway, pick in enumerate(picks)
        ]

        design_lanes = sum(case.design_lanes for case in chosen)
        before_reduction = sum(case.response_before_reduction for case in chosen)
        reduction = lane_reduction_factor(design_lanes) if apply_lane_reduction else 1.0

        combinations.append(
            TransversePlacement(
                response=before_reduction * reduction,
                response_before_reduction=before_reduction,
                lane_reduction=reduction,
                design_lanes=design_lanes,
                per_carriageway=chosen,
            )
        )

    worst_first = adverse == "maximum"
    combinations.sort(key=lambda placement: placement.response, reverse=worst_first)
    return combinations


def _walk_back_through_the_blocks(
    best_total: np.ndarray, where_the_block_to_the_left_sat: list[np.ndarray | None]
) -> list[int]:
    """Recovers which offset each block ended up at, working from the right."""
    at = int(np.argmax(best_total))
    chosen = [at]

    for block in range(len(where_the_block_to_the_left_sat) - 1, 0, -1):
        came_from = where_the_block_to_the_left_sat[block]
        assert came_from is not None
        at = int(came_from[at])
        chosen.append(at)

    chosen.reverse()
    return chosen


def _check_one_set_of_curves_per_carriageway(
    carriageways: Sequence[Carriageway], response_curves: Sequence[ResponseCurves]
) -> None:
    if len(response_curves) != len(carriageways):
        raise ValueError(
            f"there are {len(carriageways)} carriageways but {len(response_curves)} sets "
            "of response curves; a narrow carriageway carries its own residual UDL, so "
            "each one needs its own curves"
        )


def _adverse_sign(adverse: str) -> float:
    if adverse == "maximum":
        return 1.0
    if adverse == "minimum":
        return -1.0
    raise ValueError(f"adverse must be 'maximum' or 'minimum', got {adverse!r}")
