"""The finite element model of a deck, as setu needs to see it.

`bridge_model` builds one of these. `influence_surfaces` consumes one. Neither
knows about the other, which is what keeps the bridge builder and the search
independent - you can hand setu a deck built by something else entirely, as
long as it arrives in this shape.

The deck is meshed as a grid. `length_mesh_m` holds the stations along the span
and `width_mesh_m` the stations across the width, so `deck_nodes[(i, j)]` is the
solver's tag for the node where station i crosses station j.

Coordinates: x runs along the span, y is vertical and positive upwards, z runs
across the deck from its left edge.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .errors import InfluenceSurfaceError


@dataclass(frozen=True)
class GirderSection:
    """The properties of one girder, as the element stiffness needs them."""

    area_m2: float
    torsion_constant_m4: float
    weak_axis_inertia_m4: float
    """Iyy - bending about the girder's weak axis."""

    strong_axis_inertia_m4: float
    """Izz - bending about the girder's strong axis, the one that carries the span."""

    elastic_modulus_kpa: float
    shear_modulus_kpa: float


@dataclass(frozen=True, eq=False)
class DeckModel:
    """A meshed deck that has been built in a solver and is ready to be loaded."""

    length_mesh_m: np.ndarray
    """Mesh stations along the span, increasing."""

    width_mesh_m: np.ndarray
    """Mesh stations across the deck width, increasing."""

    deck_nodes: dict[tuple[int, int], int]
    """Solver node tag at each (station along span, station across width)."""

    girder_section: GirderSection

    girder_local_axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    """The vector fixing the girder element's local axes in the solver."""

    skew: float = 0.0
    """Deck skew as a shear: a support line runs along x = skew * z.

    Zero for a square deck. A skewed deck is a parallelogram, and this is what
    lets the influence surface map global coordinates back onto its own grid.
    """

    girder_elements: dict[tuple[int, int], int] = field(default_factory=dict)
    """Solver element tag at each (girder, station along span), when there are girders."""

    def __post_init__(self) -> None:
        if len(self.length_mesh_m) < 2 or len(self.width_mesh_m) < 2:
            raise InfluenceSurfaceError(
                "a deck mesh needs at least two stations in each direction, got "
                f"{len(self.length_mesh_m)} along the span and "
                f"{len(self.width_mesh_m)} across the width"
            )

    @property
    def stations_along_span(self) -> int:
        return len(self.length_mesh_m)

    @property
    def stations_across_width(self) -> int:
        return len(self.width_mesh_m)

    @property
    def span_m(self) -> float:
        return float(self.length_mesh_m[-1] - self.length_mesh_m[0])

    @property
    def width_m(self) -> float:
        return float(self.width_mesh_m[-1] - self.width_mesh_m[0])
