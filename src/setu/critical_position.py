from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .adverse_direction import BIGGER_IS_WORSE
from .deck_cross_section import (
    READ_EACH_CARRIAGEWAY_ON_ITS_OWN,
    Carriageway,
    DeckCrossSection,
)
from .influence_surfaces.surface import InfluenceSurface
from .irc_code_rules.area_loads import footway_response, needs_residual_udl
from .irc_code_rules.vehicles import Vehicle, vehicles_allowed_in_each_block
from .results import CriticalPosition, VehiclePlacement
from .sampling import DEFAULT_SAMPLING, SamplingSettings
from .vehicle_placement.across_carriageway import TransversePlacement, find_worst_placement
from .vehicle_placement.block_envelopes import BlockEnvelope, envelope_every_block
from .vehicle_placement.response_curve import VehicleResponses, positions_across_width
from .vehicle_placement.resultant_at_mid_width import centre_the_resultant

NO_FOOTWAY_LOAD = 0.0


@dataclass(frozen=True)
class SearchOptions:
    adverse: str
    vehicles: dict[str, Vehicle] | None
    carriageways_read_as: str
    material: str
    member_span_m: float | None
    wearing_course_thickness_m: float
    apply_impact: bool
    apply_lane_reduction: bool
    apply_residual_udl: bool
    apply_footway_load: bool
    allow_trains: bool
    allow_reversed_vehicles: bool
    follow_combination_drawings: bool
    sampling: SamplingSettings


@dataclass(frozen=True)
class EnvelopedCurves:
    responses: VehicleResponses
    permitted: dict[str, list[Vehicle]]
    per_carriageway: list[dict[str, BlockEnvelope]]
    z_positions_m: np.ndarray


@dataclass(frozen=True)
class WorstAcrossTheWidth:
    placements: list[TransversePlacement]
    footway: float
    udl_applied: bool
    centred_response: float | None


@dataclass(frozen=True)
class PlacementContext:
    curves_per_carriageway: list[dict[str, BlockEnvelope]]
    responses: VehicleResponses
    permitted: dict[str, list[Vehicle]]
    surface: InfluenceSurface
    adverse: str
    carriageways_read_as: str
    footway: float
    udl_applied: bool
    centred_response: float | None


def find_critical_position(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    span_m: float,
    **options: Any,
) -> CriticalPosition:
    return rank_all_positions(surface, cross_section, span_m, **options)[0]


def rank_all_positions(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    span_m: float,
    *,
    adverse: str = BIGGER_IS_WORSE,
    vehicles: dict[str, Vehicle] | None = None,
    carriageways_read_as: str = READ_EACH_CARRIAGEWAY_ON_ITS_OWN,
    material: str = "steel",
    member_span_m: float | None = None,
    wearing_course_thickness_m: float = 0.0,
    apply_impact: bool = True,
    apply_lane_reduction: bool = True,
    apply_residual_udl: bool = True,
    apply_footway_load: bool = False,
    allow_trains: bool = True,
    allow_reversed_vehicles: bool = True,
    follow_combination_drawings: bool = True,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
) -> list[CriticalPosition]:
    options = SearchOptions(
        adverse=adverse,
        vehicles=vehicles,
        carriageways_read_as=carriageways_read_as,
        material=material,
        member_span_m=member_span_m,
        wearing_course_thickness_m=wearing_course_thickness_m,
        apply_impact=apply_impact,
        apply_lane_reduction=apply_lane_reduction,
        apply_residual_udl=apply_residual_udl,
        apply_footway_load=apply_footway_load,
        allow_trains=allow_trains,
        allow_reversed_vehicles=allow_reversed_vehicles,
        follow_combination_drawings=follow_combination_drawings,
        sampling=sampling,
    )

    carriageways = cross_section.carriageways(split=carriageways_read_as)
    curves = response_curve_for_every_vehicle(surface, carriageways, span_m, options)
    worst = worst_placement_across_the_width(
        surface, cross_section, carriageways, curves, options
    )

    context = PlacementContext(
        curves_per_carriageway=curves.per_carriageway,
        responses=curves.responses,
        permitted=curves.permitted,
        surface=surface,
        adverse=adverse,
        carriageways_read_as=carriageways_read_as,
        footway=worst.footway,
        udl_applied=worst.udl_applied,
        centred_response=worst.centred_response,
    )
    return [describe(placement, context) for placement in worst.placements]


def response_curve_for_every_vehicle(
    surface: InfluenceSurface,
    carriageways: list[Carriageway],
    span_m: float,
    options: SearchOptions,
) -> EnvelopedCurves:
    permitted = vehicles_allowed_in_each_block(
        options.vehicles, options.allow_reversed_vehicles
    )

    responses = VehicleResponses(
        surface,
        span_m=span_m,
        material=options.material,
        member_span_m=options.member_span_m,
        wearing_course_thickness_m=options.wearing_course_thickness_m,
        apply_impact=options.apply_impact,
        allow_trains=options.allow_trains,
        sampling=options.sampling,
    )

    every_vehicle = [vehicle for choices in permitted.values() for vehicle in choices]
    z_positions_m = positions_across_width(
        responses,
        every_vehicle,
        z_from_m=min(carriageway.left_m for carriageway in carriageways),
        z_to_m=max(carriageway.right_m for carriageway in carriageways),
        steps=options.sampling.positions_across_the_deck_to_try,
    )

    per_carriageway = [
        envelope_every_block(
            responses,
            permitted,
            z_positions_m,
            options.adverse,
            carriageway,
            surface,
            options.apply_residual_udl,
            options.sampling,
        )
        for carriageway in carriageways
    ]

    return EnvelopedCurves(
        responses=responses,
        permitted=permitted,
        per_carriageway=per_carriageway,
        z_positions_m=z_positions_m,
    )


def worst_placement_across_the_width(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    carriageways: list[Carriageway],
    curves: EnvelopedCurves,
    options: SearchOptions,
) -> WorstAcrossTheWidth:
    placements = find_worst_placement(
        carriageways,
        curves.per_carriageway,
        adverse=options.adverse,
        apply_lane_reduction=options.apply_lane_reduction,
        curve_breakpoints_m=curves.z_positions_m,
        sampling=options.sampling,
        follow_combination_drawings=options.follow_combination_drawings,
    )

    if options.apply_footway_load:
        footway = footway_response(
            surface, cross_section, options.adverse, sampling=options.sampling
        )
    else:
        footway = NO_FOOTWAY_LOAD

    centred = centre_the_resultant(
        carriageways,
        curves.per_carriageway,
        adverse=options.adverse,
        apply_lane_reduction=options.apply_lane_reduction,
        follow_combination_drawings=options.follow_combination_drawings,
    )
    centred_response = total_with_the_resultant_centred(centred, footway)

    udl_applied = options.apply_residual_udl and any(
        needs_residual_udl(carriageway.width_m) for carriageway in carriageways
    )

    return WorstAcrossTheWidth(
        placements=placements,
        footway=footway,
        udl_applied=udl_applied,
        centred_response=centred_response,
    )


def total_with_the_resultant_centred(
    centred: list, footway: float
) -> float | None:
    if not centred:
        return None
    return sum(placed.response for placed in centred) + footway


def describe(placement: TransversePlacement, context: PlacementContext) -> CriticalPosition:
    placed_vehicles = []
    pattern = []

    for carriageway, case in enumerate(placement.per_carriageway):
        pattern.append(" + ".join(case.lane_pattern))

        lanes = zip(case.lane_pattern, case.vehicle_centres_m, strict=True)
        for block, z_centre_m in lanes:
            winner = context.curves_per_carriageway[carriageway][block].winner_at(z_centre_m)
            placed_vehicles.append(
                place_exactly(
                    context.responses,
                    context.permitted[block],
                    winner,
                    z_centre_m,
                    context.adverse,
                )
            )

    return CriticalPosition(
        response_name=context.surface.name or "response",
        adverse=context.adverse,
        response=placement.response + context.footway * placement.lane_reduction,
        response_before_reduction=placement.response_before_reduction + context.footway,
        lane_reduction=placement.lane_reduction,
        design_lanes=placement.design_lanes,
        lane_pattern=" | ".join(pattern),
        carriageways_read_as=context.carriageways_read_as,
        vehicles=placed_vehicles,
        footway_response=context.footway,
        residual_udl_applied=context.udl_applied,
        resultant_centred_response=context.centred_response,
    )


def place_exactly(
    responses: VehicleResponses,
    choices: list[Vehicle],
    winner: str,
    z_centre_m: float,
    adverse: str,
) -> VehiclePlacement:
    # The search can settle between two samples, so the winner's curve is worked out once
    # more at the exact position it ended up rather than interpolated.
    vehicle = next(choice for choice in choices if choice.name == winner)
    exactly_here = responses.for_vehicle(vehicle, np.array([z_centre_m]), adverse)

    return VehiclePlacement(
        vehicle_name=vehicle.name,
        z_centre_m=float(z_centre_m),
        x_front_m=float(exactly_here.x_positions_m[0]),
        impact_factor=exactly_here.impact_factor,
        train_x_front_m=exactly_here.train_x_front_m[0],
    )
