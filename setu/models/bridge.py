from setu.models.deck import GirderSection
import math

X_BRACING = 'X'
X_BRACING_WITH_TOP_CHORD = 'XT'
X_BRACING_WITH_BOTTOM_CHORD = 'XB'
X_BRACING_WITH_BOTH_CHORDS = 'XTB'
K_BRACING = 'K'
K_BRACING_WITH_TOP_CHORD = 'KT'

class PlateGirderSection:
    def __init__(self, top_flange_width_m, top_flange_thickness_m, bottom_flange_width_m, bottom_flange_thickness_m, web_height_m, web_thickness_m, effective_deck_width_m=0.0, deck_thickness_m=0.0, **kwargs):
        self.top_flange_width_m = top_flange_width_m
        self.top_flange_thickness_m = top_flange_thickness_m
        self.bottom_flange_width_m = bottom_flange_width_m
        self.bottom_flange_thickness_m = bottom_flange_thickness_m
        self.web_height_m = web_height_m
        self.web_thickness_m = web_thickness_m
        self.effective_deck_width_m = effective_deck_width_m
        self.deck_thickness_m = deck_thickness_m

    @property
    def depth_m(self):
        return self.top_flange_thickness_m + self.web_height_m + self.bottom_flange_thickness_m

class Steel:
    def __init__(self, elastic_modulus_kpa=200000000.0, poissons_ratio=0.3, unit_weight_kn_m3=78.5, **kwargs):
        self.elastic_modulus_kpa = elastic_modulus_kpa
        self.poissons_ratio = poissons_ratio
        self.unit_weight_kn_m3 = unit_weight_kn_m3

    @property
    def shear_modulus_kpa(self):
        return self.elastic_modulus_kpa / (2 * (1 + self.poissons_ratio))

class Concrete:
    def __init__(self, characteristic_strength_mpa=35, poissons_ratio=0.2, unit_weight_kn_m3=25.0, **kwargs):
        self.characteristic_strength_mpa = characteristic_strength_mpa
        self.poissons_ratio = poissons_ratio
        self.unit_weight_kn_m3 = unit_weight_kn_m3

    @property
    def elastic_modulus_kpa(self):
        return 5000 * math.sqrt(self.characteristic_strength_mpa) * 1000

    @property
    def shear_modulus_kpa(self):
        return self.elastic_modulus_kpa / (2 * (1 + self.poissons_ratio))

class SurfacingLayer:
    def __init__(self, thickness_m, unit_weight_kn_m3, **kwargs):
        self.thickness_m = thickness_m
        self.unit_weight_kn_m3 = unit_weight_kn_m3

    @property
    def pressure_kpa(self):
        return self.unit_weight_kn_m3 * self.thickness_m

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


class ExtendedGirderSection(GirderSection):
    def __init__(self, area_m2, neutral_axis_from_bottom_m, strong_axis_inertia_m4, weak_axis_inertia_m4, torsion_constant_m4, depth_m, **kwargs):
        self.area_m2 = area_m2
        self.neutral_axis_from_bottom_m = neutral_axis_from_bottom_m
        self.strong_axis_inertia_m4 = strong_axis_inertia_m4
        self.weak_axis_inertia_m4 = weak_axis_inertia_m4
        self.torsion_constant_m4 = torsion_constant_m4
        self.depth_m = depth_m

    def for_solver(self, steel):
        return GirderSection(
            area_m2=self.area_m2, 
            torsion_constant_m4=self.torsion_constant_m4, 
            weak_axis_inertia_m4=self.weak_axis_inertia_m4, 
            strong_axis_inertia_m4=self.strong_axis_inertia_m4, 
            elastic_modulus_kpa=steel.elastic_modulus_kpa, 
            shear_modulus_kpa=steel.shear_modulus_kpa
        )

def inertia_about_its_own_centre_m4(width_m, depth_m):
    return width_m * depth_m ** 3 / 12

def girder_properties(section):
    top_flange_area_m2 = section.top_flange_width_m * section.top_flange_thickness_m
    bottom_flange_area_m2 = section.bottom_flange_width_m * section.bottom_flange_thickness_m
    web_area_m2 = section.web_thickness_m * section.web_height_m
    area_m2 = top_flange_area_m2 + bottom_flange_area_m2 + web_area_m2
    bottom_flange_centre_m = section.bottom_flange_thickness_m / 2
    web_centre_m = section.bottom_flange_thickness_m + section.web_height_m / 2
    top_flange_centre_m = section.bottom_flange_thickness_m + section.web_height_m + section.top_flange_thickness_m / 2
    neutral_axis_m = (bottom_flange_area_m2 * bottom_flange_centre_m + web_area_m2 * web_centre_m + top_flange_area_m2 * top_flange_centre_m) / area_m2
    strong_axis_inertia_m4 = inertia_about_its_own_centre_m4(section.bottom_flange_width_m, section.bottom_flange_thickness_m) + bottom_flange_area_m2 * (neutral_axis_m - bottom_flange_centre_m) ** 2 + inertia_about_its_own_centre_m4(section.web_thickness_m, section.web_height_m) + web_area_m2 * (neutral_axis_m - web_centre_m) ** 2 + inertia_about_its_own_centre_m4(section.top_flange_width_m, section.top_flange_thickness_m) + top_flange_area_m2 * (top_flange_centre_m - neutral_axis_m) ** 2
    weak_axis_inertia_m4 = inertia_about_its_own_centre_m4(section.top_flange_thickness_m, section.top_flange_width_m) + inertia_about_its_own_centre_m4(section.bottom_flange_thickness_m, section.bottom_flange_width_m) + inertia_about_its_own_centre_m4(section.web_height_m, section.web_thickness_m)
    torsion_constant_m4 = (section.top_flange_width_m * section.top_flange_thickness_m ** 3 + section.bottom_flange_width_m * section.bottom_flange_thickness_m ** 3 + section.web_height_m * section.web_thickness_m ** 3) / 3
    return ExtendedGirderSection(area_m2=area_m2, neutral_axis_from_bottom_m=neutral_axis_m, strong_axis_inertia_m4=strong_axis_inertia_m4, weak_axis_inertia_m4=weak_axis_inertia_m4, torsion_constant_m4=torsion_constant_m4, depth_m=section.depth_m)

