"""Load spread over an area rather than carried on wheels.

Two clauses put a uniform load on the deck beside the vehicles.

Table 6 S.No.1 puts 500 kg/m2 on the part of a narrow carriageway a vehicle does
not cover. It is not a constant: the uncovered strips move with the vehicle, so
this load is part of the search rather than something added at the end.

Clause 206 puts 5 kN/m2 on footways and cycle tracks. That one does not move,
so it is worked out once.

Both are loaded on the adverse area only. A uniform load is free to be present
in some places and absent in others, so the worst case puts it exactly where it
hurts and nowhere else. Loading the full length instead, on a continuous deck,
can understate hogging by more than half.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ..sampling import DEFAULT_SAMPLING, SamplingSettings
from .code_tables import (
    CLASS_A_LANE_WIDTH_M,
    CYCLE_TRACK_UDL_KPA,
    FOOTWAY_UDL_KPA,
    RESIDUAL_UDL_APPLIES_BELOW_M,
    RESIDUAL_UDL_KPA,
)

Strip = tuple[float, float]


def needs_residual_udl(carriageway_width_m: float) -> bool:
    """Returns True when Table 6 S.No.1 puts a residual load beside the vehicle."""
    return float(carriageway_width_m) < RESIDUAL_UDL_APPLIES_BELOW_M


def strips_beside_class_a(
    z_centre_m: float, carriageway_left_m: float, carriageway_right_m: float
) -> list[Strip]:
    """Returns the parts of the carriageway a Class A vehicle here does not cover."""
    covered = (
        z_centre_m - CLASS_A_LANE_WIDTH_M / 2.0,
        z_centre_m + CLASS_A_LANE_WIDTH_M / 2.0,
    )
    return uncovered_strips([covered], carriageway_left_m, carriageway_right_m)


def uncovered_strips(
    covered: Sequence[Strip], from_m: float, to_m: float, tolerance_m: float = 1e-6
) -> list[Strip]:
    """Returns the parts of [from_m, to_m] that none of `covered` overlaps."""
    in_order = sorted((min(a, b), max(a, b)) for a, b in covered)

    strips = []
    cursor_m = from_m
    for starts_m, ends_m in in_order:
        starts_m, ends_m = max(starts_m, from_m), min(ends_m, to_m)
        if starts_m > cursor_m + tolerance_m:
            strips.append((cursor_m, starts_m))
        cursor_m = max(cursor_m, ends_m)

    if to_m > cursor_m + tolerance_m:
        strips.append((cursor_m, to_m))

    return [strip for strip in strips if strip[1] - strip[0] > tolerance_m]


def response_to_area_load(
    surface,
    strips: Sequence[Strip],
    adverse: str,
    pressure_kpa: float = RESIDUAL_UDL_KPA,
    adverse_area_only: bool = True,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
) -> float:
    """Returns the response caused by a uniform pressure over these strips.

    The strips run the full length of the deck. Each is divided into cells, and
    each cell contributes its area times the influence ordinate at its middle.

    With `adverse_area_only`, a cell whose ordinate has the helpful sign is left
    unloaded. That is the Muller-Breslau reading of a uniform load: it may stand
    anywhere, so the worst case stands only where it hurts.
    """
    if not strips:
        return 0.0

    x_centres_m, x_widths_m = _cell_centres(
        surface.length_mesh_m, sampling.udl_cells_along_span
    )

    total = 0.0
    for from_m, to_m in strips:
        if to_m - from_m <= 1e-12:
            continue

        z_centres_m, z_widths_m = _cell_centres([from_m, to_m], sampling.udl_cells_across_width)
        ordinates = surface.influence_at(x_centres_m[:, None], z_centres_m[None, :])
        cells = ordinates * x_widths_m[:, None] * z_widths_m[None, :]

        if adverse_area_only:
            hurts = ordinates < 0.0 if adverse == "minimum" else ordinates > 0.0
            cells = np.where(hurts, cells, 0.0)

        total += float(cells.sum())

    return pressure_kpa * total


def footway_response(
    surface,
    cross_section,
    adverse: str,
    pressure_kpa: float | None = None,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
) -> float:
    """Returns the response caused by the Clause 206 crowd load on the footways.

    It does not move with the traffic, so it is one number added to every case.
    No impact factor: a crowd does not bounce the way a wheel does.
    """
    footways = cross_section.footways()
    if not footways:
        return 0.0

    pressure_kpa = FOOTWAY_UDL_KPA if pressure_kpa is None else pressure_kpa
    strips = [(strip.z_from_m, strip.z_to_m) for strip in footways]

    return response_to_area_load(
        surface, strips, adverse, pressure_kpa=pressure_kpa, sampling=sampling
    )


def _cell_centres(edges_m, cells_per_interval: int) -> tuple[np.ndarray, np.ndarray]:
    """Returns the middle and the width of every cell, after subdividing each interval."""
    edges_m = np.asarray(edges_m, float)

    from_m = np.repeat(edges_m[:-1], cells_per_interval)
    to_m = np.repeat(edges_m[1:], cells_per_interval)
    which_cell = np.tile(np.arange(cells_per_interval), len(edges_m) - 1)

    widths_m = (to_m - from_m) / cells_per_interval
    return from_m + (which_cell + 0.5) * widths_m, widths_m


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
