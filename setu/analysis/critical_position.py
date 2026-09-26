import numpy as np
from setu.helpers import DEFAULT_SAMPLING
from setu.irc6.lanes import footway_loaded_strips, footway_response, strips_beside_class_a
from setu.irc6.vehicles import vehicles_allowed_in_each_block
from setu.analysis.results import CriticalPosition, VehiclePlacement
from setu.analysis.along_span import VehicleResponses, positions_across_width
from setu.analysis.across_carriageway import carries_a_residual_udl, envelope_every_block, find_worst_placement


# the worst legal IRC:6 traffic for this influence surface
def find_critical_position(surface, cross_section, span_m, adverse, wearing_course_thickness_m, sampling=DEFAULT_SAMPLING):
    return rank_all_positions(surface, cross_section, span_m, adverse, wearing_course_thickness_m, sampling)[0]


# every legal IRC:6 lane layout for this surface, worst first: vehicles, residual UDL and footway load
def rank_all_positions(surface, cross_section, span_m, adverse, wearing_course_thickness_m, sampling=DEFAULT_SAMPLING):
    carriageways = cross_section.carriageways()
    on_the_mesh = surface.along_the_mesh()
    permitted = vehicles_allowed_in_each_block()
    responses = VehicleResponses(on_the_mesh, span_m, wearing_course_thickness_m, surface.skew, sampling)
    every_vehicle = [vehicle for choices in permitted.values() for vehicle in choices]
    z_positions_m = positions_across_width(responses, every_vehicle, min(c.left_m for c in carriageways), max(c.right_m for c in carriageways))
    envelopes = [envelope_every_block(responses, permitted, z_positions_m, adverse, carriageway, on_the_mesh, sampling) for carriageway in carriageways]
    placements = find_worst_placement(carriageways, envelopes, adverse, z_positions_m, sampling)
    footway = footway_response(on_the_mesh, cross_section, adverse, span_m, sampling)
    footway_strips = footway_loaded_strips(cross_section, span_m)
    return [describe(placement, carriageways, envelopes, responses, permitted, footway, footway_strips, on_the_mesh.name, adverse, wearing_course_thickness_m)
            for placement in placements]


# turn one lane layout into a CriticalPosition with its vehicles and strips
def describe(placement, carriageways, envelopes, responses, permitted, footway, footway_strips, name, adverse, wearing_course_thickness_m):
    placed_vehicles = []
    pattern = []
    residual_udl_strips = []
    for carriageway, case in enumerate(placement.per_carriageway):
        pattern.append(' + '.join(case.lane_pattern))
        for block, z_centre_m in zip(case.lane_pattern, case.vehicle_centres_m, strict=True):
            winner = envelopes[carriageway][block].winner_at(z_centre_m)
            placed_vehicles.append(place_exactly(responses, permitted[block], winner, z_centre_m, adverse))
            on = carriageways[carriageway]
            if carries_a_residual_udl(block, on):
                residual_udl_strips += strips_beside_class_a(float(z_centre_m), on.left_m, on.right_m)
    return CriticalPosition(response_name=name or 'response', adverse=adverse, response=placement.response + footway * placement.lane_reduction,
                            response_before_reduction=placement.response_before_reduction + footway, lane_reduction=placement.lane_reduction,
                            design_lanes=placement.design_lanes, lane_pattern=' | '.join(pattern), vehicles=placed_vehicles, footway_response=footway,
                            residual_udl_strips=residual_udl_strips, footway_strips=footway_strips, wearing_course_thickness_m=wearing_course_thickness_m)


# re-solve the winning vehicle exactly at its centre for x and impact
def place_exactly(responses, choices, winner, z_centre_m, adverse):
    vehicle = next(choice for choice in choices if choice.name == winner)
    exactly_here = responses.for_vehicle(vehicle, np.array([z_centre_m]), adverse)
    return VehiclePlacement(vehicle_name=vehicle.name, z_centre_m=float(z_centre_m), x_front_m=float(exactly_here.x_positions_m[0]),
                            impact_factor=exactly_here.impact_factor, train_x_front_m=exactly_here.train_x_front_m[0])
