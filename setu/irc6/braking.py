from setu.irc6.irc_constants import (
    BRAKING_FIRST_TRAIN_FRACTION,
    BRAKING_FOLLOWING_TRAINS_FRACTION,
    BRAKING_LANES_BEYOND_TWO_FRACTION,
    BRAKING_LANES_COUNTED_AS_ONE,
)
from setu.irc6.vehicles import find_vehicle_or_its_reverse
from setu.irc6.wheel_loads import wheel_load_offsets
from setu.utils.constants import TOLERANCE_M


# clause 211 braking force for the whole critical position
def braking_force_kn(critical_position, span_m, skew=0.0):
    lanes = sorted((trains_on_the_span_kn(placed, span_m, skew) for placed in critical_position.vehicles), key=sum, reverse=True)
    if not lanes:
        return 0.0
    one_lane_kn = max(braking_in_one_lane_kn(trains_kn) for trains_kn in lanes)
    beyond_two_lanes_kn = sum(sum(trains_kn) for trains_kn in lanes[BRAKING_LANES_COUNTED_AS_ONE:])
    return one_lane_kn + BRAKING_LANES_BEYOND_TWO_FRACTION * beyond_two_lanes_kn


# 20% of the first train plus 5% of the ones behind it
def braking_in_one_lane_kn(trains_kn):
    heaviest_first = sorted(trains_kn, reverse=True)
    return BRAKING_FIRST_TRAIN_FRACTION * heaviest_first[0] + BRAKING_FOLLOWING_TRAINS_FRACTION * sum(heaviest_first[1:])


# weight of each vehicle of a train that is actually on the span
def trains_on_the_span_kn(placed, span_m, skew):
    vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
    return [sum(load_kn for _, _, load_kn in wheels_on_the_span(vehicle, x_front_m, placed.z_centre_m, span_m, skew)) for x_front_m in placed.train_x_front_m]


# the wheels of a vehicle that land on the span, as (x, z, load)
def wheels_on_the_span(vehicle, x_front_m, z_centre_m, span_m, skew=0.0):
    wheels = []
    for dx_m, dz_m, load_kn in wheel_load_offsets(vehicle):
        x_m = x_front_m + dx_m
        z_m = z_centre_m + dz_m
        along_m = x_m - skew * z_m
        if -TOLERANCE_M <= along_m <= span_m + TOLERANCE_M:
            wheels.append((x_m, z_m, float(load_kn)))
    return wheels
