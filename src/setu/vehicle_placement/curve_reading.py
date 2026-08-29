# How to evaluate a response curve once the transverse search has been handed one: read it
# at many positions at once when it accepts that, and work out which positions inside a
# floating vehicle's zone are worth trying at all.

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ..irc_code_rules.code_tables import ROUND_TO_DECIMALS, TOLERANCE_M
from ..sampling import SamplingSettings


def read_curve(
    curve: Callable[[np.ndarray], np.ndarray], positions_m: np.ndarray
) -> np.ndarray:
    # Reads a response curve at several positions at once.
    positions_m = np.asarray(positions_m, float)

    # A well-behaved curve accepts an array and returns one response per position. Some
    # hand-written curves in tests only accept a single scalar position and raise TypeError
    # or ValueError when handed an array instead, so exactly those two exceptions are
    # caught and treated as "this curve wants a scalar" - falling back to reading it one
    # position at a time. Anything else raised inside the curve is a genuine bug in the
    # curve, not this fallback case, so it is left to propagate with its own traceback
    # rather than being buried under 241 scalar calls that would only fail again with no
    # context.
    try:
        responses = np.asarray(curve(positions_m), float)
        if responses.shape == positions_m.shape:
            return responses
    except (TypeError, ValueError):
        pass

    return np.array([float(curve(position)) for position in positions_m])


def positions_inside_zone(
    from_m: float,
    to_m: float,
    curve_breakpoints_m: np.ndarray | None,
    sampling: SamplingSettings,
) -> np.ndarray:
    # Returns where a floating vehicle is worth trying inside its zone.
    positions = [
        np.array([from_m, to_m], float),
        np.linspace(from_m, to_m, sampling.float_steps),
    ]

    if curve_breakpoints_m is not None:
        breakpoints_m = np.asarray(curve_breakpoints_m, float)
        positions.append(
            breakpoints_m[
                (breakpoints_m >= from_m - TOLERANCE_M) & (breakpoints_m <= to_m + TOLERANCE_M)
            ]
        )

    return np.unique(np.round(np.concatenate(positions), ROUND_TO_DECIMALS))
