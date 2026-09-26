import numpy as np
from setu.analysis.influence_surface import cell_containing
from setu.helpers import adverse_sign, is_worse
from setu.irc6.impact import impact_factor
from setu.irc6.vehicles import class_of, most_vehicles_that_fit, pitch_between_vehicles_m
from setu.irc6.wheel_loads import split_offsets, wheel_load_offsets
from setu.utils.constants import OFF_THE_DECK, OFFSET_DX_M, OFFSET_DZ_M, ROUND_TO_DECIMALS, TOLERANCE_M

# running best value and where it was, left to right
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

class ResponseCurve:
    # worst response of one vehicle (or train) at each position across, and where along
    def __init__(self, vehicle_name, z_positions_m, response, x_positions_m, vehicles_in_train, train_x_front_m, impact_factor):
        self.vehicle_name = vehicle_name
        self.z_positions_m = z_positions_m
        self.response = response
        self.x_positions_m = x_positions_m
        self.vehicles_in_train = vehicles_in_train
        self.train_x_front_m = train_x_front_m
        self.impact_factor = impact_factor

class WorstAlongSpan:
    # worst spot along the span at each position across
    def __init__(self, response, x_positions_m, vehicles_in_train, train_x_front_m):
        self.response = response
        self.x_positions_m = x_positions_m
        self.vehicles_in_train = vehicles_in_train
        self.train_x_front_m = train_x_front_m

class VehicleResponses:

    # builds and remembers each vehicle's response curve on one surface
    def __init__(self, surface, span_m, wearing_course_thickness_m, skew, sampling):
        self.surface = surface
        self.skew = float(skew)
        self.span_m = float(span_m)
        self.wearing_course_thickness_m = float(wearing_course_thickness_m)
        self.sampling = sampling
        self._already_built = {}

    # the vehicle's response curve, built once and remembered
    def for_vehicle(self, vehicle, z_positions_m, adverse):
        z_positions_m = np.asarray(z_positions_m, float)
        remembered = remembered_as(vehicle, z_positions_m, adverse)
        if remembered not in self._already_built:
            self._already_built[remembered] = self.build_curve(vehicle, z_positions_m, adverse)
        return self._already_built[remembered]

    # slide the vehicle, or a train of them, along the span at every position across, keep the worst
    def build_curve(self, vehicle, z_positions_m, adverse):
        wheel_offsets = along_the_mesh(wheel_load_offsets(vehicle, self.wearing_course_thickness_m, self.sampling), self.skew)
        x_positions_m = with_every_train_spacing(positions_along_span(self.surface, wheel_offsets), vehicle)
        response_to_one_vehicle = response_to_one_vehicle_everywhere(self.surface, wheel_offsets, x_positions_m, z_positions_m, self.sampling)
        worst = self.worst_train_at_each_position(vehicle, response_to_one_vehicle, x_positions_m, adverse)
        factor = impact_factor(class_of(vehicle), self.span_m)
        shift_m = self.skew * z_positions_m
        train_x_front_m = [tuple(x_m + float(shift) for x_m in train) for train, shift in zip(worst.train_x_front_m, shift_m, strict=True)]
        return ResponseCurve(vehicle_name=vehicle.name, z_positions_m=z_positions_m, response=factor * worst.response, x_positions_m=worst.x_positions_m + shift_m, vehicles_in_train=worst.vehicles_in_train, train_x_front_m=train_x_front_m, impact_factor=factor)

    # worst train of any length at each position across
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

# shift wheel offsets for skew so they line up with the mesh
def along_the_mesh(wheel_offsets, skew):
    sheared = np.array(wheel_offsets, float)
    sheared[:, OFFSET_DX_M] -= skew * sheared[:, OFFSET_DZ_M]
    return sheared

# key a response curve is remembered by
def remembered_as(vehicle, z_positions_m, adverse):
    return (vehicle.name, adverse, len(z_positions_m), float(z_positions_m[0]), float(z_positions_m[-1]))

# positions across to try: an even spread plus where wheels hit stations
def positions_across_width(responses, vehicles, z_from_m, z_to_m):
    an_even_spread = np.linspace(z_from_m, z_to_m, responses.sampling.positions_across_the_deck_to_try)
    worth_sampling = [an_even_spread]
    for vehicle in vehicles:
        worth_sampling.append(bending_positions_across_width(responses.surface, wheel_load_offsets(vehicle, responses.wearing_course_thickness_m, responses.sampling), z_from_m, z_to_m))
    everywhere_m = np.unique(np.round(np.concatenate(worth_sampling), ROUND_TO_DECIMALS))
    is_on_the_deck = (everywhere_m >= z_from_m - TOLERANCE_M) & (everywhere_m <= z_to_m + TOLERANCE_M)
    return everywhere_m[is_on_the_deck]

# positions along where some wheel lands on a station
def positions_along_span(surface, wheel_offsets):
    stations_m = surface.length_mesh_m
    wheel_dx_m = np.asarray(wheel_offsets, float)[:, OFFSET_DX_M]
    puts_a_wheel_on_a_station_m = np.unique((stations_m[None, :] - wheel_dx_m[:, None]).ravel())
    part_way_onto_the_bridge_m = -wheel_dx_m.max()
    far_end_of_the_bridge_m = stations_m[-1]
    return keep_between(puts_a_wheel_on_a_station_m, part_way_onto_the_bridge_m, far_end_of_the_bridge_m)

# add positions one vehicle pitch apart so trains line up
def with_every_train_spacing(x_positions_m, vehicle):
    pitch_m = pitch_between_vehicles_m(vehicle)
    most_vehicles = most_vehicles_that_fit(vehicle, float(x_positions_m[0]), float(x_positions_m[-1]))
    one_pitch_apart = [x_positions_m + k * pitch_m for k in range(-(most_vehicles - 1), most_vehicles) if k]
    if not one_pitch_apart:
        return x_positions_m
    everywhere_m = np.unique(np.round(np.concatenate([x_positions_m, *one_pitch_apart]), ROUND_TO_DECIMALS))
    return keep_between(everywhere_m, float(x_positions_m[0]), float(x_positions_m[-1]))

# response to one vehicle at every x and z, a chunk at a time
def response_to_one_vehicle_everywhere(surface, wheel_offsets, x_positions_m, z_positions_m, sampling):
    responses = np.empty((len(x_positions_m), len(z_positions_m)))
    evaluated_at_once = sampling.span_positions_evaluated_at_once
    for start in range(0, len(x_positions_m), evaluated_at_once):
        chunk_x_m = x_positions_m[start:start + evaluated_at_once]
        responses[start:start + len(chunk_x_m)] = sum_over_wheels(surface, wheel_offsets, chunk_x_m, z_positions_m)
    return responses

# sum of wheel load times influence for every wheel, x and z at once
def sum_over_wheels(surface, wheel_offsets, x_positions_m, z_positions_m):
    wheel_dx_m, wheel_dz_m, wheel_loads_kn = split_offsets(np.asarray(wheel_offsets, float))
    x_positions_m = np.asarray(x_positions_m, float)
    z_positions_m = np.asarray(z_positions_m, float)
    if surface.skew:
        wheel_x_m = x_positions_m.reshape(-1, 1, 1) + wheel_dx_m.reshape(1, 1, -1)
        wheel_z_m = z_positions_m.reshape(1, -1, 1) + wheel_dz_m.reshape(1, 1, -1)
        return (surface.influence_at(wheel_x_m, wheel_z_m) * wheel_loads_kn).sum(axis=-1)
    total = np.zeros((len(x_positions_m), len(z_positions_m)))
    for dx_m, dz_m, load_kn in zip(wheel_dx_m, wheel_dz_m, wheel_loads_kn, strict=True):
        total += load_kn * under_one_wheel(surface, x_positions_m + dx_m, z_positions_m + dz_m)
    return total

# influence under one wheel line, interpolated in both directions
def under_one_wheel(surface, wheel_x_m, wheel_z_m):
    stations_m, strips_m = surface.length_mesh_m, surface.width_mesh_m
    j = cell_containing(strips_m, wheel_z_m)
    across = (wheel_z_m - strips_m[j]) / (strips_m[j + 1] - strips_m[j])
    along_each_station = surface.values[:, j] * (1 - across) + surface.values[:, j + 1] * across
    i = cell_containing(stations_m, wheel_x_m)
    along = ((wheel_x_m - stations_m[i]) / (stations_m[i + 1] - stations_m[i]))[:, None]
    influence = along_each_station[i] * (1 - along) + along_each_station[i + 1] * along
    on_the_deck = ((wheel_x_m >= stations_m[0]) & (wheel_x_m <= stations_m[-1]))[:, None] & ((wheel_z_m >= strips_m[0]) & (wheel_z_m <= strips_m[-1]))[None, :]
    return np.where(on_the_deck, influence, OFF_THE_DECK)

# z positions where a wheel crosses a mesh line and the curve bends
def bending_positions_across_width(surface, wheel_offsets, z_from_m, z_to_m):
    wheel_dz_m = np.asarray(wheel_offsets, float)[:, OFFSET_DZ_M]
    stations_m = surface.width_mesh_m
    puts_a_wheel_on_a_station_m = (stations_m[None, :] - wheel_dz_m[:, None]).ravel()
    both_ends_m = np.array([z_from_m, z_to_m], float)
    bends_m = np.unique(np.concatenate([puts_a_wheel_on_a_station_m, both_ends_m]))
    return keep_between(bends_m, z_from_m, z_to_m)

# positions between from and to
def keep_between(positions_m, from_m, to_m):
    is_in_range = (positions_m >= from_m - TOLERANCE_M) & (positions_m <= to_m + TOLERANCE_M)
    return positions_m[is_in_range]


# curve read at many positions, all at once when it can
def read_curve(curve, positions_m):
    positions_m = np.asarray(positions_m, float)
    responses = read_every_position_at_once(curve, positions_m)
    if responses is None:
        return read_one_position_at_a_time(curve, positions_m)
    return responses

# try the curve on the whole array; None if it can't take one
def read_every_position_at_once(curve, positions_m):
    try:
        responses = np.asarray(curve(positions_m), float)
    except (TypeError, ValueError):
        return None
    if responses.shape != positions_m.shape:
        return None
    return responses

# curve read one position at a time
def read_one_position_at_a_time(curve, positions_m):
    return np.array([float(curve(position)) for position in positions_m])

# positions to try inside a 70R zone: ends, an even spread and the curve's kinks
def positions_inside_zone(from_m, to_m, curve_breakpoints_m, sampling):
    both_ends = np.array([from_m, to_m], float)
    an_even_spread = np.linspace(from_m, to_m, sampling.positions_inside_a_70r_zone_to_try)
    breakpoints_m = np.asarray(curve_breakpoints_m, float)
    is_inside_the_zone = (breakpoints_m >= from_m - TOLERANCE_M) & (breakpoints_m <= to_m + TOLERANCE_M)
    worth_trying = [both_ends, an_even_spread, breakpoints_m[is_inside_the_zone]]
    return np.unique(np.round(np.concatenate(worth_trying), ROUND_TO_DECIMALS))

NOWHERE = -1

class TrainPlacement:
    # a train's response and where each vehicle stands
    def __init__(self, response, positions_m):
        self.response = response
        self.positions_m = positions_m

    # how many vehicles in the train
    def vehicles_in_train(self):
        return len(self.positions_m)

# for each position, the last one a pitch or more ahead
def last_position_a_vehicle_in_front_could_take(positions_m, pitch_m):
    return np.searchsorted(positions_m, positions_m - pitch_m, side='right') - 1

# worst place for a train of n vehicles, by dynamic programming
def place_train(response_to_one_vehicle, positions_m, pitch_m, vehicles_in_train, adverse):
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

# worst train of one up to the most vehicles that fit
def find_worst_train(response_to_one_vehicle, positions_m, pitch_m, most_vehicles, adverse):
    worst = None
    for how_many in range(1, int(most_vehicles) + 1):
        placement = place_train(response_to_one_vehicle, positions_m, pitch_m, how_many, adverse)
        if placement is None:
            break
        if worst is None or is_worse(placement.response, worst.response, adverse):
            worst = placement
    return worst

# read the vehicles' positions back from the last one
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
