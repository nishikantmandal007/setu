from __future__ import annotations

import numpy as np

from ..deck_cross_section import DeckCrossSection
from ..influence_surfaces.surface import InfluenceSurface
from ..irc_code_rules.lane_arrangements import (
    CLASS_A_LANE,
    ZONE_70R,
    narrowest_carriageway_that_fits,
)
from ..irc_code_rules.vehicles import (
    IRC_VEHICLES,
    TrackedVehicle,
    Vehicle,
    find_vehicle_or_its_reverse,
)
from ..results import CriticalPosition, VehiclePlacement
from ..sampling import DEFAULT_SAMPLING
from ..vehicle_placement.response_curve import VehicleResponses
from .palette import VEHICLE_COLOUR, Axes, import_matplotlib, strip_colour

DECK_TOP_M = 0.0
DECK_BOTTOM_M = -0.55
WHEEL_HEIGHT_M = 0.42
BODY_HEIGHT_M = 1.15

NARROW_STRIP_LABEL_WIDTH_M = 1.2


def draw_cross_section(
    cross_section: DeckCrossSection, critical: CriticalPosition | None = None, ax: Axes = None
) -> Axes:
    plt = import_matplotlib()
    if ax is None:
        _, ax = plt.subplots(figsize=(11, 3.5))

    for strip in cross_section.strips:
        ax.add_patch(
            plt.Rectangle(
                (strip.z_from_m, DECK_BOTTOM_M), strip.width_m, DECK_TOP_M - DECK_BOTTOM_M,
                facecolor=strip_colour(strip.name), edgecolor="white", linewidth=1.2,
            )
        )
        narrow = strip.width_m < NARROW_STRIP_LABEL_WIDTH_M
        ax.text(
            (strip.z_from_m + strip.z_to_m) / 2,
            DECK_BOTTOM_M - 0.12,
            strip.name.replace("_", " "),
            ha="right" if narrow else "center",
            va="top",
            rotation=90 if narrow else 0,
            fontsize=6.5,
            color="#444444",
        )

    if critical is not None:
        for placed in critical.vehicles:
            draw_vehicle_from_the_front(ax, placed)

    ax.set_xlim(-0.4, cross_section.total_width_m + 0.4)
    ax.set_ylim(DECK_BOTTOM_M - 2.2, 3.0)
    ax.set_aspect("equal")
    ax.set_xlabel("across the width, z (m)")
    ax.set_yticks([])
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    ax.set_title("Looking at the deck head on, with the vehicles in place")
    return ax


def draw_vehicle_from_the_front(ax: Axes, placed: VehiclePlacement) -> None:
    plt = import_matplotlib()
    vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)

    body_width_m = getattr(vehicle, "overall_width_m", None) or (
        vehicle.transverse_gauge_m + 0.6
    )
    half_gauge_m = vehicle.transverse_gauge_m / 2
    wheel_width_m = vehicle.track_width_m if isinstance(vehicle, TrackedVehicle) else 0.35

    for side in (-1, +1):
        ax.add_patch(
            plt.Rectangle(
                (placed.z_centre_m + side * half_gauge_m - wheel_width_m / 2, 0.0),
                wheel_width_m, WHEEL_HEIGHT_M,
                facecolor="#2b2b2b", edgecolor="black", linewidth=0.6, zorder=4,
            )
        )

    ax.add_patch(
        plt.Rectangle(
            (placed.z_centre_m - body_width_m / 2, WHEEL_HEIGHT_M),
            body_width_m, BODY_HEIGHT_M,
            facecolor=VEHICLE_COLOUR, edgecolor="#8a6400", linewidth=1.2, zorder=5,
        )
    )
    ax.plot(
        [placed.z_centre_m, placed.z_centre_m],
        [0, WHEEL_HEIGHT_M + BODY_HEIGHT_M + 0.35],
        color="#8a6400", linestyle=":", linewidth=1.0, zorder=6,
    )

    label = placed.vehicle_name.replace("Class_", "").replace("_", " ")
    if placed.vehicles_in_train > 1:
        label += f"\n{placed.vehicles_in_train} in the lane"
    ax.text(
        placed.z_centre_m, WHEEL_HEIGHT_M + BODY_HEIGHT_M + 0.45, label,
        ha="center", va="bottom", fontsize=7.5, fontweight="bold",
    )


def draw_response_across_width(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    critical: CriticalPosition,
    span_m: float,
    ax: Axes = None,
    *,
    wearing_course_thickness_m: float = 0.0,
    material: str = "steel",
    member_span_m: float | None = None,
) -> Axes:
    plt = import_matplotlib()
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4))

    carriageways = cross_section.carriageways()
    z_positions_m = np.linspace(
        min(carriageway.left_m for carriageway in carriageways),
        max(carriageway.right_m for carriageway in carriageways),
        DEFAULT_SAMPLING.positions_across_the_deck_to_try,
    )
    responses = VehicleResponses(
        surface,
        span_m=span_m,
        material=material,
        member_span_m=member_span_m,
        wearing_course_thickness_m=wearing_course_thickness_m,
    )
    widest_m = max(carriageway.width_m for carriageway in carriageways)

    for vehicle in vehicles_worth_drawing(critical):
        curve = responses.for_vehicle(vehicle, z_positions_m, critical.adverse)
        name = vehicle.name.replace("Class_", "").replace("_", " ")
        needed_m = narrowest_carriageway_for(vehicle)

        if needed_m <= widest_m + 1e-9:
            ax.plot(z_positions_m, curve.response, linewidth=1.8, label=name)
        else:
            ax.plot(
                z_positions_m, curve.response, linewidth=1.4, linestyle=":",
                color="#9a9a9a", alpha=0.85,
                label=f"{name} - will not fit, needs {needed_m:.2f} m",
            )

    for carriageway in carriageways:
        ax.axvspan(carriageway.left_m, carriageway.right_m, color="#3d4451", alpha=0.08)

    for placed in critical.vehicles:
        ax.axvline(placed.z_centre_m, color=VEHICLE_COLOUR, linewidth=2.0, alpha=0.9)

    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_xlabel("vehicle centreline across the width, z (m)")
    ax.set_ylabel("worst response from here")
    ax.set_title(
        f"Why that lane: what each vehicle could do "
        f"(widest carriageway here is {widest_m:.2f} m)"
    )
    ax.legend(fontsize=7.5, loc="best")
    ax.grid(alpha=0.25)
    return ax


def vehicles_worth_drawing(critical: CriticalPosition) -> list[Vehicle]:
    drawn: dict[str, Vehicle] = dict(IRC_VEHICLES)
    for placed in critical.vehicles:
        drawn.setdefault(placed.vehicle_name, find_vehicle_or_its_reverse(placed.vehicle_name))
    return list(drawn.values())


def narrowest_carriageway_for(vehicle: Vehicle) -> float:
    block = ZONE_70R if "70R" in vehicle.name else CLASS_A_LANE  # a name-substring test
    return narrowest_carriageway_that_fits([block])
