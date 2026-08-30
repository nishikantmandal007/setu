from __future__ import annotations

from typing import Literal

import numpy as np

AdverseDirection = Literal["maximum", "minimum"]

BIGGER_IS_WORSE = "maximum"
SMALLER_IS_WORSE = "minimum"


def adverse_sign(adverse: str) -> float:
    if adverse == BIGGER_IS_WORSE:
        return 1.0
    if adverse == SMALLER_IS_WORSE:
        return -1.0
    raise ValueError(f"adverse must be 'maximum' or 'minimum', got {adverse!r}")


def is_worse(candidate: float, best: float, adverse: str) -> bool:
    if adverse == BIGGER_IS_WORSE:
        return candidate > best
    return candidate < best


def index_of_worst(values: np.ndarray, adverse: str, axis: int | None = None) -> np.ndarray:
    if adverse == BIGGER_IS_WORSE:
        return np.asarray(np.argmax(values, axis=axis))
    return np.asarray(np.argmin(values, axis=axis))


def is_worst_first(adverse: str) -> bool:
    return adverse == BIGGER_IS_WORSE


def where_a_load_hurts(ordinates: np.ndarray | float, adverse: str) -> np.ndarray:
    return np.asarray(ordinates) * adverse_sign(adverse) > 0.0
