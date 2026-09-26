import numpy as np

from setu.irc6.vehicles import TrackedVehicle
from setu.utils.constants import GRAVITY_KN_PER_TONNE, OFFSET_DX_M, OFFSET_DZ_M, OFFSET_LOAD_KN

LEFT_OF_THE_CENTRELINE = -1
RIGHT_OF_THE_CENTRELINE = +1
BOTH_SIDES = (LEFT_OF_THE_CENTRELINE, RIGHT_OF_THE_CENTRELINE)
WHEELS_PER_AXLE = 2


# the dx, dz and load columns of the offset table
def split_offsets(offsets):
    return (offsets[:, OFFSET_DX_M], offsets[:, OFFSET_DZ_M], offsets[:, OFFSET_LOAD_KN])

# point loads of a vehicle relative to its front centre
def wheel_load_offsets(vehicle, wearing_course_thickness_m, sampling):
    if isinstance(vehicle, TrackedVehicle):
        return offsets_for_tracks(vehicle, wearing_course_thickness_m, sampling)
    return offsets_for_axles(vehicle)

# two wheels per axle, half the axle load each
def offsets_for_axles(vehicle):
    half_gauge_m = vehicle.transverse_gauge_m / 2.0
    offsets = []
    axles = zip(vehicle.axle_loads_t, vehicle.axle_positions_m(), strict=True)
    for axle_load_t, dx_m in axles:
        wheel_load_kn = axle_load_t * GRAVITY_KN_PER_TONNE / WHEELS_PER_AXLE
        for side in BOTH_SIDES:
            offsets.append((dx_m, side * half_gauge_m, wheel_load_kn))
    return np.array(offsets, float)

# each track as a grid of point loads, spread through the wearing course
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

