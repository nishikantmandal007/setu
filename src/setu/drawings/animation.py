# The vehicle-sweep animation - the only picture that needs matplotlib.animation, and the
# only one built from closures, because FuncAnimation redraws each frame by mutating
# artists in place rather than by being handed a fresh figure every time.

from __future__ import annotations

from typing import Any

import numpy as np

from ..adverse_direction import where_a_load_hurts
from ..influence_surfaces.surface import InfluenceSurface
from ..irc_code_rules.vehicles import Vehicle, find_vehicle_or_its_reverse
from ..irc_code_rules.wheel_loads import (
    OFFSET_DX_M,
    OFFSET_DZ_M,
    OFFSET_LOAD_KN,
    wheel_load_offsets,
)
from ..results import CriticalPosition, VehiclePlacement
from .palette import (
    ADVERSE_COLOUR,
    HELPFUL_COLOUR,
    INFLUENCE_LINE_SAMPLES,
    VEHICLE_COLOUR,
    Axes,
    Figure,
    import_matplotlib,
)


def animate_vehicle_along_span(
    surface: InfluenceSurface,
    critical: CriticalPosition,
    frames: int = 120,
    interval_ms: int = 45,
) -> Any:
    # Drives the governing vehicle across the deck and traces what it causes. Save the
    # result with `.save("sweep.gif", writer="pillow")`, or show it - the marker on the
    # trace stops where the search said it should. Any here for the same reason as Axes
    # and Figure: FuncAnimation has no usable type stubs either.
    plt = import_matplotlib()
    from matplotlib.animation import FuncAnimation

    governing = critical.vehicles[0]
    vehicle = find_vehicle_or_its_reverse(governing.vehicle_name)
    offsets = wheel_load_offsets(vehicle)
    axle_dx_m = np.unique(offsets[:, OFFSET_DX_M])

    first_m = surface.length_mesh_m[0] - float(offsets[:, OFFSET_DX_M].max())
    last_m = float(surface.length_mesh_m[-1])
    where_m = np.linspace(first_m, last_m, frames)
    trace = response_trace_along_span(surface, governing, offsets, where_m)

    along_m = np.linspace(
        surface.length_mesh_m[0], surface.length_mesh_m[-1], INFLUENCE_LINE_SAMPLES
    )
    figure, top, bottom = two_panel_figure(plt)
    axles = style_the_influence_line_panel(top, surface, critical, governing, vehicle, along_m)
    so_far, now = style_the_trace_panel(bottom, critical, governing, where_m, trace)

    def draw_frame(frame: int) -> tuple[Any, Any, Any]:
        x_front_m = where_m[frame]
        axle_x_m = x_front_m + axle_dx_m
        on_the_deck = (axle_x_m >= along_m[0]) & (axle_x_m <= along_m[-1])
        axles.set_offsets(
            np.column_stack(
                [
                    axle_x_m[on_the_deck],
                    surface.influence_at(
                        axle_x_m[on_the_deck],
                        np.full(on_the_deck.sum(), governing.z_centre_m),
                    ),
                ]
            )
            if on_the_deck.any()
            else np.empty((0, 2))
        )
        so_far.set_data(where_m[: frame + 1], trace[: frame + 1])
        now.set_offsets([[x_front_m, trace[frame]]])
        return axles, so_far, now

    return FuncAnimation(figure, draw_frame, frames=frames, interval=interval_ms, blit=False)


def response_trace_along_span(
    surface: InfluenceSurface,
    governing: VehiclePlacement,
    offsets: np.ndarray,
    where_m: np.ndarray,
) -> np.ndarray:
    # What the governing vehicle alone causes, as its front sweeps from before the deck to
    # the far end.
    def response_with_front_at(x_front_m: float) -> float:
        wheel_x_m = x_front_m + offsets[:, OFFSET_DX_M]
        wheel_z_m = governing.z_centre_m + offsets[:, OFFSET_DZ_M]
        return float(
            (surface.influence_at(wheel_x_m, wheel_z_m) * offsets[:, OFFSET_LOAD_KN]).sum()
            * governing.impact_factor
        )

    return np.array([response_with_front_at(x_m) for x_m in where_m])


def two_panel_figure(plt: Any) -> tuple[Figure, Axes, Axes]:
    # The influence line up top, the trace of what it causes below.
    figure, (top, bottom) = plt.subplots(
        2, 1, figsize=(10, 7), height_ratios=[1.2, 1.0], gridspec_kw={"hspace": 0.32}
    )
    return figure, top, bottom


def style_the_influence_line_panel(
    top: Axes,
    surface: InfluenceSurface,
    critical: CriticalPosition,
    governing: VehiclePlacement,
    vehicle: Vehicle,
    along_m: np.ndarray,
) -> Axes:
    # Styles the top panel and returns the (empty, for now) scatter of axle markers that
    # draw_frame moves every frame.
    line = surface.influence_at(along_m, np.full_like(along_m, governing.z_centre_m))
    hurts = where_a_load_hurts(line, critical.adverse)
    top.fill_between(along_m, 0, line, where=hurts, color=ADVERSE_COLOUR, alpha=0.28)
    top.fill_between(along_m, 0, line, where=~hurts, color=HELPFUL_COLOUR, alpha=0.20)
    top.plot(along_m, line, color="#222222", linewidth=1.5)
    top.axhline(0, color="black", linewidth=0.7)
    top.set_ylabel("response to a unit load")
    top.set_title(
        f"{vehicle.name.replace('_', ' ')} driving across, at z = {governing.z_centre_m:.2f} m"
    )
    top.grid(alpha=0.2)
    return top.scatter(
        [], [], s=48, c=VEHICLE_COLOUR, edgecolors="black", linewidths=0.6, zorder=6
    )


def style_the_trace_panel(
    bottom: Axes,
    critical: CriticalPosition,
    governing: VehiclePlacement,
    where_m: np.ndarray,
    trace: np.ndarray,
) -> tuple[Axes, Axes]:
    # Styles the bottom panel and returns the (empty, for now) trace-so-far line and
    # current-position marker that draw_frame moves every frame.
    bottom.plot(where_m, trace, color="#999999", linewidth=1.2)
    bottom.axhline(0, color="black", linewidth=0.7)

    # Where the search put this vehicle. Deliberately not the response for the whole deck
    # - that is every lane added together with the residual UDL on top, and drawing it
    # against one vehicle's trace would only mislead.
    chosen_m = governing.train_x_front_m[0]
    bottom.axvline(
        chosen_m, color=ADVERSE_COLOUR, linestyle="--", linewidth=1.4,
        label=f"where setu put it, x = {chosen_m:.2f} m",
    )
    bottom.set_xlabel("front of the vehicle, x (m)")
    bottom.set_ylabel("response this one vehicle causes")
    bottom.set_title(
        f"What it causes from each position   "
        f"(the whole deck, all lanes and UDL, comes to {critical.response:,.0f})"
    )
    bottom.legend(fontsize=8, loc="best")
    bottom.grid(alpha=0.2)
    (so_far,) = bottom.plot([], [], color=ADVERSE_COLOUR, linewidth=2.2)
    now = bottom.scatter([], [], s=60, c=VEHICLE_COLOUR, edgecolors="black", zorder=6)
    return so_far, now
