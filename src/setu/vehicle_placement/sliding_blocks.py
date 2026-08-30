from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ..adverse_direction import adverse_sign
from .running_best import best_so_far


def place_vehicles(
    block_curves: Sequence[np.ndarray], adverse: str = "maximum"
) -> tuple[float, list[int]]:
    # Blocks keep their clearances exactly when their sliding offsets never decrease
    # from left to right, which is what makes this a dynamic program.
    worse_is_positive = adverse_sign(adverse)

    signed_best_total = worse_is_positive * np.asarray(block_curves[0], float)
    offset_of_the_block_to_the_left: list[np.ndarray | None] = [None]

    for curve in block_curves[1:]:
        best_to_the_left, where_that_best_sat = best_so_far(signed_best_total)
        signed_best_total = worse_is_positive * np.asarray(curve, float) + best_to_the_left
        offset_of_the_block_to_the_left.append(where_that_best_sat)

    chosen_offsets = walk_back_through_the_blocks(
        signed_best_total, offset_of_the_block_to_the_left
    )

    worst_total = sum(
        float(np.asarray(curve)[offset])
        for curve, offset in zip(block_curves, chosen_offsets, strict=True)
    )
    return worst_total, chosen_offsets


def walk_back_through_the_blocks(
    signed_best_total: np.ndarray, offset_of_the_block_to_the_left: list[np.ndarray | None]
) -> list[int]:
    offset = int(np.argmax(signed_best_total))
    chosen_offsets = [offset]

    for where_the_block_to_the_left_sat in reversed(offset_of_the_block_to_the_left[1:]):
        if where_the_block_to_the_left_sat is None:
            raise RuntimeError(
                "backtracking reached a block with no recorded offset to its left - "
                "only the leftmost block may have one"
            )
        offset = int(where_the_block_to_the_left_sat[offset])
        chosen_offsets.append(offset)

    chosen_offsets.reverse()
    return chosen_offsets
