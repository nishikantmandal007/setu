import numpy as np
from setu.helpers import import_opensees
from setu.builder.mesh import tributary_length_m
from setu.loads.load_builders import as_a_load_case, share_between_nodes
from setu.loads.load_cases import LoadCase
from setu.utils.constants import CRASH_BARRIER_PREFIX, KERB_PREFIX, MEDIAN_PREFIX, RAILING_PREFIX


NOTHING_ON_TOP_KPA = 0.0


# six nodal load terms for a downward force
def downward_force(load_kn):
    force_x, force_y, force_z = (0.0, -load_kn, 0.0)
    moment_x, moment_y, moment_z = (0.0, 0.0, 0.0)
    return (force_x, force_y, force_z, moment_x, moment_y, moment_z)

# half of each brace member's weight at each end
def bracing_weight_at_its_ends(ops, model):
    unit_weight_kn_m3 = model.bridge.steel.unit_weight_kn_m3
    area_m2 = model.bridge.bracing.area_m2
    ends = []
    for element in model.brace_elements.values():
        start, end = ops.eleNodes(element)
        start_m = np.array(ops.nodeCoord(start))
        end_m = np.array(ops.nodeCoord(end))
        length_m = float(np.linalg.norm(end_m - start_m))
        half_of_it_kn = area_m2 * unit_weight_kn_m3 * length_m / 2
        ends += [(start, half_of_it_kn), (end, half_of_it_kn)]
    return ends

# construction stage 1 on the bare steel: girder and bracing self weight
def steel_self_weight_load(model, ops=None):
    ops = import_opensees() if ops is None else ops
    nodal_loads = [(node, *downward_force(load_kn)) for node, load_kn in bracing_weight_at_its_ends(ops, model)]
    return LoadCase(name='steel self weight', nodal_loads=nodal_loads, element_loads=girder_weight_on_the_elements(model))

# construction stage 2 on the bare steel: the wet slab, each girder carrying its share of the deck width
def wet_slab_load(model):
    bridge = model.bridge
    wet_slab_kpa = bridge.concrete.unit_weight_kn_m3 * bridge.deck.thickness_m
    nodal_loads = []
    for k in range(bridge.girders.count):
        tributary_width_m = girder_tributary_width_m(model, k)
        for i in range(model.mesh.stations_along_span):
            load_kn = wet_slab_kpa * tributary_width_m * tributary_length_m(model.mesh.length_mesh_m, i)
            nodal_loads.append((model.girder_nodes[k, i], *downward_force(load_kn)))
    return LoadCase(name='wet slab', nodal_loads=nodal_loads)

# the deck width a girder carries in the steel stage
def girder_tributary_width_m(model, girder):
    lines_m = model.mesh.girder_lines_m
    left_edge_m = 0.0 if girder == 0 else (lines_m[girder - 1] + lines_m[girder]) / 2
    right_edge_m = model.bridge.width_m() if girder == len(lines_m) - 1 else (lines_m[girder] + lines_m[girder + 1]) / 2
    return right_edge_m - left_edge_m

# girder self weight as element loads
def girder_weight_on_the_elements(model):
    weight_kn_per_m = model.bridge.steel.unit_weight_kn_m3 * model.girder.area_m2
    down_the_local_y_axis = -weight_kn_per_m
    along_the_local_z_axis = 0.0
    return [(element, '-beamUniform', (down_the_local_y_axis, along_the_local_z_axis)) for element in model.girder_elements.values()]

# SIDL on the composite deck: footpath as an area load, kerb / median / crash barrier / railing as line loads along each strip's centre
def superimposed_dead_load(model):
    forces_kn = {}
    for z_m, kn_per_m in line_loads_across(model.bridge):
        line_along_the_span(model, z_m, kn_per_m, forces_kn)
    return LoadCase(name='superimposed', nodal_loads=footpath_loads(model) + as_a_load_case(model, forces_kn, 'line loads').nodal_loads)

# the footpath area load, on the footpath strips only
def footpath_loads(model):
    footpath_kpa = model.bridge.added_dead_loads.footpath_kpa
    footways = model.bridge.cross_section.footways()
    return deck_loads(model, lambda z_m: footpath_kpa if any(s.z_from_m <= z_m <= s.z_to_m for s in footways) else NOTHING_ON_TOP_KPA)

# (z of the strip centre, kN/m) for every loaded kerb, median, crash barrier and railing strip
def line_loads_across(bridge):
    added = bridge.added_dead_loads
    per_metre_kn = {KERB_PREFIX: added.kerb_kn_per_m, MEDIAN_PREFIX: added.median_kn_per_m,
                    CRASH_BARRIER_PREFIX: added.crash_barrier_kn_per_m, RAILING_PREFIX: added.railing_kn_per_m}
    return [((strip.z_from_m + strip.z_to_m) / 2, kn_per_m) for strip in bridge.cross_section.strips
            for prefix, kn_per_m in per_metre_kn.items() if strip.name.startswith(prefix) and kn_per_m]

# a line load along the span at z, shared onto the deck nodes station by station
def line_along_the_span(model, z_m, kn_per_m, forces_kn):
    mesh = model.mesh
    for i, along_m in enumerate(mesh.length_mesh_m):
        share_between_nodes(model, float(along_m) + model.bridge.skew * z_m, z_m, kn_per_m * tributary_length_m(mesh.length_mesh_m, i), forces_kn)

# the wearing course, kept apart for its own factor
def surfacing_load(model):
    return LoadCase(name='surfacing', nodal_loads=deck_loads(model, lambda z_m: wearing_course_pressure_at(model, z_m)))

# wearing course pressure at z, only on the carriageway
def wearing_course_pressure_at(model, z_m):
    for strip in model.bridge.cross_section.strips:
        if strip.z_from_m <= z_m <= strip.z_to_m and strip.carries_traffic():
            return model.bridge.wearing_course.pressure_kpa
    return NOTHING_ON_TOP_KPA

# a pressure that changes across the deck turned into deck nodal loads
def deck_loads(model, pressure_kpa_at):
    mesh = model.mesh
    strip_edges_m = sorted({edge_m for strip in model.bridge.cross_section.strips for edge_m in (strip.z_from_m, strip.z_to_m)})
    nodal_loads = []
    for j in range(mesh.stations_across_width):
        kn_per_m_along = load_across_the_share_of(mesh.width_mesh_m, j, strip_edges_m, pressure_kpa_at)
        if not kn_per_m_along:
            continue
        for i in range(mesh.stations_along_span):
            load_kn = kn_per_m_along * tributary_length_m(mesh.length_mesh_m, i)
            nodal_loads.append((model.deck_nodes[i, j], *downward_force(load_kn)))
    return nodal_loads

# load per metre along on one width station's share, cut at strip edges
def load_across_the_share_of(stations_m, station, strip_edges_m, pressure_kpa_at):
    share_from_m = stations_m[0] if station == 0 else (stations_m[station - 1] + stations_m[station]) / 2
    share_to_m = stations_m[-1] if station == len(stations_m) - 1 else (stations_m[station] + stations_m[station + 1]) / 2
    cuts_m = [share_from_m] + [edge_m for edge_m in strip_edges_m if share_from_m < edge_m < share_to_m] + [share_to_m]
    return sum(pressure_kpa_at((from_m + to_m) / 2) * (to_m - from_m) for from_m, to_m in zip(cuts_m, cuts_m[1:], strict=False))
