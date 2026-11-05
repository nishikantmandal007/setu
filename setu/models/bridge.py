from numbers import Integral
from setu.models.materials import SurfacingLayer
from setu.utils.constants import CRASH_BARRIER_PREFIX, KERB_PREFIX, MEDIAN_PREFIX, RAILING_PREFIX

X_BRACING = 'X'
X_BRACING_WITH_TOP_CHORD = 'XT'
X_BRACING_WITH_BOTTOM_CHORD = 'XB'
X_BRACING_WITH_BOTH_CHORDS = 'XTB'
K_BRACING = 'K'
K_BRACING_WITH_TOP_CHORD = 'KT'


class DeckSlab:
    # the RC slab: its thickness, how far it hangs past the outer girder, and the wearing course on it
    def __init__(self, thickness_m, overhang_m, wearing_course_thickness_m):
        self.thickness_m = thickness_m
        self.overhang_m = overhang_m
        self.wearing_course_thickness_m = wearing_course_thickness_m


class Girders:
    # how many main girders and their plate girder section
    def __init__(self, count, section=None, *, sections=None):
        if not isinstance(count, Integral) or isinstance(count, bool) or count < 2:
            raise ValueError("need at least two girders, with an integer count")
        if section is not None and sections is None:
            each = (section,) * count
        elif sections is not None and section is None:
            each = tuple(sections)
            if len(each) != count or any(s is None for s in each):
                raise ValueError(f"need {count} girder sections, ordered left to right")
        else:
            raise ValueError("give either one shared section or sections for every girder")
        self.count = int(count)
        self.section = section
        self.sections = None if sections is None else each
        self.section_of_each_girder = each

    # the section of one girder, counted from the left
    def section_at(self, index):
        if not 0 <= index < self.count:
            raise IndexError(f"girder {index} is outside 0..{self.count - 1}")
        return self.section_of_each_girder[index]


class Bracing:
    # cross bracing: its arrangement, how many stations along the span, and the member area
    def __init__(self, arrangement, station_count, area_m2, steel_grade=None, end_diaphragm_steel_grade=None):
        self.arrangement = arrangement
        self.station_count = station_count
        self.area_m2 = area_m2
        self.steel_grade = steel_grade
        self.end_diaphragm_steel_grade = end_diaphragm_steel_grade

    # K, KT
    @property
    def is_k_braced(self):
        return self.arrangement.upper().startswith(K_BRACING)

    # X, XT, XB, XTB
    @property
    def is_x_braced(self):
        return self.arrangement.upper().startswith(X_BRACING)

    # XT, XTB, KT
    @property
    def has_top_chord(self):
        return self.arrangement.upper() in (X_BRACING_WITH_TOP_CHORD, X_BRACING_WITH_BOTH_CHORDS, K_BRACING_WITH_TOP_CHORD)

    # XB, XTB
    @property
    def has_bottom_chord(self):
        return self.arrangement.upper() in (X_BRACING_WITH_BOTTOM_CHORD, X_BRACING_WITH_BOTH_CHORDS)


class MeshSettings:
    # how fine the grillage is along the span and across the deck. Along the span either a fixed number of panels between two brace
    # stations, or element_length_m: each brace bay split into the fewest equal elements no longer than that, with elements no longer
    # than support_element_length_m within support_zone_m of each bearing (support shear converges with the first element's length).
    # Across the deck, elements of about target_size_across_width_m. These are numerical choices, not IRC values.
    def __init__(self, panels_between_braces, target_size_across_width_m, *, element_length_m=None, support_element_length_m=None, support_zone_m=None):
        if (panels_between_braces is None) == (element_length_m is None):
            raise ValueError("give either panels_between_braces or element_length_m")
        if (support_element_length_m is None) != (support_zone_m is None):
            raise ValueError("support_element_length_m and support_zone_m go together")
        self.panels_between_braces = panels_between_braces
        self.target_size_across_width_m = target_size_across_width_m
        self.element_length_m = element_length_m
        self.support_element_length_m = support_element_length_m
        self.support_zone_m = support_zone_m

    # a named mesh: element length along the span, element length within the zone at each bearing, element size across the deck.
    # Chosen from setu's convergence studies (docs/accuracy.md); numerical choices, not IRC values.
    @staticmethod
    def preset(name):
        if name not in MESH_PRESETS:
            raise ValueError(f"mesh preset must be one of {sorted(MESH_PRESETS)}, got {name!r}")
        along_m, support_m, zone_m, across_m = MESH_PRESETS[name]
        return MeshSettings(None, across_m, element_length_m=along_m, support_element_length_m=support_m, support_zone_m=zone_m)


# (element length along the span, at the bearings, length of the bearing zone, element size across the deck), metres
MESH_PRESETS = {
    "fast": (3.0, 0.2, 1.5, 0.25),
    "standard": (1.5, 0.1, 1.5, 0.15),
    "fine": (0.75, 0.05, 1.5, 0.10),
}


class AddedDeadLoads:
    # SIDL as OsdagBridge gives it: footpath as an area load (kN/m2), kerb / median / crash barrier / railing as line loads (kN/m) along each strip
    def __init__(self, footpath_kpa, kerb_kn_per_m, median_kn_per_m, crash_barrier_kn_per_m, railing_kn_per_m):
        self.footpath_kpa = footpath_kpa
        self.kerb_kn_per_m = kerb_kn_per_m
        self.median_kn_per_m = median_kn_per_m
        self.crash_barrier_kn_per_m = crash_barrier_kn_per_m
        self.railing_kn_per_m = railing_kn_per_m


class BridgeInput:
    # everything setu needs about the bridge, straight from OsdagBridge; skew is the tan of the skew angle
    def __init__(self, span_m, skew, cross_section, deck, girders, bracing, mesh, steel, concrete,
                 wearing_course_unit_weight_kn_m3, added_dead_loads):
        self.span_m = span_m
        self.skew = skew
        self.cross_section = cross_section
        self.deck = deck
        self.girders = girders
        self.bracing = bracing
        self.mesh = mesh
        self.steel = steel
        self.concrete = concrete
        self.wearing_course_unit_weight_kn_m3 = wearing_course_unit_weight_kn_m3
        self.added_dead_loads = added_dead_loads
        refuse_a_load_with_nowhere_to_go(cross_section, added_dead_loads)

    # full deck width, edge to edge
    def width_m(self):
        return self.cross_section.total_width_m()

    # wearing course thickness, read off the deck slab
    @property
    def wearing_course_thickness_m(self):
        return self.deck.wearing_course_thickness_m

    # the wearing course as a layer, for its weight
    @property
    def wearing_course(self):
        return SurfacingLayer(self.deck.wearing_course_thickness_m, self.wearing_course_unit_weight_kn_m3)


# a SIDL given for a strip the cross-section doesn't have would silently vanish, so refuse it
def refuse_a_load_with_nowhere_to_go(cross_section, added):
    given = {"footpath": added.footpath_kpa, KERB_PREFIX: added.kerb_kn_per_m, MEDIAN_PREFIX: added.median_kn_per_m,
             CRASH_BARRIER_PREFIX: added.crash_barrier_kn_per_m, RAILING_PREFIX: added.railing_kn_per_m}
    has = {prefix: any(strip.name.startswith(prefix) for strip in cross_section.strips) for prefix in given}
    has["footpath"] = bool(cross_section.footways())
    stranded = [prefix for prefix, load in given.items() if load and not has[prefix]]
    if stranded:
        raise ValueError(f"added dead load given for {stranded} but the cross-section has no such strip")
