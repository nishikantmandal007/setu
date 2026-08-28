# Which direction of a response is the damaging one. Hogging over a pier is a
# "minimum" response, sagging at midspan is a "maximum" - every search in setu
# turns that one string into a sign, a comparison, an argmax/argmin choice, or a
# mask. Collected here so the choice is made once rather than copied into every
# search that needs it.

from __future__ import annotations

from typing import Literal

import numpy as np

# The vocabulary the rest of the library states this in. Taken as a plain str
# below, so a caller holding either type needs no cast.
AdverseDirection = Literal["maximum", "minimum"]


def adverse_sign(adverse: str) -> float:
    # +1 when a larger response is worse, -1 when a smaller one is. Every search
    # here maximises; flipping the sign is what lets the same code find the worst
    # hogging as well as the worst sagging.
    if adverse == "maximum":
        return 1.0
    if adverse == "minimum":
        return -1.0
    raise ValueError(f"adverse must be 'maximum' or 'minimum', got {adverse!r}")


def is_worse(candidate: float, best: float, adverse: str) -> bool:
    return candidate > best if adverse == "maximum" else candidate < best


def index_of_worst(
    values: np.ndarray, adverse: str, axis: int | None = None
) -> np.ndarray:
    # np.argmax or np.argmin, chosen once. Always an array, even for a single
    # index, so callers do not each have to narrow the type back down.
    if adverse == "maximum":
        return np.asarray(np.argmax(values, axis=axis))
    return np.asarray(np.argmin(values, axis=axis))


def is_worst_first(adverse: str) -> bool:
    # For sort(reverse=...) - the worst placement sorts first when a larger
    # response is the worse one.
    return adverse == "maximum"


def where_a_load_hurts(ordinates: np.ndarray, adverse: str) -> np.ndarray:
    # Boolean mask - a uniform load may stand anywhere, so it is placed only
    # where the influence ordinate has the damaging sign.
    return ordinates * adverse_sign(adverse) > 0.0
