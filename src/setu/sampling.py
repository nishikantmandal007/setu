from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SamplingSettings:
    sliding_offsets_to_try: int = 41
    positions_inside_a_70r_zone_to_try: int = 41
    positions_across_the_deck_to_try: int = 241
    span_positions_evaluated_at_once: int = 192
    point_loads_along_a_track: int = 4
    point_loads_across_a_track: int = 2
    udl_cells_per_mesh_interval_along_span: int = 2
    udl_cells_per_mesh_interval_across_width: int = 4


DEFAULT_SAMPLING = SamplingSettings()
