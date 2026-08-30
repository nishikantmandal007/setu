from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..deck_cross_section import DeckCrossSection

X_BRACING = "X"
X_BRACING_WITH_TOP_CHORD = "XT"
X_BRACING_WITH_BOTTOM_CHORD = "XB"
X_BRACING_WITH_BOTH_CHORDS = "XTB"
K_BRACING = "K"
K_BRACING_WITH_TOP_CHORD = "KT"


@dataclass(frozen=True)
class PlateGirderSection:
    top_flange_width_m: float
    top_flange_thickness_m: float
    bottom_flange_width_m: float
    bottom_flange_thickness_m: float
    web_thickness_m: float
    web_height_m: float

    @property
    def depth_m(self) -> float:
        return self.top_flange_thickness_m + self.web_height_m + self.bottom_flange_thickness_m


@dataclass(frozen=True)
class Steel:
    elastic_modulus_kpa: float = 2.0e8
    poissons_ratio: float = 0.30
    unit_weight_kn_m3: float = 78.5

    @property
    def shear_modulus_kpa(self) -> float:
        return self.elastic_modulus_kpa / (2 * (1 + self.poissons_ratio))


@dataclass(frozen=True)
class Concrete:
    characteristic_strength_mpa: float = 35
    poissons_ratio: float = 0.20
    unit_weight_kn_m3: float = 25

    @property
    def elastic_modulus_kpa(self) -> float:
        # IS 456 Cl. 6.2.3.1: E = 5000 root(fck), in N/mm2, converted to kN/m2.
        return 5000 * math.sqrt(self.characteristic_strength_mpa) * 1000

    @property
    def shear_modulus_kpa(self) -> float:
        return self.elastic_modulus_kpa / (2 * (1 + self.poissons_ratio))


@dataclass(frozen=True)
class SurfacingLayer:
    thickness_m: float
    unit_weight_kn_m3: float

    @property
    def pressure_kpa(self) -> float:
        return self.unit_weight_kn_m3 * self.thickness_m


@dataclass(frozen=True)
class DeckSlab:
    thickness_m: float
    overhang_m: float
    wearing_course_thickness_m: float


@dataclass(frozen=True)
class Girders:
    count: int
    section: PlateGirderSection


@dataclass(frozen=True)
class Bracing:
    station_count: int
    area_m2: float

    arrangement: str = X_BRACING_WITH_TOP_CHORD

    @property
    def is_k_braced(self) -> bool:
        return self.arrangement.upper().startswith(K_BRACING)

    @property
    def is_x_braced(self) -> bool:
        return self.arrangement.upper().startswith(X_BRACING)

    @property
    def has_top_chord(self) -> bool:
        return self.arrangement.upper() in (
            X_BRACING_WITH_TOP_CHORD,
            X_BRACING_WITH_BOTH_CHORDS,
            K_BRACING_WITH_TOP_CHORD,
        )

    @property
    def has_bottom_chord(self) -> bool:
        return self.arrangement.upper() in (
            X_BRACING_WITH_BOTTOM_CHORD,
            X_BRACING_WITH_BOTH_CHORDS,
        )


@dataclass(frozen=True)
class MeshSettings:
    panels_between_braces: int
    target_size_across_width_m: float


@dataclass(frozen=True)
class AddedDeadLoads:
    footpath: SurfacingLayer = SurfacingLayer(0.150, 24.0)
    kerb: SurfacingLayer = SurfacingLayer(0.300, 24.0)
    median: SurfacingLayer = SurfacingLayer(0.250, 24.0)
    crash_barrier: SurfacingLayer = SurfacingLayer(0.300, 24.0)


@dataclass(frozen=True)
class BridgeInput:
    span_m: float
    cross_section: DeckCrossSection
    deck: DeckSlab
    girders: Girders
    bracing: Bracing
    mesh: MeshSettings
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
