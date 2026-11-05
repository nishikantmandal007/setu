import copy

import numpy as np
from setu.helpers import DEFAULT_SAMPLING
from setu.helpers import is_worst_first
from setu.irc6.irc_constants import CROWD_LOAD_KPA
from setu.irc6.lanes import congestion_factor, footway_live_load_strips, footway_loaded_strips, footway_response, response_to_area_load, strips_beside_class_a
from setu.irc6.vehicles import vehicles_allowed_in_each_block
from setu.analysis.results import CriticalPosition, VehiclePlacement
from setu.analysis.along_span import positions_across_width, vehicle_responses
from setu.analysis.across_carriageway import carries_a_residual_udl, envelope_every_block, find_worst_placement


# the worst legal IRC:6 traffic for this influence surface; lane_reduction=False for cross girders and diaphragms (Table 8 note 3, Amendment 10)
# Every other arrangement's worst placement rides along as .alternatives: braking, added later on the real solve, can make one of them worse.
def find_critical_position(surface, cross_section, span_m, adverse, wearing_course_thickness_m, sampling=DEFAULT_SAMPLING, lane_reduction=True):
    ranked = with_site_conditions(list(described_positions(surface, cross_section, span_m, adverse, wearing_course_thickness_m, sampling, lane_reduction)),
                                  surface, cross_section, span_m, adverse, sampling)
    worst = ranked[0]
    worst.alternatives = ranked[1:]
    return worst


# every legal IRC:6 lane layout for this surface, worst first: vehicles, residual UDL and footway load
def rank_all_positions(surface, cross_section, span_m, adverse, wearing_course_thickness_m, sampling=DEFAULT_SAMPLING, lane_reduction=True):
    return with_site_conditions(list(described_positions(surface, cross_section, span_m, adverse, wearing_course_thickness_m, sampling, lane_reduction)),
                                surface, cross_section, span_m, adverse, sampling)


# the cases the authority's site conditions add, sorted in with the traffic: each placement congested (cl. 204.4: Table 7 factor on the
# vehicles after impact and reduction, footway unchanged, no braking), and crowd load on the whole deck (cl. 206.1)
def with_site_conditions(ranked, surface, cross_section, span_m, adverse, sampling):
    extra = []
    if cross_section.congestion:
        factor = congestion_factor(span_m)
        extra += [congested(placement, factor) for placement in ranked if placement.vehicles]
    if cross_section.crowd_load:
        extra.append(crowd_everywhere(surface, cross_section, adverse, sampling, ranked[0]))
    if not extra:
        return ranked
    return sorted(ranked + extra, key=lambda placement: placement.response, reverse=is_worst_first(adverse))


# a placement with its vehicles' share times the Table 7 factor and no braking
def congested(placement, factor):
    footway_share = placement.footway_response * placement.lane_reduction
    twin = copy.copy(placement)
    twin.response = factor * (placement.response - footway_share) + footway_share
    twin.response_before_reduction = factor * (placement.response_before_reduction - placement.footway_response) + placement.footway_response
    twin.lane_pattern = f"{placement.lane_pattern} (congested, x {factor:.4f}, IRC:6 cl. 204.4)"
    twin.takes_braking = False
    twin.congestion_factor = factor
    twin.alternatives = []
    return twin


# crowd load 5 kN/m2 over every carriageway and footway where it makes the response worse (206.1); not a vehicle, so no cl. 208 impact; no braking; no 205 reduction (interpretation, conservative)
def crowd_everywhere(surface, cross_section, adverse, sampling, like):
    on_the_mesh = surface.along_the_mesh()
    strips = [(c.left_m, c.right_m) for c in cross_section.carriageways()] + [(s.z_from_m, s.z_to_m) for s in footway_live_load_strips(cross_section)]
    response = response_to_area_load(on_the_mesh, strips, adverse, CROWD_LOAD_KPA, sampling)
    crowd = CriticalPosition(response_name=like.response_name, adverse=adverse, response=response, response_before_reduction=response, lane_reduction=1.0,
                             design_lanes=0, lane_pattern="crowd load on the whole deck (IRC:6 cl. 206.1)", vehicles=[], footway_response=response,
                             residual_udl_strips=[], footway_strips=[(a, b, CROWD_LOAD_KPA) for a, b in strips], wearing_course_thickness_m=like.wearing_course_thickness_m)
    crowd.takes_braking = False
    return crowd


# describe layouts on demand so a winning-only search stops after the first
def described_positions(surface, cross_section, span_m, adverse, wearing_course_thickness_m, sampling, lane_reduction=True):
    carriageways = cross_section.carriageways()
    responses = vehicle_responses(surface, span_m, wearing_course_thickness_m, sampling)
    on_the_mesh = responses.surface
    permitted = vehicles_allowed_in_each_block()
    every_vehicle = [vehicle for choices in permitted.values() for vehicle in choices]
    z_positions_m = positions_across_width(responses, every_vehicle, min(c.left_m for c in carriageways), max(c.right_m for c in carriageways))
    envelopes = [envelope_every_block(responses, permitted, z_positions_m, adverse, carriageway, on_the_mesh, sampling) for carriageway in carriageways]
    placements = find_worst_placement(carriageways, envelopes, adverse, z_positions_m, sampling, lane_reduction)
    footway = footway_response(on_the_mesh, cross_section, adverse, span_m, sampling)
    footway_strips = footway_loaded_strips(cross_section, span_m)
    for placement in placements:
        yield describe(placement, carriageways, envelopes, responses, permitted, footway, footway_strips, on_the_mesh.name, adverse, wearing_course_thickness_m)


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
