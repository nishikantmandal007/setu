# Where across the width the vehicles do the most damage.
#
# Every design lane of every carriageway carries a vehicle at the same time, and they all
# have to be positioned together, because the code fixes how close they may come to each
# other and to the kerb. sliding_blocks.py holds the pure dynamic program over sliding
# offsets - see it for the derivation that collapses every clearance rule into "the sliding
# amounts never decrease left to right". This module works out what each admissible
# arrangement contributes at every offset the search tries, one carriageway at a time (see
# curve_reading.py for how a block's response curve is evaluated), and then combines one
# case from each carriageway into a ranked list of placements for the whole deck.
#
# Each carriageway gets its own ResponseCurves mapping, because a narrow carriageway
# carries its own residual UDL and so has its own curves - the two cannot share one map.
#
# The DP answer is exact rather than merely finely sampled, because the sliding offsets
# tried (see sliding_offsets below) include every offset at which any block's response
# curve bends. Between two such offsets the total is linear, so nothing can hide in the
# gaps.

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from ..adverse_direction import index_of_worst, is_worst_first
from ..deck_cross_section import Carriageway
from ..errors import NoAdmissibleArrangementError
from ..irc_code_rules.code_tables import ROUND_TO_DECIMALS, TOLERANCE_M
from ..irc_code_rules.lane_arrangements import (
    BlockLayout,
    LaneArrangement,
    fit_blocks_between,
    list_admissible_arrangements,
    where_vehicle_sits_in_block,
)
from ..irc_code_rules.lane_reduction import lane_reduction_factor
from ..sampling import DEFAULT_SAMPLING, SamplingSettings
from .curve_reading import positions_inside_zone, read_curve
from .sliding_blocks import place_vehicles

# One curve per kind of lane block. Each returns the response of one vehicle of that kind,
# centred at a given position across the deck.
ResponseCurves = Mapping[str, Callable[[np.ndarray], np.ndarray]]


@dataclass(frozen=True)
class CarriagewayCase:
    # One arrangement, placed at its worst, on one carriageway.
    lane_pattern: list[str]
    design_lanes: int
    sliding_room_m: float

    # Where each vehicle's centreline ended up, left to right.
    vehicle_centres_m: list[float]

    response_before_reduction: float
    lane_reduction: float
    response: float


@dataclass(frozen=True)
class TransversePlacement:
    # One way of loading every carriageway at once, and what it does.
    response: float
    response_before_reduction: float
    lane_reduction: float

    # Design lanes loaded across the whole deck.
    design_lanes: int

    per_carriageway: list[CarriagewayCase]


@dataclass(frozen=True)
class TransverseSearch:
    # Everything about how the sweep is being run, carried as one thing so the inner layers
    # stop taking half a dozen positional arguments each.
    adverse: str
    sampling: SamplingSettings
    curve_breakpoints_m: np.ndarray | None
    apply_lane_reduction: bool
    follow_combination_drawings: bool


def find_worst_placement(
    carriageways: Sequence[Carriageway],
    response_curves: Sequence[ResponseCurves],
    adverse: str = "maximum",
    apply_lane_reduction: bool = True,
    curve_breakpoints_m: np.ndarray | None = None,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
    follow_combination_drawings: bool = True,
) -> list[TransversePlacement]:
    # Returns every way of loading the deck, worst first.
    #
    # One ResponseCurves mapping per carriageway, because a narrow carriageway carries its
    # own residual UDL and so has its own curves.
    #
    # Pass curve_breakpoints_m - the positions the curves were sampled at - to make the
    # answer exact rather than merely finely sampled.
    check_one_set_of_curves_per_carriageway(carriageways, response_curves)

    search = TransverseSearch(
        adverse=adverse,
        sampling=sampling,
        curve_breakpoints_m=curve_breakpoints_m,
        apply_lane_reduction=apply_lane_reduction,
        follow_combination_drawings=follow_combination_drawings,
    )

    cases_per_carriageway = [
        cases_for_one_carriageway(carriageway, curves, search)
        for carriageway, curves in zip(carriageways, response_curves, strict=True)
    ]

    if any(not cases for cases in cases_per_carriageway):
        raise NoAdmissibleArrangementError(
            "no IRC:6 lane arrangement fits this cross-section; carriageway widths are "
            f"{[round(carriageway.width_m, 3) for carriageway in carriageways]} m"
        )

    return combine_across_carriageways(cases_per_carriageway, search)


def cases_for_one_carriageway(
    carriageway: Carriageway,
    curves: ResponseCurves,
    search: TransverseSearch,
) -> list[CarriagewayCase]:
    # Places every admissible arrangement on one carriageway at its worst.
    cases = []

    for arrangement in list_admissible_arrangements(
        carriageway.width_m, search.follow_combination_drawings
    ):
        layout = fit_blocks_between(
            arrangement.lane_pattern, carriageway.left_m, carriageway.right_m
        )
        if layout is None:
            continue

        offsets_m = sliding_offsets(arrangement, layout, search)

        contributions = []
        centres_m = []
        for block, width_m, packed_left_m in zip(
            arrangement.lane_pattern,
            layout.block_widths_m,
            layout.packed_left_edges_m,
            strict=True,
        ):
            values, positions = block_contribution(
                block, width_m, packed_left_m, offsets_m, curves, search
            )
            contributions.append(values)
            centres_m.append(positions)

        response, chosen = place_vehicles(contributions, search.adverse)
        reduction = (
            lane_reduction_factor(arrangement.design_lanes)
            if search.apply_lane_reduction
            else 1.0
        )

        cases.append(
            CarriagewayCase(
                lane_pattern=list(arrangement.lane_pattern),
                design_lanes=arrangement.design_lanes,
                sliding_room_m=layout.sliding_room_m,
                vehicle_centres_m=[
                    float(centre_m[offset])
                    for centre_m, offset in zip(centres_m, chosen, strict=True)
                ],
                response_before_reduction=response,
                lane_reduction=reduction,
                response=response * reduction,
            )
        )

    return cases


def sliding_offsets(
    arrangement: LaneArrangement,
    layout: BlockLayout,
    search: TransverseSearch,
) -> np.ndarray:
    # Returns every sliding offset worth trying for this arrangement.
    #
    # An even spread across the sliding room, plus - and this is what makes the answer
    # exact - every offset that puts some vehicle exactly on a bend in its response curve.
    # Between two such offsets the total varies linearly, so the worst case is always at
    # one of them.
    room_m = layout.sliding_room_m
    steps = 1 if room_m < TOLERANCE_M else search.sampling.sliding_steps
    offsets = [np.linspace(0.0, room_m, steps)]

    if search.curve_breakpoints_m is not None and room_m >= TOLERANCE_M:
        breakpoints_m = np.asarray(search.curve_breakpoints_m, float)

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


def block_contribution(
    block: str,
    block_width_m: float,
    packed_left_m: float,
    offsets_m: np.ndarray,
    curves: ResponseCurves,
    search: TransverseSearch,
) -> tuple[np.ndarray, np.ndarray]:
    # Returns what one block contributes at each sliding offset, and where its vehicle sits.
    #
    # A Class A vehicle is pinned to the centre of its lane block, so its position follows
    # the sliding offset directly. A 70R vehicle floats inside its zone instead, so it is
    # re-positioned at every offset to whichever spot inside the zone is worse.
    nearest_m, furthest_m = where_vehicle_sits_in_block(block, block_width_m)

    if nearest_m == furthest_m:
        centres_m = packed_left_m + offsets_m + nearest_m
        return read_curve(curves[block], centres_m), centres_m

    from_m = packed_left_m + offsets_m + nearest_m
    to_m = packed_left_m + offsets_m + furthest_m

    values = np.empty(len(offsets_m))
    centres_m = np.empty(len(offsets_m))

    for i, (zone_from_m, zone_to_m) in enumerate(zip(from_m, to_m, strict=True)):
        inside_the_zone_m = positions_inside_zone(
            zone_from_m, zone_to_m, search.curve_breakpoints_m, search.sampling
        )
        responses = read_curve(curves[block], inside_the_zone_m)
        worst = int(index_of_worst(responses, search.adverse))
        values[i] = responses[worst]
        centres_m[i] = inside_the_zone_m[worst]

    return values, centres_m


def combine_across_carriageways(
    cases_per_carriageway: Sequence[list[CarriagewayCase]], search: TransverseSearch
) -> list[TransversePlacement]:
    # Puts one case from each carriageway together, and ranks the combinations.
    #
    # Table 8 asks for the reduction on the total number of lanes loaded across the whole
    # deck, not on each carriageway separately, so it is worked out again here on the
    # combined lane count.
    combinations = []

    for picks in itertools.product(*[range(len(cases)) for cases in cases_per_carriageway]):
        chosen = [
            cases[pick] for cases, pick in zip(cases_per_carriageway, picks, strict=True)
        ]

        design_lanes = sum(case.design_lanes for case in chosen)
        before_reduction = sum(case.response_before_reduction for case in chosen)
        reduction = (
            lane_reduction_factor(design_lanes) if search.apply_lane_reduction else 1.0
        )

        combinations.append(
            TransversePlacement(
                response=before_reduction * reduction,
                response_before_reduction=before_reduction,
                lane_reduction=reduction,
                design_lanes=design_lanes,
                per_carriageway=chosen,
            )
        )

    combinations.sort(
        key=lambda placement: placement.response,
        reverse=is_worst_first(search.adverse),
    )
    return combinations


def check_one_set_of_curves_per_carriageway(
    carriageways: Sequence[Carriageway], response_curves: Sequence[ResponseCurves]
) -> None:
    if len(response_curves) != len(carriageways):
        raise ValueError(
            f"there are {len(carriageways)} carriageways but {len(response_curves)} sets "
            "of response curves; a narrow carriageway carries its own residual UDL, so "
            "each one needs its own curves"
        )
