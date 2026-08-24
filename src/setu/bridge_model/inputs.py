"""Everything that describes the bridge before anything is built.

The shape follows the way the input was always written: geometry, deck,
girders, bracing, mesh, materials, and the dead loads that sit on top of the
slab. Each of those is its own small piece here, so a change to the girder
section cannot accidentally be a change to the mesh.

Lengths are metres, forces kilonewtons, unit weights kN/m3, concrete strength
N/mm2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..deck_cross_section import DeckCrossSection


@dataclass(frozen=True)
class PlateGirderSection:
    """The plates a welded girder is made of."""

    top_flange_width_m: float
    top_flange_thickness_m: float
    bottom_flange_width_m: float
    bottom_flange_thickness_m: float
    web_thickness_m: float
    web_height_m: float

    @property
    def depth_m(self) -> float:
        """Overall depth, bottom of the bottom flange to top of the top flange."""
        return self.top_flange_thickness_m + self.web_height_m + self.bottom_flange_thickness_m


@dataclass(frozen=True)
class Steel:
    """Structural steel."""

    elastic_modulus_kpa: float = 2.0e8
    poissons_ratio: float = 0.30
    unit_weight_kn_m3: float = 78.5

    @property
    def shear_modulus_kpa(self) -> float:
        return self.elastic_modulus_kpa / (2 * (1 + self.poissons_ratio))


@dataclass(frozen=True)
class Concrete:
    """Deck concrete."""

    characteristic_strength_mpa: float = 35
    poissons_ratio: float = 0.20
    unit_weight_kn_m3: float = 25

    @property
    def elastic_modulus_kpa(self) -> float:
        """IS 456 Clause 6.2.3.1: E = 5000 root(fck), in N/mm2, converted to kN/m2."""
        return 5000 * math.sqrt(self.characteristic_strength_mpa) * 1000

    @property
    def shear_modulus_kpa(self) -> float:
        return self.elastic_modulus_kpa / (2 * (1 + self.poissons_ratio))


@dataclass(frozen=True)
class SurfacingLayer:
    """Something laid on the deck that adds weight but no stiffness."""

    thickness_m: float
    unit_weight_kn_m3: float

    @property
    def pressure_kpa(self) -> float:
        """The load it puts on the deck, per square metre."""
        return self.unit_weight_kn_m3 * self.thickness_m


@dataclass(frozen=True)
class DeckSlab:
    thickness_m: float
    overhang_m: float
    """From the outer girder out to the edge of the deck."""

    wearing_course_thickness_m: float


@dataclass(frozen=True)
class Girders:
    count: int
    section: PlateGirderSection


@dataclass(frozen=True)
class Bracing:
    """Cross bracing between the girders, at a number of stations along the span."""

    station_count: int
    area_m2: float
    arrangement: str = "XT"
    """One of:
        X    X diagonals only
        XT   X diagonals and a top chord
        XB   X diagonals and a bottom chord
        XTB  X diagonals with both chords
        K    K bracing and a bottom chord
        KT   K bracing with both chords
    """

    @property
    def is_k_braced(self) -> bool:
        return self.arrangement.upper().startswith("K")

    @property
    def is_x_braced(self) -> bool:
        return self.arrangement.upper().startswith("X")

    @property
    def has_top_chord(self) -> bool:
        return self.arrangement.upper() in ("XT", "XTB", "KT")

    @property
    def has_bottom_chord(self) -> bool:
        return self.arrangement.upper() in ("XB", "XTB")


@dataclass(frozen=True)
class Mesh:
    """How finely the deck is divided."""

    panels_between_braces: int
    """Elements along the span between one bracing station and the next."""

    target_size_across_width_m: float
    """Elements across the width are made no larger than this."""


@dataclass(frozen=True)
class AddedDeadLoads:
    """The things sitting on the slab that are not the slab."""

    footpath: SurfacingLayer = SurfacingLayer(0.150, 24.0)
    kerb: SurfacingLayer = SurfacingLayer(0.300, 24.0)
    median: SurfacingLayer = SurfacingLayer(0.250, 24.0)


@dataclass(frozen=True)
class BridgeInput:
    """A complete description of a plate girder bridge."""

    span_m: float
    cross_section: DeckCrossSection
    deck: DeckSlab
    girders: Girders
    bracing: Bracing
    mesh: Mesh
    steel: Steel = Steel()
    concrete: Concrete = Concrete()
    wearing_course_unit_weight_kn_m3: float = 22.0
    added_dead_loads: AddedDeadLoads = field(default_factory=AddedDeadLoads)

    @property
    def width_m(self) -> float:
        return self.cross_section.total_width_m

    @property
    def wearing_course(self) -> SurfacingLayer:
        return SurfacingLayer(
            self.deck.wearing_course_thickness_m, self.wearing_course_unit_weight_kn_m3
        )
