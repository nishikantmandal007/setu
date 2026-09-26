from setu.models.materials import SurfacingLayer

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
    def __init__(self, count, section):
        self.count = count
        self.section = section


class Bracing:
    # cross bracing: its arrangement, how many stations along the span, and the member area
    def __init__(self, arrangement, station_count, area_m2):
        self.arrangement = arrangement
        self.station_count = station_count
        self.area_m2 = area_m2

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
    # how fine the grillage is: panels between two brace stations, and the element size across the deck
    def __init__(self, panels_between_braces, target_size_across_width_m):
        self.panels_between_braces = panels_between_braces
        self.target_size_across_width_m = target_size_across_width_m


class AddedDeadLoads:
    # the layers that sit on the footpath, kerb, median and crash barrier strips
    def __init__(self, footpath, kerb, median, crash_barrier):
        self.footpath = footpath
        self.kerb = kerb
        self.median = median
        self.crash_barrier = crash_barrier


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
