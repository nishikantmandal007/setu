# The best value seen so far, and where it was seen. Both of setu's searches are dynamic
# programs, and both need the same thing at every step: for each position, the best total
# achievable at or before it. That running best is what turns a search over every
# combination into a search that touches each position once.

from __future__ import annotations

import numpy as np


def best_so_far(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # Returns the running maximum of `values`, and the index it came from.
    #
    # Ties go to the earliest position. That is deliberate: it makes a repeated run of the
    # same search return the same placement, which matters when the answer is going into a
    # design document.
    values = np.asarray(values, float)
    running_best = np.maximum.accumulate(values)

    is_a_new_best = np.empty(len(values), bool)
    is_a_new_best[0] = True
    is_a_new_best[1:] = values[1:] > running_best[:-1]

    where_the_best_came_from = np.maximum.accumulate(
        np.where(is_a_new_best, np.arange(len(values)), -1)
    )
    return running_best, where_the_best_came_from
