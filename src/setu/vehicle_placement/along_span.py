from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..adverse_direction import adverse_sign, is_worse
from .running_best import best_so_far

NOWHERE = -1


@dataclass(frozen=True)
class TrainPlacement:
    response: float
    positions_m: tuple[float, ...]

    @property
    def vehicles_in_train(self) -> int:
        return len(self.positions_m)


def last_position_a_vehicle_in_front_could_take(
    positions_m: np.ndarray, pitch_m: float
) -> np.ndarray:
    # Resolved on real coordinates, not grid indices: the positions are unevenly spaced,
    # and doing it by index once turned a legal 1.20 m gap into an illegal 1.18 m.
    return np.searchsorted(positions_m, positions_m - pitch_m, side="right") - 1


def place_train(
    response_to_one_vehicle: np.ndarray,
    positions_m: np.ndarray,
    pitch_m: float,
    vehicles_in_train: int,
    adverse: str = "minimum",
) -> TrainPlacement | None:
    response_to_one_vehicle = np.asarray(response_to_one_vehicle, float)
    positions_m = np.asarray(positions_m, float)
    worse_is_positive = adverse_sign(adverse)

    vehicle_in_front = last_position_a_vehicle_in_front_could_take(positions_m, pitch_m)
    has_room_in_front = vehicle_in_front >= 0
    room_in_front = vehicle_in_front[has_room_in_front]

    signed_best_total = worse_is_positive * response_to_one_vehicle
    position_of_the_vehicle_in_front: list[np.ndarray | None] = [None]

    for _ in range(1, vehicles_in_train):
        best_behind, where_that_best_sat = best_so_far(signed_best_total)

        best_with_one_more = np.full(len(positions_m), -np.inf)
        best_with_one_more[has_room_in_front] = (
            worse_is_positive * response_to_one_vehicle[has_room_in_front]
            + best_behind[room_in_front]
        )

        came_from = np.full(len(positions_m), NOWHERE, int)
        came_from[has_room_in_front] = where_that_best_sat[room_in_front]

        signed_best_total = best_with_one_more
        position_of_the_vehicle_in_front.append(came_from)

    if not np.isfinite(signed_best_total).any():
        return None

    chosen = walk_back_through_the_train(signed_best_total, position_of_the_vehicle_in_front)
    if chosen is None:
        return None

    return TrainPlacement(
        response=float(sum(response_to_one_vehicle[position] for position in chosen)),
        positions_m=tuple(float(positions_m[position]) for position in chosen),
    )


def find_worst_train(
    response_to_one_vehicle: np.ndarray,
    positions_m: np.ndarray,
    pitch_m: float,
    most_vehicles: int,
    adverse: str = "minimum",
) -> TrainPlacement | None:
    # Every train length is tried, because a vehicle added at the far end can land where
    # the influence surface changes sign and relieve the response instead of adding to it.
    worst: TrainPlacement | None = None

    for how_many in range(1, int(most_vehicles) + 1):
        placement = place_train(
            response_to_one_vehicle, positions_m, pitch_m, how_many, adverse
        )
        if placement is None:
            break

        if worst is None or is_worse(placement.response, worst.response, adverse):
            worst = placement

    return worst


def walk_back_through_the_train(
    signed_best_total: np.ndarray, position_of_the_vehicle_in_front: list[np.ndarray | None]
) -> list[int] | None:
    position = int(np.argmax(signed_best_total))
    chosen = [position]

    for where_the_vehicle_in_front_sat in reversed(position_of_the_vehicle_in_front[1:]):
        if where_the_vehicle_in_front_sat is None:
            raise RuntimeError(
                "backtracking reached a vehicle with no recorded position in front of it - "
                "only the leading vehicle may have one"
            )
        position = int(where_the_vehicle_in_front_sat[position])
        if position == NOWHERE:
            return None
        chosen.append(position)

    chosen.reverse()
    return chosen
