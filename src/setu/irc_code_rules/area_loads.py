# Load spread over an area rather than carried on wheels: the Table 6 residual UDL beside
# a vehicle on a narrow carriageway, and the Clause 206 footway and cycle track load. Both
# are loaded on the adverse area only - see response_to_area_load for why that matters.

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np

from ..adverse_direction import where_a_load_hurts
from ..sampling import DEFAULT_SAMPLING, SamplingSettings
from .code_tables import (
    CLASS_A_LANE_WIDTH_M,
    CYCLE_TRACK_UDL_KPA,  # re-exported for the public API; no code path applies it yet
    FOOTWAY_UDL_KPA,
    RESIDUAL_UDL_APPLIES_BELOW_M,
    RESIDUAL_UDL_KPA,
)

Strip = tuple[float, float]


# ---------------------------------------------------------------------------
# Duck Types For The Surface And The Cross-Section
# ---------------------------------------------------------------------------

# irc_code_rules knows nothing about finite elements, so InfluenceSurface and
# DeckCrossSection cannot be imported here. These Protocols name only the members this
# module actually reads off them, so the layering holds without giving up type hints.


class InfluenceSurfaceLike(Protocol):
    length_mesh_m: np.ndarray

    def influence_at(self, x_m: np.ndarray, z_m: np.ndarray) -> np.ndarray: ...


class FootwayStrip(Protocol):
    # Read-only properties, not plain attributes - the real DeckStrip is a frozen
    # dataclass, so its fields are read-only too, and a Protocol needs the same shape.
    @property
    def z_from_m(self) -> float: ...
    @property
    def z_to_m(self) -> float: ...


class CrossSectionLike(Protocol):
    def footways(self) -> Sequence[FootwayStrip]: ...


# ---------------------------------------------------------------------------
# Table 6 S.No.1 - The Residual Load Beside A Vehicle
# ---------------------------------------------------------------------------


def needs_residual_udl(carriageway_width_m: float) -> bool:
    # Table 6 S.No.1 puts a residual load beside the vehicle below this width.
    return float(carriageway_width_m) < RESIDUAL_UDL_APPLIES_BELOW_M


def strips_beside_class_a(
    z_centre_m: float, carriageway_left_m: float, carriageway_right_m: float
) -> list[Strip]:
    # The uncovered strips move with the vehicle, so this is evaluated for each candidate
    # position searched, rather than being one load added at the end.
    covered = (
        z_centre_m - CLASS_A_LANE_WIDTH_M / 2.0,
        z_centre_m + CLASS_A_LANE_WIDTH_M / 2.0,
    )
    return uncovered_strips([covered], carriageway_left_m, carriageway_right_m)


def uncovered_strips(
    covered: Sequence[Strip], from_m: float, to_m: float, tolerance_m: float = 1e-6
) -> list[Strip]:
    # The parts of [from_m, to_m] that none of `covered` overlaps.
    # tolerance_m is this function's own tolerance, not code_tables.TOLERANCE_M - leave it
    # at 1e-6.
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

    return [strip for strip in strips if strip[1] - strip[0] > tolerance_m]


# ---------------------------------------------------------------------------
# The Response To A Uniform Pressure
# ---------------------------------------------------------------------------


def response_to_area_load(
    surface: InfluenceSurfaceLike,
    strips: Sequence[Strip],
    adverse: str,
    pressure_kpa: float = RESIDUAL_UDL_KPA,
    adverse_area_only: bool = True,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
) -> float:
    # The response caused by a uniform pressure over these strips, run the full length of
    # the deck. Each strip is divided into cells - see cell_centres - and each cell
    # contributes its area times the influence ordinate at its middle.
    #
    # With adverse_area_only, a cell whose ordinate has the helpful sign is left unloaded -
    # the Muller-Breslau reading of a uniform load: it is free to be present in some places
    # and absent in others, so the worst case stands only where it hurts. Loading the full
    # length instead, on a continuous deck, can understate hogging by more than half.
    if not strips:
        return 0.0

    x_centres_m, x_widths_m = cell_centres(
        surface.length_mesh_m, sampling.udl_cells_along_span
    )

    total = 0.0
    for from_m, to_m in strips:
        if to_m - from_m <= 1e-12:
            continue

        z_centres_m, z_widths_m = cell_centres(
            [from_m, to_m], sampling.udl_cells_across_width
        )
        ordinates = surface.influence_at(x_centres_m[:, None], z_centres_m[None, :])
        cells = ordinates * x_widths_m[:, None] * z_widths_m[None, :]

        if adverse_area_only:
            cells = np.where(where_a_load_hurts(ordinates, adverse), cells, 0.0)

        total += float(cells.sum())

    return pressure_kpa * total


def footway_response(
    surface: InfluenceSurfaceLike,
    cross_section: CrossSectionLike,
    adverse: str,
    pressure_kpa: float | None = None,
    sampling: SamplingSettings = DEFAULT_SAMPLING,
) -> float:
    # Clause 206 crowd load on the footways. It does not move with the traffic, so this is
    # one number added to every case. No impact factor - a crowd does not bounce the way a
    # wheel does.
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
    # The middle and the width of every cell, after subdividing each interval of edges_m
    # into cells_per_interval equal cells - the quadrature grid response_to_area_load
    # integrates the pressure over.
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
