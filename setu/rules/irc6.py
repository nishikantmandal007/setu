from setu.config.constants import *

import numpy as np

from setu.utils.helpers import adverse_sign, where_a_load_hurts, DEFAULT_SAMPLING

from setu.models.vehicles import pitch_between_vehicles_m, TrackedVehicle, AxleVehicle, CLASS_A, CLASS_70R_WHEELED, IRC_VEHICLES

def is_steel(material):
    return material == 'steel'

def is_tracked(vehicle_name):
    return 'Tracked' in vehicle_name

def is_class_a(vehicle_name):
    return vehicle_name == 'Class_A'

def class_a_impact_fraction(span_m, material='steel'):
    span_m = min(max(float(span_m), SHORTEST_TABULATED_SPAN_M), LONGEST_TABULATED_SPAN_M)
    if is_steel(material):
        return 9.0 / (13.5 + span_m)
    return 4.5 / (6.0 + span_m)

def impact_fraction(vehicle_name, span_m, material='steel'):
    span_m = float(span_m)
    if is_class_a(vehicle_name):
        return class_a_impact_fraction(span_m, material)
    if span_m < SHORT_SPAN_UPPER_LIMIT_M:
        return short_span_impact_fraction(span_m, is_tracked(vehicle_name))
    return long_span_impact_fraction(span_m, is_tracked(vehicle_name), material)

def short_span_impact_fraction(span_m, vehicle_is_tracked):
    if not vehicle_is_tracked:
        return SHORT_SPAN_IMPACT_FRACTION
    if span_m <= TRACKED_TRANSITION_START_SPAN_M:
        return SHORT_SPAN_IMPACT_FRACTION
    fall = TRACKED_IMPACT_FRACTION_FLOOR - SHORT_SPAN_IMPACT_FRACTION
    into_the_band_m = span_m - TRACKED_TRANSITION_START_SPAN_M
    fallen_so_far = fall * into_the_band_m / TRACKED_TRANSITION_SPAN_WIDTH_M
    return SHORT_SPAN_IMPACT_FRACTION + fallen_so_far

def long_span_impact_fraction(span_m, vehicle_is_tracked, material):
    if vehicle_is_tracked:
        return tracked_long_span_impact_fraction(span_m, material)
    return wheeled_70r_long_span_impact_fraction(span_m, material)

def tracked_long_span_impact_fraction(span_m, material):
    if is_steel(material):
        return TRACKED_IMPACT_FRACTION_FLOOR
    if span_m <= TRACKED_RC_IMPACT_PLATEAU_LIMIT_M:
        return TRACKED_IMPACT_FRACTION_FLOOR
    return class_a_impact_fraction(span_m, 'rc')

def wheeled_70r_long_span_impact_fraction(span_m, material):
    if is_steel(material):
        curve_takes_over_above_m = WHEELED_70R_IMPACT_CURVE_TAKES_OVER_STEEL_M
    else:
        curve_takes_over_above_m = WHEELED_70R_IMPACT_CURVE_TAKES_OVER_RC_M
    if span_m <= curve_takes_over_above_m:
        return SHORT_SPAN_IMPACT_FRACTION
    return class_a_impact_fraction(span_m, material)

def impact_factor(vehicle_name, span_m, material='steel'):
    return 1.0 + impact_fraction(vehicle_name, span_m, material)

from itertools import product, zip_longest

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

LEFT_OF_THE_CENTRELINE = -1
RIGHT_OF_THE_CENTRELINE = +1
BOTH_SIDES = (LEFT_OF_THE_CENTRELINE, RIGHT_OF_THE_CENTRELINE)
WHEELS_PER_AXLE = 2
OFFSET_DX_M = 0
OFFSET_DZ_M = 1
OFFSET_LOAD_KN = 2

class WheelLoad:
    def __init__(self, x_m, z_m, load_kn):
        self.x_m = x_m
        self.z_m = z_m
        self.load_kn = load_kn

    def to_dict(self):
        return self.__dict__

class ContactPatch:
    def __init__(self, x_from_m, x_to_m, z_from_m, z_to_m, pressure_kpa):
        self.x_from_m = x_from_m
        self.x_to_m = x_to_m
        self.z_from_m = z_from_m
        self.z_to_m = z_to_m
        self.pressure_kpa = pressure_kpa

    def to_dict(self):
        return self.__dict__

    def total_load_kn(self):
        length_m = self.x_to_m - self.x_from_m
        width_m = self.z_to_m - self.z_from_m
        return self.pressure_kpa * length_m * width_m

class LaneAssignment:
    def __init__(self, vehicle, x_front_m, z_centre_m, how_many=1, gap_m=None):
        self.vehicle = vehicle
        self.x_front_m = x_front_m
        self.z_centre_m = z_centre_m
        self.how_many = how_many
        self.gap_m = gap_m

    def to_dict(self):
        return self.__dict__

def split_offsets(offsets):
    return (offsets[:, OFFSET_DX_M], offsets[:, OFFSET_DZ_M], offsets[:, OFFSET_LOAD_KN])

def wheel_load_offsets(vehicle, wearing_course_thickness_m=0.0, sampling=DEFAULT_SAMPLING):
    if isinstance(vehicle, TrackedVehicle):
        return offsets_for_tracks(vehicle, wearing_course_thickness_m, sampling)
    return offsets_for_axles(vehicle)

def offsets_for_axles(vehicle):
    half_gauge_m = vehicle.transverse_gauge_m / 2.0
    offsets = []
    axles = zip(vehicle.axle_loads_t, vehicle.axle_positions_m(), strict=True)
    for axle_load_t, dx_m in axles:
        wheel_load_kn = axle_load_t * GRAVITY_KN_PER_TONNE / WHEELS_PER_AXLE
        for side in BOTH_SIDES:
            offsets.append((dx_m, side * half_gauge_m, wheel_load_kn))
    return np.array(offsets, float)

def offsets_for_tracks(vehicle, wearing_course_thickness_m, sampling):
    length_m = vehicle.track_length_m + 2.0 * wearing_course_thickness_m
    width_m = vehicle.track_width_m + 2.0 * wearing_course_thickness_m
    steps_along = sampling.point_loads_along_a_track
    steps_across = sampling.point_loads_across_a_track
    points_per_track = steps_along * steps_across
    load_per_point_kn = vehicle.load_per_track_t * GRAVITY_KN_PER_TONNE / points_per_track
    dx_m = (np.arange(steps_along) + 0.5) * length_m / steps_along
    dz_m = (np.arange(steps_across) + 0.5) * width_m / steps_across - width_m / 2.0
    half_gauge_m = vehicle.transverse_gauge_m / 2.0
    offsets = [(along_m, side * half_gauge_m + across_m, load_per_point_kn) for side in BOTH_SIDES for along_m in dx_m for across_m in dz_m]
    return np.array(offsets, float)

def wheel_loads_at(vehicle, x_front_m, z_centre_m, wearing_course_thickness_m=0.0):
    offsets = wheel_load_offsets(vehicle, wearing_course_thickness_m)
    return [WheelLoad(x_m=x_front_m + dx_m, z_m=z_centre_m + dz_m, load_kn=load_kn) for dx_m, dz_m, load_kn in offsets]

def contact_patches_at(vehicle, x_front_m, z_centre_m):
    half_gauge_m = vehicle.transverse_gauge_m / 2.0
    half_track_m = vehicle.track_width_m / 2.0
    pressure_kpa = vehicle.contact_pressure_kpa()
    patches = []
    for side in BOTH_SIDES:
        track_centre_m = z_centre_m + side * half_gauge_m
        patches.append(ContactPatch(x_from_m=x_front_m, x_to_m=x_front_m + vehicle.track_length_m, z_from_m=track_centre_m - half_track_m, z_to_m=track_centre_m + half_track_m, pressure_kpa=pressure_kpa))
    return patches

def train_at(vehicle, x_front_of_leader_m, z_centre_m, how_many=1, gap_m=None):
    if gap_m is None:
        gap_m = vehicle.min_nose_to_tail_m
    pitch_m = vehicle.length_m() + gap_m
    wheel_loads = []
    patches = []
    for position_in_train in range(how_many):
        x_front_m = x_front_of_leader_m + position_in_train * pitch_m
        if isinstance(vehicle, TrackedVehicle):
            patches.extend(contact_patches_at(vehicle, x_front_m, z_centre_m))
        else:
            wheel_loads.extend(wheel_loads_at(vehicle, x_front_m, z_centre_m))
    return (wheel_loads, patches)

def loads_for_lanes(lanes):
    all_wheel_loads = []
    all_patches = []
    for lane in lanes:
        wheel_loads, patches = train_at(lane.vehicle, lane.x_front_m, lane.z_centre_m, lane.how_many, lane.gap_m)
        all_wheel_loads.extend(wheel_loads)
        all_patches.extend(patches)
    return (all_wheel_loads, all_patches)


def braking_force_kn(total_live_load_kn):
    return 0.2 * total_live_load_kn


def seismic_coefficient(zone_factor, importance_factor, response_reduction, sa_over_g=2.5):
    return (zone_factor / 2.0) * (importance_factor / response_reduction) * sa_over_g


K2_TERRAIN_CATEGORY_2 = {10: 1.00, 15: 1.05, 20: 1.10, 30: 1.15, 50: 1.20}


def wind_pressure_kpa(basic_speed_mps, deck_height_m, drag_coefficient=1.2, terrain_category=2):
    if terrain_category != 2:
        raise ValueError(f"only terrain category 2 is implemented, got {terrain_category}")
    k1 = 1.0
    k2 = 1.0
    for threshold, factor in K2_TERRAIN_CATEGORY_2.items():
        if deck_height_m <= threshold:
            k2 = factor
            break
    else:
        k2 = 1.20
    k3 = 1.0
    design_speed = basic_speed_mps * k1 * k2 * k3
    return 0.6 * design_speed ** 2 / 1000 * drag_coefficient