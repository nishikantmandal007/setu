from __future__ import annotations

import numpy as np


def best_so_far(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(values, float)
    every_position = np.arange(len(values))

    best_value_so_far = np.maximum.accumulate(values)

    # A strict ">" gives ties to the earliest position, so repeat runs answer the same.
    beats_everything_before_it = np.empty(len(values), bool)
    beats_everything_before_it[0] = True
    beats_everything_before_it[1:] = values[1:] > best_value_so_far[:-1]

    position_when_it_is_a_new_best = np.where(beats_everything_before_it, every_position, -1)
    position_of_the_best_so_far = np.maximum.accumulate(position_when_it_is_a_new_best)

    return best_value_so_far, position_of_the_best_so_far
