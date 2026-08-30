from __future__ import annotations

from .code_tables import (
    LANE_REDUCTION_BY_LANE_COUNT,
    LANE_REDUCTION_FOR_FOUR_OR_MORE_LANES,
)


def lane_reduction_factor(loaded_lanes: int) -> float:
    return LANE_REDUCTION_BY_LANE_COUNT.get(
        int(loaded_lanes), LANE_REDUCTION_FOR_FOUR_OR_MORE_LANES
    )
