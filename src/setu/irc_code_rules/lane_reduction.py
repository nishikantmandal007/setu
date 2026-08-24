"""Clause 205, Table 8 - the reduction for loading several lanes at once.

Loading every lane of a wide bridge to its full value at the same instant is
less likely the more lanes there are, so the code allows the total to be scaled
down once three or more lanes are loaded together.
"""

from __future__ import annotations

from .code_tables import (
    LANE_REDUCTION_BY_LANE_COUNT,
    LANE_REDUCTION_FOR_FOUR_OR_MORE_LANES,
)


def lane_reduction_factor(loaded_lanes: int) -> float:
    """Returns the Table 8 factor for this many lanes loaded together."""
    return LANE_REDUCTION_BY_LANE_COUNT.get(
        int(loaded_lanes), LANE_REDUCTION_FOR_FOUR_OR_MORE_LANES
    )
