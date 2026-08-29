# The neutral, solver-agnostic description of a meshed deck that influence_surfaces
# consumes - bridge_model builds one, and neither knows about the other. Meshed as a grid:
# length_mesh_m holds stations along the span, width_mesh_m across the width, and
# deck_nodes[(i, j)] is the solver's node tag where station i crosses station j. x runs
# along the span, y is vertical positive upwards, z runs across the deck from its left edge.

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .errors import InfluenceSurfaceError


@dataclass(frozen=True)
class GirderSection:
    # The properties of one girder, as the element stiffness needs them.
    area_m2: float
    torsion_constant_m4: float

    # Iyy - bending about the girder's weak axis.
    weak_axis_inertia_m4: float

    # Izz - bending about the girder's strong axis, the one that carries the span.
    strong_axis_inertia_m4: float

    elastic_modulus_kpa: float
    shear_modulus_kpa: float


@dataclass(frozen=True, eq=False)
class DeckModel:
    # A meshed deck that has been built in a solver and is ready to be loaded.

    # Mesh stations along the span, increasing.
    length_mesh_m: np.ndarray

    # Mesh stations across the deck width, increasing.
    width_mesh_m: np.ndarray

    # Solver node tag at each (station along span, station across width).
    deck_nodes: dict[tuple[int, int], int]

    girder_section: GirderSection

    # The vector fixing the girder element's local axes in the solver.
    girder_local_axis: tuple[float, float, float] = (0.0, 0.0, 1.0)

    # Deck skew as a shear: a support line runs along x = skew * z. Zero for a square deck;
    # a skewed deck is a parallelogram, and this is what lets the influence surface map
    # global coordinates back onto its own grid.
    skew: float = 0.0

    # Solver element tag at each (girder, station along span), when there are girders.
    # frozen=True protects the fields themselves, not what they point to - this dict is
    # still mutated in place by bridge_model/build_model.py after the model is built, via
    # .update(). Frozen in name only; do not rely on it being immutable.
    girder_elements: dict[tuple[int, int], int] = field(default_factory=dict)

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
