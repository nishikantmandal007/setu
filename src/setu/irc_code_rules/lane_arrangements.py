# Clause 204.3 and Tables 3, 6 and 6A - how vehicles may be arranged across a carriageway.
# An arrangement is an ordered list of lane blocks, left to right: a 70R vehicle takes an
# exclusive zone two design lanes wide, a Class A vehicle takes one lane block. Table 6A
# note (b) - a partly loaded carriageway is a load case of its own and can genuinely govern,
# since fewer loaded lanes attract a smaller Table 8 reduction - so list_admissible_arrangements
# returns subsets too, not only fully loaded arrangements.

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

# One Class A vehicle in one design lane.
CLASS_A_LANE = "class_a"

# One 70R vehicle in an exclusive zone two design lanes wide.
ZONE_70R = "zone_70r"

LanePattern = list[str]


# ---------------------------------------------------------------------------
# What the search returns
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaneArrangement:
    # One admissible way of filling a carriageway with vehicles.

    # The lane blocks, left to right.
    lane_pattern: LanePattern

    # Design lanes this arrangement consumes - a 70R zone consumes two.
    design_lanes: int

    # The narrowest carriageway this arrangement fits in.
    narrowest_carriageway_m: float

    # How far the whole arrangement can slide across the carriageway.
    sliding_room_m: float

    # True when this arrangement fills every design lane the carriageway has.
    is_fully_loaded: bool


@dataclass(frozen=True)
class BlockLayout:
    # Where each lane block may sit, once an arrangement is fitted to a carriageway.

    # Left edge of each block with the whole arrangement pushed as far left as it goes.
    packed_left_edges_m: list[float]

    block_widths_m: list[float]
    gaps_between_blocks_m: list[float]
    sliding_room_m: float


# ---------------------------------------------------------------------------
# Table 6 - how many design lanes a carriageway has
# ---------------------------------------------------------------------------


def count_design_lanes(carriageway_width_m: float) -> int:
    for width_from, width_up_to, design_lanes in DESIGN_LANES_BY_WIDTH:
        if width_from <= carriageway_width_m < width_up_to:
            return design_lanes

    if carriageway_width_m >= WIDEST_TABULATED_CARRIAGEWAY_M:
        return MOST_DESIGN_LANES
    return 0


def can_carry_vehicles(carriageway_width_m: float) -> bool:
    # IRC:5-2015 Clause 104.3 - below NARROWEST_LOADED_CARRIAGEWAY_M nothing is loaded.
    if count_design_lanes(carriageway_width_m) == 0:
        return False
    return carriageway_width_m >= NARROWEST_LOADED_CARRIAGEWAY_M


# ---------------------------------------------------------------------------
# Table 3 - fitting lane blocks into a carriageway
# ---------------------------------------------------------------------------


def class_a_gap(carriageway_width_m: float) -> float:
    # Above 6.10 m the gap between two adjacent Class A vehicles is the full 1.20 m. Below
    # that, on a narrow two-lane carriageway, the gap is whatever width is left once the
    # two lane blocks and their kerb clearances are taken out - Table 3 never lets it fall
    # under 0.40 m.
    if carriageway_width_m > CLASS_A_GAP_OPENS_UP_BELOW_M:
        return CLASS_A_VEHICLE_GAP_M

    # The 6 decimal places here is its own thing - not ROUND_TO_DECIMALS or
    # COORDINATE_DECIMALS - so leave it exactly as it is; changing it changes results.
    width_left_over_m = round(
        carriageway_width_m - TWO_CLASS_A_LANES_AND_KERB_CLEARANCES_M, 6
    )
    return max(SMALLEST_CLASS_A_GAP_M, min(CLASS_A_VEHICLE_GAP_M, width_left_over_m))


def block_widths(lane_pattern: LanePattern) -> list[float]:
    # A 70R zone is wider at the carriageway edge than between lanes, and narrower still
    # when it is alone - then it only has to hold the vehicle and its two clearances.
    widths_m = []

    for position, block in enumerate(lane_pattern):
        if block == CLASS_A_LANE:
            widths_m.append(CLASS_A_LANE_WIDTH_M)
        elif len(lane_pattern) == 1:
            widths_m.append(ZONE_70R_ALONE_M)
        elif position in (0, len(lane_pattern) - 1):
            widths_m.append(ZONE_70R_AT_EDGE_M)
        else:
            widths_m.append(ZONE_70R_INSIDE_M)

    return widths_m


def narrowest_carriageway_that_fits(
    lane_pattern: LanePattern, carriageway_width_m: float | None = None
) -> float:
    # Pass the actual carriageway width to pick up the reduced Table 3 gap on a narrow
    # two-lane carriageway; leave it out (None) to assume the full 1.20 m gap instead -
    # callers rely on both paths.
    if not lane_pattern:
        return 0.0

    width_m = sum(block_widths(lane_pattern))

    if lane_pattern[0] == CLASS_A_LANE:
        width_m += CLASS_A_KERB_CLEARANCE_M
    if lane_pattern[-1] == CLASS_A_LANE:
        width_m += CLASS_A_KERB_CLEARANCE_M

    gap_m = (
        CLASS_A_VEHICLE_GAP_M
        if carriageway_width_m is None
        else class_a_gap(carriageway_width_m)
    )
    for gap in gaps_between(lane_pattern, gap_m):
        width_m += gap

    return round(width_m, ROUND_TO_DECIMALS)


def gaps_between(lane_pattern: LanePattern, class_a_to_class_a_gap_m: float) -> list[float]:
    # Only two adjacent Class A vehicles need a gap. A 70R zone already carries its own
    # clearance inside its width, so nothing extra is needed beside it.
    gaps_m = []
    for left, right in zip(lane_pattern, lane_pattern[1:], strict=False):
        both_are_class_a = left == CLASS_A_LANE and right == CLASS_A_LANE
        gaps_m.append(class_a_to_class_a_gap_m if both_are_class_a else 0.0)
    return gaps_m


def fits_in_carriageway(lane_pattern: LanePattern, carriageway_width_m: float) -> bool:
    needed_m = narrowest_carriageway_that_fits(lane_pattern, carriageway_width_m)
    return needed_m <= carriageway_width_m + TOLERANCE_M


# ---------------------------------------------------------------------------
# Table 6A - which arrangements are admissible
# ---------------------------------------------------------------------------


def is_70r_placed_as_the_code_draws_it(lane_pattern: LanePattern) -> bool:
    # True when every 70R zone has a kerb or another 70R zone beside it: starting from a
    # 70R zone and stepping only through other 70R zones, you must be able to reach a
    # kerb. The heavy vehicles are worked inwards from the edges of the carriageway and
    # never boxed in behind a lane of Class A.
    #
    # That is how all thirteen combination drawings place them, without exception. A 70R
    # between two Class A lanes is never drawn, nor is a pair of them with Class A on both
    # sides - even at widths where either would fit.
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


def list_admissible_arrangements(
    carriageway_width_m: float, follow_combination_drawings: bool = True
) -> list[LaneArrangement]:
    # Every way this carriageway may be loaded, most heavily loaded first. An arrangement
    # is admissible when it fits between the kerbs and uses no more design lanes than
    # Table 6 gives the carriageway - a 70R zone uses two.
    #
    # Table 6A note (b): a partly loaded carriageway is a load case of its own, and it
    # genuinely governs - by more than a little. Fewer loaded lanes attract a smaller
    # Table 8 reduction, so a single 70R standing over a deck panel can be worse than every
    # lane of the bridge filled with Class A. That is why every arrangement is returned
    # here, not only the ones that fill every lane.
    #
    # follow_combination_drawings keeps to what the standard drawings show: a 70R always
    # reaches a kerb through 70R zones only, and never more than two of them on one
    # carriageway. Turning it off searches every arrangement the geometry permits, which is
    # the more conservative reading and can only make the answer more adverse.
    if not can_carry_vehicles(carriageway_width_m):
        return []

    design_lanes = count_design_lanes(carriageway_width_m)
    arrangements = []

    for blocks in range(1, design_lanes + 1):
        for pattern in product((CLASS_A_LANE, ZONE_70R), repeat=blocks):
            lanes_used = sum(2 if block == ZONE_70R else 1 for block in pattern)

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


def is_drawn_in_the_combinations(pattern: tuple[str, ...]) -> bool:
    if pattern.count(ZONE_70R) > MOST_70R_VEHICLES_DRAWN:
        return False
    return is_70r_placed_as_the_code_draws_it(list(pattern))


def describe_arrangement(
    pattern: tuple[str, ...], carriageway_width_m: float, *, is_fully_loaded: bool
) -> LaneArrangement:
    narrowest_m = narrowest_carriageway_that_fits(list(pattern), carriageway_width_m)

    return LaneArrangement(
        lane_pattern=list(pattern),
        design_lanes=sum(2 if block == ZONE_70R else 1 for block in pattern),
        narrowest_carriageway_m=narrowest_m,
        sliding_room_m=round(carriageway_width_m - narrowest_m, ROUND_TO_DECIMALS),
        is_fully_loaded=is_fully_loaded,
    )


# ---------------------------------------------------------------------------
# Placing blocks across the carriageway
# ---------------------------------------------------------------------------


def fit_blocks_between(
    lane_pattern: LanePattern, carriageway_left_m: float, carriageway_right_m: float
) -> BlockLayout | None:
    # Where each lane block sits when the arrangement is pushed fully left, or None when
    # the arrangement does not fit between these two edges. Each block may then slide right
    # by anything from zero to sliding_room_m, and the clearances stay satisfied as long as
    # no block overtakes the one to its right.
    carriageway_width_m = carriageway_right_m - carriageway_left_m
    if not fits_in_carriageway(lane_pattern, carriageway_width_m):
        return None

    widths_m = block_widths(lane_pattern)
    gaps_m = gaps_between(lane_pattern, class_a_gap(carriageway_width_m))
    kerb_clearance_m = kerb_clearance_at_each_end(lane_pattern)

    # Edges are rounded as they are built so the candidate grids downstream compare equal
    # no matter what order the additions happened in.
    packed_left_edges_m = []
    edge_m = carriageway_left_m + kerb_clearance_m[0]
    for width_m, gap_m in zip_longest(widths_m, gaps_m, fillvalue=0.0):
        packed_left_edges_m.append(round(edge_m, ROUND_TO_DECIMALS))
        edge_m += width_m
        edge_m += gap_m

    room_m = carriageway_right_m - kerb_clearance_m[1] - edge_m

    return BlockLayout(
        packed_left_edges_m=packed_left_edges_m,
        block_widths_m=widths_m,
        gaps_between_blocks_m=gaps_m,
        sliding_room_m=max(round(room_m, ROUND_TO_DECIMALS), 0.0),
    )


def kerb_clearance_at_each_end(lane_pattern: LanePattern) -> tuple[float, float]:
    # Only Class A needs a kerb clearance here - a 70R zone already contains its own
    # clearance inside its width.
    at_left = CLASS_A_KERB_CLEARANCE_M if lane_pattern[0] == CLASS_A_LANE else 0.0
    at_right = CLASS_A_KERB_CLEARANCE_M if lane_pattern[-1] == CLASS_A_LANE else 0.0
    return at_left, at_right


def where_vehicle_sits_in_block(block: str, block_width_m: float) -> tuple[float, float]:
    # How far the vehicle centreline may sit from the block's left edge, nearest bound
    # first. A Class A vehicle is pinned to the centre of its lane block, so the two
    # numbers are equal. A 70R vehicle floats anywhere inside its zone that keeps its
    # clearance from both boundaries, so they differ.
    if block == CLASS_A_LANE:
        half_lane_m = CLASS_A_LANE_WIDTH_M / 2.0
        return half_lane_m, half_lane_m

    nearest_m = VEHICLE_70R_CLEARANCE_M + VEHICLE_70R_WIDTH_M / 2.0
    return nearest_m, block_width_m - nearest_m
