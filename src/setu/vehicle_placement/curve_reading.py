from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ..irc_code_rules.code_tables import ROUND_TO_DECIMALS, TOLERANCE_M
from ..sampling import SamplingSettings


def read_curve(
    curve: Callable[[np.ndarray], np.ndarray], positions_m: np.ndarray
) -> np.ndarray:
    positions_m = np.asarray(positions_m, float)

    responses = read_every_position_at_once(curve, positions_m)
    if responses is None:
        return read_one_position_at_a_time(curve, positions_m)
    return responses


def read_every_position_at_once(
    curve: Callable[[np.ndarray], np.ndarray], positions_m: np.ndarray
) -> np.ndarray | None:
    try:
        responses = np.asarray(curve(positions_m), float)
    except (TypeError, ValueError):
        return None

    if responses.shape != positions_m.shape:
        return None
    return responses


def read_one_position_at_a_time(
    curve: Callable[[np.ndarray], np.ndarray], positions_m: np.ndarray
) -> np.ndarray:
    return np.array([float(curve(position)) for position in positions_m])


def positions_inside_zone(
    from_m: float,
    to_m: float,
    curve_breakpoints_m: np.ndarray | None,
    sampling: SamplingSettings,
) -> np.ndarray:
    both_ends = np.array([from_m, to_m], float)
    an_even_spread = np.linspace(from_m, to_m, sampling.positions_inside_a_70r_zone_to_try)
    worth_trying = [both_ends, an_even_spread]

    if curve_breakpoints_m is not None:
        breakpoints_m = np.asarray(curve_breakpoints_m, float)
        is_inside_the_zone = (breakpoints_m >= from_m - TOLERANCE_M) & (
            breakpoints_m <= to_m + TOLERANCE_M
        )
        worth_trying.append(breakpoints_m[is_inside_the_zone])

    return np.unique(np.round(np.concatenate(worth_trying), ROUND_TO_DECIMALS))
