"""Clause 204.3 and Tables 3, 6 and 6A - how vehicles may be arranged across a carriageway.

A carriageway of a given width has a number of design lanes (Table 6), and those
lanes may be filled by Class A vehicles and 70R vehicles in a number of ways
(Table 6A). Each way is an *arrangement*.

An arrangement is an ordered list of lane blocks read left to right, so
`['zone_70r', 'class_a']` means a 70R zone at the left of the carriageway with a
Class A lane to its right. A 70R vehicle needs two design lanes and gets an
exclusive zone; a Class A vehicle gets one lane block.

Every arrangement also has to be searched with *fewer* vehicles than it allows,
because a partly loaded bridge sometimes governs. That is Table 6A note (b), and
it is why `list_admissible_arrangements` returns subsets as well as full ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .code_tables import (
    CLASS_A_GAP_OPENS_UP_BELOW_M,
    CLASS_A_KERB_CLEARANCE_M,
    CLASS_A_LANE_WIDTH_M,
    CLASS_A_VEHICLE_GAP_M,
    DESIGN_LANES_BY_WIDTH,
    MOST_DESIGN_LANES,
    NARROWEST_LOADED_CARRIAGEWAY_M,
    ROUND_TO_DECIMALS,
    SMALLEST_CLASS_A_GAP_M,
    TOLERANCE_M,
    VEHICLE_70R_CLEARANCE_M,
    VEHICLE_70R_WIDTH_M,
    WIDEST_TABULATED_CARRIAGEWAY_M,
    ZONE_70R_ALONE_M,
    ZONE_70R_AT_EDGE_M,
    ZONE_70R_INSIDE_M,
)

CLASS_A_LANE = "class_a"
"""One Class A vehicle in one design lane."""

ZONE_70R = "zone_70r"
"""One 70R vehicle in an exclusive zone two design lanes wide."""

LanePattern = list[str]


@dataclass(frozen=True)
class LaneArrangement:
    """One admissible way of filling a carriageway with vehicles."""

    lane_pattern: LanePattern
    """The lane blocks, left to right."""

    design_lanes: int
    """Design lanes this arrangement consumes. A 70R zone consumes two."""

    narrowest_carriageway_m: float
    """The narrowest carriageway this arrangement fits in."""

    sliding_room_m: float
    """How far the whole arrangement can slide across the carriageway."""

    is_fully_loaded: bool
    """True when this arrangement fills every design lane the carriageway has."""


@dataclass(frozen=True)
class BlockLayout:
    """Where each lane block may sit, once an arrangement is fitted to a carriageway."""

    packed_left_edges_m: list[float]
    """Left edge of each block with the whole arrangement pushed as far left as it goes."""

    block_widths_m: list[float]
    gaps_between_blocks_m: list[float]
    sliding_room_m: float


def count_design_lanes(carriageway_width_m: float) -> int:
    """Returns the number of design lanes for a clear carriageway width, from Table 6."""
    for width_from, width_up_to, design_lanes in DESIGN_LANES_BY_WIDTH:
        if width_from <= carriageway_width_m < width_up_to:
            return design_lanes

    if carriageway_width_m >= WIDEST_TABULATED_CARRIAGEWAY_M:
        return MOST_DESIGN_LANES
    return 0


def can_carry_vehicles(carriageway_width_m: float) -> bool:
    """Returns True when this carriageway is wide enough to be loaded at all."""
    if count_design_lanes(carriageway_width_m) == 0:
        return False
    return carriageway_width_m >= NARROWEST_LOADED_CARRIAGEWAY_M


def class_a_gap(carriageway_width_m: float) -> float:
    """Returns the Table 3 gap between two adjacent Class A vehicles.

    Above 6.10 m the gap is the full 1.20 m. On a narrower two-lane carriageway
    the gap is simply whatever width is left once the two 2.30 m lane blocks and
    their two 0.15 m kerb clearances have been taken out - which is why the
    subtraction below is 4.90 m. Table 3 never lets it fall under 0.40 m.
    """
    if carriageway_width_m > CLASS_A_GAP_OPENS_UP_BELOW_M:
        return CLASS_A_VEHICLE_GAP_M

    width_left_over_m = round(carriageway_width_m - 4.90, 6)
    return max(SMALLEST_CLASS_A_GAP_M, min(CLASS_A_VEHICLE_GAP_M, width_left_over_m))


def block_widths(lane_pattern: LanePattern) -> list[float]:
    """Returns the width of each lane block in this pattern.

    A 70R zone is wider at the edge of the carriageway than between other lanes,
    and wider still is not needed when it is the only thing on the carriageway -
    then it only has to hold the vehicle and its two clearances.
    """
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
    """Returns the narrowest carriageway this pattern fits in.

    Pass the actual carriageway width to pick up the reduced Table 3 gap on a
    narrow two-lane carriageway; leave it out to assume the full 1.20 m gap.
    """
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
    for gap in _gaps_between(lane_pattern, gap_m):
        width_m += gap

    return round(width_m, ROUND_TO_DECIMALS)


def _gaps_between(lane_pattern: LanePattern, class_a_to_class_a_gap_m: float) -> list[float]:
    """Returns the gap required after each block except the last.

    Only two adjacent Class A vehicles need a gap. A 70R zone already carries its
    own clearance inside its width, so nothing extra is required beside it.
    """
    gaps_m = []
    for left, right in zip(lane_pattern, lane_pattern[1:], strict=False):
        both_are_class_a = left == CLASS_A_LANE and right == CLASS_A_LANE
        gaps_m.append(class_a_to_class_a_gap_m if both_are_class_a else 0.0)
    return gaps_m


def fits_in_carriageway(lane_pattern: LanePattern, carriageway_width_m: float) -> bool:
    """Returns True when this pattern fits inside a carriageway of this width."""
    needed_m = narrowest_carriageway_that_fits(lane_pattern, carriageway_width_m)
    return needed_m <= carriageway_width_m + TOLERANCE_M


def list_admissible_arrangements(carriageway_width_m: float) -> list[LaneArrangement]:
    """Returns every way this carriageway may be loaded, most heavily loaded first.

    An arrangement is admissible when it fits between the kerbs and uses no more
    design lanes than Table 6 gives the carriageway. A 70R zone uses two.

    Every arrangement is returned, not only the ones that fill every lane. Table
    6A note (b) is explicit that a partly loaded carriageway may govern, and it
    genuinely does: leaving a lane empty can be more onerous than filling it when
    the empty lane sits where the influence surface changes sign.
    """
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

            arrangements.append(
                _describe_arrangement(
                    pattern,
                    carriageway_width_m,
                    is_fully_loaded=lanes_used == design_lanes,
                )
            )

    arrangements.sort(key=lambda a: (-a.design_lanes, a.lane_pattern))
    return arrangements


def _describe_arrangement(
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


def fit_blocks_between(
    lane_pattern: LanePattern, carriageway_left_m: float, carriageway_right_m: float
) -> BlockLayout | None:
    """Returns where each lane block sits when the arrangement is pushed fully left.

    Returns None when the arrangement does not fit between these two edges.

    Everything the search needs follows from this one layout: each block may
    slide right by anything from zero to `sliding_room_m`, and the clearances
    stay satisfied as long as no block overtakes the one to its right.
    """
    carriageway_width_m = carriageway_right_m - carriageway_left_m
    if not fits_in_carriageway(lane_pattern, carriageway_width_m):
        return None

    widths_m = block_widths(lane_pattern)
    gaps_m = _gaps_between(lane_pattern, class_a_gap(carriageway_width_m))
    kerb_clearance_m = _kerb_clearance_at_each_end(lane_pattern)

    # Edges are rounded as they are built so the candidate grids downstream
    # compare equal no matter what order the additions happened in.
    packed_left_edges_m = []
    edge_m = carriageway_left_m + kerb_clearance_m[0]
    for block in range(len(lane_pattern)):
        packed_left_edges_m.append(round(edge_m, ROUND_TO_DECIMALS))
        edge_m += widths_m[block]
        if block < len(gaps_m):
            edge_m += gaps_m[block]

    room_m = carriageway_right_m - kerb_clearance_m[1] - edge_m

    return BlockLayout(
        packed_left_edges_m=packed_left_edges_m,
        block_widths_m=widths_m,
        gaps_between_blocks_m=gaps_m,
        sliding_room_m=max(round(room_m, ROUND_TO_DECIMALS), 0.0),
    )


def _kerb_clearance_at_each_end(lane_pattern: LanePattern) -> tuple[float, float]:
    """Returns the clearance the leftmost and rightmost blocks keep from the kerb.

    Only Class A needs it here - a 70R zone already contains its clearance.
    """
    at_left = CLASS_A_KERB_CLEARANCE_M if lane_pattern[0] == CLASS_A_LANE else 0.0
    at_right = CLASS_A_KERB_CLEARANCE_M if lane_pattern[-1] == CLASS_A_LANE else 0.0
    return at_left, at_right


def where_vehicle_sits_in_block(block: str, block_width_m: float) -> tuple[float, float]:
    """Returns how far the vehicle centreline may sit from the block's left edge.

    A Class A vehicle is fixed at the centre of its lane block, so the two
    numbers are equal. A 70R vehicle floats anywhere inside its zone that keeps
    its clearance from both boundaries, so they differ.
    """
    if block == CLASS_A_LANE:
        half_lane_m = CLASS_A_LANE_WIDTH_M / 2.0
        return half_lane_m, half_lane_m

    nearest_m = VEHICLE_70R_CLEARANCE_M + VEHICLE_70R_WIDTH_M / 2.0
    return nearest_m, block_width_m - nearest_m
