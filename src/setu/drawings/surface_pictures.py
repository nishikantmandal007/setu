from __future__ import annotations

import numpy as np

from ..adverse_direction import where_a_load_hurts
from ..influence_surfaces.surface import InfluenceSurface
from ..irc_code_rules.vehicles import find_vehicle_or_its_reverse
from ..irc_code_rules.wheel_loads import OFFSET_DX_M, OFFSET_DZ_M, wheel_load_offsets
from ..results import CriticalPosition
from .palette import (
    ADVERSE_COLOUR,
    HELPFUL_COLOUR,
    INFLUENCE_LINE_SAMPLES,
    VEHICLE_COLOUR,
    Axes,
    adverse_colourmap,
    import_matplotlib,
)


def draw_influence_surface(
    surface: InfluenceSurface, critical: CriticalPosition | None = None, ax: Axes = None
) -> Axes:
    plt = import_matplotlib()
    if ax is None:
        ax = plt.figure(figsize=(9, 7)).add_subplot(projection="3d")

    along_m, across_m = np.meshgrid(
        surface.length_mesh_m, surface.width_mesh_m, indexing="ij"
    )
    peak = float(np.abs(surface.values).max()) or 1.0

    colours = adverse_colourmap()
    ax.plot_surface(
        along_m, across_m, surface.values,
        cmap=colours, vmin=-peak, vmax=peak,
        linewidth=0, antialiased=True, alpha=0.95, rstride=1, cstride=1,
    )

    floor = float(surface.values.min()) - 0.35 * peak
    ax.contourf(
        along_m, across_m, surface.values,
        levels=18, cmap=colours, vmin=-peak, vmax=peak,
        zdir="z", offset=floor, alpha=0.85,
    )

    if critical is not None:
        mark_wheels_on_surface(ax, surface, critical, peak)

    ax.set_zlim(floor, max(float(surface.values.max()), 0.05 * peak))
    ax.set_xlabel("along the span, x (m)", labelpad=2)
    ax.set_ylabel("across the width, z (m)", labelpad=2)
    ax.set_zlabel("response to a unit load", labelpad=2)
    ax.set_title("The influence surface, and where the wheels went", pad=-4)
    ax.view_init(elev=28, azim=-128)
    ax.set_box_aspect((1.5, 1.1, 0.85), zoom=1.15)
    ax.tick_params(labelsize=7.5)
    return ax


def mark_wheels_on_surface(
    ax: Axes, surface: InfluenceSurface, critical: CriticalPosition, peak: float
) -> None:
    for placed in critical.vehicles:
        vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
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


def draw_influence_along_span(
    surface: InfluenceSurface, critical: CriticalPosition, ax: Axes = None
) -> Axes:
    plt = import_matplotlib()
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4))

    governing = critical.vehicles[0]
    along_m = np.linspace(
        surface.length_mesh_m[0], surface.length_mesh_m[-1], INFLUENCE_LINE_SAMPLES
    )
    line = surface.influence_at(along_m, np.full_like(along_m, governing.z_centre_m))

    hurts = where_a_load_hurts(line, critical.adverse)
    ax.fill_between(
        along_m, 0, line, where=hurts, color=ADVERSE_COLOUR, alpha=0.30,
        label="loading here hurts",
    )
    ax.fill_between(
        along_m, 0, line, where=~hurts, color=HELPFUL_COLOUR, alpha=0.22,
        label="loading here helps",
    )
    ax.plot(along_m, line, color="#222222", linewidth=1.6)

    vehicle = find_vehicle_or_its_reverse(governing.vehicle_name)
    axle_dx_m = np.unique(wheel_load_offsets(vehicle)[:, OFFSET_DX_M])
    for number, x_front_m in enumerate(governing.train_x_front_m, start=1):
        axle_x_m = x_front_m + axle_dx_m
        on_the_deck = (axle_x_m >= along_m[0]) & (axle_x_m <= along_m[-1])
        ax.scatter(
            axle_x_m[on_the_deck],
            surface.influence_at(
                axle_x_m[on_the_deck], np.full(on_the_deck.sum(), governing.z_centre_m)
            ),
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
