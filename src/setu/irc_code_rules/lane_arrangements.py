from __future__ import annotations

from dataclasses import dataclass
from itertools import product, zip_longest

from .code_tables import (
    CLASS_A_GAP_OPENS_UP_BELOW_M,
    CLASS_A_KERB_CLEARANCE_M,
    CLASS_A_LANE_WIDTH_M,
    CLASS_A_VEHICLE_GAP_M,
    DESIGN_LANES_BY_WIDTH,
    MOST_70R_VEHICLES_DRAWN,
    MOST_DESIGN_LANES,
    NARROWEST_LOADED_CARRIAGEWAY_M,
    ROUND_TO_DECIMALS,
    SMALLEST_CLASS_A_GAP_M,
    TOLERANCE_M,
    TWO_CLASS_A_LANES_AND_KERB_CLEARANCES_M,
    VEHICLE_70R_CLEARANCE_M,
    VEHICLE_70R_WIDTH_M,
    WIDEST_TABULATED_CARRIAGEWAY_M,
    ZONE_70R_ALONE_M,
    ZONE_70R_AT_EDGE_M,
    ZONE_70R_INSIDE_M,
)

CLASS_A_LANE = "class_a"
ZONE_70R = "zone_70r"

LanePattern = list[str]

DESIGN_LANES_PER_70R_ZONE = 2
DESIGN_LANES_PER_CLASS_A_LANE = 1

NO_GAP_NEEDED_M = 0.0
NOT_LOADED_AT_ALL = 0

# Kept at 6 places on purpose - it is not ROUND_TO_DECIMALS, and changing it changes results.
LEFT_OVER_WIDTH_DECIMALS = 6


@dataclass(frozen=True)
class LaneArrangement:
    lane_pattern: LanePattern
    design_lanes: int
    narrowest_carriageway_m: float
    sliding_room_m: float
    is_fully_loaded: bool


@dataclass(frozen=True)
class BlockLayout:
    packed_left_edges_m: list[float]
    block_widths_m: list[float]
    gaps_between_blocks_m: list[float]
    sliding_room_m: float


def design_lanes_used_by(lane_pattern: LanePattern | tuple[str, ...]) -> int:
    return sum(
        DESIGN_LANES_PER_70R_ZONE if block == ZONE_70R else DESIGN_LANES_PER_CLASS_A_LANE
        for block in lane_pattern
    )


def count_design_lanes(carriageway_width_m: float) -> int:
    for width_from, width_up_to, design_lanes in DESIGN_LANES_BY_WIDTH:
        if width_from <= carriageway_width_m < width_up_to:
            return design_lanes

    if carriageway_width_m >= WIDEST_TABULATED_CARRIAGEWAY_M:
        return MOST_DESIGN_LANES
    return NOT_LOADED_AT_ALL


def can_carry_vehicles(carriageway_width_m: float) -> bool:
    if count_design_lanes(carriageway_width_m) == NOT_LOADED_AT_ALL:
        return False
    return carriageway_width_m >= NARROWEST_LOADED_CARRIAGEWAY_M


def class_a_gap(carriageway_width_m: float) -> float:
    if carriageway_width_m > CLASS_A_GAP_OPENS_UP_BELOW_M:
        return CLASS_A_VEHICLE_GAP_M

    width_left_over_m = round(
        carriageway_width_m - TWO_CLASS_A_LANES_AND_KERB_CLEARANCES_M,
        LEFT_OVER_WIDTH_DECIMALS,
    )
    return max(SMALLEST_CLASS_A_GAP_M, min(CLASS_A_VEHICLE_GAP_M, width_left_over_m))


def block_widths(lane_pattern: LanePattern) -> list[float]:
    widths_m = []

    for position, block in enumerate(lane_pattern):
        is_at_an_edge = position in (0, len(lane_pattern) - 1)

        if block == CLASS_A_LANE:
            widths_m.append(CLASS_A_LANE_WIDTH_M)
        elif len(lane_pattern) == 1:
            widths_m.append(ZONE_70R_ALONE_M)
        elif is_at_an_edge:
            widths_m.append(ZONE_70R_AT_EDGE_M)
        else:
            widths_m.append(ZONE_70R_INSIDE_M)

    return widths_m


def gaps_between(lane_pattern: LanePattern, class_a_to_class_a_gap_m: float) -> list[float]:
    gaps_m = []
    for left, right in zip(lane_pattern, lane_pattern[1:], strict=False):
        both_are_class_a = left == CLASS_A_LANE and right == CLASS_A_LANE
        gaps_m.append(class_a_to_class_a_gap_m if both_are_class_a else NO_GAP_NEEDED_M)
    return gaps_m


def kerb_clearance_at_each_end(lane_pattern: LanePattern) -> tuple[float, float]:
    at_left = CLASS_A_KERB_CLEARANCE_M if lane_pattern[0] == CLASS_A_LANE else 0.0
    at_right = CLASS_A_KERB_CLEARANCE_M if lane_pattern[-1] == CLASS_A_LANE else 0.0
    return at_left, at_right


def narrowest_carriageway_that_fits(
    lane_pattern: LanePattern, carriageway_width_m: float | None = None
) -> float:
    if not lane_pattern:
        return 0.0

    at_left_m, at_right_m = kerb_clearance_at_each_end(lane_pattern)

    if carriageway_width_m is None:
        gap_m = CLASS_A_VEHICLE_GAP_M
    else:
        gap_m = class_a_gap(carriageway_width_m)

    width_m = (
        sum(block_widths(lane_pattern))
        + at_left_m
        + at_right_m
        + sum(gaps_between(lane_pattern, gap_m))
    )
    return round(width_m, ROUND_TO_DECIMALS)


def fits_in_carriageway(lane_pattern: LanePattern, carriageway_width_m: float) -> bool:
    needed_m = narrowest_carriageway_that_fits(lane_pattern, carriageway_width_m)
    return needed_m <= carriageway_width_m + TOLERANCE_M


def is_70r_placed_as_the_code_draws_it(lane_pattern: LanePattern) -> bool:
    # Every 70R zone must reach a kerb through 70R zones only, which is how all thirteen
    # combination drawings place them.
    last = len(lane_pattern) - 1

    for position, block in enumerate(lane_pattern):
        if block != ZONE_70R:
            continue

        reaches_the_left_kerb = all(
            lane_pattern[nearer] == ZONE_70R for nearer in range(position)
        )
        reaches_the_right_kerb = all(
            lane_pattern[further] == ZONE_70R for further in range(position + 1, last + 1)
        )

        if not (reaches_the_left_kerb or reaches_the_right_kerb):
            return False

    return True


def is_drawn_in_the_combinations(pattern: tuple[str, ...]) -> bool:
    if pattern.count(ZONE_70R) > MOST_70R_VEHICLES_DRAWN:
        return False
    return is_70r_placed_as_the_code_draws_it(list(pattern))


def list_admissible_arrangements(
    carriageway_width_m: float, follow_combination_drawings: bool = True
) -> list[LaneArrangement]:
    # Table 6A note (b): partly loaded carriageways are returned too, because fewer loaded
    # lanes attract a smaller Table 8 reduction and can genuinely govern.
    if not can_carry_vehicles(carriageway_width_m):
        return []

    design_lanes = count_design_lanes(carriageway_width_m)
    arrangements = []

    for how_many_blocks in range(1, design_lanes + 1):
        for pattern in product((CLASS_A_LANE, ZONE_70R), repeat=how_many_blocks):
            lanes_used = design_lanes_used_by(pattern)

            if lanes_used > design_lanes:
                continue
            if not fits_in_carriageway(list(pattern), carriageway_width_m):
                continue
            if follow_combination_drawings and not is_drawn_in_the_combinations(pattern):
                continue

            arrangements.append(
                describe_arrangement(
                    pattern,
                    carriageway_width_m,
                    is_fully_loaded=lanes_used == design_lanes,
                )
            )

    arrangements.sort(
        key=lambda arrangement: (-arrangement.design_lanes, arrangement.lane_pattern)
    )
    return arrangements


def describe_arrangement(
    pattern: tuple[str, ...], carriageway_width_m: float, *, is_fully_loaded: bool
) -> LaneArrangement:
    narrowest_m = narrowest_carriageway_that_fits(list(pattern), carriageway_width_m)

    return LaneArrangement(
        lane_pattern=list(pattern),
        design_lanes=design_lanes_used_by(pattern),
        narrowest_carriageway_m=narrowest_m,
        sliding_room_m=round(carriageway_width_m - narrowest_m, ROUND_TO_DECIMALS),
        is_fully_loaded=is_fully_loaded,
    )


def fit_blocks_between(
    lane_pattern: LanePattern, carriageway_left_m: float, carriageway_right_m: float
) -> BlockLayout | None:
    carriageway_width_m = carriageway_right_m - carriageway_left_m
    if not fits_in_carriageway(lane_pattern, carriageway_width_m):
        return None

    widths_m = block_widths(lane_pattern)
    gaps_m = gaps_between(lane_pattern, class_a_gap(carriageway_width_m))
    at_left_m, at_right_m = kerb_clearance_at_each_end(lane_pattern)

    packed_left_edges_m = []
    edge_m = carriageway_left_m + at_left_m
    for width_m, gap_m in zip_longest(widths_m, gaps_m, fillvalue=NO_GAP_NEEDED_M):
        packed_left_edges_m.append(round(edge_m, ROUND_TO_DECIMALS))
        edge_m += width_m
        edge_m += gap_m

    room_m = carriageway_right_m - at_right_m - edge_m

    return BlockLayout(
        packed_left_edges_m=packed_left_edges_m,
        block_widths_m=widths_m,
        gaps_between_blocks_m=gaps_m,
        sliding_room_m=max(round(room_m, ROUND_TO_DECIMALS), 0.0),
    )


def where_vehicle_sits_in_block(block: str, block_width_m: float) -> tuple[float, float]:
    # A Class A vehicle is pinned to the middle of its lane, so both bounds are equal.
    # A 70R vehicle floats anywhere inside its zone that keeps its clearance.
    if block == CLASS_A_LANE:
        half_lane_m = CLASS_A_LANE_WIDTH_M / 2.0
        return half_lane_m, half_lane_m

    nearest_m = VEHICLE_70R_CLEARANCE_M + VEHICLE_70R_WIDTH_M / 2.0
    return nearest_m, block_width_m - nearest_m
