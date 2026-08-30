from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..errors import InfluenceSurfaceError

OFF_THE_DECK = 0.0


@dataclass(eq=False)
class InfluenceSurface:
    # The response to a unit downward load at every point of the deck, indexed
    # [station along span, station across width].
    values: np.ndarray
    length_mesh_m: np.ndarray
    width_mesh_m: np.ndarray
    name: str = ""
    skew: float = 0.0
    describes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.values = np.asarray(self.values, float)
        self.length_mesh_m = np.asarray(self.length_mesh_m, float)
        self.width_mesh_m = np.asarray(self.width_mesh_m, float)

        expected_shape = (len(self.length_mesh_m), len(self.width_mesh_m))
        if self.values.shape != expected_shape:
            raise InfluenceSurfaceError(
                f"influence values have shape {self.values.shape}, but the deck mesh "
                f"is {expected_shape}"
            )

    def influence_at(
        self, x_m: float | np.ndarray, z_m: float | np.ndarray
    ) -> float | np.ndarray:
        x_m = np.asarray(x_m, float)
        z_m = np.asarray(z_m, float)
        asked_for_one_point = x_m.ndim == 0 and z_m.ndim == 0

        # Shearing x back by skew * z puts a point on a skewed deck where the grid expects.
        along, across = np.broadcast_arrays(x_m - self.skew * z_m, z_m)

        is_on_the_deck = (
            (along >= self.length_mesh_m[0])
            & (along <= self.length_mesh_m[-1])
            & (across >= self.width_mesh_m[0])
            & (across <= self.width_mesh_m[-1])
        )

        interpolated = self.bilinear(along, across)
        response = np.where(is_on_the_deck, interpolated, OFF_THE_DECK)
        return float(response) if asked_for_one_point else response

    def bilinear(self, along: np.ndarray, across: np.ndarray) -> np.ndarray:
        # Exact, not approximate: the deck elements are bilinear, so the surface really is
        # flat-faceted between its mesh stations.
        i = cell_containing(self.length_mesh_m, along)
        j = cell_containing(self.width_mesh_m, across)

        fraction_along = (along - self.length_mesh_m[i]) / (
            self.length_mesh_m[i + 1] - self.length_mesh_m[i]
        )
        fraction_across = (across - self.width_mesh_m[j]) / (
            self.width_mesh_m[j + 1] - self.width_mesh_m[j]
        )

        return (
            (1 - fraction_along) * (1 - fraction_across) * self.values[i, j]
            + fraction_along * (1 - fraction_across) * self.values[i + 1, j]
            + fraction_along * fraction_across * self.values[i + 1, j + 1]
            + (1 - fraction_along) * fraction_across * self.values[i, j + 1]
        )

    def save(self, path: str) -> None:
        # describes is carried as JSON because np.load is called with allow_pickle=False.
        np.savez(
            path,
            values=self.values,
            length_mesh_m=self.length_mesh_m,
            width_mesh_m=self.width_mesh_m,
            skew=self.skew,
            name=str(self.name),
            describes=json.dumps(self.describes),
        )

    @classmethod
    def load(cls, path: str) -> InfluenceSurface:
        stored = np.load(path, allow_pickle=False)

        if "describes" in stored.files:
            describes = json.loads(str(stored["describes"]))
        else:
            describes = {}

        return cls(
            values=stored["values"],
            length_mesh_m=stored["length_mesh_m"],
            width_mesh_m=stored["width_mesh_m"],
            name=str(stored["name"]),
            skew=float(stored["skew"]),
            describes=describes,
        )


def cell_containing(stations_m: np.ndarray, positions_m: np.ndarray) -> np.ndarray:
    last_cell = len(stations_m) - 2
    return np.clip(np.searchsorted(stations_m, positions_m) - 1, 0, last_cell)
