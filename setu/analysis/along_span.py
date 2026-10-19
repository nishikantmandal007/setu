from functools import lru_cache

import numpy as np
from setu.analysis.influence_surface import cell_containing
from setu.helpers import adverse_sign
from setu.irc6.impact import impact_factor
from setu.irc6.vehicles import class_of, most_vehicles_that_fit, pitch_between_vehicles_m
from setu.irc6.wheel_loads import split_offsets, wheel_load_offsets
from setu.utils.constants import OFF_THE_DECK, OFFSET_DX_M, OFFSET_DZ_M, ROUND_TO_DECIMALS, TOLERANCE_M

WHEEL_LINE_WEIGHTS_KEPT = 16  # distinct (mesh, vehicle, grid) sets held at once; each is a few MB
SURFACES_SEARCHED_TOGETHER = 2  # both directions of one surface are searched one after the other

# running best value and where it was, left to right along the last axis
def best_so_far(values):
    values = np.asarray(values, float)
    every_position = np.arange(values.shape[-1])
    best_value_so_far = np.maximum.accumulate(values, axis=-1)
    beats_everything_before_it = np.empty(values.shape, bool)
    beats_everything_before_it[..., 0] = True
    beats_everything_before_it[..., 1:] = values[..., 1:] > best_value_so_far[..., :-1]
    position_when_it_is_a_new_best = np.where(beats_everything_before_it, every_position, -1)
    position_of_the_best_so_far = np.maximum.accumulate(position_when_it_is_a_new_best, axis=-1)
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
        self._grids = {}

    # the vehicle's response curve, built once and remembered
    def for_vehicle(self, vehicle, z_positions_m, adverse):
        z_positions_m = np.asarray(z_positions_m, float)
        remembered = remembered_as(vehicle, z_positions_m, adverse)
        if remembered not in self._already_built:
            self._already_built[remembered] = self.build_curve(vehicle, z_positions_m, adverse)
        return self._already_built[remembered]

    # one vehicle's response at every position along and across, worked out once for both directions
    def grid_for(self, vehicle, z_positions_m):
        key = (vehicle.name, len(z_positions_m), float(z_positions_m[0]), float(z_positions_m[-1]))
        if key not in self._grids:
            wheel_offsets = along_the_mesh(wheel_load_offsets(vehicle, self.wearing_course_thickness_m, self.sampling), self.skew)
            x_positions_m = with_every_train_spacing(positions_along_span(self.surface, wheel_offsets), vehicle)
            self._grids[key] = (x_positions_m, response_to_one_vehicle_everywhere(self.surface, wheel_offsets, x_positions_m, z_positions_m, self.sampling))
        return self._grids[key]

    # slide the vehicle, or a train of them, along the span at every position across, keep the worst
    def build_curve(self, vehicle, z_positions_m, adverse):
        x_positions_m, response_to_one_vehicle = self.grid_for(vehicle, z_positions_m)
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
        for z_index, worst in enumerate(find_worst_trains(response_to_one_vehicle, x_positions_m, pitch_m, longest_train, adverse)):
            if worst is None:
                raise RuntimeError('no legal placement was found for even a single vehicle at one of the positions across the width, but one vehicle should always fit')
            response[z_index] = worst.response
            leading_x_m[z_index] = worst.positions_m[0]
            vehicles_in_train[z_index] = worst.vehicles_in_train()
            trains.append(worst.positions_m)
        return WorstAlongSpan(response=response, x_positions_m=leading_x_m, vehicles_in_train=vehicles_in_train, train_x_front_m=trains)

# the vehicle responses for one surface, shared by the searches in both directions that follow each other
@lru_cache(maxsize=SURFACES_SEARCHED_TOGETHER)
def vehicle_responses(surface, span_m, wearing_course_thickness_m, sampling):
    return VehicleResponses(surface.along_the_mesh(), span_m, wearing_course_thickness_m, surface.skew, sampling)

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

# response to one vehicle at every x and z: per wheel line, x weights · surface · z weights, or chunked when skewed
def response_to_one_vehicle_everywhere(surface, wheel_offsets, x_positions_m, z_positions_m, sampling):
    if not surface.skew:
        responses = np.zeros((len(x_positions_m), len(z_positions_m)))
        for along, across in wheel_line_weights(surface.length_mesh_m, surface.width_mesh_m, wheel_offsets, x_positions_m, z_positions_m):
            responses += along @ surface.values @ across.T
        return responses
    responses = np.empty((len(x_positions_m), len(z_positions_m)))
    evaluated_at_once = sampling.span_positions_evaluated_at_once
    for start in range(0, len(x_positions_m), evaluated_at_once):
        chunk_x_m = x_positions_m[start:start + evaluated_at_once]
        responses[start:start + len(chunk_x_m)] = sum_over_wheels(surface, wheel_offsets, chunk_x_m, z_positions_m)
    return responses

# the interpolation weights of each wheel line; they depend on the mesh, vehicle and grids, never on the surface
def wheel_line_weights(stations_m, strips_m, wheel_offsets, x_positions_m, z_positions_m):
    arrays = [np.ascontiguousarray(a, float) for a in (stations_m, strips_m, wheel_offsets, x_positions_m, z_positions_m)]
    return cached_wheel_line_weights(*((a.tobytes(), a.shape) for a in arrays))

# one entry per distinct mesh, vehicle and grid; every surface on that mesh reuses it
@lru_cache(maxsize=WHEEL_LINE_WEIGHTS_KEPT)
def cached_wheel_line_weights(*packed):
    stations_m, strips_m, wheel_offsets, x_positions_m, z_positions_m = (np.frombuffer(data).reshape(shape) for data, shape in packed)
    wheel_dx_m, wheel_dz_m, wheel_loads_kn = split_offsets(wheel_offsets)
    lines = []
    for dz_m in np.unique(wheel_dz_m):
        on_line = wheel_dz_m == dz_m
        along = sum(load_kn * interpolation_weights(stations_m, x_positions_m + dx_m) for dx_m, load_kn in zip(wheel_dx_m[on_line], wheel_loads_kn[on_line]))
        lines.append((along, interpolation_weights(strips_m, z_positions_m + dz_m)))
    return tuple(lines)

# linear interpolation weights from mesh stations to positions; a position off the mesh gets a zero row (OFF_THE_DECK)
def interpolation_weights(stations_m, positions_m):
    cell = cell_containing(stations_m, positions_m)
    fraction = (positions_m - stations_m[cell]) / (stations_m[cell + 1] - stations_m[cell])
    on_the_mesh = np.flatnonzero((positions_m >= stations_m[0]) & (positions_m <= stations_m[-1]))
    weights = np.zeros((len(positions_m), len(stations_m)))
    weights[on_the_mesh, cell[on_the_mesh]] = 1 - fraction[on_the_mesh]
    weights[on_the_mesh, cell[on_the_mesh] + 1] = fraction[on_the_mesh]
    return weights

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

# one more vehicle behind the best train so far, positions along the last axis: its signed total and where the vehicle
# in front sat, NOWHERE when it has no room
def add_a_vehicle(signed_one, signed_total, vehicle_in_front):
    has_room_in_front = vehicle_in_front >= 0
    room_in_front = vehicle_in_front[has_room_in_front]
    best_behind, where_that_best_sat = best_so_far(signed_total)
    with_one_more = np.full_like(signed_one, -np.inf)
    with_one_more[..., has_room_in_front] = signed_one[..., has_room_in_front] + best_behind[..., room_in_front]
    came_from = np.full(signed_one.shape, NOWHERE, int)
    came_from[..., has_room_in_front] = where_that_best_sat[..., room_in_front]
    return with_one_more, came_from

# worst place for a train of n vehicles, by dynamic programming
def place_train(response_to_one_vehicle, positions_m, pitch_m, vehicles_in_train, adverse):
    response_to_one_vehicle = np.asarray(response_to_one_vehicle, float)
    positions_m = np.asarray(positions_m, float)
    signed_one = adverse_sign(adverse) * response_to_one_vehicle
    vehicle_in_front = last_position_a_vehicle_in_front_could_take(positions_m, pitch_m)
    signed_best_total = signed_one
    position_of_the_vehicle_in_front = []
    for _ in range(1, vehicles_in_train):
        signed_best_total, came_from = add_a_vehicle(signed_one, signed_best_total, vehicle_in_front)
        position_of_the_vehicle_in_front.append(came_from)
    if not np.isfinite(signed_best_total).any():
        return None
    chosen = walk_back_through_the_train(signed_best_total, position_of_the_vehicle_in_front)
    if chosen is None:
        return None
    return TrainPlacement(response=float(sum(response_to_one_vehicle[position] for position in chosen)),
                          positions_m=tuple(float(positions_m[position]) for position in chosen))

# worst train of one up to the most vehicles that fit
def find_worst_train(response_to_one_vehicle, positions_m, pitch_m, most_vehicles, adverse):
    return find_worst_trains(np.asarray(response_to_one_vehicle, float)[:, None], positions_m, pitch_m, most_vehicles, adverse)[0]

# worst train of one up to the most vehicles that fit, for every position across the width in one pass;
# each length grows the previous one, a longer train wins only if strictly worse, a position stops at its first length that cannot fit
def find_worst_trains(response_to_one_vehicle, positions_m, pitch_m, most_vehicles, adverse):
    across_then_along = np.ascontiguousarray(np.asarray(response_to_one_vehicle, float).T)  # one row per position across, so each running best reads memory in order
    positions_m = np.asarray(positions_m, float)
    signed_one = adverse_sign(adverse) * across_then_along
    vehicle_in_front = last_position_a_vehicle_in_front_could_take(positions_m, pitch_m)
    signed_total = signed_one
    came_from_each_vehicle = []
    still_fits = np.ones(signed_one.shape[0], bool)
    signed_worst = np.full(signed_one.shape[0], -np.inf)
    worst_train = [None] * signed_one.shape[0]  # (chosen positions of its length, its column among them) of each row's worst train
    for vehicles in range(1, int(most_vehicles) + 1):
        if vehicles > 1:
            signed_total, came_from = add_a_vehicle(signed_one, signed_total, vehicle_in_front)
            came_from_each_vehicle.append(came_from)
        still_fits &= np.isfinite(signed_total).any(axis=1)
        columns = np.flatnonzero(still_fits)
        if not len(columns):
            break
        chosen = walk_back_every_column(signed_total, came_from_each_vehicle, columns)
        response = np.zeros(len(columns))  # 0 + first, then left to right, exactly as Python's sum over these numpy values
        for position in chosen:
            response = response + across_then_along[columns, position]
        signed_response = adverse_sign(adverse) * response
        is_worse_here = signed_response > signed_worst[columns]  # strictly worse, so a longer train must beat a shorter one
        for k in np.flatnonzero(is_worse_here):
            worst_train[columns[k]] = (chosen, k)
        signed_worst[columns[is_worse_here]] = signed_response[is_worse_here]
    return [None if train is None else placed_train(across_then_along, positions_m, train[0], train[1], row) for row, train in enumerate(worst_train)]

# a row's worst train with its response summed front to back, as it was compared
def placed_train(across_then_along, positions_m, chosen, k, row):
    response = 0.0
    for position in chosen:
        response = response + across_then_along[row, position[k]]
    return TrainPlacement(response=float(response), positions_m=tuple(float(positions_m[position[k]]) for position in chosen))

# the worst train's positions for the chosen rows across, front vehicle first, read back from the last vehicle
def walk_back_every_column(signed_total, came_from_each_vehicle, columns):
    position = np.argmax(signed_total[columns], axis=1)
    chosen = [position]
    for came_from in reversed(came_from_each_vehicle):
        position = came_from[columns, position]
        chosen.append(position)
    chosen.reverse()
    return chosen

# read the vehicles' positions back from the last one
def walk_back_through_the_train(signed_best_total, position_of_the_vehicle_in_front):
    position = int(np.argmax(signed_best_total))
    chosen = [position]
    for where_the_vehicle_in_front_sat in reversed(position_of_the_vehicle_in_front):
        position = int(where_the_vehicle_in_front_sat[position])
        if position == NOWHERE:
            return None
        chosen.append(position)
    chosen.reverse()
    return chosen
