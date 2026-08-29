# The influence surface: what one unit load anywhere on the deck does to one response. It
# is a grid of numbers over the deck mesh - read the value at a point and you have the
# response caused by a unit downward load at that point. Add up the values under a
# vehicle's wheels, each times its wheel load, and you have that vehicle's effect, without
# solving anything. That is the whole reason setu is fast: every vehicle position
# afterwards costs an interpolation instead of an analysis.
#
# The value at a point is written eta in the textbooks; here it is `influence_at`.

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, overload

import numpy as np

from ..errors import InfluenceSurfaceError


@dataclass(eq=False)
class InfluenceSurface:
    # The response to a unit downward load at every point of the deck.

    # Grid of influence ordinates, indexed [station along span, station across width].
    values: np.ndarray

    length_mesh_m: np.ndarray
    width_mesh_m: np.ndarray

    # What response this is the influence surface for, for reporting.
    name: str = ""

    skew: float = 0.0

    # How this surface was built - the response quantity, the element, the mode.
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

    @overload
    def influence_at(self, x_m: float, z_m: float) -> float: ...
    @overload
    def influence_at(self, x_m: np.ndarray, z_m: np.ndarray) -> np.ndarray: ...

    def influence_at(
        self, x_m: float | np.ndarray, z_m: float | np.ndarray
    ) -> float | np.ndarray:
        # Between mesh stations the surface is read by bilinear interpolation, which is
        # exact: the deck elements are themselves bilinear, so the surface really is
        # flat-faceted between its stations, not merely sampled.
        #
        # A point off the deck reads zero, so a vehicle part-way onto the bridge is
        # handled without any special case - its wheels that have not yet arrived simply
        # contribute nothing.
        x_m = np.asarray(x_m, float)
        z_m = np.asarray(z_m, float)
        asked_for_one_point = x_m.ndim == 0 and z_m.ndim == 0

        # On a skewed deck the mesh is a parallelogram in global coordinates. Shearing x
        # back by skew * z puts the point where the grid expects it.
        along, across = np.broadcast_arrays(x_m - self.skew * z_m, z_m)

        is_on_the_deck = (
            (along >= self.length_mesh_m[0])
            & (along <= self.length_mesh_m[-1])
            & (across >= self.width_mesh_m[0])
            & (across <= self.width_mesh_m[-1])
        )

        i = np.clip(
            np.searchsorted(self.length_mesh_m, along) - 1, 0, len(self.length_mesh_m) - 2
        )
        j = np.clip(
            np.searchsorted(self.width_mesh_m, across) - 1, 0, len(self.width_mesh_m) - 2
        )

        fraction_along = (along - self.length_mesh_m[i]) / (
            self.length_mesh_m[i + 1] - self.length_mesh_m[i]
        )
        fraction_across = (across - self.width_mesh_m[j]) / (
            self.width_mesh_m[j + 1] - self.width_mesh_m[j]
        )

        interpolated = (
            (1 - fraction_along) * (1 - fraction_across) * self.values[i, j]
            + fraction_along * (1 - fraction_across) * self.values[i + 1, j]
            + fraction_along * fraction_across * self.values[i + 1, j + 1]
            + (1 - fraction_along) * fraction_across * self.values[i, j + 1]
        )

        response = np.where(is_on_the_deck, interpolated, 0.0)
        return float(response) if asked_for_one_point else response

    def save(self, path: str) -> None:
        # Writes this surface to a .npz file, so it need not be solved again. describes is
        # a dict, and np.load is called with allow_pickle=False, so it is carried as a
        # JSON string rather than as a pickled object.
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
        # Reads back a surface written by save().
        stored = np.load(path, allow_pickle=False)
        describes = json.loads(str(stored["describes"])) if "describes" in stored.files else {}
        return cls(
            values=stored["values"],
            length_mesh_m=stored["length_mesh_m"],
            width_mesh_m=stored["width_mesh_m"],
            name=str(stored["name"]),
            skew=float(stored["skew"]),
            describes=describes,
        )
