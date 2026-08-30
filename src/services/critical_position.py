import numpy as np
from src.utils.helpers import *
from src.utils.code_rules import *
from src.models.results import *
from src.models.vehicles import vehicles_allowed_in_each_block
from src.services.placement import *

NO_FOOTWAY_LOAD = 0.0
READ_EACH_CARRIAGEWAY_ON_ITS_OWN = "separate"

NO_FOOTWAY_LOAD = 0.0

class SearchOptions:
    def __init__(self, adverse, vehicles, carriageways_read_as, material, member_span_m, wearing_course_thickness_m, apply_impact, apply_lane_reduction, apply_residual_udl, apply_footway_load, allow_trains, allow_reversed_vehicles, follow_combination_drawings, sampling):
        self.adverse = adverse
        self.vehicles = vehicles
        self.carriageways_read_as = carriageways_read_as
        self.material = material
        self.member_span_m = member_span_m
        self.wearing_course_thickness_m = wearing_course_thickness_m
        self.apply_impact = apply_impact
        self.apply_lane_reduction = apply_lane_reduction
        self.apply_residual_udl = apply_residual_udl
        self.apply_footway_load = apply_footway_load
        self.allow_trains = allow_trains
        self.allow_reversed_vehicles = allow_reversed_vehicles
        self.follow_combination_drawings = follow_combination_drawings
        self.sampling = sampling

    def to_dict(self):
        return self.__dict__

class EnvelopedCurves:
    def __init__(self, responses, permitted, per_carriageway, z_positions_m):
        self.responses = responses
        self.permitted = permitted
        self.per_carriageway = per_carriageway
        self.z_positions_m = z_positions_m

    def to_dict(self):
        return self.__dict__

class WorstAcrossTheWidth:
    def __init__(self, placements, footway, udl_applied, centred_response):
        self.placements = placements
        self.footway = footway
        self.udl_applied = udl_applied
        self.centred_response = centred_response

    def to_dict(self):
        return self.__dict__

class PlacementContext:
    def __init__(self, curves_per_carriageway, responses, permitted, surface, adverse, carriageways_read_as, footway, udl_applied, centred_response):
        self.curves_per_carriageway = curves_per_carriageway
        self.responses = responses
        self.permitted = permitted
        self.surface = surface
        self.adverse = adverse
        self.carriageways_read_as = carriageways_read_as
        self.footway = footway
        self.udl_applied = udl_applied
        self.centred_response = centred_response

    def to_dict(self):
        return self.__dict__

class CriticalPositionService:

    @staticmethod
    def find_critical_position(surface, cross_section, span_m, **options):
        return CriticalPositionService.rank_all_positions(surface, cross_section, span_m, **options)[0]

    @staticmethod
    def rank_all_positions(surface, cross_section, span_m, *, adverse=BIGGER_IS_WORSE, vehicles=None, carriageways_read_as=READ_EACH_CARRIAGEWAY_ON_ITS_OWN, material='steel', member_span_m=None, wearing_course_thickness_m=0.0, apply_impact=True, apply_lane_reduction=True, apply_residual_udl=True, apply_footway_load=False, allow_trains=True, allow_reversed_vehicles=True, follow_combination_drawings=True, sampling=DEFAULT_SAMPLING):
        options = SearchOptions(adverse=adverse, vehicles=vehicles, carriageways_read_as=carriageways_read_as, material=material, member_span_m=member_span_m, wearing_course_thickness_m=wearing_course_thickness_m, apply_impact=apply_impact, apply_lane_reduction=apply_lane_reduction, apply_residual_udl=apply_residual_udl, apply_footway_load=apply_footway_load, allow_trains=allow_trains, allow_reversed_vehicles=allow_reversed_vehicles, follow_combination_drawings=follow_combination_drawings, sampling=sampling)
        carriageways = cross_section.carriageways(split=carriageways_read_as)
        curves = CriticalPositionService.response_curve_for_every_vehicle(surface, carriageways, span_m, options)
        worst = CriticalPositionService.worst_placement_across_the_width(surface, cross_section, carriageways, curves, options)
        context = PlacementContext(curves_per_carriageway=curves.per_carriageway, responses=curves.responses, permitted=curves.permitted, surface=surface, adverse=adverse, carriageways_read_as=carriageways_read_as, footway=worst.footway, udl_applied=worst.udl_applied, centred_response=worst.centred_response)
        return [CriticalPositionService.describe(placement, context) for placement in worst.placements]

    @staticmethod
    def response_curve_for_every_vehicle(surface, carriageways, span_m, options):
        permitted = vehicles_allowed_in_each_block(options.vehicles, options.allow_reversed_vehicles)
        responses = VehicleResponses(surface, span_m=span_m, material=options.material, member_span_m=options.member_span_m, wearing_course_thickness_m=options.wearing_course_thickness_m, apply_impact=options.apply_impact, allow_trains=options.allow_trains, sampling=options.sampling)
        every_vehicle = [vehicle for choices in permitted.values() for vehicle in choices]
        z_positions_m = positions_across_width(responses, every_vehicle, z_from_m=min((carriageway.left_m for carriageway in carriageways)), z_to_m=max((carriageway.right_m for carriageway in carriageways)), steps=options.sampling.positions_across_the_deck_to_try)
        per_carriageway = [envelope_every_block(responses, permitted, z_positions_m, options.adverse, carriageway, surface, options.apply_residual_udl, options.sampling) for carriageway in carriageways]
        return EnvelopedCurves(responses=responses, permitted=permitted, per_carriageway=per_carriageway, z_positions_m=z_positions_m)

    @staticmethod
    def worst_placement_across_the_width(surface, cross_section, carriageways, curves, options):
        placements = find_worst_placement(carriageways, curves.per_carriageway, adverse=options.adverse, apply_lane_reduction=options.apply_lane_reduction, curve_breakpoints_m=curves.z_positions_m, sampling=options.sampling, follow_combination_drawings=options.follow_combination_drawings)
        if options.apply_footway_load:
            footway = footway_response(surface, cross_section, options.adverse, sampling=options.sampling)
        else:
            footway = NO_FOOTWAY_LOAD
        centred = centre_the_resultant(carriageways, curves.per_carriageway, adverse=options.adverse, apply_lane_reduction=options.apply_lane_reduction, follow_combination_drawings=options.follow_combination_drawings)
        centred_response = CriticalPositionService.total_with_the_resultant_centred(centred, footway)
        udl_applied = options.apply_residual_udl and any((needs_residual_udl(carriageway.width_m()) for carriageway in carriageways))
        return WorstAcrossTheWidth(placements=placements, footway=footway, udl_applied=udl_applied, centred_response=centred_response)

    @staticmethod
    def total_with_the_resultant_centred(centred, footway):
        if not centred:
            return None
        return sum((placed.response for placed in centred)) + footway

    @staticmethod
    def describe(placement, context):
        placed_vehicles = []
        pattern = []
        for carriageway, case in enumerate(placement.per_carriageway):
            pattern.append(' + '.join(case.lane_pattern))
            lanes = zip(case.lane_pattern, case.vehicle_centres_m, strict=True)
            for block, z_centre_m in lanes:
                winner = context.curves_per_carriageway[carriageway][block].winner_at(z_centre_m)
                placed_vehicles.append(CriticalPositionService.place_exactly(context.responses, context.permitted[block], winner, z_centre_m, context.adverse))
        return CriticalPosition(response_name=context.surface.name or 'response', adverse=context.adverse, response=placement.response + context.footway * placement.lane_reduction, response_before_reduction=placement.response_before_reduction + context.footway, lane_reduction=placement.lane_reduction, design_lanes=placement.design_lanes, lane_pattern=' | '.join(pattern), carriageways_read_as=context.carriageways_read_as, vehicles=placed_vehicles, footway_response=context.footway, residual_udl_applied=context.udl_applied, resultant_centred_response=context.centred_response)

    @staticmethod
    def place_exactly(responses, choices, winner, z_centre_m, adverse):
        vehicle = next((choice for choice in choices if choice.name == winner))
        exactly_here = responses.for_vehicle(vehicle, np.array([z_centre_m]), adverse)
        return VehiclePlacement(vehicle_name=vehicle.name, z_centre_m=float(z_centre_m), x_front_m=float(exactly_here.x_positions_m[0]), impact_factor=exactly_here.impact_factor, train_x_front_m=exactly_here.train_x_front_m[0])