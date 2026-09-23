import itertools
import numpy as np
from setu.errors import NoAdmissibleArrangementError
from setu.helpers import DEFAULT_SAMPLING, ROUND_TO_DECIMALS, adverse_sign, index_of_worst, is_worst_first
from setu.irc6.constants import TOLERANCE_M
from setu.irc6.lanes import (
    CLASS_A_LANE,
    fit_blocks_between,
    lane_reduction_factor,
    list_admissible_arrangements,
    needs_residual_udl,
    response_to_area_load,
    strips_beside_class_a,
    where_vehicle_sits_in_block,
)
from setu.analysis.along_span import best_so_far, positions_inside_zone, read_curve

class BlockEnvelope:
    def __init__(self, z_positions_m=None, response=None, winner=None, **kwargs):
        self.z_positions_m = z_positions_m
        self.response = response
        self.winner = winner
        self.winner = winner

    def to_dict(self):
        return self.__dict__

    def __call__(self, z_m):
        return np.interp(z_m, self.z_positions_m, self.response)

    def winner_at(self, z_m):
        distance_away_m = np.abs(self.z_positions_m - float(z_m))
        nearest = int(distance_away_m.argmin())
        return self.winner[nearest]

def envelope_every_block(responses, permitted, z_positions_m, adverse, carriageway, surface, apply_residual_udl, sampling):
    envelopes = {}
    for block, choices in permitted.items():
        response, winner = worst_of_the_permitted_vehicles(responses, choices, z_positions_m, adverse)
        if carries_a_residual_udl(block, carriageway, apply_residual_udl):
            response = response + residual_udl_curve(surface, z_positions_m, carriageway, adverse, sampling)
        envelopes[block] = BlockEnvelope(z_positions_m=z_positions_m, response=response, winner=winner)
    return envelopes

def worst_of_the_permitted_vehicles(responses, choices, z_positions_m, adverse):
    curves = [responses.for_vehicle(vehicle, z_positions_m, adverse) for vehicle in choices]
    one_row_per_vehicle = np.vstack([curve.response for curve in curves])
    worst_vehicle = index_of_worst(one_row_per_vehicle, adverse, axis=0)
    every_position = np.arange(len(z_positions_m))
    response = one_row_per_vehicle[worst_vehicle, every_position]
    winner = [choices[which].name for which in worst_vehicle]
    return (response, winner)

def carries_a_residual_udl(block, carriageway, apply_residual_udl):
    if block != CLASS_A_LANE or not apply_residual_udl:
        return False
    return needs_residual_udl(carriageway.width_m())

def residual_udl_curve(surface, z_positions_m, carriageway, adverse, sampling):
    added_at_each_position = [response_to_area_load(surface, strips_beside_class_a(float(z_m), carriageway.left_m, carriageway.right_m), adverse, sampling=sampling) for z_m in z_positions_m]
    return np.array(added_at_each_position)


def place_vehicles(block_curves, adverse='maximum'):
    worse_is_positive = adverse_sign(adverse)
    signed_best_total = worse_is_positive * np.asarray(block_curves[0], float)
    offset_of_the_block_to_the_left = [None]
    for curve in block_curves[1:]:
        best_to_the_left, where_that_best_sat = best_so_far(signed_best_total)
        signed_best_total = worse_is_positive * np.asarray(curve, float) + best_to_the_left
        offset_of_the_block_to_the_left.append(where_that_best_sat)
    chosen_offsets = walk_back_through_the_blocks(signed_best_total, offset_of_the_block_to_the_left)
    worst_total = sum((float(np.asarray(curve)[offset]) for curve, offset in zip(block_curves, chosen_offsets, strict=True)))
    return (worst_total, chosen_offsets)

def walk_back_through_the_blocks(signed_best_total, offset_of_the_block_to_the_left):
    offset = int(np.argmax(signed_best_total))
    chosen_offsets = [offset]
    for where_the_block_to_the_left_sat in reversed(offset_of_the_block_to_the_left[1:]):
        if where_the_block_to_the_left_sat is None:
            raise RuntimeError('backtracking reached a block with no recorded offset to its left - only the leftmost block may have one')
        offset = int(where_the_block_to_the_left_sat[offset])
        chosen_offsets.append(offset)
    chosen_offsets.reverse()
    return chosen_offsets


NO_LANE_REDUCTION = 1.0

class CarriagewayCase:
    def __init__(self, lane_pattern, design_lanes, sliding_room_m, vehicle_centres_m, response_before_reduction, response=0.0, lane_reduction=1.0, **kwargs):
        self.lane_pattern = lane_pattern
        self.design_lanes = design_lanes
        self.sliding_room_m = sliding_room_m
        self.vehicle_centres_m = vehicle_centres_m
        self.response_before_reduction = response_before_reduction
        self.response = response
        self.lane_reduction = lane_reduction
        self.response = response
        self.__dict__.update(kwargs)

    def to_dict(self):
        return self.__dict__

class TransversePlacement:
    def __init__(self, response=0.0, response_before_reduction=0.0, lane_reduction=1.0, design_lanes=0, per_carriageway=None, **kwargs):
        self.response = response
        self.response_before_reduction = response_before_reduction
        self.lane_reduction = lane_reduction
        self.design_lanes = design_lanes
        self.per_carriageway = per_carriageway or {}
        self.lane_reduction = lane_reduction
        self.design_lanes = design_lanes
        self.per_carriageway = per_carriageway

    def to_dict(self):
        return self.__dict__

class TransverseSearch:
    def __init__(self, adverse, sampling, curve_breakpoints_m, apply_lane_reduction, follow_combination_drawings):
        self.adverse = adverse
        self.sampling = sampling
        self.curve_breakpoints_m = curve_breakpoints_m
        self.apply_lane_reduction = apply_lane_reduction
        self.follow_combination_drawings = follow_combination_drawings

    def to_dict(self):
        return self.__dict__

    def reduction_for(self, design_lanes):
        if not self.apply_lane_reduction:
            return NO_LANE_REDUCTION
        return lane_reduction_factor(design_lanes)

def find_worst_placement(carriageways, response_curves, adverse='maximum', apply_lane_reduction=True, curve_breakpoints_m=None, sampling=DEFAULT_SAMPLING, follow_combination_drawings=True):
    check_one_set_of_curves_per_carriageway(carriageways, response_curves)
    search = TransverseSearch(adverse=adverse, sampling=sampling, curve_breakpoints_m=curve_breakpoints_m, apply_lane_reduction=apply_lane_reduction, follow_combination_drawings=follow_combination_drawings)
    cases_per_carriageway = [cases_for_one_carriageway(carriageway, curves, search) for carriageway, curves in zip(carriageways, response_curves, strict=True)]
    if any((not cases for cases in cases_per_carriageway)):
        widths_m = [round(carriageway.width_m(), 3) for carriageway in carriageways]
        raise NoAdmissibleArrangementError(f'no IRC:6 lane arrangement fits this cross-section; carriageway widths are {widths_m} m')
    return combine_across_carriageways(cases_per_carriageway, search)

def cases_for_one_carriageway(carriageway, curves, search):
    cases = []
    for arrangement in list_admissible_arrangements(carriageway.width_m(), search.follow_combination_drawings):
        layout = fit_blocks_between(arrangement.lane_pattern, carriageway.left_m, carriageway.right_m)
        if layout is None:
            continue
        offsets_m = sliding_offsets(arrangement, layout, search)
        contributions = []
        centres_m = []
        for block, width_m, packed_left_m in walk_the_blocks(arrangement, layout):
            values, positions = block_contribution(block, width_m, packed_left_m, offsets_m, curves, search)
            contributions.append(values)
            centres_m.append(positions)
        response, chosen = place_vehicles(contributions, search.adverse)
        reduction = search.reduction_for(arrangement.design_lanes)
        cases.append(CarriagewayCase(lane_pattern=list(arrangement.lane_pattern), design_lanes=arrangement.design_lanes, sliding_room_m=layout.sliding_room_m, vehicle_centres_m=[float(centre_m[offset]) for centre_m, offset in zip(centres_m, chosen, strict=True)], response_before_reduction=response, lane_reduction=reduction, response=response * reduction))
    return cases

def walk_the_blocks(arrangement, layout):
    return list(zip(arrangement.lane_pattern, layout.block_widths_m, layout.packed_left_edges_m, strict=True))

def sliding_offsets(arrangement, layout, search):
    room_m = layout.sliding_room_m
    has_nowhere_to_slide = room_m < TOLERANCE_M
    steps = 1 if has_nowhere_to_slide else search.sampling.sliding_offsets_to_try
    worth_trying = [np.linspace(0.0, room_m, steps)]
    if search.curve_breakpoints_m is not None and (not has_nowhere_to_slide):
        breakpoints_m = np.asarray(search.curve_breakpoints_m, float)
        for block, width_m, packed_left_m in walk_the_blocks(arrangement, layout):
            for where_in_block_m in set(where_vehicle_sits_in_block(block, width_m)):
                lands_on_a_bend = breakpoints_m - packed_left_m - where_in_block_m
                is_within_the_sliding_room = (lands_on_a_bend >= -TOLERANCE_M) & (lands_on_a_bend <= room_m + TOLERANCE_M)
                worth_trying.append(lands_on_a_bend[is_within_the_sliding_room])
    return np.unique(np.round(np.concatenate(worth_trying), ROUND_TO_DECIMALS))

def block_contribution(block, block_width_m, packed_left_m, offsets_m, curves, search):
    nearest_m, furthest_m = where_vehicle_sits_in_block(block, block_width_m)
    is_pinned_to_the_middle_of_its_lane = nearest_m == furthest_m
    if is_pinned_to_the_middle_of_its_lane:
        centres_m = packed_left_m + offsets_m + nearest_m
        return (read_curve(curves[block], centres_m), centres_m)
    return worst_spot_inside_the_zone(block, packed_left_m, nearest_m, furthest_m, offsets_m, curves, search)

def worst_spot_inside_the_zone(block, packed_left_m, nearest_m, furthest_m, offsets_m, curves, search):
    zone_from_m = packed_left_m + offsets_m + nearest_m
    zone_to_m = packed_left_m + offsets_m + furthest_m
    values = np.empty(len(offsets_m))
    centres_m = np.empty(len(offsets_m))
    for i, (from_m, to_m) in enumerate(zip(zone_from_m, zone_to_m, strict=True)):
        inside_the_zone_m = positions_inside_zone(from_m, to_m, search.curve_breakpoints_m, search.sampling)
        responses = read_curve(curves[block], inside_the_zone_m)
        worst = int(index_of_worst(responses, search.adverse))
        values[i] = responses[worst]
        centres_m[i] = inside_the_zone_m[worst]
    return (values, centres_m)

def combine_across_carriageways(cases_per_carriageway, search):
    combinations = []
    for chosen in itertools.product(*cases_per_carriageway):
        design_lanes = sum((case.design_lanes for case in chosen))
        before_reduction = sum((case.response_before_reduction for case in chosen))
        reduction = search.reduction_for(design_lanes)
        combinations.append(TransversePlacement(response=before_reduction * reduction, response_before_reduction=before_reduction, lane_reduction=reduction, design_lanes=design_lanes, per_carriageway=list(chosen)))
    combinations.sort(key=lambda placement: placement.response, reverse=is_worst_first(search.adverse))
    return combinations

def check_one_set_of_curves_per_carriageway(carriageways, response_curves):
    if len(response_curves) != len(carriageways):
        raise ValueError(f'there are {len(carriageways)} carriageways but {len(response_curves)} sets of response curves; a narrow carriageway carries its own residual UDL, so each one needs its own curves')
