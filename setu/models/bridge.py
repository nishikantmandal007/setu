from setu.models.materials import Steel, Concrete, SurfacingLayer
from setu.models.sections import GirderSection, PlateGirderSection, ExtendedGirderSection, girder_properties

X_BRACING = 'X'
X_BRACING_WITH_TOP_CHORD = 'XT'
X_BRACING_WITH_BOTTOM_CHORD = 'XB'
X_BRACING_WITH_BOTH_CHORDS = 'XTB'
K_BRACING = 'K'
K_BRACING_WITH_TOP_CHORD = 'KT'


class DeckSlab:
    def __init__(self, thickness_m, overhang_m=0.0, wearing_course_thickness_m=0.0, **kwargs):
        self.thickness_m = thickness_m
        self.overhang_m = overhang_m
        self.wearing_course_thickness_m = wearing_course_thickness_m


class Girders:
    def __init__(self, spacing_m=0.0, count=0, **kwargs):
        self.spacing_m = spacing_m
        self.count = count
        self.section = kwargs.get("section")


class Bracing:
    def __init__(self, arrangement=X_BRACING_WITH_TOP_CHORD, distance_from_bottom_m=0.0, station_count=0, **kwargs):
        self.arrangement = arrangement
        self.distance_from_bottom_m = distance_from_bottom_m
        self.station_count = station_count
        self.area_m2 = kwargs.get("area_m2", 0.0)

    @property
    def is_k_braced(self):
        return self.arrangement.upper().startswith(K_BRACING)

    @property
    def is_x_braced(self):
        return self.arrangement.upper().startswith(X_BRACING)

    @property
    def has_top_chord(self):
        return self.arrangement.upper() in (X_BRACING_WITH_TOP_CHORD, X_BRACING_WITH_BOTH_CHORDS, K_BRACING_WITH_TOP_CHORD)

    @property
    def has_bottom_chord(self):
        return self.arrangement.upper() in (X_BRACING_WITH_BOTTOM_CHORD, X_BRACING_WITH_BOTH_CHORDS)


class MeshSettings:
    def __init__(self, max_length_m=0.0, max_width_m=0.0, panels_between_braces=0, target_size_across_width_m=0.0, **kwargs):
        self.max_length_m = max_length_m
        self.max_width_m = max_width_m
        self.panels_between_braces = panels_between_braces
        self.target_size_across_width_m = target_size_across_width_m


class AddedDeadLoads:
    def __init__(self, **kwargs):
        self.footpath = SurfacingLayer(0.15, 24.0)
        self.kerb = SurfacingLayer(0.3, 24.0)
        self.median = SurfacingLayer(0.25, 24.0)
        self.crash_barrier = SurfacingLayer(0.3, 24.0)


class BridgeInput:
    def __init__(self, span_m=0.0, skew=0.0, cross_section=None, deck=None, girders=None, bracing=None, cross_girders=None, section=None, wearing_course_thickness_m=0.0, mesh=None, steel=None, concrete=None, wearing_course_unit_weight_kn_m3=22.0, added_dead_loads=None, **kwargs):
        self.span_m = span_m
        self.skew = skew
        self.cross_section = cross_section
        self.deck = deck
        self.girders = girders
        self.bracing = bracing
        self.bracings = bracing
        self.cross_girders = cross_girders
        self.section = section
        self.wearing_course_thickness_m = wearing_course_thickness_m
        self.mesh = mesh
        self.steel = steel or Steel()
        self.concrete = concrete or Concrete()
        self.wearing_course_unit_weight_kn_m3 = wearing_course_unit_weight_kn_m3
        self.added_dead_loads = added_dead_loads or AddedDeadLoads()

    def width_m(self):
        return self.cross_section.total_width_m()

    @property
    def wearing_course(self):
        return SurfacingLayer(self.wearing_course_thickness_m, self.wearing_course_unit_weight_kn_m3)
