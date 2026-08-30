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


def positions_along_span(surface: InfluenceSurface, wheel_offsets: np.ndarray) -> np.ndarray:
    # The surface is flat-faceted between mesh stations, so the worst position always
    # puts some wheel exactly on a station and nothing else is worth trying.
    stations_m = surface.length_mesh_m
    wheel_dx_m = np.asarray(wheel_offsets, float)[:, OFFSET_DX_M]

    puts_a_wheel_on_a_station_m = np.unique(
        (stations_m[None, :] - wheel_dx_m[:, None]).ravel()
    )

    part_way_onto_the_bridge_m = -wheel_dx_m.max()
    far_end_of_the_bridge_m = stations_m[-1]

    return keep_between(
        puts_a_wheel_on_a_station_m, part_way_onto_the_bridge_m, far_end_of_the_bridge_m
    )


def response_to_one_vehicle_everywhere(
    surface: InfluenceSurface,
    wheel_offsets: np.ndarray,
    x_positions_m: np.ndarray,
    z_positions_m: np.ndarray,
    sampling: SamplingSettings,
) -> np.ndarray:
    responses = np.empty((len(x_positions_m), len(z_positions_m)))
    evaluated_at_once = sampling.span_positions_evaluated_at_once

    for start in range(0, len(x_positions_m), evaluated_at_once):
        chunk_x_m = x_positions_m[start : start + evaluated_at_once]
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
    # Axes throughout are (position along span, position across width, wheel).
    wheel_dx_m, wheel_dz_m, wheel_loads_kn = split_offsets(np.asarray(wheel_offsets, float))

    vehicle_front_m = np.asarray(x_positions_m, float).reshape(-1, 1, 1)
    vehicle_centreline_m = np.asarray(z_positions_m, float).reshape(1, -1, 1)

    wheel_x_m = vehicle_front_m + wheel_dx_m.reshape(1, 1, -1)
    wheel_z_m = vehicle_centreline_m + wheel_dz_m.reshape(1, 1, -1)

    influence_under_each_wheel = surface.influence_at(wheel_x_m, wheel_z_m)
    return (influence_under_each_wheel * wheel_loads_kn).sum(axis=-1)


def bending_positions_across_width(
    surface: InfluenceSurface,
    vehicle: Vehicle,
    wearing_course_thickness_m: float,
    sampling: SamplingSettings,
    z_from_m: float,
    z_to_m: float,
) -> np.ndarray:
    wheel_offsets = wheel_load_offsets(vehicle, wearing_course_thickness_m, sampling)
    wheel_dz_m = np.asarray(wheel_offsets, float)[:, OFFSET_DZ_M]
    stations_m = surface.width_mesh_m

    puts_a_wheel_on_a_station_m = (stations_m[None, :] - wheel_dz_m[:, None]).ravel()
    both_ends_m = np.array([z_from_m, z_to_m], float)

    bends_m = np.unique(np.concatenate([puts_a_wheel_on_a_station_m, both_ends_m]))
    return keep_between(bends_m, z_from_m, z_to_m)


def keep_between(positions_m: np.ndarray, from_m: float, to_m: float) -> np.ndarray:
    is_in_range = (positions_m >= from_m - TOLERANCE_M) & (positions_m <= to_m + TOLERANCE_M)
    return positions_m[is_in_range]
