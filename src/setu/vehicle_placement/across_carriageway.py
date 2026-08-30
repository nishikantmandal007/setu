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

ResponseCurves = Mapping[str, Callable[[np.ndarray], np.ndarray]]

NO_LANE_REDUCTION = 1.0


@dataclass(frozen=True)
class CarriagewayCase:
    lane_pattern: list[str]
    design_lanes: int
    sliding_room_m: float
    vehicle_centres_m: list[float]
    response_before_reduction: float
    lane_reduction: float
    response: float


@dataclass(frozen=True)
class TransversePlacement:
    response: float
    response_before_reduction: float
    lane_reduction: float
    design_lanes: int
    per_carriageway: list[CarriagewayCase]


@dataclass(frozen=True)
class TransverseSearch:
    adverse: str
    sampling: SamplingSettings
    curve_breakpoints_m: np.ndarray | None
    apply_lane_reduction: bool
    follow_combination_drawings: bool

    def reduction_for(self, design_lanes: int) -> float:
        if not self.apply_lane_reduction:
            return NO_LANE_REDUCTION
        return lane_reduction_factor(design_lanes)


def find_worst_placement(
    carriageways: Sequence[Carriageway],
    response_curves: Sequence[ResponseCurves],
    adverse: str = "maximum",
    apply_lane_reduction: bool = True,
    curve_breakpoints_m: np.ndarray | None = None,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
    follow_combination_drawings: bool = True,
) -> list[TransversePlacement]:
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
        widths_m = [round(carriageway.width_m, 3) for carriageway in carriageways]
        raise NoAdmissibleArrangementError(
            "no IRC:6 lane arrangement fits this cross-section; carriageway widths are "
            f"{widths_m} m"
        )

    return combine_across_carriageways(cases_per_carriageway, search)


def cases_for_one_carriageway(
    carriageway: Carriageway, curves: ResponseCurves, search: TransverseSearch
) -> list[CarriagewayCase]:
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
        for block, width_m, packed_left_m in walk_the_blocks(arrangement, layout):
            values, positions = block_contribution(
                block, width_m, packed_left_m, offsets_m, curves, search
            )
            contributions.append(values)
            centres_m.append(positions)

        response, chosen = place_vehicles(contributions, search.adverse)
        reduction = search.reduction_for(arrangement.design_lanes)

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


def walk_the_blocks(
    arrangement: LaneArrangement, layout: BlockLayout
) -> list[tuple[str, float, float]]:
    return list(
        zip(
            arrangement.lane_pattern,
            layout.block_widths_m,
            layout.packed_left_edges_m,
            strict=True,
        )
    )


def sliding_offsets(
    arrangement: LaneArrangement, layout: BlockLayout, search: TransverseSearch
) -> np.ndarray:
    # Including every offset that lands a vehicle on a bend in its curve is what makes
    # the answer exact: between two of them the total is linear.
    room_m = layout.sliding_room_m
    has_nowhere_to_slide = room_m < TOLERANCE_M

    steps = 1 if has_nowhere_to_slide else search.sampling.sliding_offsets_to_try
    worth_trying = [np.linspace(0.0, room_m, steps)]

    if search.curve_breakpoints_m is not None and not has_nowhere_to_slide:
        breakpoints_m = np.asarray(search.curve_breakpoints_m, float)

        for block, width_m, packed_left_m in walk_the_blocks(arrangement, layout):
            for where_in_block_m in set(where_vehicle_sits_in_block(block, width_m)):
                lands_on_a_bend = breakpoints_m - packed_left_m - where_in_block_m
                is_within_the_sliding_room = (lands_on_a_bend >= -TOLERANCE_M) & (
                    lands_on_a_bend <= room_m + TOLERANCE_M
                )
                worth_trying.append(lands_on_a_bend[is_within_the_sliding_room])

    return np.unique(np.round(np.concatenate(worth_trying), ROUND_TO_DECIMALS))


def block_contribution(
    block: str,
    block_width_m: float,
    packed_left_m: float,
    offsets_m: np.ndarray,
    curves: ResponseCurves,
    search: TransverseSearch,
) -> tuple[np.ndarray, np.ndarray]:
    nearest_m, furthest_m = where_vehicle_sits_in_block(block, block_width_m)
    is_pinned_to_the_middle_of_its_lane = nearest_m == furthest_m

    if is_pinned_to_the_middle_of_its_lane:
        centres_m = packed_left_m + offsets_m + nearest_m
        return read_curve(curves[block], centres_m), centres_m

    return worst_spot_inside_the_zone(
        block, packed_left_m, nearest_m, furthest_m, offsets_m, curves, search
    )


def worst_spot_inside_the_zone(
    block: str,
    packed_left_m: float,
    nearest_m: float,
    furthest_m: float,
    offsets_m: np.ndarray,
    curves: ResponseCurves,
    search: TransverseSearch,
) -> tuple[np.ndarray, np.ndarray]:
    zone_from_m = packed_left_m + offsets_m + nearest_m
    zone_to_m = packed_left_m + offsets_m + furthest_m

    values = np.empty(len(offsets_m))
    centres_m = np.empty(len(offsets_m))

    for i, (from_m, to_m) in enumerate(zip(zone_from_m, zone_to_m, strict=True)):
        inside_the_zone_m = positions_inside_zone(
            from_m, to_m, search.curve_breakpoints_m, search.sampling
        )
        responses = read_curve(curves[block], inside_the_zone_m)

        worst = int(index_of_worst(responses, search.adverse))
        values[i] = responses[worst]
        centres_m[i] = inside_the_zone_m[worst]

    return values, centres_m


def combine_across_carriageways(
    cases_per_carriageway: Sequence[list[CarriagewayCase]], search: TransverseSearch
) -> list[TransversePlacement]:
    # Table 8 reduces on the lanes loaded across the whole deck, not on each carriageway,
    # so the reduction is worked out again here on the combined lane count.
    combinations = []

    for chosen in itertools.product(*cases_per_carriageway):
        design_lanes = sum(case.design_lanes for case in chosen)
        before_reduction = sum(case.response_before_reduction for case in chosen)
        reduction = search.reduction_for(design_lanes)

        combinations.append(
            TransversePlacement(
                response=before_reduction * reduction,
                response_before_reduction=before_reduction,
                lane_reduction=reduction,
                design_lanes=design_lanes,
                per_carriageway=list(chosen),
            )
        )

    combinations.sort(
        key=lambda placement: placement.response, reverse=is_worst_first(search.adverse)
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
