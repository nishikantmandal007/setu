import numpy as np
from matplotlib import colormaps
from matplotlib.colors import CenteredNorm, LinearSegmentedColormap, Normalize
from matplotlib.patches import Rectangle
from matplotlib.animation import FuncAnimation
from typing import Any

from src.utils.helpers import is_worst_first, where_a_load_hurts, DEFAULT_SAMPLING
from src.rules.irc6 import CLASS_A_LANE, ZONE_70R, OFFSET_DX_M, OFFSET_DZ_M, OFFSET_LOAD_KN, narrowest_carriageway_that_fits, wheel_load_offsets
from src.models.vehicles import class_of, IRC_VEHICLES
from src.services.vehicle_placement import VehicleResponses
from src.models.vehicles import pitch_between_vehicles_m, AxleVehicle, TrackedVehicle, find_vehicle_or_its_reverse

class DrawingService:
    STRIP_COLOURS = {'carriageway': '#3d4451', 'footpath': '#8d9aad', 'footway': '#8d9aad', 'kerb': '#c2b59b', 'median': '#9aa77f'}
    OTHER_STRIP_COLOUR = '#b8b8b8'
    ADVERSE_COLOUR = '#c0392b'
    HELPFUL_COLOUR = '#2471a3'
    VEHICLE_COLOUR = '#f0b323'
    INFLUENCE_LINE_SAMPLES = 600

    @staticmethod
    def strip_colour(name):
        for prefix, colour in DrawingService.STRIP_COLOURS.items():
            if name.startswith(prefix):
                return colour
        return DrawingService.OTHER_STRIP_COLOUR

    @staticmethod
    def adverse_colourmap():
        from matplotlib.colors import LinearSegmentedColormap
        return LinearSegmentedColormap.from_list('adverse', [DrawingService.HELPFUL_COLOUR, '#dfe6ec', '#f7f2e8', '#e8a798', DrawingService.ADVERSE_COLOUR])
    Axes = Any
    Figure = Any

    @staticmethod
    def import_matplotlib():
        try:
            import matplotlib.pyplot as plt
            import matplotlib.pyplot as plt
        except ImportError as missing:
            raise ImportError('drawing needs matplotlib, which setu does not install by default. Add it with `uv sync --extra plot`.') from missing
        return plt
    DECK_TOP_M = 0.0
    DECK_BOTTOM_M = -0.55
    WHEEL_HEIGHT_M = 0.42
    BODY_HEIGHT_M = 1.15
    NARROW_STRIP_LABEL_WIDTH_M = 1.2

    @staticmethod
    def draw_cross_section(cross_section, critical=None, ax=None):
        plt = DrawingService.import_matplotlib()
        if ax is None:
            _, ax = plt.subplots(figsize=(11, 3.5))
        for strip in cross_section.strips:
            ax.add_patch(plt.Rectangle((strip.z_from_m, DrawingService.DECK_BOTTOM_M), strip.width_m, DrawingService.DECK_TOP_M - DrawingService.DECK_BOTTOM_M, facecolor=DrawingService.strip_colour(strip.name), edgecolor='white', linewidth=1.2))
            narrow = strip.width_m < DrawingService.NARROW_STRIP_LABEL_WIDTH_M
            ax.text((strip.z_from_m + strip.z_to_m) / 2, DrawingService.DECK_BOTTOM_M - 0.12, strip.name.replace('_', ' '), ha='right' if narrow else 'center', va='top', rotation=90 if narrow else 0, fontsize=6.5, color='#444444')
        if critical is not None:
            for placed in critical.vehicles:
                DrawingService.draw_vehicle_from_the_front(ax, placed)
        ax.set_xlim(-0.4, cross_section.total_width_m() + 0.4)
        ax.set_ylim(DrawingService.DECK_BOTTOM_M - 2.2, 3.0)
        ax.set_aspect('equal')
        ax.set_xlabel('across the width, z (m)')
        ax.set_yticks([])
        for side in ('left', 'right', 'top'):
            ax.spines[side].set_visible(False)
        ax.set_title('Looking at the deck head on, with the vehicles in place')
        return ax

    @staticmethod
    def draw_vehicle_from_the_front(ax, placed):
        plt = DrawingService.import_matplotlib()
        vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
        body_width_m = getattr(vehicle, 'overall_width_m', None) or vehicle.transverse_gauge_m + 0.6
        half_gauge_m = vehicle.transverse_gauge_m / 2
        wheel_width_m = vehicle.track_width_m if isinstance(vehicle, TrackedVehicle) else 0.35
        for side in (-1, +1):
            ax.add_patch(plt.Rectangle((placed.z_centre_m + side * half_gauge_m - wheel_width_m / 2, 0.0), wheel_width_m, DrawingService.WHEEL_HEIGHT_M, facecolor='#2b2b2b', edgecolor='black', linewidth=0.6, zorder=4))
        ax.add_patch(plt.Rectangle((placed.z_centre_m - body_width_m / 2, DrawingService.WHEEL_HEIGHT_M), body_width_m, DrawingService.BODY_HEIGHT_M, facecolor=DrawingService.VEHICLE_COLOUR, edgecolor='#8a6400', linewidth=1.2, zorder=5))
        ax.plot([placed.z_centre_m, placed.z_centre_m], [0, DrawingService.WHEEL_HEIGHT_M + DrawingService.BODY_HEIGHT_M + 0.35], color='#8a6400', linestyle=':', linewidth=1.0, zorder=6)
        label = placed.vehicle_name.replace('Class_', '').replace('_', ' ')
        if placed.vehicles_in_train() > 1:
            label += f'\n{placed.vehicles_in_train()} in the lane'
        ax.text(placed.z_centre_m, DrawingService.WHEEL_HEIGHT_M + DrawingService.BODY_HEIGHT_M + 0.45, label, ha='center', va='bottom', fontsize=7.5, fontweight='bold')

    @staticmethod
    def draw_response_across_width(surface, cross_section, critical, span_m, ax=None, *, wearing_course_thickness_m=0.0, material='steel', member_span_m=None):
        plt = DrawingService.import_matplotlib()
        if ax is None:
            _, ax = plt.subplots(figsize=(9, 4))
        carriageways = cross_section.carriageways()
        z_positions_m = np.linspace(min((carriageway.left_m for carriageway in carriageways)), max((carriageway.right_m for carriageway in carriageways)), DEFAULT_SAMPLING.positions_across_the_deck_to_try)
        responses = VehicleResponses(surface, span_m=span_m, material=material, member_span_m=member_span_m, wearing_course_thickness_m=wearing_course_thickness_m)
        widest_m = max((carriageway.width_m() for carriageway in carriageways))
        for vehicle in DrawingService.vehicles_worth_drawing(critical):
            curve = responses.for_vehicle(vehicle, z_positions_m, critical.adverse)
            name = vehicle.name.replace('Class_', '').replace('_', ' ')
            needed_m = DrawingService.narrowest_carriageway_for(vehicle)
            if needed_m <= widest_m + 1e-09:
                ax.plot(z_positions_m, curve.response, linewidth=1.8, label=name)
            else:
                ax.plot(z_positions_m, curve.response, linewidth=1.4, linestyle=':', color='#9a9a9a', alpha=0.85, label=f'{name} - will not fit, needs {needed_m:.2f} m')
        for carriageway in carriageways:
            ax.axvspan(carriageway.left_m, carriageway.right_m, color='#3d4451', alpha=0.08)
        for placed in critical.vehicles:
            ax.axvline(placed.z_centre_m, color=DrawingService.VEHICLE_COLOUR, linewidth=2.0, alpha=0.9)
        ax.axhline(0, color='black', linewidth=0.7)
        ax.set_xlabel('vehicle centreline across the width, z (m)')
        ax.set_ylabel('worst response from here')
        ax.set_title(f'Why that lane: what each vehicle could do (widest carriageway here is {widest_m:.2f} m)')
        ax.legend(fontsize=7.5, loc='best')
        ax.grid(alpha=0.25)
        return ax

    @staticmethod
    def vehicles_worth_drawing(critical):
        drawn = dict(IRC_VEHICLES)
        for placed in critical.vehicles:
            drawn.setdefault(placed.vehicle_name, find_vehicle_or_its_reverse(placed.vehicle_name))
        return list(drawn.values())

    @staticmethod
    def narrowest_carriageway_for(vehicle):
        block = ZONE_70R if '70R' in vehicle.name else CLASS_A_LANE
        return narrowest_carriageway_that_fits([block])

    @staticmethod
    def draw_influence_surface(surface, critical=None, ax=None):
        plt = DrawingService.import_matplotlib()
        if ax is None:
            ax = plt.figure(figsize=(9, 7)).add_subplot(projection='3d')
        along_m, across_m = np.meshgrid(surface.length_mesh_m, surface.width_mesh_m, indexing='ij')
        peak = float(np.abs(surface.values).max()) or 1.0
        colours = DrawingService.adverse_colourmap()
        ax.plot_surface(along_m, across_m, surface.values, cmap=colours, vmin=-peak, vmax=peak, linewidth=0, antialiased=True, alpha=0.95, rstride=1, cstride=1)
        floor = float(surface.values.min()) - 0.35 * peak
        ax.contourf(along_m, across_m, surface.values, levels=18, cmap=colours, vmin=-peak, vmax=peak, zdir='z', offset=floor, alpha=0.85)
        if critical is not None:
            DrawingService.mark_wheels_on_surface(ax, surface, critical, peak)
        ax.set_zlim(floor, max(float(surface.values.max()), 0.05 * peak))
        ax.set_xlabel('along the span, x (m)', labelpad=2)
        ax.set_ylabel('across the width, z (m)', labelpad=2)
        ax.set_zlabel('response to a unit load', labelpad=2)
        ax.set_title('The influence surface, and where the wheels went', pad=-4)
        ax.view_init(elev=28, azim=-128)
        ax.set_box_aspect((1.5, 1.1, 0.85), zoom=1.15)
        ax.tick_params(labelsize=7.5)
        return ax

    @staticmethod
    def mark_wheels_on_surface(ax, surface, critical, peak):
        for placed in critical.vehicles:
            vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
            offsets = wheel_load_offsets(vehicle)
            for x_front_m in placed.train_x_front_m:
                wheel_x_m = x_front_m + offsets[:, OFFSET_DX_M]
                wheel_z_m = placed.z_centre_m + offsets[:, OFFSET_DZ_M]
                on_the_deck = (wheel_x_m >= surface.length_mesh_m[0]) & (wheel_x_m <= surface.length_mesh_m[-1])
                ax.scatter(wheel_x_m[on_the_deck], wheel_z_m[on_the_deck], surface.influence_at(wheel_x_m[on_the_deck], wheel_z_m[on_the_deck]), s=18, c=DrawingService.VEHICLE_COLOUR, edgecolors='black', linewidths=0.4, depthshade=False, zorder=10)

    @staticmethod
    def draw_influence_along_span(surface, critical, ax=None):
        plt = DrawingService.import_matplotlib()
        if ax is None:
            _, ax = plt.subplots(figsize=(9, 4))
        governing = critical.vehicles[0]
        along_m = np.linspace(surface.length_mesh_m[0], surface.length_mesh_m[-1], DrawingService.INFLUENCE_LINE_SAMPLES)
        line = surface.influence_at(along_m, np.full_like(along_m, governing.z_centre_m))
        hurts = where_a_load_hurts(line, critical.adverse)
        ax.fill_between(along_m, 0, line, where=hurts, color=DrawingService.ADVERSE_COLOUR, alpha=0.3, label='loading here hurts')
        ax.fill_between(along_m, 0, line, where=~hurts, color=DrawingService.HELPFUL_COLOUR, alpha=0.22, label='loading here helps')
        ax.plot(along_m, line, color='#222222', linewidth=1.6)
        vehicle = find_vehicle_or_its_reverse(governing.vehicle_name)
        axle_dx_m = np.unique(wheel_load_offsets(vehicle)[:, OFFSET_DX_M])
        for number, x_front_m in enumerate(governing.train_x_front_m, start=1):
            axle_x_m = x_front_m + axle_dx_m
            on_the_deck = (axle_x_m >= along_m[0]) & (axle_x_m <= along_m[-1])
            ax.scatter(axle_x_m[on_the_deck], surface.influence_at(axle_x_m[on_the_deck], np.full(on_the_deck.sum(), governing.z_centre_m)), s=42, c=DrawingService.VEHICLE_COLOUR, edgecolors='black', linewidths=0.6, zorder=6, label='axles' if number == 1 else None)
            if len(governing.train_x_front_m) > 1:
                ax.annotate(f'vehicle {number}', (x_front_m, 0), textcoords='offset points', xytext=(0, -14), ha='center', fontsize=7.5, color='#8a6400')
        ax.axhline(0, color='black', linewidth=0.7)
        ax.set_xlabel('along the span, x (m)')
        ax.set_ylabel('response to a unit load')
        ax.set_title(f'Why that spot: the influence line at z = {governing.z_centre_m:.2f} m')
        ax.legend(fontsize=8, loc='best')
        ax.grid(alpha=0.25)
        return ax

    @staticmethod
    def animate_vehicle_along_span(surface, critical, frames=120, interval_ms=45):
        plt = DrawingService.import_matplotlib()
        from matplotlib.animation import FuncAnimation
        governing = critical.vehicles[0]
        vehicle = find_vehicle_or_its_reverse(governing.vehicle_name)
        offsets = wheel_load_offsets(vehicle)
        axle_dx_m = np.unique(offsets[:, OFFSET_DX_M])
        first_m = surface.length_mesh_m[0] - float(offsets[:, OFFSET_DX_M].max())
        last_m = float(surface.length_mesh_m[-1])
        where_m = np.linspace(first_m, last_m, frames)
        trace = DrawingService.response_trace_along_span(surface, governing, offsets, where_m)
        along_m = np.linspace(surface.length_mesh_m[0], surface.length_mesh_m[-1], DrawingService.INFLUENCE_LINE_SAMPLES)
        figure, top, bottom = DrawingService.two_panel_figure(plt)
        axles = DrawingService.style_the_influence_line_panel(top, surface, critical, governing, vehicle, along_m)
        so_far, now = DrawingService.style_the_trace_panel(bottom, critical, governing, where_m, trace)

        def draw_frame(frame):
            x_front_m = where_m[frame]
            axles.set_offsets(DrawingService.axle_markers(surface, governing, x_front_m + axle_dx_m, along_m))
            so_far.set_data(where_m[:frame + 1], trace[:frame + 1])
            now.set_offsets([[x_front_m, trace[frame]]])
            return (axles, so_far, now)
        return FuncAnimation(figure, draw_frame, frames=frames, interval=interval_ms, blit=False)

    @staticmethod
    def axle_markers(surface, governing, axle_x_m, along_m):
        on_the_deck = (axle_x_m >= along_m[0]) & (axle_x_m <= along_m[-1])
        if not on_the_deck.any():
            return np.empty((0, 2))
        x_m = axle_x_m[on_the_deck]
        z_m = np.full(on_the_deck.sum(), governing.z_centre_m)
        return np.column_stack([x_m, surface.influence_at(x_m, z_m)])

    @staticmethod
    def response_trace_along_span(surface, governing, offsets, where_m):

        def response_with_front_at(x_front_m):
            wheel_x_m = x_front_m + offsets[:, OFFSET_DX_M]
            wheel_z_m = governing.z_centre_m + offsets[:, OFFSET_DZ_M]
            return float((surface.influence_at(wheel_x_m, wheel_z_m) * offsets[:, OFFSET_LOAD_KN]).sum() * governing.impact_factor)
        return np.array([response_with_front_at(x_m) for x_m in where_m])

    @staticmethod
    def two_panel_figure(plt):
        figure, (top, bottom) = plt.subplots(2, 1, figsize=(10, 7), height_ratios=[1.2, 1.0], gridspec_kw={'hspace': 0.32})
        return (figure, top, bottom)

    @staticmethod
    def style_the_influence_line_panel(top, surface, critical, governing, vehicle, along_m):
        line = surface.influence_at(along_m, np.full_like(along_m, governing.z_centre_m))
        hurts = where_a_load_hurts(line, critical.adverse)
        top.fill_between(along_m, 0, line, where=hurts, color=DrawingService.ADVERSE_COLOUR, alpha=0.28)
        top.fill_between(along_m, 0, line, where=~hurts, color=DrawingService.HELPFUL_COLOUR, alpha=0.2)
        top.plot(along_m, line, color='#222222', linewidth=1.5)
        top.axhline(0, color='black', linewidth=0.7)
        top.set_ylabel('response to a unit load')
        top.set_title(f'{vehicle.name.replace('_', ' ')} driving across, at z = {governing.z_centre_m:.2f} m')
        top.grid(alpha=0.2)
        return top.scatter([], [], s=48, c=DrawingService.VEHICLE_COLOUR, edgecolors='black', linewidths=0.6, zorder=6)

    @staticmethod
    def style_the_trace_panel(bottom, critical, governing, where_m, trace):
        bottom.plot(where_m, trace, color='#999999', linewidth=1.2)
        bottom.axhline(0, color='black', linewidth=0.7)
        chosen_m = governing.train_x_front_m[0]
        bottom.axvline(chosen_m, color=DrawingService.ADVERSE_COLOUR, linestyle='--', linewidth=1.4, label=f'where setu put it, x = {chosen_m:.2f} m')
        bottom.set_xlabel('front of the vehicle, x (m)')
        bottom.set_ylabel('response this one vehicle causes')
        bottom.set_title(f'What it causes from each position   (the whole deck, all lanes and UDL, comes to {critical.response:,.0f})')
        bottom.legend(fontsize=8, loc='best')
        bottom.grid(alpha=0.2)
        so_far, = bottom.plot([], [], color=DrawingService.ADVERSE_COLOUR, linewidth=2.2)
        now = bottom.scatter([], [], s=60, c=DrawingService.VEHICLE_COLOUR, edgecolors='black', zorder=6)
        return (so_far, now)

    @staticmethod
    def draw_everything(surface, cross_section, critical, span_m, figure_size=(17.0, 10.0), *, wearing_course_thickness_m=0.0, material='steel', member_span_m=None):
        plt = DrawingService.import_matplotlib()
        figure = plt.figure(figsize=figure_size)
        figure.suptitle(f'{critical.response_name}   worst {critical.adverse} = {critical.response:,.3f}', fontsize=14, fontweight='bold')
        grid = figure.add_gridspec(2, 2, height_ratios=[1.35, 1.0], hspace=0.28, wspace=0.2)
        DrawingService.draw_influence_surface(surface, critical, ax=figure.add_subplot(grid[0, 0], projection='3d'))
        DrawingService.draw_cross_section(cross_section, critical, ax=figure.add_subplot(grid[0, 1]))
        DrawingService.draw_response_across_width(surface, cross_section, critical, span_m, ax=figure.add_subplot(grid[1, 0]), wearing_course_thickness_m=wearing_course_thickness_m, material=material, member_span_m=member_span_m)
        DrawingService.draw_influence_along_span(surface, critical, ax=figure.add_subplot(grid[1, 1]))
        return figure

DrawingService.DrawingService = DrawingService


def draw_cross_section(*args, **kwargs):
    """Draw the deck cross-section and any selected vehicle placement."""
    return DrawingService.draw_cross_section(*args, **kwargs)


def draw_everything(*args, **kwargs):
    """Draw the four-panel explanation of an influence result."""
    return DrawingService.draw_everything(*args, **kwargs)


def animate_vehicle_along_span(*args, **kwargs):
    """Animate a governing vehicle travelling along the influence line."""
    return DrawingService.animate_vehicle_along_span(*args, **kwargs)
