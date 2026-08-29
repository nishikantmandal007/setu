"""Drawing what setu worked out, so it can be looked at rather than read.

Four pictures, which together tell the whole story of one answer:

    the influence surface, as the deck shape it really is,
    the deck cross-section with the vehicles standing where they ended up,
    the response curve across the width, showing why that lane and not another,
    and the influence line along the span, showing why that spot and not another.

matplotlib is imported inside the functions, so `import setu` stays free of it.
Install it with `uv sync --extra plot`.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .adverse_direction import where_a_load_hurts
from .deck_cross_section import DeckCrossSection
from .influence_surfaces.surface import InfluenceSurface
from .irc_code_rules.vehicles import IRC_VEHICLES, TrackedVehicle, Vehicle, facing_backwards
from .irc_code_rules.wheel_loads import (
    OFFSET_DX_M,
    OFFSET_DZ_M,
    OFFSET_LOAD_KN,
    wheel_load_offsets,
)
from .results import CriticalPosition

STRIP_COLOURS = {
    "carriageway": "#3d4451",
    "footpath": "#8d9aad",
    "footway": "#8d9aad",
    "kerb": "#c2b59b",
    "median": "#9aa77f",
}
OTHER_STRIP_COLOUR = "#b8b8b8"

ADVERSE_COLOUR = "#c0392b"
HELPFUL_COLOUR = "#2471a3"
VEHICLE_COLOUR = "#f0b323"


def draw_everything(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    critical: CriticalPosition,
    span_m: float,
    figure_size: tuple[float, float] = (17.0, 10.0),
):
    """Draws the whole answer as one figure, and returns it.

    Reads left to right, top to bottom: what the deck does, where the vehicles
    went, why that position across the width, and why that position along it.
    """
    plt = _matplotlib()

    figure = plt.figure(figsize=figure_size)
    figure.suptitle(
        f"{critical.response_name}   worst {critical.adverse} = {critical.response:,.3f}",
        fontsize=14,
        fontweight="bold",
    )

    grid = figure.add_gridspec(2, 2, height_ratios=[1.35, 1.0], hspace=0.28, wspace=0.2)

    draw_influence_surface(
        surface, critical, ax=figure.add_subplot(grid[0, 0], projection="3d")
    )
    draw_cross_section(cross_section, critical, ax=figure.add_subplot(grid[0, 1]))
    draw_response_across_width(
        surface, cross_section, critical, span_m, ax=figure.add_subplot(grid[1, 0])
    )
    draw_influence_along_span(surface, critical, ax=figure.add_subplot(grid[1, 1]))

    return figure


def draw_influence_surface(
    surface: InfluenceSurface, critical: CriticalPosition | None = None, ax=None
):
    """Draws the influence surface as the deck shape it is, with the wheels on it.

    Height is the response to a unit load at that point. Red is where a load
    hurts, blue where it helps - which is why the vehicles end up standing on
    the red and nowhere near the blue.
    """
    plt = _matplotlib()
    if ax is None:
        ax = plt.figure(figsize=(9, 7)).add_subplot(projection="3d")

    along_m, across_m = np.meshgrid(
        surface.length_mesh_m, surface.width_mesh_m, indexing="ij"
    )
    peak = float(np.abs(surface.values).max()) or 1.0

    colours = _adverse_colourmap()
    ax.plot_surface(
        along_m, across_m, surface.values,
        cmap=colours, vmin=-peak, vmax=peak,
        linewidth=0, antialiased=True, alpha=0.95, rstride=1, cstride=1,
    )

    # The same surface flattened onto the floor. A deck response is usually a
    # narrow trough on a broad flat plain, and the plan view reads that far
    # better than the perspective one does.
    floor = float(surface.values.min()) - 0.35 * peak
    ax.contourf(
        along_m, across_m, surface.values,
        levels=18, cmap=colours, vmin=-peak, vmax=peak,
        zdir="z", offset=floor, alpha=0.85,
    )

    if critical is not None:
        _mark_wheels_on_surface(ax, surface, critical, peak)

    ax.set_zlim(floor, max(float(surface.values.max()), 0.05 * peak))
    ax.set_xlabel("along the span, x (m)", labelpad=2)
    ax.set_ylabel("across the width, z (m)", labelpad=2)
    ax.set_zlabel("response to a unit load", labelpad=2)
    ax.set_title("The influence surface, and where the wheels went", pad=-4)
    ax.view_init(elev=28, azim=-128)
    ax.set_box_aspect((1.5, 1.1, 0.85), zoom=1.15)
    ax.tick_params(labelsize=7.5)
    return ax


def _mark_wheels_on_surface(ax, surface, critical, peak) -> None:
    """Puts every wheel of every vehicle on the surface, at the height it reads."""
    for placed in critical.vehicles:
        vehicle = _vehicle_named(placed.vehicle_name)
        offsets = wheel_load_offsets(vehicle)

        for x_front_m in placed.train_x_front_m:
            wheel_x_m = x_front_m + offsets[:, OFFSET_DX_M]
            wheel_z_m = placed.z_centre_m + offsets[:, OFFSET_DZ_M]
            on_the_deck = (
                (wheel_x_m >= surface.length_mesh_m[0])
                & (wheel_x_m <= surface.length_mesh_m[-1])
            )
            ax.scatter(
                wheel_x_m[on_the_deck],
                wheel_z_m[on_the_deck],
                surface.influence_at(wheel_x_m[on_the_deck], wheel_z_m[on_the_deck]),
                s=18, c=VEHICLE_COLOUR, edgecolors="black", linewidths=0.4,
                depthshade=False, zorder=10,
            )


def draw_cross_section(
    cross_section: DeckCrossSection, critical: CriticalPosition | None = None, ax=None
):
    """Draws the deck across its width, with the vehicles standing where they ended up.

    Every strip is drawn to scale and named, so it is plain to see that no
    vehicle has strayed onto a kerb, a median or a footpath.
    """
    plt = _matplotlib()
    if ax is None:
        _, ax = plt.subplots(figsize=(11, 3.5))

    deck_top_m, deck_bottom_m = 0.0, -0.55
    for strip in cross_section.strips:
        ax.add_patch(
            plt.Rectangle(
                (strip.z_from_m, deck_bottom_m), strip.width_m, deck_top_m - deck_bottom_m,
                facecolor=_strip_colour(strip.name), edgecolor="white", linewidth=1.2,
            )
        )
        ax.text(
            (strip.z_from_m + strip.z_to_m) / 2,
            deck_bottom_m - 0.12,
            strip.name.replace("_", " "),
            ha="right" if strip.width_m < 1.2 else "center",
            va="top",
            rotation=90 if strip.width_m < 1.2 else 0,
            fontsize=6.5,
            color="#444444",
        )

    if critical is not None:
        for placed in critical.vehicles:
            _draw_vehicle_from_the_front(ax, placed)

    ax.set_xlim(-0.4, cross_section.total_width_m + 0.4)
    ax.set_ylim(deck_bottom_m - 2.2, 3.0)
    ax.set_aspect("equal")
    ax.set_xlabel("across the width, z (m)")
    ax.set_yticks([])
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    ax.set_title("Looking at the deck head on, with the vehicles in place")
    return ax


def _draw_vehicle_from_the_front(ax, placed) -> None:
    """Draws one vehicle as a box on two wheels, at its centreline."""
    plt = _matplotlib()
    vehicle = _vehicle_named(placed.vehicle_name)

    body_width_m = getattr(vehicle, "overall_width_m", None) or (
        vehicle.transverse_gauge_m + 0.6
    )
    wheel_height_m, body_height_m = 0.42, 1.15
    half_gauge_m = vehicle.transverse_gauge_m / 2
    wheel_width_m = vehicle.track_width_m if isinstance(vehicle, TrackedVehicle) else 0.35

    for side in (-1, +1):
        ax.add_patch(
            plt.Rectangle(
                (placed.z_centre_m + side * half_gauge_m - wheel_width_m / 2, 0.0),
                wheel_width_m, wheel_height_m,
                facecolor="#2b2b2b", edgecolor="black", linewidth=0.6, zorder=4,
            )
        )

    ax.add_patch(
        plt.Rectangle(
            (placed.z_centre_m - body_width_m / 2, wheel_height_m),
            body_width_m, body_height_m,
            facecolor=VEHICLE_COLOUR, edgecolor="#8a6400", linewidth=1.2, zorder=5,
        )
    )
    ax.plot([placed.z_centre_m, placed.z_centre_m], [0, wheel_height_m + body_height_m + 0.35],
            color="#8a6400", linestyle=":", linewidth=1.0, zorder=6)

    label = placed.vehicle_name.replace("Class_", "").replace("_", " ")
    if placed.vehicles_in_train > 1:
        label += f"\n{placed.vehicles_in_train} in the lane"
    ax.text(placed.z_centre_m, wheel_height_m + body_height_m + 0.45, label,
            ha="center", va="bottom", fontsize=7.5, fontweight="bold")


def draw_response_across_width(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    critical: CriticalPosition,
    span_m: float,
    ax=None,
):
    """Draws what each vehicle would do from every position across the deck.

    The curve is the worst that vehicle can manage from that position, having
    already been slid along the span to its own worst spot. Where the vehicles
    actually ended up is marked - and it is where the curve peaks, subject to
    them keeping out of each other's way.
    """
    plt = _matplotlib()
    from .vehicle_placement.response_curve import VehicleResponses

    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4))

    carriageways = cross_section.carriageways()
    z_positions_m = np.linspace(
        min(c.left_m for c in carriageways), max(c.right_m for c in carriageways), 241
    )
    responses = VehicleResponses(surface, span_m=span_m)
    widest_m = max(c.width_m for c in carriageways)

    for vehicle in _vehicles_worth_drawing(critical):
        curve = responses.for_vehicle(vehicle, z_positions_m, critical.adverse)
        name = vehicle.name.replace("Class_", "").replace("_", " ")
        needed_m = _narrowest_carriageway_for(vehicle)

        # A vehicle that cannot be placed is still worth drawing - it is often
        # the more damaging one, and seeing that it was ruled out on width
        # rather than overlooked is half of understanding the answer.
        if needed_m <= widest_m + 1e-9:
            ax.plot(z_positions_m, curve.response, linewidth=1.8, label=name)
        else:
            ax.plot(z_positions_m, curve.response, linewidth=1.4, linestyle=":",
                    color="#9a9a9a", alpha=0.85,
                    label=f"{name} - will not fit, needs {needed_m:.2f} m")

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


def draw_influence_along_span(surface: InfluenceSurface, critical: CriticalPosition, ax=None):
    """Draws the influence line down the middle of the governing vehicle's lane.

    Every axle is marked where it stopped. The vehicles sit over the adverse
    part of the line and stay off the rest, which is the whole of what the
    search along the span is doing.
    """
    plt = _matplotlib()
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4))

    governing = critical.vehicles[0]
    along_m = np.linspace(surface.length_mesh_m[0], surface.length_mesh_m[-1], 600)
    line = surface.influence_at(along_m, np.full_like(along_m, governing.z_centre_m))

    hurts = where_a_load_hurts(line, critical.adverse)
    ax.fill_between(along_m, 0, line, where=hurts, color=ADVERSE_COLOUR, alpha=0.30,
                    label="loading here hurts")
    ax.fill_between(along_m, 0, line, where=~hurts, color=HELPFUL_COLOUR, alpha=0.22,
                    label="loading here helps")
    ax.plot(along_m, line, color="#222222", linewidth=1.6)

    vehicle = _vehicle_named(governing.vehicle_name)
    axle_dx_m = np.unique(wheel_load_offsets(vehicle)[:, OFFSET_DX_M])
    for number, x_front_m in enumerate(governing.train_x_front_m, start=1):
        axle_x_m = x_front_m + axle_dx_m
        on_the_deck = (axle_x_m >= along_m[0]) & (axle_x_m <= along_m[-1])
        ax.scatter(
            axle_x_m[on_the_deck],
            surface.influence_at(axle_x_m[on_the_deck],
                                 np.full(on_the_deck.sum(), governing.z_centre_m)),
            s=42, c=VEHICLE_COLOUR, edgecolors="black", linewidths=0.6, zorder=6,
            label="axles" if number == 1 else None,
        )
        if len(governing.train_x_front_m) > 1:
            ax.annotate(
                f"vehicle {number}", (x_front_m, 0), textcoords="offset points",
                xytext=(0, -14), ha="center", fontsize=7.5, color="#8a6400",
            )

    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_xlabel("along the span, x (m)")
    ax.set_ylabel("response to a unit load")
    ax.set_title(f"Why that spot: the influence line at z = {governing.z_centre_m:.2f} m")
    ax.legend(fontsize=8, loc="best")
    ax.grid(alpha=0.25)
    return ax


def animate_vehicle_along_span(
    surface: InfluenceSurface,
    critical: CriticalPosition,
    frames: int = 120,
    interval_ms: int = 45,
):
    """Drives the governing vehicle across the deck and traces what it causes.

    Returns the animation. Save it with `.save("sweep.gif", writer="pillow")`,
    or show it. The marker on the trace stops where the search said it should.
    """
    plt = _matplotlib()
    from matplotlib.animation import FuncAnimation

    governing = critical.vehicles[0]
    vehicle = _vehicle_named(governing.vehicle_name)
    offsets = wheel_load_offsets(vehicle)
    axle_dx_m = np.unique(offsets[:, OFFSET_DX_M])

    first_m = surface.length_mesh_m[0] - float(offsets[:, OFFSET_DX_M].max())
    last_m = float(surface.length_mesh_m[-1])
    where_m = np.linspace(first_m, last_m, frames)

    def response_with_front_at(x_front_m: float) -> float:
        wheel_x_m = x_front_m + offsets[:, OFFSET_DX_M]
        wheel_z_m = governing.z_centre_m + offsets[:, OFFSET_DZ_M]
        return float(
            (surface.influence_at(wheel_x_m, wheel_z_m) * offsets[:, OFFSET_LOAD_KN]).sum()
            * governing.impact_factor
        )

    trace = np.array([response_with_front_at(x_m) for x_m in where_m])

    figure, (top, bottom) = plt.subplots(
        2, 1, figsize=(10, 7), height_ratios=[1.2, 1.0],
        gridspec_kw={"hspace": 0.32},
    )

    along_m = np.linspace(surface.length_mesh_m[0], surface.length_mesh_m[-1], 600)
    line = surface.influence_at(along_m, np.full_like(along_m, governing.z_centre_m))
    hurts = where_a_load_hurts(line, critical.adverse)
    top.fill_between(along_m, 0, line, where=hurts, color=ADVERSE_COLOUR, alpha=0.28)
    top.fill_between(along_m, 0, line, where=~hurts, color=HELPFUL_COLOUR, alpha=0.20)
    top.plot(along_m, line, color="#222222", linewidth=1.5)
    top.axhline(0, color="black", linewidth=0.7)
    top.set_ylabel("response to a unit load")
    top.set_title(f"{vehicle.name.replace('_', ' ')} driving across, at z = "
                  f"{governing.z_centre_m:.2f} m")
    top.grid(alpha=0.2)
    axles = top.scatter([], [], s=48, c=VEHICLE_COLOUR, edgecolors="black",
                        linewidths=0.6, zorder=6)

    bottom.plot(where_m, trace, color="#999999", linewidth=1.2)
    bottom.axhline(0, color="black", linewidth=0.7)

    # Where the search put this vehicle. Deliberately not the response for the
    # whole deck - that is every lane added together with the residual UDL on
    # top, and drawing it against one vehicle's trace would only mislead.
    chosen_m = governing.train_x_front_m[0]
    bottom.axvline(chosen_m, color=ADVERSE_COLOUR, linestyle="--", linewidth=1.4,
                   label=f"where setu put it, x = {chosen_m:.2f} m")
    bottom.set_xlabel("front of the vehicle, x (m)")
    bottom.set_ylabel("response this one vehicle causes")
    bottom.set_title(
        f"What it causes from each position   "
        f"(the whole deck, all lanes and UDL, comes to {critical.response:,.0f})"
    )
    bottom.legend(fontsize=8, loc="best")
    bottom.grid(alpha=0.2)
    so_far, = bottom.plot([], [], color=ADVERSE_COLOUR, linewidth=2.2)
    now = bottom.scatter([], [], s=60, c=VEHICLE_COLOUR, edgecolors="black", zorder=6)

    def draw_frame(frame: int):
        x_front_m = where_m[frame]
        axle_x_m = x_front_m + axle_dx_m
        on_the_deck = (axle_x_m >= along_m[0]) & (axle_x_m <= along_m[-1])
        axles.set_offsets(
            np.column_stack([
                axle_x_m[on_the_deck],
                surface.influence_at(axle_x_m[on_the_deck],
                                     np.full(on_the_deck.sum(), governing.z_centre_m)),
            ])
            if on_the_deck.any()
            else np.empty((0, 2))
        )
        so_far.set_data(where_m[: frame + 1], trace[: frame + 1])
        now.set_offsets([[x_front_m, trace[frame]]])
        return axles, so_far, now

    return FuncAnimation(figure, draw_frame, frames=frames, interval=interval_ms, blit=False)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _vehicles_worth_drawing(critical: CriticalPosition) -> list[Vehicle]:
    """The vehicles that actually took part, plus the ones they beat."""
    drawn: dict[str, Vehicle] = {name: v for name, v in IRC_VEHICLES.items()}
    for placed in critical.vehicles:
        drawn.setdefault(placed.vehicle_name, _vehicle_named(placed.vehicle_name))
    return list(drawn.values())


def _narrowest_carriageway_for(vehicle: Vehicle) -> float:
    """The narrowest carriageway this vehicle could be placed on at all."""
    from .irc_code_rules.lane_arrangements import (
        CLASS_A_LANE,
        ZONE_70R,
        narrowest_carriageway_that_fits,
    )

    block = ZONE_70R if "70R" in vehicle.name else CLASS_A_LANE
    return narrowest_carriageway_that_fits([block])


def _vehicle_named(name: str) -> Vehicle:
    """Finds a vehicle by name, including one that has been turned round."""
    if name in IRC_VEHICLES:
        return IRC_VEHICLES[name]

    forwards = name.removesuffix("_reversed")
    if forwards in IRC_VEHICLES:
        return facing_backwards(IRC_VEHICLES[forwards])

    raise KeyError(f"nothing known about a vehicle called {name!r}")


def _strip_colour(name: str) -> str:
    for prefix, colour in STRIP_COLOURS.items():
        if name.startswith(prefix):
            return colour
    return OTHER_STRIP_COLOUR


def _adverse_colourmap():
    """Blue where a load helps, red where it hurts, pale in between."""
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(
        "adverse", [HELPFUL_COLOUR, "#dfe6ec", "#f7f2e8", "#e8a798", ADVERSE_COLOUR]
    )


def _matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as missing:
        raise ImportError(
            "drawing needs matplotlib, which setu does not install by default. "
            "Add it with `uv sync --extra plot`."
        ) from missing
    return plt
