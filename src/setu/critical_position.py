# The worst legal position of the IRC:6 vehicles on a deck.
#
# This is what setu is for. Give it an influence surface for the response you care about
# and a description of the deck width, and it returns where the vehicles have to stand to
# do the most damage the code allows them to do.
#
# The search reads as one sentence:
#
#     split the deck into carriageways,
#     build a response curve for every kind of vehicle that may be placed,
#     find the worst placement across the width,
#     and describe it.
#
# What each of those steps hides is a search of its own - along the span for the worst
# train in a lane, across the width for the worst arrangement of lanes - and both are
# exact. See `vehicle_placement.along_span` and `vehicle_placement.across_carriageway`.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .deck_cross_section import Carriageway, DeckCrossSection
from .influence_surfaces.surface import InfluenceSurface
from .irc_code_rules.area_loads import footway_response, needs_residual_udl
from .irc_code_rules.vehicles import Vehicle, vehicles_allowed_in_each_block
from .results import CriticalPosition, VehiclePlacement
from .sampling import DEFAULT_SAMPLING, SamplingSettings
from .vehicle_placement.across_carriageway import TransversePlacement, find_worst_placement
from .vehicle_placement.block_envelopes import BlockEnvelope, envelope_every_block
from .vehicle_placement.response_curve import VehicleResponses, positions_across_width
from .vehicle_placement.resultant_at_mid_width import centre_the_resultant


def find_critical_position(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    span_m: float,
    **options: Any,
) -> CriticalPosition:
    # Takes the same options as rank_all_positions, which is where they are written out -
    # this is that search, answered with its first result.
    return rank_all_positions(surface, cross_section, span_m, **options)[0]


def rank_all_positions(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    span_m: float,
    *,
    # Which direction hurts: "maximum" for a response that is worse the more positive it
    # gets, "minimum" for one that is worse the more negative.
    adverse: str = "maximum",
    vehicles: dict[str, Vehicle] | None = None,
    # "separate" reads each carriageway on its own, "combined" reads them as one. On a deck
    # with a median this changes the design load by 15 to 30 per cent, so it is stated
    # rather than guessed at.
    carriageways_read_as: str = "separate",
    material: str = "steel",
    # The effective span of the member being checked, when it is not the span of the
    # bridge. Clause 208.5.
    member_span_m: float | None = None,
    wearing_course_thickness_m: float = 0.0,
    apply_impact: bool = True,
    apply_lane_reduction: bool = True,
    apply_residual_udl: bool = True,
    apply_footway_load: bool = False,
    # Whether one lane may carry several vehicles nose to tail.
    allow_trains: bool = True,
    # Whether a vehicle may head either way along the span. Clause 204.1.4.
    allow_reversed_vehicles: bool = True,
    # Keep to the arrangements the standard combination drawings show: a 70R always
    # reaching a kerb, and never more than two on one carriageway. On by default, so
    # results match those drawings. Turning it off searches every arrangement the geometry
    # allows, which can only be more adverse.
    follow_combination_drawings: bool = True,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
) -> list[CriticalPosition]:
    # Returns every legal way of loading the deck, worst first. find_critical_position is
    # the first of these - this one is for seeing why it won, what else was considered, and
    # by how much it lost.

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

    # split the deck into carriageways
    carriageways = cross_section.carriageways(split=carriageways_read_as)

    # build a response curve for every kind of vehicle that may be placed
    curves = response_curve_for_every_vehicle(surface, carriageways, span_m, options)

    # find the worst placement across the width
    worst = worst_placement_across_the_width(
        surface, cross_section, carriageways, curves, options
    )

    # and describe it
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


# ---------------------------------------------------------------------------
# How The Search Is Being Run
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchOptions:
    # Every option rank_all_positions was given, carried as one thing so the steps below
    # take what they are for rather than fourteen flags each.
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


# ---------------------------------------------------------------------------
# Response Curve For Every Vehicle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvelopedCurves:
    # Everything that came out of building the response curves, kept together because
    # describing a placement later needs to look a vehicle up again by name.
    responses: VehicleResponses
    permitted: dict[str, list[Vehicle]]
    per_carriageway: list[dict[str, BlockEnvelope]]
    z_positions_m: np.ndarray


def response_curve_for_every_vehicle(
    surface: InfluenceSurface,
    carriageways: list[Carriageway],
    span_m: float,
    options: SearchOptions,
) -> EnvelopedCurves:
    # Builds a response curve for every kind of vehicle that may be placed, enveloped to
    # its worst at each position, one set of curves per carriageway.
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

    z_positions_m = positions_across_width(
        responses,
        [vehicle for choices in permitted.values() for vehicle in choices],
        z_from_m=min(carriageway.left_m for carriageway in carriageways),
        z_to_m=max(carriageway.right_m for carriageway in carriageways),
        steps=options.sampling.transverse_steps,
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


# ---------------------------------------------------------------------------
# Worst Placement Across The Width
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorstAcrossTheWidth:
    # The ranked list of placements, and the numbers the code asks be reported alongside
    # every one of them.
    placements: list[TransversePlacement]
    footway: float
    udl_applied: bool
    centred_response: float | None


def worst_placement_across_the_width(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    carriageways: list[Carriageway],
    curves: EnvelopedCurves,
    options: SearchOptions,
) -> WorstAcrossTheWidth:
    # Runs the transverse sweep, then the two things the code asks be checked alongside it:
    # the footway load and the resultant-centred condition.
    placements = find_worst_placement(
        carriageways,
        curves.per_carriageway,
        adverse=options.adverse,
        apply_lane_reduction=options.apply_lane_reduction,
        curve_breakpoints_m=curves.z_positions_m,
        sampling=options.sampling,
        follow_combination_drawings=options.follow_combination_drawings,
    )

    footway = (
        footway_response(
            surface, cross_section, options.adverse, sampling=options.sampling
        )
        if options.apply_footway_load
        else 0.0
    )

    # The second transverse condition the code asks for. Reported, never raced against the
    # sweep - it is one position the sweep has already been over.
    centred = centre_the_resultant(
        carriageways,
        curves.per_carriageway,
        adverse=options.adverse,
        apply_lane_reduction=options.apply_lane_reduction,
        follow_combination_drawings=options.follow_combination_drawings,
    )
    centred_response = (
        sum(placed.response for placed in centred) + footway if centred else None
    )

    udl_applied = options.apply_residual_udl and any(
        needs_residual_udl(carriageway.width_m) for carriageway in carriageways
    )

    return WorstAcrossTheWidth(
        placements=placements,
        footway=footway,
        udl_applied=udl_applied,
        centred_response=centred_response,
    )


# ---------------------------------------------------------------------------
# Describing A Placement
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlacementContext:
    # Everything needed to turn a swept placement into a CriticalPosition that stays the
    # same across every placement in the ranked list - only the placement itself varies,
    # so this is what keeps describe() from taking ten positional arguments.
    curves_per_carriageway: list[dict[str, BlockEnvelope]]
    responses: VehicleResponses
    permitted: dict[str, list[Vehicle]]
    surface: InfluenceSurface
    adverse: str
    carriageways_read_as: str
    footway: float
    udl_applied: bool
    centred_response: float | None


def describe(placement: TransversePlacement, context: PlacementContext) -> CriticalPosition:
    # Turns one swept placement into a result anyone can check or redraw.
    placed_vehicles = []
    pattern = []

    for carriageway, case in enumerate(placement.per_carriageway):
        pattern.append(" + ".join(case.lane_pattern))

        for block, z_centre_m in zip(case.lane_pattern, case.vehicle_centres_m, strict=True):
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
    # The curves were sampled across the width, but the search is free to settle between
    # two samples. Rather than interpolate a position no vehicle actually occupied, the
    # winning vehicle's curve is worked out once more at the exact position it ended up.
    vehicle = next(choice for choice in choices if choice.name == winner)
    exactly_here = responses.for_vehicle(vehicle, np.array([z_centre_m]), adverse)

    return VehiclePlacement(
        vehicle_name=vehicle.name,
        z_centre_m=float(z_centre_m),
        x_front_m=float(exactly_here.x_positions_m[0]),
        impact_factor=exactly_here.impact_factor,
        train_x_front_m=exactly_here.train_x_front_m[0],
    )
