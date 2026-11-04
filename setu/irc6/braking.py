from setu.irc6.irc_constants import (
    BRAKING_FIRST_TRAIN_FRACTION,
    BRAKING_FOLLOWING_TRAINS_FRACTION,
    BRAKING_LANES_BEYOND_TWO_FRACTION,
    BRAKING_LANES_COUNTED_AS_ONE,
)
from setu.irc6.vehicles import find_vehicle_or_its_reverse
from setu.helpers import DEFAULT_SAMPLING
from setu.irc6.wheel_loads import wheel_load_offsets
from setu.utils.constants import TOLERANCE_M

DESIGN_LANES_PER_70R_ZONE = 2  # Fig. 1 note 2: each Class 70R occupies two lanes
VEHICLE_70R_PREFIX = "Class_70R"


# clause 211.2 braking force for the whole critical position: (a) on one lane, plus (b) 5 % of the loads on the lanes beyond the
# first two design lanes; a 70R occupies two lanes (Fig. 1 note 2); the first two lanes are taken where the force is largest (204.1.2)
def braking_force_kn(critical_position, span_m, skew):
    lanes = [(design_lanes_of(placed), trains_on_the_span_kn(placed, span_m, skew, critical_position.wearing_course_thickness_m)) for placed in critical_position.vehicles]
    if not lanes:
        return 0.0
    return max(braking_with_this_lane_first(lanes, first) for first in range(len(lanes)))


# a 70R occupies two design lanes, any other vehicle one
def design_lanes_of(placed):
    return DESIGN_LANES_PER_70R_ZONE if placed.vehicle_name.startswith(VEHICLE_70R_PREFIX) else 1


# (a) on lane `first`, the lightest other one-lane vehicles filling the rest of the first two lanes, 5 % of every remaining load
def braking_with_this_lane_first(lanes, first):
    lanes_used, _ = lanes[first]
    others = sorted((sum(trains_kn), lanes_taken) for k, (lanes_taken, trains_kn) in enumerate(lanes) if k != first)
    beyond_kn = 0.0
    for load_kn, lanes_taken in others:
        if lanes_used + lanes_taken <= BRAKING_LANES_COUNTED_AS_ONE:
            lanes_used += lanes_taken
        else:
            beyond_kn += load_kn
    return braking_in_one_lane_kn(lanes[first][1]) + BRAKING_LANES_BEYOND_TWO_FRACTION * beyond_kn


# 20% of the first train plus 10% of the ones behind it
def braking_in_one_lane_kn(trains_kn):
    heaviest_first = sorted(trains_kn, reverse=True)
    return BRAKING_FIRST_TRAIN_FRACTION * heaviest_first[0] + BRAKING_FOLLOWING_TRAINS_FRACTION * sum(heaviest_first[1:])


# weight of each vehicle of a train that is actually on the span
def trains_on_the_span_kn(placed, span_m, skew, wearing_course_thickness_m):
    vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
    return [sum(load_kn for _, _, load_kn in wheels_on_the_span(vehicle, x_front_m, placed.z_centre_m, span_m, skew, wearing_course_thickness_m)) for x_front_m in placed.train_x_front_m]


# the wheels of a vehicle that land on the span, as (x, z, load)
def wheels_on_the_span(vehicle, x_front_m, z_centre_m, span_m, skew, wearing_course_thickness_m):
    wheels = []
    for dx_m, dz_m, load_kn in wheel_load_offsets(vehicle, wearing_course_thickness_m, DEFAULT_SAMPLING):
        x_m = x_front_m + dx_m
        z_m = z_centre_m + dz_m
        along_m = x_m - skew * z_m
        if -TOLERANCE_M <= along_m <= span_m + TOLERANCE_M:
            wheels.append((x_m, z_m, float(load_kn)))
    return wheels
