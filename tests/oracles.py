"""Slow, obviously-correct answers to check the fast ones against.

These enumerate every possibility. They are far too slow to use for real work,
which is the whole reason the dynamic programs exist - but that also makes them
the only honest way to know the dynamic programs are right.
"""

from __future__ import annotations

import itertools

import numpy as np


def worst_train_by_enumeration(
    response_to_one_vehicle: np.ndarray,
    positions_m: np.ndarray,
    pitch_m: float,
    vehicles_in_train: int,
    adverse: str,
) -> float | None:
    """Tries every legal set of positions for a train and returns the worst total."""
    worst = None

    for chosen in itertools.combinations(range(len(positions_m)), vehicles_in_train):
        gaps_are_legal = all(
            positions_m[behind] - positions_m[in_front] >= pitch_m - 1e-12
            for in_front, behind in zip(chosen, chosen[1:], strict=False)
        )
        if not gaps_are_legal:
            continue

        total = sum(response_to_one_vehicle[at] for at in chosen)
        if worst is None or _is_worse(total, worst, adverse):
            worst = total

    return worst


def worst_chain_by_enumeration(block_curves, adverse: str) -> float:
    """Tries every set of sliding offsets that never decreases, left to right."""
    blocks = len(block_curves)
    offsets = len(block_curves[0])
    worst = None

    for chosen in itertools.combinations_with_replacement(range(offsets), blocks):
        total = sum(float(block_curves[b][chosen[b]]) for b in range(blocks))
        if worst is None or _is_worse(total, worst, adverse):
            worst = total

    return worst


# Deliberately not imported from setu.adverse_direction - an oracle that imports
# the code it is checking is not an oracle.
def _is_worse(candidate: float, best: float, adverse: str) -> bool:
    return candidate > best if adverse == "maximum" else candidate < best
