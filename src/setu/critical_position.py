"""The worst legal position of the IRC:6 vehicles on a deck.

This is what setu is for. Give it an influence surface for the response you care
about and a description of the deck width, and it returns where the vehicles
have to stand to do the most damage the code allows them to do.

The search reads as one sentence:

    split the deck into carriageways,
    build a response curve for every kind of vehicle that may be placed,
    find the worst placement across the width,
    and describe it.

What each of those steps hides is a search of its own - along the span for the
worst train in a lane, across the width for the worst arrangement of lanes - and
both are exact. See `vehicle_placement.along_span` and
`vehicle_placement.across_carriageway`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .deck_cross_section import Carriageway, DeckCrossSection
from .influence_surfaces.surface import InfluenceSurface
from .irc_code_rules.carriageway_udl import (
    footway_response,
    needs_residual_udl,
    response_to_area_load,
    strips_beside_class_a,
)
from .irc_code_rules.lane_arrangements import CLASS_A_LANE
from .irc_code_rules.vehicles import (
    IRC_VEHICLES,
    VEHICLES_ALLOWED_IN_BLOCK,
    Vehicle,
    facing_backwards,
    find_vehicle,
)
from .results import CriticalPosition, VehiclePlacement
from .sampling import DEFAULT_SAMPLING, SamplingSettings
from .vehicle_placement.across_carriageway import TransversePlacement, find_worst_placement
from .vehicle_placement.response_curve import VehicleResponses, positions_across_width
from .vehicle_placement.resultant_centred import centre_the_resultant


@dataclass(frozen=True)
class BlockEnvelope:
    """The worst any permitted vehicle can do in one kind of lane block.

    A 70R zone may hold a wheeled or a tracked vehicle, and a Class A lane may
    hold a vehicle facing either way. Which of them is worse changes along the
    deck, so all of them are worked out and the worst is taken at each position.

    Callable, so the transverse search can read it as a response curve.
    """

    z_positions_m: np.ndarray
    response: np.ndarray
    winner: list[str]
    """Which vehicle was worst at each position across the deck."""

    def __call__(self, z_m):
        return np.interp(z_m, self.z_positions_m, self.response)

    def winner_at(self, z_m: float) -> str:
        """Returns the vehicle that governs at this position.

        Read by nearest position, not interpolated: which vehicle wins is a
        choice between two of them, and there is nothing in between.
        """
        nearest = int(np.abs(self.z_positions_m - float(z_m)).argmin())
        return self.winner[nearest]


def find_critical_position(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    span_m: float,
    **options: Any,
) -> CriticalPosition:
    """Returns the worst legal IRC:6 vehicle placement for one response quantity.

    Takes the same options as `rank_all_positions`, which is where they are
    written out - this is that search, answered with its first result.
    """
    return rank_all_positions(surface, cross_section, span_m, **options)[0]


def rank_all_positions(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    span_m: float,
    *,
    adverse: str = "maximum",
    vehicles: dict[str, Vehicle] | None = None,
    carriageways_read_as: str = "separate",
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
    """Returns every legal way of loading the deck, worst first.

    `find_critical_position` is the first of these. This one is for seeing why
    it won - what else was considered, and by how much it lost.

    Parameters
    ----------
    adverse
        Which direction hurts: "maximum" for a response that is worse the more
        positive it gets, "minimum" for one that is worse the more negative.
    carriageways_read_as
        "separate" reads each carriageway on its own, "combined" reads them as
        one. On a deck with a median this changes the design load by 15 to 30
        per cent, so it is stated rather than guessed at.
    member_span_m
        The effective span of the member being checked, when it is not the span
        of the bridge. Clause 208.5.
    allow_trains
        Whether one lane may carry several vehicles nose to tail.
    allow_reversed_vehicles
        Whether a vehicle may head either way along the span. Clause 204.1.4.
    follow_combination_drawings
        Keep to the arrangements the standard combination drawings show: a 70R
        always reaching a kerb, and never more than two on one carriageway. On
        by default, so results match those drawings. Turning it off searches
        every arrangement the geometry allows, which can only be more adverse.
    """
    carriageways = cross_section.carriageways(split=carriageways_read_as)
    permitted = _vehicles_permitted_in_each_block(vehicles, allow_reversed_vehicles)

    responses = VehicleResponses(
        surface,
        span_m=span_m,
        material=material,
        member_span_m=member_span_m,
        wearing_course_thickness_m=wearing_course_thickness_m,
        apply_impact=apply_impact,
        allow_trains=allow_trains,
        sampling=sampling,
    )

    z_positions_m = positions_across_width(
        responses,
        [vehicle for choices in permitted.values() for vehicle in choices],
        z_from_m=min(carriageway.left_m for carriageway in carriageways),
        z_to_m=max(carriageway.right_m for carriageway in carriageways),
        steps=sampling.transverse_steps,
    )

    curves_per_carriageway = [
        _envelope_every_block(
            responses,
            permitted,
            z_positions_m,
            adverse,
            carriageway,
            surface,
            apply_residual_udl,
            sampling,
        )
        for carriageway in carriageways
    ]

    placements = find_worst_placement(
        carriageways,
        curves_per_carriageway,
        adverse=adverse,
        apply_lane_reduction=apply_lane_reduction,
        curve_breakpoints_m=z_positions_m,
        sampling=sampling,
        follow_combination_drawings=follow_combination_drawings,
    )

    footway = (
        footway_response(surface, cross_section, adverse, sampling=sampling)
        if apply_footway_load
        else 0.0
    )

    # The second transverse condition the code asks for. Reported, never raced
    # against the sweep - it is one position the sweep has already been over.
    centred = centre_the_resultant(
        carriageways, curves_per_carriageway, adverse=adverse,
        apply_lane_reduction=apply_lane_reduction,
        follow_combination_drawings=follow_combination_drawings,
    )
    centred_response = (
        sum(placed.response for placed in centred) + footway if centred else None
    )
    udl_applied = apply_residual_udl and any(
        needs_residual_udl(carriageway.width_m) for carriageway in carriageways
    )

    return [
        _describe(
            placement,
            curves_per_carriageway,
            responses,
            permitted,
            surface,
            adverse,
            carriageways_read_as,
            footway,
            udl_applied,
            centred_response,
        )
        for placement in placements
    ]


def _vehicles_permitted_in_each_block(
    vehicles: dict[str, Vehicle] | None, allow_reversed_vehicles: bool
) -> dict[str, list[Vehicle]]:
    """Returns which vehicles may be tried in each kind of lane block.

    A vehicle that is not symmetric front to back is added twice, once facing
    each way, because Clause 204.1.4 lets it drive in either direction and the
    two are different load cases.
    """
    known = IRC_VEHICLES if vehicles is None else vehicles

    permitted: dict[str, list[Vehicle]] = {}
    for block, names in VEHICLES_ALLOWED_IN_BLOCK.items():
        choices = []
        for name in names:
            if name not in known:
                continue
            vehicle = find_vehicle(name, known)
            choices.append(vehicle)

            if allow_reversed_vehicles:
                reversed_vehicle = facing_backwards(vehicle)
                if reversed_vehicle is not vehicle:
                    choices.append(reversed_vehicle)

        if not choices:
            raise ValueError(
                f"no vehicle available for a {block!r} lane block; "
                f"expected one of {list(names)} among {sorted(known)}"
            )
        permitted[block] = choices

    return permitted


def _envelope_every_block(
    responses: VehicleResponses,
    permitted: dict[str, list[Vehicle]],
    z_positions_m: np.ndarray,
    adverse: str,
    carriageway: Carriageway,
    surface: InfluenceSurface,
    apply_residual_udl: bool,
    sampling: SamplingSettings,
) -> dict[str, BlockEnvelope]:
    """Returns one enveloped response curve per kind of lane block, for one carriageway."""
    envelopes = {}

    for block, choices in permitted.items():
        curves = [responses.for_vehicle(vehicle, z_positions_m, adverse) for vehicle in choices]
        stacked = np.vstack([curve.response for curve in curves])

        pick_worst = np.argmax if adverse == "maximum" else np.argmin
        worst = pick_worst(stacked, axis=0)
        response = stacked[worst, np.arange(len(z_positions_m))]

        # Table 6 S.No.1: on a narrow carriageway the strip the vehicle does not
        # cover carries 500 kg/m2, and that strip moves with the vehicle - so it
        # rides along with the Class A curve rather than being added at the end.
        if (
            block == CLASS_A_LANE
            and apply_residual_udl
            and needs_residual_udl(carriageway.width_m)
        ):
            response = response + _residual_udl_curve(
                surface, z_positions_m, carriageway, adverse, sampling
            )

        envelopes[block] = BlockEnvelope(
            z_positions_m=z_positions_m,
            response=response,
            winner=[choices[which].name for which in worst],
        )

    return envelopes


def _residual_udl_curve(
    surface: InfluenceSurface,
    z_positions_m: np.ndarray,
    carriageway: Carriageway,
    adverse: str,
    sampling: SamplingSettings,
) -> np.ndarray:
    """Returns what the residual UDL adds at each position a Class A vehicle could sit."""
    return np.array(
        [
            response_to_area_load(
                surface,
                strips_beside_class_a(float(z_m), carriageway.left_m, carriageway.right_m),
                adverse,
                sampling=sampling,
            )
            for z_m in z_positions_m
        ]
    )


def _describe(
    placement: TransversePlacement,
    curves_per_carriageway: list[dict[str, BlockEnvelope]],
    responses: VehicleResponses,
    permitted: dict[str, list[Vehicle]],
    surface: InfluenceSurface,
    adverse: str,
    carriageways_read_as: str,
    footway: float,
    udl_applied: bool,
    centred_response: float | None,
) -> CriticalPosition:
    """Turns one swept placement into a result anyone can check or redraw."""
    placed_vehicles = []
    pattern = []

    for carriageway, case in enumerate(placement.per_carriageway):
        pattern.append(" + ".join(case.lane_pattern))

        for block, z_centre_m in zip(case.lane_pattern, case.vehicle_centres_m, strict=True):
            winner = curves_per_carriageway[carriageway][block].winner_at(z_centre_m)
            placed_vehicles.append(
                _place_exactly(responses, permitted[block], winner, z_centre_m, adverse)
            )

    return CriticalPosition(
        response_name=surface.name or "response",
        adverse=adverse,
        response=placement.response + footway * placement.lane_reduction,
        response_before_reduction=placement.response_before_reduction + footway,
        lane_reduction=placement.lane_reduction,
        design_lanes=placement.design_lanes,
        lane_pattern=" | ".join(pattern),
        carriageways_read_as=carriageways_read_as,
        vehicles=placed_vehicles,
        footway_response=footway,
        residual_udl_applied=udl_applied,
        resultant_centred_response=centred_response,
    )


def _place_exactly(
    responses: VehicleResponses,
    choices: list[Vehicle],
    winner: str,
    z_centre_m: float,
    adverse: str,
) -> VehiclePlacement:
    """Works out exactly where the governing vehicle stopped along the span.

    The curves were sampled across the width, but the search is free to settle
    between two samples. Rather than interpolate a position no vehicle actually
    occupied, the winning vehicle's curve is worked out once more at the exact
    position it ended up.
    """
    vehicle = next(choice for choice in choices if choice.name == winner)
    exactly_here = responses.for_vehicle(vehicle, np.array([z_centre_m]), adverse)

    return VehiclePlacement(
        vehicle_name=vehicle.name,
        z_centre_m=float(z_centre_m),
        x_front_m=float(exactly_here.x_positions_m[0]),
        impact_factor=exactly_here.impact_factor,
        train_x_front_m=exactly_here.train_x_front_m[0],
    )
