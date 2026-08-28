"""Where along the span the vehicles in one lane do the most damage.

One lane may carry more than one vehicle at a time, nose to tail. On a long
span, or over the pier of a continuous deck, a train of vehicles is worse than
any single one - so searching only for the worst single vehicle understates the
load, sometimes badly.

Finding the worst train is not a matter of putting each vehicle at its own worst
spot, because they get in each other's way: the code sets a minimum gap between
them, so the best place for one vehicle may be denied to it by the one in front.

The search is a dynamic program. Reading the positions left to right, the best
train of k vehicles ending at a position is that position's own response plus
the best train of k-1 vehicles ending anywhere far enough behind it. Each
position is visited once per train length, so the cost grows with the number of
positions rather than exploding with the number of vehicles.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..adverse_direction import adverse_sign, is_worse
from .best_prefix import best_so_far


@dataclass(frozen=True)
class TrainPlacement:
    """Where a train of vehicles sits, and what it does."""

    response: float
    positions_m: tuple[float, ...]
    """Where each vehicle's front sits, front vehicle first."""

    @property
    def vehicles_in_train(self) -> int:
        return len(self.positions_m)


def place_train(
    response_to_one_vehicle: np.ndarray,
    positions_m: np.ndarray,
    pitch_m: float,
    vehicles_in_train: int,
    adverse: str = "minimum",
) -> TrainPlacement | None:
    """Returns the worst legal placement of exactly this many vehicles in one lane.

    `response_to_one_vehicle[i]` is the response when a single vehicle's front
    sits at `positions_m[i]`. `pitch_m` is the smallest front-to-front spacing
    the code allows between consecutive vehicles.

    Returns None when that many vehicles cannot be spaced legally on the span.
    """
    response_to_one_vehicle = np.asarray(response_to_one_vehicle, float)
    positions_m = np.asarray(positions_m, float)
    worse_is_positive = adverse_sign(adverse)

    # For each position, the last position a vehicle in front could occupy while
    # still leaving the required gap. Resolved on the real coordinates rather
    # than on grid indices, because the positions are not evenly spaced - doing
    # it by index once produced a 1.20 m gap as 1.18 m, an illegal train.
    furthest_vehicle_in_front = (
        np.searchsorted(positions_m, positions_m - pitch_m, side="right") - 1
    )
    has_room_in_front = furthest_vehicle_in_front >= 0

    best_total = worse_is_positive * response_to_one_vehicle
    where_the_vehicle_in_front_sat: list[np.ndarray | None] = [None]

    for _ in range(1, vehicles_in_train):
        best_behind, came_from = best_so_far(best_total)

        best_with_one_more = np.full(len(positions_m), -np.inf)
        best_with_one_more[has_room_in_front] = (
            worse_is_positive * response_to_one_vehicle[has_room_in_front]
            + best_behind[furthest_vehicle_in_front[has_room_in_front]]
        )

        previous = np.full(len(positions_m), -1, int)
        previous[has_room_in_front] = came_from[furthest_vehicle_in_front[has_room_in_front]]

        best_total = best_with_one_more
        where_the_vehicle_in_front_sat.append(previous)

    if not np.isfinite(best_total).any():
        return None

    chosen = _walk_back_through_the_train(best_total, where_the_vehicle_in_front_sat)
    if chosen is None:
        return None

    return TrainPlacement(
        response=float(sum(response_to_one_vehicle[i] for i in chosen)),
        positions_m=tuple(float(positions_m[i]) for i in chosen),
    )


def find_worst_train(
    response_to_one_vehicle: np.ndarray,
    positions_m: np.ndarray,
    pitch_m: float,
    most_vehicles: int,
    adverse: str = "minimum",
) -> TrainPlacement | None:
    """Returns the worst train of any legal length, from one vehicle up to `most_vehicles`.

    Every length has to be tried, not just the longest. A shorter train can be
    worse, because a vehicle added at the far end of a span may sit where the
    influence surface has the opposite sign and relieve the response instead of
    adding to it. This is Table 6A note (b) read along the span rather than
    across the width.
    """
    worst: TrainPlacement | None = None

    for vehicles_in_train in range(1, int(most_vehicles) + 1):
        placement = place_train(
            response_to_one_vehicle, positions_m, pitch_m, vehicles_in_train, adverse
        )
        if placement is None:
            break

        if worst is None or is_worse(
            placement.response, worst.response, adverse
        ):
            worst = placement

    return worst


def _walk_back_through_the_train(
    best_total: np.ndarray, where_the_vehicle_in_front_sat: list[np.ndarray | None]
) -> list[int] | None:
    """Recovers which position each vehicle ended up at, working from the back."""
    at = int(np.argmax(best_total))
    chosen = [at]

    for vehicles_behind in range(len(where_the_vehicle_in_front_sat) - 1, 0, -1):
        came_from = where_the_vehicle_in_front_sat[vehicles_behind]
        assert came_from is not None
        at = int(came_from[at])
        if at < 0:
            return None
        chosen.append(at)

    chosen.reverse()
    return chosen
