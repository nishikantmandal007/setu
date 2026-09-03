import numpy as np
import itertools
from setu.rules.irc6 import *
from setu.utils.helpers import *
from setu.utils.errors import *
from setu.models.results import VehiclePlacement
from setu.models.vehicles import *
from setu.models.vehicles import most_vehicles_that_fit, class_of

def best_so_far(values):
    values = np.asarray(values, float)
    every_position = np.arange(len(values))
    best_value_so_far = np.maximum.accumulate(values)
    beats_everything_before_it = np.empty(len(values), bool)
    beats_everything_before_it[0] = True
    beats_everything_before_it[1:] = values[1:] > best_value_so_far[:-1]
    position_when_it_is_a_new_best = np.where(beats_everything_before_it, every_position, -1)
    position_of_the_best_so_far = np.maximum.accumulate(position_when_it_is_a_new_best)
    return (best_value_so_far, position_of_the_best_so_far)

NO_IMPACT = 1.0

class ResponseCurve:
    def __init__(self, z_positions_m, response, **kwargs):
        self.z_positions_m = z_positions_m
        self.response = response
        self.__dict__.update(kwargs)

    def to_dict(self):
        return self.__dict__

    def read_at(self, z_m):
        return np.interp(z_m, self.z_positions_m, self.response)

class WorstAlongSpan:
    def __init__(self, response, x_front_m=None, **kwargs):
        self.response = response
        self.x_front_m = x_front_m if x_front_m is not None else kwargs.get("x_positions_m")
        self.__dict__.update(kwargs)
        self.x_positions_m = self.x_front_m

    def to_dict(self):
        return self.__dict__

class VehicleResponses:

    def __init__(self, surface, span_m, material='steel', member_span_m=None, wearing_course_thickness_m=0.0, apply_impact=True, allow_trains=True, sampling=DEFAULT_SAMPLING):
        self.surface = surface
        self.span_m = float(span_m)
        self.material = material
        self.member_span_m = member_span_m
        self.wearing_course_thickness_m = float(wearing_course_thickness_m)
        self.apply_impact = apply_impact
        self.allow_trains = allow_trains
        self.sampling = sampling
        self._already_built = {}

    def for_vehicle(self, vehicle, z_positions_m, adverse='maximum'):
        z_positions_m = np.asarray(z_positions_m, float)
        remembered = remembered_as(vehicle, z_positions_m, adverse)
        if remembered not in self._already_built:
            self._already_built[remembered] = self.build_curve(vehicle, z_positions_m, adverse)
        return self._already_built[remembered]

    def build_curve(self, vehicle, z_positions_m, adverse):
        wheel_offsets = wheel_load_offsets(vehicle, self.wearing_course_thickness_m, self.sampling)
        x_positions_m = positions_along_span(self.surface, wheel_offsets)
        response_to_one_vehicle = response_to_one_vehicle_everywhere(self.surface, wheel_offsets, x_positions_m, z_positions_m, self.sampling)
        if self.allow_trains:
            worst = self.worst_train_at_each_position(vehicle, response_to_one_vehicle, x_positions_m, adverse)
        else:
            worst = self.worst_single_vehicle_at_each_position(response_to_one_vehicle, x_positions_m, adverse)
        factor = self.impact_factor_for(vehicle)
        return ResponseCurve(vehicle_name=vehicle.name, z_positions_m=z_positions_m, response=factor * worst.response, x_positions_m=worst.x_positions_m, vehicles_in_train=worst.vehicles_in_train, train_x_front_m=worst.train_x_front_m, impact_factor=factor)

    def worst_single_vehicle_at_each_position(self, response_to_one_vehicle, x_positions_m, adverse):
        positions_across_the_width = response_to_one_vehicle.shape[1]
        worst_along_the_span = index_of_worst(response_to_one_vehicle, adverse, axis=0)
        every_position = np.arange(positions_across_the_width)
        where_it_stopped_m = x_positions_m[worst_along_the_span]
        return WorstAlongSpan(response=response_to_one_vehicle[worst_along_the_span, every_position], x_positions_m=where_it_stopped_m, vehicles_in_train=np.ones(positions_across_the_width, int), train_x_front_m=[(float(x_m),) for x_m in where_it_stopped_m])

    def worst_train_at_each_position(self, vehicle, response_to_one_vehicle, x_positions_m, adverse):
        pitch_m = pitch_between_vehicles_m(vehicle)
        longest_train = most_vehicles_that_fit(vehicle, float(x_positions_m[0]), float(x_positions_m[-1]))
        positions_across_the_width = response_to_one_vehicle.shape[1]
        response = np.empty(positions_across_the_width)
        leading_x_m = np.empty(positions_across_the_width)
        vehicles_in_train = np.empty(positions_across_the_width, int)
        trains = []
        for z_index in range(positions_across_the_width):
            worst = find_worst_train(response_to_one_vehicle[:, z_index], x_positions_m, pitch_m, longest_train, adverse)
            if worst is None:
                raise RuntimeError('no legal placement was found for even a single vehicle at one of the positions across the width, but one vehicle should always fit')
            response[z_index] = worst.response
            leading_x_m[z_index] = worst.positions_m[0]
            vehicles_in_train[z_index] = worst.vehicles_in_train()
            trains.append(worst.positions_m)
        return WorstAlongSpan(response=response, x_positions_m=leading_x_m, vehicles_in_train=vehicles_in_train, train_x_front_m=trains)

    def impact_factor_for(self, vehicle):
        if not self.apply_impact:
            return NO_IMPACT
        span_m = self.span_m if self.member_span_m is None else float(self.member_span_m)
        return impact_factor(class_of(vehicle), span_m, self.material)

def remembered_as(vehicle, z_positions_m, adverse):
    return (vehicle.name, adverse, len(z_positions_m), float(z_positions_m[0]), float(z_positions_m[-1]))

def positions_across_width(responses, vehicles, z_from_m, z_to_m, steps=None):
    steps = DEFAULT_SAMPLING.positions_across_the_deck_to_try if steps is None else steps
    an_even_spread = np.linspace(z_from_m, z_to_m, steps)
    worth_sampling = [an_even_spread]
    for vehicle in vehicles:
        worth_sampling.append(bending_positions_across_width(responses.surface, vehicle, responses.wearing_course_thickness_m, responses.sampling, z_from_m, z_to_m))
    everywhere_m = np.unique(np.round(np.concatenate(worth_sampling), ROUND_TO_DECIMALS))
    is_on_the_deck = (everywhere_m >= z_from_m - TOLERANCE_M) & (everywhere_m <= z_to_m + TOLERANCE_M)
    return everywhere_m[is_on_the_deck]

def positions_along_span(surface, wheel_offsets):
    stations_m = surface.length_mesh_m
    wheel_dx_m = np.asarray(wheel_offsets, float)[:, OFFSET_DX_M]
    puts_a_wheel_on_a_station_m = np.unique((stations_m[None, :] - wheel_dx_m[:, None]).ravel())
    part_way_onto_the_bridge_m = -wheel_dx_m.max()
    far_end_of_the_bridge_m = stations_m[-1]
    return keep_between(puts_a_wheel_on_a_station_m, part_way_onto_the_bridge_m, far_end_of_the_bridge_m)

def response_to_one_vehicle_everywhere(surface, wheel_offsets, x_positions_m, z_positions_m, sampling):
    responses = np.empty((len(x_positions_m), len(z_positions_m)))
    evaluated_at_once = sampling.span_positions_evaluated_at_once
    for start in range(0, len(x_positions_m), evaluated_at_once):
        chunk_x_m = x_positions_m[start:start + evaluated_at_once]
        responses[start:start + len(chunk_x_m)] = sum_over_wheels(surface, wheel_offsets, chunk_x_m, z_positions_m)
    return responses

def sum_over_wheels(surface, wheel_offsets, x_positions_m, z_positions_m):
    wheel_dx_m, wheel_dz_m, wheel_loads_kn = split_offsets(np.asarray(wheel_offsets, float))
    vehicle_front_m = np.asarray(x_positions_m, float).reshape(-1, 1, 1)
    vehicle_centreline_m = np.asarray(z_positions_m, float).reshape(1, -1, 1)
    wheel_x_m = vehicle_front_m + wheel_dx_m.reshape(1, 1, -1)
    wheel_z_m = vehicle_centreline_m + wheel_dz_m.reshape(1, 1, -1)
    influence_under_each_wheel = surface.influence_at(wheel_x_m, wheel_z_m)
    return (influence_under_each_wheel * wheel_loads_kn).sum(axis=-1)

def bending_positions_across_width(surface, vehicle, wearing_course_thickness_m, sampling, z_from_m, z_to_m):
    wheel_offsets = wheel_load_offsets(vehicle, wearing_course_thickness_m, sampling)
    wheel_dz_m = np.asarray(wheel_offsets, float)[:, OFFSET_DZ_M]
    stations_m = surface.width_mesh_m
    puts_a_wheel_on_a_station_m = (stations_m[None, :] - wheel_dz_m[:, None]).ravel()
    both_ends_m = np.array([z_from_m, z_to_m], float)
    bends_m = np.unique(np.concatenate([puts_a_wheel_on_a_station_m, both_ends_m]))
    return keep_between(bends_m, z_from_m, z_to_m)

def keep_between(positions_m, from_m, to_m):
    is_in_range = (positions_m >= from_m - TOLERANCE_M) & (positions_m <= to_m + TOLERANCE_M)
    return positions_m[is_in_range]


def read_curve(curve, positions_m):
    positions_m = np.asarray(positions_m, float)
    responses = read_every_position_at_once(curve, positions_m)
    if responses is None:
        return read_one_position_at_a_time(curve, positions_m)
    return responses

def read_every_position_at_once(curve, positions_m):
    try:
        responses = np.asarray(curve(positions_m), float)
    except (TypeError, ValueError):
        return None
    if responses.shape != positions_m.shape:
        return None
    return responses

def read_one_position_at_a_time(curve, positions_m):
    return np.array([float(curve(position)) for position in positions_m])

def positions_inside_zone(from_m, to_m, curve_breakpoints_m, sampling):
    both_ends = np.array([from_m, to_m], float)
    an_even_spread = np.linspace(from_m, to_m, sampling.positions_inside_a_70r_zone_to_try)
    worth_trying = [both_ends, an_even_spread]
    if curve_breakpoints_m is not None:
        breakpoints_m = np.asarray(curve_breakpoints_m, float)
        is_inside_the_zone = (breakpoints_m >= from_m - TOLERANCE_M) & (breakpoints_m <= to_m + TOLERANCE_M)
        worth_trying.append(breakpoints_m[is_inside_the_zone])
    return np.unique(np.round(np.concatenate(worth_trying), ROUND_TO_DECIMALS))

NOWHERE = -1

class TrainPlacement:
    def __init__(self, response, positions_m):
        self.response = response
        self.positions_m = positions_m

    def vehicles_in_train(self):
        return len(self.positions_m)

def last_position_a_vehicle_in_front_could_take(positions_m, pitch_m):
    return np.searchsorted(positions_m, positions_m - pitch_m, side='right') - 1

def place_train(response_to_one_vehicle, positions_m, pitch_m, vehicles_in_train, adverse='minimum'):
    response_to_one_vehicle = np.asarray(response_to_one_vehicle, float)
    positions_m = np.asarray(positions_m, float)
    worse_is_positive = adverse_sign(adverse)
    vehicle_in_front = last_position_a_vehicle_in_front_could_take(positions_m, pitch_m)
    has_room_in_front = vehicle_in_front >= 0
    room_in_front = vehicle_in_front[has_room_in_front]
    signed_best_total = worse_is_positive * response_to_one_vehicle
    position_of_the_vehicle_in_front = [None]
    for _ in range(1, vehicles_in_train):
        best_behind, where_that_best_sat = best_so_far(signed_best_total)
        best_with_one_more = np.full(len(positions_m), -np.inf)
        best_with_one_more[has_room_in_front] = worse_is_positive * response_to_one_vehicle[has_room_in_front] + best_behind[room_in_front]
        came_from = np.full(len(positions_m), NOWHERE, int)
        came_from[has_room_in_front] = where_that_best_sat[room_in_front]
        signed_best_total = best_with_one_more
        position_of_the_vehicle_in_front.append(came_from)
    if not np.isfinite(signed_best_total).any():
        return None
    chosen = walk_back_through_the_train(signed_best_total, position_of_the_vehicle_in_front)
    if chosen is None:
        return None
    return TrainPlacement(response=float(sum((response_to_one_vehicle[position] for position in chosen))), positions_m=tuple((float(positions_m[position]) for position in chosen)))

def find_worst_train(response_to_one_vehicle, positions_m, pitch_m, most_vehicles, adverse='minimum'):
    worst = None
    for how_many in range(1, int(most_vehicles) + 1):
        placement = place_train(response_to_one_vehicle, positions_m, pitch_m, how_many, adverse)
        if placement is None:
            break
        if worst is None or is_worse(placement.response, worst.response, adverse):
            worst = placement
    return worst

def walk_back_through_the_train(signed_best_total, position_of_the_vehicle_in_front):
    position = int(np.argmax(signed_best_total))
    chosen = [position]
    for where_the_vehicle_in_front_sat in reversed(position_of_the_vehicle_in_front[1:]):
        if where_the_vehicle_in_front_sat is None:
            raise RuntimeError('backtracking reached a vehicle with no recorded position in front of it - only the leading vehicle may have one')
        position = int(where_the_vehicle_in_front_sat[position])
        if position == NOWHERE:
            return None
        chosen.append(position)
    chosen.reverse()
    return chosen

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