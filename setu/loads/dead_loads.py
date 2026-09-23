import numpy as np
from setu.helpers import report
from setu.builder.mesh import tributary_length_m
from setu.loads.load_cases import LoadCase

KERB_PREFIX = "kerb"
MEDIAN_PREFIX = "median"
CRASH_BARRIER_PREFIX = "crash_barrier"

DEAD_LOAD_PATTERN = 1
DEAD_LOAD_TIME_SERIES = 1
START_OF_THE_LOAD_STEP = 0.0
NOTHING_ON_TOP_KPA = 0.0


class DeadLoadTotals:

    def __init__(self, deck_and_surfacing_kn=0.0, girders_kn=0.0, bracing_kn=0.0):
        self.deck_and_surfacing_kn = deck_and_surfacing_kn
        self.girders_kn = girders_kn
        self.bracing_kn = bracing_kn

    @property
    def total_kn(self):
        return self.deck_and_surfacing_kn + self.girders_kn + self.bracing_kn

def downward_force(load_kn):
    force_x, force_y, force_z = (0.0, -load_kn, 0.0)
    moment_x, moment_y, moment_z = (0.0, 0.0, 0.0)
    return (force_x, force_y, force_z, moment_x, moment_y, moment_z)

def apply_dead_loads(model, ops=None, new_pattern=True):
    ops = load_opensees() if ops is None else ops
    if new_pattern:
        start_a_fresh_load_case(ops)
    deck_kn = apply_deck_and_surfacing(ops, model)
    girders_kn = apply_girder_weight(ops, model)
    bracing_kn = apply_bracing_weight(ops, model)
    totals = DeadLoadTotals(deck_and_surfacing_kn=deck_kn, girders_kn=girders_kn, bracing_kn=bracing_kn)
    report_dead_loads(model, totals)
    return totals

def start_a_fresh_load_case(ops):
    ops.remove('loadPattern', DEAD_LOAD_PATTERN)
    ops.remove('timeSeries', DEAD_LOAD_TIME_SERIES)
    ops.timeSeries('Linear', DEAD_LOAD_TIME_SERIES)
    ops.pattern('Plain', DEAD_LOAD_PATTERN, DEAD_LOAD_TIME_SERIES)
    ops.reset()
    ops.setTime(START_OF_THE_LOAD_STEP)

def apply_deck_and_surfacing(ops, model):
    slab_kpa = model.bridge.concrete.unit_weight_kn_m3 * model.bridge.deck.thickness_m
    applied_kn = 0.0
    for node, *force in deck_loads(model, lambda z_m: slab_kpa + surfacing_pressure_at(model, z_m)):
        ops.load(node, *force)
        applied_kn -= force[1]
    return applied_kn

def surfacing_pressure_at(model, z_m):
    bridge = model.bridge
    added = bridge.added_dead_loads
    for strip in bridge.cross_section.strips:
        if not strip.z_from_m <= z_m <= strip.z_to_m:
            continue
        if strip.carries_traffic():
            return bridge.wearing_course.pressure_kpa
        if strip.carries_pedestrians():
            return added.footpath.pressure_kpa
        if strip.name.startswith(KERB_PREFIX):
            return added.kerb.pressure_kpa
        if strip.name.startswith(MEDIAN_PREFIX):
            return added.median.pressure_kpa
        if strip.name.startswith(CRASH_BARRIER_PREFIX):
            return added.crash_barrier.pressure_kpa
        return NOTHING_ON_TOP_KPA
    return NOTHING_ON_TOP_KPA

def apply_girder_weight(ops, model):
    weight_kn_per_m = model.bridge.steel.unit_weight_kn_m3 * model.girder.area_m2
    down_the_local_y_axis = -weight_kn_per_m
    along_the_local_z_axis = 0.0
    for element in model.girder_elements.values():
        ops.eleLoad('-ele', element, '-type', '-beamUniform', down_the_local_y_axis, along_the_local_z_axis)
    return weight_kn_per_m * model.bridge.span_m * model.bridge.girders.count

def apply_bracing_weight(ops, model):
    applied_kn = 0.0
    for node, half_of_it_kn in bracing_weight_at_its_ends(ops, model):
        ops.load(node, *downward_force(half_of_it_kn))
        applied_kn += half_of_it_kn
    return applied_kn

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

def construction_stage_load(model, shuttering_kpa=None, ops=None):
    ops = load_opensees() if ops is None else ops
    bridge = model.bridge
    shuttering_kpa = bridge.shuttering_kpa if shuttering_kpa is None else shuttering_kpa
    wet_slab_kpa = bridge.concrete.unit_weight_kn_m3 * bridge.deck.thickness_m + shuttering_kpa
    nodal_loads = []
    for k in range(bridge.girders.count):
        tributary_width_m = girder_tributary_width_m(model, k)
        for i in range(model.mesh.stations_along_span):
            load_kn = wet_slab_kpa * tributary_width_m * tributary_length_m(model.mesh.length_mesh_m, i)
            nodal_loads.append((model.girder_nodes[k, i], *downward_force(load_kn)))
    nodal_loads += [(node, *downward_force(load_kn)) for node, load_kn in bracing_weight_at_its_ends(ops, model)]
    return LoadCase(name='construction', nodal_loads=nodal_loads, element_loads=girder_weight_on_the_elements(model))

def girder_tributary_width_m(model, girder):
    lines_m = model.mesh.girder_lines_m
    left_edge_m = 0.0 if girder == 0 else (lines_m[girder - 1] + lines_m[girder]) / 2
    right_edge_m = model.bridge.width_m() if girder == len(lines_m) - 1 else (lines_m[girder] + lines_m[girder + 1]) / 2
    return right_edge_m - left_edge_m

def girder_weight_on_the_elements(model):
    weight_kn_per_m = model.bridge.steel.unit_weight_kn_m3 * model.girder.area_m2
    down_the_local_y_axis = -weight_kn_per_m
    along_the_local_z_axis = 0.0
    return [(element, '-beamUniform', (down_the_local_y_axis, along_the_local_z_axis)) for element in model.girder_elements.values()]

def superimposed_dead_load(model):
    return LoadCase(name='superimposed', nodal_loads=deck_loads(model, lambda z_m: surfacing_pressure_at(model, z_m) - wearing_course_pressure_at(model, z_m)))

def surfacing_load(model):
    return LoadCase(name='surfacing', nodal_loads=deck_loads(model, lambda z_m: wearing_course_pressure_at(model, z_m)))

def wearing_course_pressure_at(model, z_m):
    for strip in model.bridge.cross_section.strips:
        if strip.z_from_m <= z_m <= strip.z_to_m and strip.carries_traffic():
            return model.bridge.wearing_course.pressure_kpa
    return NOTHING_ON_TOP_KPA

def whole_dead_load(model, ops=None):
    ops = load_opensees() if ops is None else ops
    slab_kpa = model.bridge.concrete.unit_weight_kn_m3 * model.bridge.deck.thickness_m
    nodal_loads = deck_loads(model, lambda z_m: slab_kpa + surfacing_pressure_at(model, z_m) - wearing_course_pressure_at(model, z_m))
    nodal_loads += [(node, *downward_force(load_kn)) for node, load_kn in bracing_weight_at_its_ends(ops, model)]
    return LoadCase(name='dead', nodal_loads=nodal_loads, element_loads=girder_weight_on_the_elements(model))

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

def load_across_the_share_of(stations_m, station, strip_edges_m, pressure_kpa_at):
    share_from_m = stations_m[0] if station == 0 else (stations_m[station - 1] + stations_m[station]) / 2
    share_to_m = stations_m[-1] if station == len(stations_m) - 1 else (stations_m[station] + stations_m[station + 1]) / 2
    cuts_m = [share_from_m] + [edge_m for edge_m in strip_edges_m if share_from_m < edge_m < share_to_m] + [share_to_m]
    return sum(pressure_kpa_at((from_m + to_m) / 2) * (to_m - from_m) for from_m, to_m in zip(cuts_m, cuts_m[1:], strict=False))

def report_dead_loads(model, totals):
    bridge = model.bridge
    added = bridge.added_dead_loads
    slab_kpa = bridge.concrete.unit_weight_kn_m3 * bridge.deck.thickness_m
    girder_kn_per_m = bridge.steel.unit_weight_kn_m3 * model.girder.area_m2
    report('DEAD LOADS APPLIED', {'Deck slab': f'{slab_kpa:8.3f} kN/m2', 'Wearing course': f'{bridge.wearing_course.pressure_kpa:8.3f} kN/m2', 'Footpath': f'{added.footpath.pressure_kpa:8.3f} kN/m2', 'Kerb': f'{added.kerb.pressure_kpa:8.3f} kN/m2', 'Median': f'{added.median.pressure_kpa:8.3f} kN/m2', 'Girder self weight': f'{girder_kn_per_m:8.3f} kN/m', 'Deck and surfacing': f'{totals.deck_and_surfacing_kn:8.1f} kN', 'Girders': f'{totals.girders_kn:8.1f} kN', 'Bracing': f'{totals.bracing_kn:8.1f} kN', 'Total dead load': f'{totals.total_kn:8.1f} kN'})

def load_opensees():
    from setu.solver.backend import import_opensees as load
    return load()
