# What one vehicle's wheels do to the influence surface, at every position worth trying.
# This is the exactness argument for the whole vehicle-placement search:
#
#     curve(z) = impact factor * worst over x of  sum over wheels  load * influence_at(x, z)
#
# (impact factor is applied by the caller - see response_curve.py. This file builds the
# "sum over wheels" part, and works out where "worst over x" actually needs to look.)
#
# Two things make the answer exact rather than merely finely sampled.
#
# Along the span, the only positions tried are those that put some wheel exactly on a mesh
# station. The influence surface is flat-faceted between its stations, so the worst position
# is always one of those - checking more would find nothing.
#
# Across the width, the same reasoning gives the positions where the curve bends, and the
# searches are handed those so they can bend their grids to match.

from __future__ import annotations

import numpy as np

from ..influence_surfaces.surface import InfluenceSurface
from ..irc_code_rules.code_tables import TOLERANCE_M
from ..irc_code_rules.vehicles import Vehicle
from ..irc_code_rules.wheel_loads import (
    OFFSET_DX_M,
    OFFSET_DZ_M,
    split_offsets,
    wheel_load_offsets,
)
from ..sampling import SamplingSettings

# ---------------------------------------------------------------------------
# Along The Span
# ---------------------------------------------------------------------------


def positions_along_span(surface: InfluenceSurface, wheel_offsets: np.ndarray) -> np.ndarray:
    # Returns every position along the span worth trying for these wheels.
    #
    # A position is worth trying when it puts some wheel exactly on a mesh station, because
    # that is where the surface bends. The range starts far enough back for the vehicle to
    # be part-way onto the bridge, which is a real load case and often the worst one near a
    # support.
    stations_m = surface.length_mesh_m
    wheel_dx_m = np.asarray(wheel_offsets, float)[:, OFFSET_DX_M]

    candidates_m = np.unique((stations_m[None, :] - wheel_dx_m[:, None]).ravel())
    first_m = -wheel_dx_m.max()
    last_m = stations_m[-1]
    return candidates_m[
        (candidates_m >= first_m - TOLERANCE_M) & (candidates_m <= last_m + TOLERANCE_M)
    ]


def response_to_one_vehicle_everywhere(
    surface: InfluenceSurface,
    wheel_offsets: np.ndarray,
    x_positions_m: np.ndarray,
    z_positions_m: np.ndarray,
    sampling: SamplingSettings,
) -> np.ndarray:
    # Returns the response to one vehicle at every (along span, across width) pair.
    #
    # Built a chunk of longitudinal positions at a time, because the full wheel-by-wheel
    # tensor would be large enough to matter on a fine mesh.
    responses = np.empty((len(x_positions_m), len(z_positions_m)))
    chunk = sampling.positions_per_chunk

    for start in range(0, len(x_positions_m), chunk):
        chunk_x_m = x_positions_m[start : start + chunk]
        responses[start : start + len(chunk_x_m)] = sum_over_wheels(
            surface, wheel_offsets, chunk_x_m, z_positions_m
        )

    return responses


def sum_over_wheels(
    surface: InfluenceSurface,
    wheel_offsets: np.ndarray,
    x_positions_m: np.ndarray,
    z_positions_m: np.ndarray,
) -> np.ndarray:
    # Returns sum over wheels of load times influence, for every position pair.
    offsets = np.asarray(wheel_offsets, float)
    wheel_dx_m, wheel_dz_m, wheel_loads_kn = split_offsets(offsets)

    wheel_x_m = np.asarray(x_positions_m, float)[:, None, None] + wheel_dx_m[None, None, :]
    wheel_z_m = np.asarray(z_positions_m, float)[None, :, None] + wheel_dz_m[None, None, :]

    return (surface.influence_at(wheel_x_m, wheel_z_m) * wheel_loads_kn).sum(axis=-1)


# ---------------------------------------------------------------------------
# Across The Width
# ---------------------------------------------------------------------------


def bending_positions_across_width(
    surface: InfluenceSurface,
    vehicle: Vehicle,
    wearing_course_thickness_m: float,
    sampling: SamplingSettings,
    z_from_m: float,
    z_to_m: float,
) -> np.ndarray:
    # Returns the positions across the deck where this vehicle's curve bends.
    #
    # The curve bends when a wheel crosses a mesh station, so these are the stations
    # shifted back by each wheel's offset. Sampling a curve here makes it exactly
    # piecewise linear rather than approximately so.
    wheel_offsets = wheel_load_offsets(vehicle, wearing_course_thickness_m, sampling)
    wheel_dz_m = np.asarray(wheel_offsets, float)[:, OFFSET_DZ_M]
    stations_m = surface.width_mesh_m

    bends_m = np.unique(
        np.concatenate(
            [
                (stations_m[None, :] - wheel_dz_m[:, None]).ravel(),
                np.array([z_from_m, z_to_m], float),
            ]
        )
    )
    return bends_m[(bends_m >= z_from_m - TOLERANCE_M) & (bends_m <= z_to_m + TOLERANCE_M)]
