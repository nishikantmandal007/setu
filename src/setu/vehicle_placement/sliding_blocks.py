# The trick that makes the transverse search searchable is to stop thinking in absolute
# positions. Push the whole arrangement as far left as the clearances allow, and then let
# each block slide right by some amount. Two blocks keep their clearance exactly when the
# left one does not slide further than the right one - so the whole tangle of clearance
# rules collapses into one rule: the sliding amounts never decrease from left to right.
#
# That turns the search into a dynamic program. Reading the blocks left to right, the best
# arrangement up to a block is that block's own contribution plus the best arrangement of
# everything to its left that has not slid past it. Each block is visited once instead of
# every combination of block positions being tried, so the cost grows with the number of
# blocks rather than exploding with it.
#
# See across_carriageway.py for why the answer built from this DP is exact rather than
# merely finely sampled.

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ..adverse_direction import adverse_sign
from .running_best import best_so_far


def place_vehicles(
    block_curves: Sequence[np.ndarray], adverse: str = "maximum"
) -> tuple[float, list[int]]:
    # Returns the worst total over sliding offsets that never decrease left to right.
    #
    # `block_curves[b][s]` is what block b contributes when it slides by offset s.
    # Returns the worst total and the offset each block ended up at.
    worse_is_positive = adverse_sign(adverse)

    best_total = worse_is_positive * np.asarray(block_curves[0], float)
    where_the_block_to_the_left_sat: list[np.ndarray | None] = [None]

    for curve in block_curves[1:]:
        best_to_the_left, came_from = best_so_far(best_total)
        best_total = worse_is_positive * np.asarray(curve, float) + best_to_the_left
        where_the_block_to_the_left_sat.append(came_from)

    chosen = walk_back_through_the_blocks(best_total, where_the_block_to_the_left_sat)
    worst = sum(
        float(np.asarray(curve)[offset])
        for curve, offset in zip(block_curves, chosen, strict=True)
    )
    return worst, chosen


def walk_back_through_the_blocks(
    best_total: np.ndarray, where_the_block_to_the_left_sat: list[np.ndarray | None]
) -> list[int]:
    # Recovers which offset each block ended up at, working from the right.
    #
    # np.argmax is used unconditionally here, with no adverse check. That is correct, not a
    # bug: place_vehicles has already multiplied every curve by adverse_sign, so best_total
    # is always being maximised at this point, even when the search itself is for a minimum
    # response.
    position = int(np.argmax(best_total))
    chosen = [position]

    for came_from in reversed(where_the_block_to_the_left_sat[1:]):
        if came_from is None:
            raise RuntimeError(
                "backtracking reached a step with no recorded predecessor - "
                "where_the_block_to_the_left_sat should hold None only at index 0"
            )
        position = int(came_from[position])
        chosen.append(position)

    chosen.reverse()
    return chosen
