import numpy as np

from setu.irc6.constants import GRAVITY_KN_PER_TONNE
from setu.helpers import DEFAULT_SAMPLING
from setu.models.vehicles import TrackedVehicle

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
