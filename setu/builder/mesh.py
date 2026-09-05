import numpy as np

from setu.errors import InfluenceSurfaceError

COORDINATE_DECIMALS = 5
GIRDER_LANDS_ON_A_STATION_M = 0.0001


class DeckMesh:

    def __init__(self, length_mesh_m, width_mesh_m, girder_lines_m, brace_lines_m):
        self.length_mesh_m = np.asarray(length_mesh_m, float)
        self.width_mesh_m = np.asarray(width_mesh_m, float)
        self.girder_lines_m = np.asarray(girder_lines_m, float)
        self.brace_lines_m = np.asarray(brace_lines_m, float)

    @property
    def stations_along_span(self):
        return len(self.length_mesh_m)

    @property
    def stations_across_width(self):
        return len(self.width_mesh_m)

    @property
    def girder_spacing_m(self):
        return float(self.girder_lines_m[1] - self.girder_lines_m[0])

    def width_station_of_girder(self, girder):
        girder_line_m = self.girder_lines_m[girder]
        on_this_station = np.where(np.isclose(self.width_mesh_m, girder_line_m, atol=GIRDER_LANDS_ON_A_STATION_M))[0]
        if len(on_this_station) == 0:
            raise ValueError(f'girder {girder} at z = {girder_line_m:.4f} m does not land on a width mesh station, so the deck cannot be tied to it')
        return int(on_this_station[0])

def station_at(stations_m, position_m):
    found = np.where(np.isclose(stations_m, position_m))[0]
    if len(found) == 0:
        raise ValueError(f'no mesh station at {position_m:.5f} m')
    return int(found[0])

def build_mesh(bridge):
    girder_lines_m = rounded(np.linspace(bridge.deck.overhang_m, bridge.width_m() - bridge.deck.overhang_m, bridge.girders.count))
    brace_lines_m = rounded(np.linspace(0, bridge.span_m, bridge.bracing.station_count))
    return DeckMesh(length_mesh_m=stations_along_span(brace_lines_m, bridge.mesh.panels_between_braces), width_mesh_m=stations_across_width(bridge.cross_section, girder_lines_m, bridge.mesh.target_size_across_width_m), girder_lines_m=girder_lines_m, brace_lines_m=brace_lines_m)

def stations_along_span(brace_lines_m, panels_between_braces):
    stations_m = []
    for panel_start_m, panel_end_m in zip(brace_lines_m, brace_lines_m[1:], strict=False):
        within_panel_m = np.linspace(panel_start_m, panel_end_m, panels_between_braces + 1)
        stations_m.extend(within_panel_m[:-1])
    stations_m.append(float(brace_lines_m[-1]))
    return rounded(np.array(stations_m))

def lines_that_matter_across_width(cross_section, girder_lines_m):
    keep_these_m = [strip.z_from_m for strip in cross_section.strips]
    keep_these_m.append(cross_section.total_width_m())
    keep_these_m.extend((float(line) for line in girder_lines_m))
    return np.unique(rounded(np.array(keep_these_m)))

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

def rounded(values):
    return np.round(values, COORDINATE_DECIMALS)

def tributary_length_m(stations_m, station):
    first_station = 0
    last_station = len(stations_m) - 1
    if station == first_station:
        return float(stations_m[1] - stations_m[0]) / 2
    if station == last_station:
        return float(stations_m[-1] - stations_m[-2]) / 2
    return float(stations_m[station + 1] - stations_m[station - 1]) / 2


class DeckModel:
    def __init__(self, length_mesh_m, width_mesh_m, deck_nodes, girder_section,
                 girder_local_axis=(0.0, 0.0, 1.0), skew=0.0, **kwargs):
        self.length_mesh_m = length_mesh_m
        self.width_mesh_m = width_mesh_m
        self.deck_nodes = deck_nodes
        self.girder_section = girder_section
        self.girder_local_axis = girder_local_axis
        self.skew = skew
        self.girder_elements = kwargs.get("girder_elements", {})

        if len(length_mesh_m) < 2 or len(width_mesh_m) < 2:
            raise InfluenceSurfaceError(
                f"need at least 2 stations each way, got {len(length_mesh_m)} x {len(width_mesh_m)}"
            )

    @property
    def stations_along_span(self):
        return len(self.length_mesh_m)

    @property
    def stations_across_width(self):
        return len(self.width_mesh_m)

    @property
    def span_m(self):
        return float(self.length_mesh_m[-1] - self.length_mesh_m[0])

    @property
    def width_m(self):
        return float(self.width_mesh_m[-1] - self.width_mesh_m[0])

    def to_dict(self):
        return self.__dict__
