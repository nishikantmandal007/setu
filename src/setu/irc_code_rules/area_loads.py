from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

from ..adverse_direction import where_a_load_hurts
from ..sampling import DEFAULT_SAMPLING, SamplingSettings
from .code_tables import (
    CLASS_A_LANE_WIDTH_M,
    CYCLE_TRACK_UDL_KPA,
    FOOTWAY_UDL_KPA,
    RESIDUAL_UDL_APPLIES_BELOW_M,
    RESIDUAL_UDL_KPA,
)

if TYPE_CHECKING:
    from ..deck_cross_section import DeckCrossSection
    from ..influence_surfaces.surface import InfluenceSurface

Strip = tuple[float, float]

NOTHING_THERE_M = 1e-12


def needs_residual_udl(carriageway_width_m: float) -> bool:
    return float(carriageway_width_m) < RESIDUAL_UDL_APPLIES_BELOW_M


def strips_beside_class_a(
    z_centre_m: float, carriageway_left_m: float, carriageway_right_m: float
) -> list[Strip]:
    half_lane_m = CLASS_A_LANE_WIDTH_M / 2.0
    covered_by_the_vehicle = (z_centre_m - half_lane_m, z_centre_m + half_lane_m)

    return uncovered_strips(
        [covered_by_the_vehicle], carriageway_left_m, carriageway_right_m
    )


def uncovered_strips(
    covered: Sequence[Strip], from_m: float, to_m: float, tolerance_m: float = 1e-6
) -> list[Strip]:
    in_order = sorted(
        (min(edge_a_m, edge_b_m), max(edge_a_m, edge_b_m)) for edge_a_m, edge_b_m in covered
    )

    strips = []
    cursor_m = from_m
    for starts_m, ends_m in in_order:
        starts_m, ends_m = max(starts_m, from_m), min(ends_m, to_m)
        if starts_m > cursor_m + tolerance_m:
            strips.append((cursor_m, starts_m))
        cursor_m = max(cursor_m, ends_m)

    if to_m > cursor_m + tolerance_m:
        strips.append((cursor_m, to_m))

    return [
        (starts_m, ends_m)
        for starts_m, ends_m in strips
        if ends_m - starts_m > tolerance_m
    ]


def response_to_area_load(
    surface: InfluenceSurface,
    strips: Sequence[Strip],
    adverse: str,
    pressure_kpa: float = RESIDUAL_UDL_KPA,
    adverse_area_only: bool = True,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
) -> float:
    # A uniform load may stand anywhere, so the worst case stands only where it hurts.
    if not strips:
        return 0.0

    x_centres_m, x_widths_m = cell_centres(
        surface.length_mesh_m, sampling.udl_cells_per_mesh_interval_along_span
    )

    total = 0.0
    for from_m, to_m in strips:
        if to_m - from_m <= NOTHING_THERE_M:
            continue

        z_centres_m, z_widths_m = cell_centres(
            [from_m, to_m], sampling.udl_cells_per_mesh_interval_across_width
        )
        ordinates = surface.influence_at(x_centres_m[:, None], z_centres_m[None, :])
        cell_areas_m2 = x_widths_m[:, None] * z_widths_m[None, :]
        cells = ordinates * cell_areas_m2

        if adverse_area_only:
            cells = np.where(where_a_load_hurts(ordinates, adverse), cells, 0.0)

        total += float(cells.sum())

    return pressure_kpa * total


def footway_response(
    surface: InfluenceSurface,
    cross_section: DeckCrossSection,
    adverse: str,
    pressure_kpa: float | None = None,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
) -> float:
    footways = cross_section.footways()
    if not footways:
        return 0.0

    pressure_kpa = FOOTWAY_UDL_KPA if pressure_kpa is None else pressure_kpa
    strips = [(strip.z_from_m, strip.z_to_m) for strip in footways]

    return response_to_area_load(
        surface, strips, adverse, pressure_kpa=pressure_kpa, sampling=sampling
    )


def cell_centres(
    edges_m: Sequence[float] | np.ndarray, cells_per_interval: int
) -> tuple[np.ndarray, np.ndarray]:
    edges_m = np.asarray(edges_m, float)
    intervals = len(edges_m) - 1

    interval_starts_m = np.repeat(edges_m[:-1], cells_per_interval)
    interval_ends_m = np.repeat(edges_m[1:], cells_per_interval)
    which_cell = np.tile(np.arange(cells_per_interval), intervals)

    widths_m = (interval_ends_m - interval_starts_m) / cells_per_interval
    centres_m = interval_starts_m + (which_cell + 0.5) * widths_m
    return centres_m, widths_m


__all__ = [
    "CYCLE_TRACK_UDL_KPA",
    "FOOTWAY_UDL_KPA",
    "RESIDUAL_UDL_KPA",
    "footway_response",
    "needs_residual_udl",
    "response_to_area_load",
    "strips_beside_class_a",
    "uncovered_strips",
]
