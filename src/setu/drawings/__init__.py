from __future__ import annotations

from ..deck_cross_section import DeckCrossSection
from ..influence_surfaces.surface import InfluenceSurface
from ..results import CriticalPosition
from .animation import animate_vehicle_along_span
from .deck_pictures import (
    draw_cross_section,
    draw_response_across_width,
    draw_vehicle_from_the_front,
    narrowest_carriageway_for,
    vehicles_worth_drawing,
)
from .palette import (
    ADVERSE_COLOUR,
    HELPFUL_COLOUR,
    OTHER_STRIP_COLOUR,
    STRIP_COLOURS,
    VEHICLE_COLOUR,
    Figure,
    adverse_colourmap,
    import_matplotlib,
    strip_colour,
)
from .surface_pictures import (
    draw_influence_along_span,
    draw_influence_surface,
    mark_wheels_on_surface,
)

__all__ = [
    "ADVERSE_COLOUR",
    "HELPFUL_COLOUR",
    "OTHER_STRIP_COLOUR",
    "STRIP_COLOURS",
    "VEHICLE_COLOUR",
    "adverse_colourmap",
    "animate_vehicle_along_span",
    "draw_cross_section",
    "draw_everything",
    "draw_influence_along_span",
    "draw_influence_surface",
    "draw_response_across_width",
    "draw_vehicle_from_the_front",
    "import_matplotlib",
    "mark_wheels_on_surface",
    "narrowest_carriageway_for",
    "strip_colour",
    "vehicles_worth_drawing",
]


def draw_everything(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    critical: CriticalPosition,
    span_m: float,
    figure_size: tuple[float, float] = (17.0, 10.0),
    *,
    wearing_course_thickness_m: float = 0.0,
    material: str = "steel",
    member_span_m: float | None = None,
) -> Figure:
    plt = import_matplotlib()

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
        surface, cross_section, critical, span_m,
        ax=figure.add_subplot(grid[1, 0]),
        wearing_course_thickness_m=wearing_course_thickness_m,
        material=material,
        member_span_m=member_span_m,
    )
    draw_influence_along_span(surface, critical, ax=figure.add_subplot(grid[1, 1]))

    return figure
