import numpy as np
from setu.helpers import is_worse
from setu.irc6.constants import GRAVITY_KN_PER_TONNE, TOLERANCE_M
from setu.irc6.lanes import (
    CLASS_A_LANE,
    fit_blocks_between,
    lane_reduction_factor,
    list_admissible_arrangements,
    where_vehicle_sits_in_block,
)
from setu.irc6.vehicles import CLASS_70R_WHEELED, CLASS_A

ALREADY_CENTRED_TOLERANCE_M = 1e-06
FRACTION_TOLERANCE = 1e-09
PACKED_HARD_LEFT = 0.0
PACKED_HARD_RIGHT = 1.0
NO_LANE_REDUCTION = 1.0

class ResultantCentredPlacement:
    def __init__(self, lane_pattern, design_lanes, vehicle_centres_m, response_before_reduction, lane_reduction, response=0.0, **kwargs):
        self.lane_pattern = lane_pattern
        self.design_lanes = design_lanes
        self.vehicle_centres_m = vehicle_centres_m
        self.response_before_reduction = response_before_reduction
        self.lane_reduction = lane_reduction
        self.response = response

    def to_dict(self):
        return self.__dict__

def weight_of(vehicle):
    return vehicle.total_load_t() * GRAVITY_KN_PER_TONNE

def centre_the_resultant(carriageways, response_curves, adverse='maximum', apply_lane_reduction=True, follow_combination_drawings=True):
    worst_on_each = []
    for carriageway, curves in zip(carriageways, response_curves, strict=True):
        worst = None
        for arrangement in list_admissible_arrangements(carriageway.width_m(), follow_combination_drawings):
            placed = centre_one_arrangement(carriageway, arrangement, curves, adverse, apply_lane_reduction)
            if placed is None:
                continue
            if worst is None or is_worse(placed.response, worst.response, adverse):
                worst = placed
        if worst is not None:
            worst_on_each.append(worst)
    return worst_on_each

def centre_one_arrangement(carriageway, arrangement, curves, adverse, apply_lane_reduction):
    layout = fit_blocks_between(arrangement.lane_pattern, carriageway.left_m, carriageway.right_m)
    if layout is None:
        return None
    packed_left_m, packed_right_m = how_far_each_vehicle_can_go(arrangement, layout)
    weights_kn = [weight_of(representative_vehicle(block)) for block in arrangement.lane_pattern]
    mid_width_m = 0.5 * (carriageway.left_m + carriageway.right_m)
    fraction, is_exactly_centred = fraction_that_centres_the_resultant(packed_left_m, packed_right_m, weights_kn, target_m=mid_width_m)
    centres_m = [left_m + fraction * (right_m - left_m) for left_m, right_m in zip(packed_left_m, packed_right_m, strict=True)]
    before_reduction = sum((float(curves[block](np.asarray(z_m))) for block, z_m in zip(arrangement.lane_pattern, centres_m, strict=True)))
    reduction = lane_reduction_factor(arrangement.design_lanes) if apply_lane_reduction else NO_LANE_REDUCTION
    return ResultantCentredPlacement(lane_pattern=list(arrangement.lane_pattern), design_lanes=arrangement.design_lanes, vehicle_centres_m=centres_m, response_before_reduction=before_reduction, lane_reduction=reduction, response=before_reduction * reduction, is_exactly_centred=is_exactly_centred)

def how_far_each_vehicle_can_go(arrangement, layout):
    packed_left_m = []
    packed_right_m = []
    blocks = zip(arrangement.lane_pattern, layout.block_widths_m, layout.packed_left_edges_m, strict=True)
    for block, width_m, edge_m in blocks:
        nearest_m, furthest_m = where_vehicle_sits_in_block(block, width_m)
        packed_left_m.append(edge_m + nearest_m)
        packed_right_m.append(edge_m + layout.sliding_room_m + furthest_m)
    return (packed_left_m, packed_right_m)

def fraction_that_centres_the_resultant(packed_left_m, packed_right_m, weights_kn, target_m):
    total_kn = float(sum(weights_kn))
    if total_kn <= 0:
        raise ValueError('this arrangement carries no load, so it has no resultant')
    resultant_packed_left_m = weighted_average(packed_left_m, weights_kn, total_kn)
    room_each_vehicle_has_m = [right_m - left_m for left_m, right_m in zip(packed_left_m, packed_right_m, strict=True)]
    how_far_it_can_move_m = weighted_average(room_each_vehicle_has_m, weights_kn, total_kn)
    if abs(how_far_it_can_move_m) < TOLERANCE_M:
        is_already_centred = abs(resultant_packed_left_m - target_m) < ALREADY_CENTRED_TOLERANCE_M
        return (PACKED_HARD_LEFT, is_already_centred)
    fraction = (target_m - resultant_packed_left_m) / how_far_it_can_move_m
    reaches_the_centreline = -FRACTION_TOLERANCE <= fraction <= PACKED_HARD_RIGHT + FRACTION_TOLERANCE
    clamped = min(max(fraction, PACKED_HARD_LEFT), PACKED_HARD_RIGHT)
    return (clamped, reaches_the_centreline)

def weighted_average(positions_m, weights_kn, total_kn):
    moment = sum((weight_kn * position_m for weight_kn, position_m in zip(weights_kn, positions_m, strict=True)))
    return moment / total_kn

def representative_vehicle(block):
    return CLASS_A if block == CLASS_A_LANE else CLASS_70R_WHEELED
