from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .errors import InfluenceSurfaceError

STATIONS_NEEDED_IN_EACH_DIRECTION = 2
NO_SKEW = 0.0
GIRDER_LOCAL_AXIS_ALONG_Z = (0.0, 0.0, 1.0)


@dataclass(frozen=True)
class GirderSection:
    area_m2: float
    torsion_constant_m4: float
    weak_axis_inertia_m4: float
    strong_axis_inertia_m4: float
    elastic_modulus_kpa: float
    shear_modulus_kpa: float


@dataclass(frozen=True, eq=False)
class DeckModel:
    length_mesh_m: np.ndarray
    width_mesh_m: np.ndarray
    deck_nodes: dict[tuple[int, int], int]
    girder_section: GirderSection
    girder_local_axis: tuple[float, float, float] = GIRDER_LOCAL_AXIS_ALONG_Z

    # A support line runs along x = skew * z, so a skewed deck is a parallelogram.
    skew: float = NO_SKEW

    # Frozen in name only: build_model.py still fills this in place after the model is built.
    girder_elements: dict[tuple[int, int], int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        too_few_along_the_span = (
            len(self.length_mesh_m) < STATIONS_NEEDED_IN_EACH_DIRECTION
        )
        too_few_across_the_width = (
            len(self.width_mesh_m) < STATIONS_NEEDED_IN_EACH_DIRECTION
        )

        if too_few_along_the_span or too_few_across_the_width:
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
