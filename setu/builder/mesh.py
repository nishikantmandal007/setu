import numpy as np

from setu.errors import InfluenceSurfaceError

COORDINATE_DECIMALS = 5
GIRDER_LANDS_ON_A_STATION_M = 0.0001


class DeckMesh:

    # mesh stations along and across, plus the girder and brace lines
    def __init__(self, length_mesh_m, width_mesh_m, girder_lines_m, brace_lines_m):
        self.length_mesh_m = np.asarray(length_mesh_m, float)
        self.width_mesh_m = np.asarray(width_mesh_m, float)
        self.girder_lines_m = np.asarray(girder_lines_m, float)
        self.brace_lines_m = np.asarray(brace_lines_m, float)

    # stations along the span
    @property
    def stations_along_span(self):
        return len(self.length_mesh_m)

    # stations across the deck
    @property
    def stations_across_width(self):
        return len(self.width_mesh_m)

    # centre to centre girder spacing
    @property
    def girder_spacing_m(self):
        return float(self.girder_lines_m[1] - self.girder_lines_m[0])

    # the width station a girder lands on
    def width_station_of_girder(self, girder):
        girder_line_m = self.girder_lines_m[girder]
        on_this_station = np.where(np.isclose(self.width_mesh_m, girder_line_m, atol=GIRDER_LANDS_ON_A_STATION_M))[0]
        if len(on_this_station) == 0:
            raise ValueError(f'girder {girder} at z = {girder_line_m:.4f} m does not land on a width mesh station, so the deck cannot be tied to it')
        return int(on_this_station[0])

# index of the station at this position, or an error
def station_at(stations_m, position_m):
    found = np.where(np.isclose(stations_m, position_m))[0]
    if len(found) == 0:
        raise ValueError(f'no mesh station at {position_m:.5f} m')
    return int(found[0])

# mesh the deck so girders, braces and strip edges all land on stations
def build_mesh(bridge):
    girder_lines_m = rounded(np.linspace(bridge.deck.overhang_m, bridge.width_m() - bridge.deck.overhang_m, bridge.girders.count))
    brace_lines_m = rounded(np.linspace(0, bridge.span_m, bridge.bracing.station_count))
    return DeckMesh(length_mesh_m=stations_along_span(brace_lines_m, bridge.mesh), width_mesh_m=stations_across_width(bridge.cross_section, girder_lines_m, bridge.mesh.target_size_across_width_m), girder_lines_m=girder_lines_m, brace_lines_m=brace_lines_m)

# split each brace panel into equal pieces
def stations_along_span(brace_lines_m, mesh):
    stations_m = []
    for panel_start_m, panel_end_m in zip(brace_lines_m, brace_lines_m[1:], strict=False):
        panels = mesh.panels_between_braces if mesh.element_length_m is None else int(np.ceil((panel_end_m - panel_start_m) / mesh.element_length_m - 1e-9))
        stations_m.extend(np.linspace(panel_start_m, panel_end_m, panels + 1)[:-1])
    stations_m.append(float(brace_lines_m[-1]))
    if mesh.support_zone_m is not None:
        stations_m.extend(refined_near_the_bearings(float(brace_lines_m[0]), float(brace_lines_m[-1]), stations_m, mesh))
    return np.unique(rounded(np.array(stations_m)))


# extra stations so no element within support_zone_m of a bearing is longer than support_element_length_m
def refined_near_the_bearings(start_m, end_m, stations_m, mesh):
    extra_m = []
    for bearing_m, inward in ((start_m, 1.0), (end_m, -1.0)):
        zone_edge_m = min(stations_m, key=lambda s: abs(s - (bearing_m + inward * mesh.support_zone_m)))
        reach_m = abs(zone_edge_m - bearing_m)
        pieces = int(np.ceil(reach_m / mesh.support_element_length_m - 1e-9))
        extra_m.extend(bearing_m + inward * np.linspace(0.0, reach_m, pieces + 1))
    return extra_m

# strip edges and girder lines the mesh must keep
def lines_that_matter_across_width(cross_section, girder_lines_m):
    keep_these_m = [strip.z_from_m for strip in cross_section.strips]
    keep_these_m.append(cross_section.total_width_m())
    keep_these_m.extend((float(line) for line in girder_lines_m))
    return np.unique(rounded(np.array(keep_these_m)))

# fill between the lines that matter at about the target size
def stations_across_width(cross_section, girder_lines_m, target_size_m):
    lines_m = lines_that_matter_across_width(cross_section, girder_lines_m)
    stations_m = []
    for panel_start_m, panel_end_m in zip(lines_m, lines_m[1:], strict=False):
        panel_width_m = panel_end_m - panel_start_m
        elements = max(1, int(np.ceil(panel_width_m / target_size_m)))
        within_panel_m = np.linspace(panel_start_m, panel_end_m, elements + 1)
        stations_m.extend(within_panel_m[:-1])
    stations_m.append(float(lines_m[-1]))
    return np.unique(rounded(np.array(stations_m)))

# round coordinates so equal ones compare equal
def rounded(values):
    return np.round(values, COORDINATE_DECIMALS)

# half the gap to each neighbour, half a gap at the ends
def tributary_length_m(stations_m, station):
    first_station = 0
    last_station = len(stations_m) - 1
    if station == first_station:
        return float(stations_m[1] - stations_m[0]) / 2
    if station == last_station:
        return float(stations_m[-1] - stations_m[-2]) / 2
    return float(stations_m[station + 1] - stations_m[station - 1]) / 2


class DeckModel:
    # what the influence solver needs: mesh, deck nodes, girder section and elements
    def __init__(self, length_mesh_m, width_mesh_m, deck_nodes, girder_section,
                 girder_local_axis=(0.0, 0.0, 1.0), skew=0.0, composite_lever_arm_m=0.0, girder_elements=None,
                 *, girder_sections=None, composite_lever_arms_m=None, brace_area_m2=None, slab_moments=None, slab_shears=None, girder_station_of_element=None):
        self.length_mesh_m = length_mesh_m
        self.width_mesh_m = width_mesh_m
        self.deck_nodes = deck_nodes
        self.girder_section = girder_section
        self.girder_local_axis = girder_local_axis
        self.skew = skew
        self.composite_lever_arm_m = composite_lever_arm_m
        self.girder_elements = girder_elements or {}
        self.girder_sections = girder_sections
        self.composite_lever_arms_m = composite_lever_arms_m
        self.brace_area_m2 = brace_area_m2
        self.slab_moments = slab_moments  # the slab's own bending shared to the girders, None without a composite deck
        self.slab_shears = slab_shears  # and its vertical shear
        self.girder_station_of_element = girder_station_of_element or {}

        if len(length_mesh_m) < 2 or len(width_mesh_m) < 2:
            raise InfluenceSurfaceError(
                f"need at least 2 stations each way, got {len(length_mesh_m)} x {len(width_mesh_m)}"
            )

    def section_for_element(self, element):
        return self.girder_section if self.girder_sections is None else self.girder_sections[element]

    def lever_arm_for_element(self, element):
        return self.composite_lever_arm_m if self.composite_lever_arms_m is None else self.composite_lever_arms_m[element]

    # stations along the span
    @property
    def stations_along_span(self):
        return len(self.length_mesh_m)

    # stations across the deck
    @property
    def stations_across_width(self):
        return len(self.width_mesh_m)

    # first to last station along
    @property
    def span_m(self):
        return float(self.length_mesh_m[-1] - self.length_mesh_m[0])

    # first to last station across
    @property
    def width_m(self):
        return float(self.width_mesh_m[-1] - self.width_mesh_m[0])

