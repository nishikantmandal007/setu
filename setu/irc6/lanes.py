from itertools import product, zip_longest

import numpy as np

from setu.config.constants import (
    CLASS_A_GAP_OPENS_UP_BELOW_M,
    CLASS_A_KERB_CLEARANCE_M,
    CLASS_A_LANE_WIDTH_M,
    CLASS_A_VEHICLE_GAP_M,
    DESIGN_LANES_BY_WIDTH,
    FOOTWAY_UDL_KPA,
    LANE_REDUCTION_BY_LANE_COUNT,
    LANE_REDUCTION_FOR_FOUR_OR_MORE_LANES,
    MOST_70R_VEHICLES_DRAWN,
    MOST_DESIGN_LANES,
    NARROWEST_LOADED_CARRIAGEWAY_M,
    RESIDUAL_UDL_APPLIES_BELOW_M,
    RESIDUAL_UDL_KPA,
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
from setu.utils.helpers import adverse_sign, where_a_load_hurts, DEFAULT_SAMPLING

CLASS_A_LANE = 'class_a'
ZONE_70R = 'zone_70r'
LanePattern = list[str]
DESIGN_LANES_PER_70R_ZONE = 2
DESIGN_LANES_PER_CLASS_A_LANE = 1
NO_GAP_NEEDED_M = 0.0
NOT_LOADED_AT_ALL = 0
LEFT_OVER_WIDTH_DECIMALS = 6


class LaneArrangement:
    def __init__(self, lane_pattern, design_lanes, narrowest_carriageway_m, sliding_room_m, is_fully_loaded):
        self.lane_pattern = lane_pattern
        self.design_lanes = design_lanes
        self.narrowest_carriageway_m = narrowest_carriageway_m
        self.sliding_room_m = sliding_room_m
        self.is_fully_loaded = is_fully_loaded

    def to_dict(self):
        return self.__dict__


class BlockLayout:
    def __init__(self, packed_left_edges_m, block_widths_m, gaps_between_blocks_m, sliding_room_m):
        self.packed_left_edges_m = packed_left_edges_m
        self.block_widths_m = block_widths_m
        self.gaps_between_blocks_m = gaps_between_blocks_m
        self.sliding_room_m = sliding_room_m

    def to_dict(self):
        return self.__dict__


def design_lanes_used_by(lane_pattern):
    return sum((DESIGN_LANES_PER_70R_ZONE if block == ZONE_70R else DESIGN_LANES_PER_CLASS_A_LANE for block in lane_pattern))

def count_design_lanes(carriageway_width_m):
    for width_from, width_up_to, design_lanes in DESIGN_LANES_BY_WIDTH:
        if width_from <= carriageway_width_m < width_up_to:
            return design_lanes
    if carriageway_width_m >= WIDEST_TABULATED_CARRIAGEWAY_M:
        return MOST_DESIGN_LANES
    return NOT_LOADED_AT_ALL

def can_carry_vehicles(carriageway_width_m):
    if count_design_lanes(carriageway_width_m) == NOT_LOADED_AT_ALL:
        return False
    return carriageway_width_m >= NARROWEST_LOADED_CARRIAGEWAY_M

def class_a_gap(carriageway_width_m):
    if carriageway_width_m > CLASS_A_GAP_OPENS_UP_BELOW_M:
        return CLASS_A_VEHICLE_GAP_M
    width_left_over_m = round(carriageway_width_m - TWO_CLASS_A_LANES_AND_KERB_CLEARANCES_M, LEFT_OVER_WIDTH_DECIMALS)
    return max(SMALLEST_CLASS_A_GAP_M, min(CLASS_A_VEHICLE_GAP_M, width_left_over_m))

def block_widths(lane_pattern):
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

def gaps_between(lane_pattern, class_a_to_class_a_gap_m):
    gaps_m = []
    for left, right in zip(lane_pattern, lane_pattern[1:], strict=False):
        both_are_class_a = left == CLASS_A_LANE and right == CLASS_A_LANE
        gaps_m.append(class_a_to_class_a_gap_m if both_are_class_a else NO_GAP_NEEDED_M)
    return gaps_m

def kerb_clearance_at_each_end(lane_pattern):
    at_left = CLASS_A_KERB_CLEARANCE_M if lane_pattern[0] == CLASS_A_LANE else 0.0
    at_right = CLASS_A_KERB_CLEARANCE_M if lane_pattern[-1] == CLASS_A_LANE else 0.0
    return (at_left, at_right)

def narrowest_carriageway_that_fits(lane_pattern, carriageway_width_m=None):
    if not lane_pattern:
        return 0.0
    at_left_m, at_right_m = kerb_clearance_at_each_end(lane_pattern)
    if carriageway_width_m is None:
        gap_m = CLASS_A_VEHICLE_GAP_M
    else:
        gap_m = class_a_gap(carriageway_width_m)
    width_m = sum(block_widths(lane_pattern)) + at_left_m + at_right_m + sum(gaps_between(lane_pattern, gap_m))
    return round(width_m, ROUND_TO_DECIMALS)

def fits_in_carriageway(lane_pattern, carriageway_width_m):
    needed_m = narrowest_carriageway_that_fits(lane_pattern, carriageway_width_m)
    return needed_m <= carriageway_width_m + TOLERANCE_M

def is_70r_placed_as_the_code_draws_it(lane_pattern):
    last = len(lane_pattern) - 1
    for position, block in enumerate(lane_pattern):
        if block != ZONE_70R:
            continue
        reaches_the_left_kerb = all((lane_pattern[nearer] == ZONE_70R for nearer in range(position)))
        reaches_the_right_kerb = all((lane_pattern[further] == ZONE_70R for further in range(position + 1, last + 1)))
        if not (reaches_the_left_kerb or reaches_the_right_kerb):
            return False
    return True

def is_drawn_in_the_combinations(pattern):
    if pattern.count(ZONE_70R) > MOST_70R_VEHICLES_DRAWN:
        return False
    return is_70r_placed_as_the_code_draws_it(list(pattern))

def list_admissible_arrangements(carriageway_width_m, follow_combination_drawings=True):
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
            if follow_combination_drawings and (not is_drawn_in_the_combinations(pattern)):
                continue
            arrangements.append(describe_arrangement(pattern, carriageway_width_m, is_fully_loaded=lanes_used == design_lanes))
    arrangements.sort(key=lambda arrangement: (-arrangement.design_lanes, arrangement.lane_pattern))
    return arrangements

def describe_arrangement(pattern, carriageway_width_m, *, is_fully_loaded):
    narrowest_m = narrowest_carriageway_that_fits(list(pattern), carriageway_width_m)
    return LaneArrangement(lane_pattern=list(pattern), design_lanes=design_lanes_used_by(pattern), narrowest_carriageway_m=narrowest_m, sliding_room_m=round(carriageway_width_m - narrowest_m, ROUND_TO_DECIMALS), is_fully_loaded=is_fully_loaded)

def fit_blocks_between(lane_pattern, carriageway_left_m, carriageway_right_m):
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
    return BlockLayout(packed_left_edges_m=packed_left_edges_m, block_widths_m=widths_m, gaps_between_blocks_m=gaps_m, sliding_room_m=max(round(room_m, ROUND_TO_DECIMALS), 0.0))

def where_vehicle_sits_in_block(block, block_width_m):
    if block == CLASS_A_LANE:
        half_lane_m = CLASS_A_LANE_WIDTH_M / 2.0
        return (half_lane_m, half_lane_m)
    nearest_m = VEHICLE_70R_CLEARANCE_M + VEHICLE_70R_WIDTH_M / 2.0
    return (nearest_m, block_width_m - nearest_m)

def lane_reduction_factor(loaded_lanes):
    return LANE_REDUCTION_BY_LANE_COUNT.get(int(loaded_lanes), LANE_REDUCTION_FOR_FOUR_OR_MORE_LANES)

NOTHING_THERE_M = 1e-12

def needs_residual_udl(carriageway_width_m):
    return float(carriageway_width_m) < RESIDUAL_UDL_APPLIES_BELOW_M

def strips_beside_class_a(z_centre_m, carriageway_left_m, carriageway_right_m):
    half_lane_m = CLASS_A_LANE_WIDTH_M / 2.0
    covered_by_the_vehicle = (z_centre_m - half_lane_m, z_centre_m + half_lane_m)
    return uncovered_strips([covered_by_the_vehicle], carriageway_left_m, carriageway_right_m)

def uncovered_strips(covered, from_m, to_m, tolerance_m=1e-06):
    in_order = sorted(((min(edge_a_m, edge_b_m), max(edge_a_m, edge_b_m)) for edge_a_m, edge_b_m in covered))
    strips = []
    cursor_m = from_m
    for starts_m, ends_m in in_order:
        starts_m, ends_m = (max(starts_m, from_m), min(ends_m, to_m))
        if starts_m > cursor_m + tolerance_m:
            strips.append((cursor_m, starts_m))
        cursor_m = max(cursor_m, ends_m)
    if to_m > cursor_m + tolerance_m:
        strips.append((cursor_m, to_m))
    return [(starts_m, ends_m) for starts_m, ends_m in strips if ends_m - starts_m > tolerance_m]

def response_to_area_load(surface, strips, adverse, pressure_kpa=RESIDUAL_UDL_KPA, adverse_area_only=True, sampling=DEFAULT_SAMPLING):
    if not strips:
        return 0.0
    x_centres_m, x_widths_m = cell_centres(surface.length_mesh_m, sampling.udl_cells_per_mesh_interval_along_span)
    total = 0.0
    for from_m, to_m in strips:
        if to_m - from_m <= NOTHING_THERE_M:
            continue
        z_centres_m, z_widths_m = cell_centres([from_m, to_m], sampling.udl_cells_per_mesh_interval_across_width)
        ordinates = surface.influence_at(x_centres_m[:, None], z_centres_m[None, :])
        cell_areas_m2 = x_widths_m[:, None] * z_widths_m[None, :]
        cells = ordinates * cell_areas_m2
        if adverse_area_only:
            cells = np.where(where_a_load_hurts(ordinates, adverse), cells, 0.0)
        total += float(cells.sum())
    return pressure_kpa * total

def footway_response(surface, cross_section, adverse, pressure_kpa=None, sampling=DEFAULT_SAMPLING):
    footways = cross_section.footways()
    if not footways:
        return 0.0
    pressure_kpa = FOOTWAY_UDL_KPA if pressure_kpa is None else pressure_kpa
    strips = [(strip.z_from_m, strip.z_to_m) for strip in footways]
    return response_to_area_load(surface, strips, adverse, pressure_kpa=pressure_kpa, sampling=sampling)

def cell_centres(edges_m, cells_per_interval):
    edges_m = np.asarray(edges_m, float)
    intervals = len(edges_m) - 1
    interval_starts_m = np.repeat(edges_m[:-1], cells_per_interval)
    interval_ends_m = np.repeat(edges_m[1:], cells_per_interval)
    which_cell = np.tile(np.arange(cells_per_interval), intervals)
    widths_m = (interval_ends_m - interval_starts_m) / cells_per_interval
    centres_m = interval_starts_m + (which_cell + 0.5) * widths_m
    return (centres_m, widths_m)
