import numpy as np
from src.models.deck import DeckModel
from src.models.bridge import girder_properties
from src.utils.helpers import report, log
KERB_PREFIX = "kerb"
MEDIAN_PREFIX = "median"
CRASH_BARRIER_PREFIX = "crash_barrier"

DECK_NODE_BASE = 1000
DECK_ELEMENT_BASE = 1000
DECK_SECTION = 1
GIRDER_TRANSFORM = 1
BRACE_MATERIAL = 10
DIMENSIONS = 3
DEGREES_OF_FREEDOM_PER_NODE = 6
GIRDER_LOCAL_AXIS = (0.0, 0.0, 1.0)

def deck_node_count(mesh):
    return mesh.stations_along_span * mesh.stations_across_width

def girder_node_count(bridge, mesh):
    return bridge.girders.count * mesh.stations_along_span

def brace_node_count(bridge):
    return bridge.girders.count * bridge.bracing.station_count

def first_girder_node_tag(mesh):
    return DECK_NODE_BASE + deck_node_count(mesh)

def first_bottom_brace_node_tag(bridge, mesh):
    return first_girder_node_tag(mesh) + girder_node_count(bridge, mesh)

def first_top_brace_node_tag(bridge, mesh):
    return first_bottom_brace_node_tag(bridge, mesh) + brace_node_count(bridge)

def first_k_brace_node_tag(bridge, mesh):
    return first_top_brace_node_tag(bridge, mesh) + brace_node_count(bridge)

def deck_panel_count(mesh):
    return (mesh.stations_along_span - 1) * (mesh.stations_across_width - 1)

def first_girder_element_tag(mesh):
    return DECK_ELEMENT_BASE + deck_panel_count(mesh)

def first_brace_element_tag(bridge, mesh):
    beams_per_girder = mesh.stations_along_span - 1
    return first_girder_element_tag(mesh) + bridge.girders.count * beams_per_girder

def place_deck_nodes(ops, mesh):
    deck_level_m = 0.0
    nodes = {}
    for i, x_m in enumerate(mesh.length_mesh_m):
        for j, z_m in enumerate(mesh.width_mesh_m):
            tag = DECK_NODE_BASE + i * mesh.stations_across_width + j
            ops.node(tag, float(x_m), deck_level_m, float(z_m))
            nodes[i, j] = tag
    return nodes

def place_girder_nodes(ops, bridge, mesh, girder):
    base = first_girder_node_tag(mesh)
    level_m = girder_centroid_level_m(bridge, girder)
    nodes = {}
    for k, z_m in enumerate(mesh.girder_lines_m):
        for i, x_m in enumerate(mesh.length_mesh_m):
            tag = base + k * mesh.stations_along_span + i
            ops.node(tag, float(x_m), level_m, float(z_m))
            nodes[k, i] = tag
    return nodes

def place_brace_nodes(ops, bridge, mesh, girder):
    stations = bridge.bracing.station_count
    bottom_base = first_bottom_brace_node_tag(bridge, mesh)
    top_base = first_top_brace_node_tag(bridge, mesh)
    centroid_m = girder_centroid_level_m(bridge, girder)
    bottom_m = centroid_m - girder.neutral_axis_from_bottom_m
    top_m = centroid_m + (girder.depth_m - girder.neutral_axis_from_bottom_m)
    bottom_nodes, top_nodes = ({}, {})
    for k, z_m in enumerate(mesh.girder_lines_m):
        for n, x_m in enumerate(mesh.brace_lines_m):
            bottom_tag = bottom_base + k * stations + n
            ops.node(bottom_tag, float(x_m), bottom_m, float(z_m))
            bottom_nodes[k, n] = bottom_tag
            top_tag = top_base + k * stations + n
            ops.node(top_tag, float(x_m), top_m, float(z_m))
            top_nodes[k, n] = top_tag
    return (bottom_nodes, top_nodes)

def place_k_brace_nodes(ops, bridge, mesh, girder):
    if not bridge.bracing.is_k_braced:
        return {}
    girders = bridge.girders.count
    base = first_k_brace_node_tag(bridge, mesh)
    level_m = girder_centroid_level_m(bridge, girder) - girder.neutral_axis_from_bottom_m
    nodes = {}
    for n, x_m in enumerate(mesh.brace_lines_m):
        for k in range(girders - 1):
            between_girders_m = 0.5 * (mesh.girder_lines_m[k] + mesh.girder_lines_m[k + 1])
            tag = base + n * (girders - 1) + k
            ops.node(tag, float(x_m), level_m, float(between_girders_m))
            nodes[k, n] = tag
    return nodes

def girder_centroid_level_m(bridge, girder):
    top_of_girder_to_centroid_m = girder.depth_m - girder.neutral_axis_from_bottom_m
    return -(top_of_girder_to_centroid_m + bridge.deck.thickness_m / 2)

import numpy as np

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

def build_deck_shells(ops, bridge, mesh, deck_nodes):
    ops.section('ElasticMembranePlateSection', DECK_SECTION, bridge.concrete.elastic_modulus_kpa, bridge.concrete.poissons_ratio, bridge.deck.thickness_m)
    elements = {}
    tag = DECK_ELEMENT_BASE
    for i in range(mesh.stations_along_span - 1):
        for j in range(mesh.stations_across_width - 1):
            ops.element('ShellMITC4', tag, deck_nodes[i, j], deck_nodes[i + 1, j], deck_nodes[i + 1, j + 1], deck_nodes[i, j + 1], DECK_SECTION)
            elements[i, j] = tag
            tag += 1
    return elements

def build_girder_beams(ops, bridge, mesh, girder, girder_nodes):
    ops.geomTransf('Linear', GIRDER_TRANSFORM, *GIRDER_LOCAL_AXIS)
    tag = first_girder_element_tag(mesh)
    elements = {}
    for k in range(bridge.girders.count):
        for i in range(mesh.stations_along_span - 1):
            ops.element('elasticBeamColumn', tag, girder_nodes[k, i], girder_nodes[k, i + 1], girder.area_m2, bridge.steel.elastic_modulus_kpa, bridge.steel.shear_modulus_kpa, girder.torsion_constant_m4, girder.weak_axis_inertia_m4, girder.strong_axis_inertia_m4, GIRDER_TRANSFORM)
            elements[k, i] = tag
            tag += 1
    return elements

def build_bracing(ops, bridge, mesh, model):
    ops.uniaxialMaterial('Elastic', BRACE_MATERIAL, bridge.steel.elastic_modulus_kpa)
    tag = first_brace_element_tag(bridge, mesh)
    elements = {}
    for n in range(bridge.bracing.station_count):
        for k in range(bridge.girders.count - 1):
            corners = brace_panel_corners(model, k, n)
            for role, (start, end) in brace_members(bridge, model, corners, k, n):
                ops.element('corotTruss', tag, start, end, bridge.bracing.area_m2, BRACE_MATERIAL)
                elements[k, n, role] = tag
                tag += 1
    return elements

def brace_panel_corners(model, k, n):
    return {'top_left': model.top_brace_nodes[k, n], 'top_right': model.top_brace_nodes[k + 1, n], 'bottom_left': model.bottom_brace_nodes[k, n], 'bottom_right': model.bottom_brace_nodes[k + 1, n]}

def brace_members(bridge, model, corners, k, n):
    members = []
    if bridge.bracing.is_x_braced:
        members.append(('diagonal_down', (corners['top_left'], corners['bottom_right'])))
        members.append(('diagonal_up', (corners['top_right'], corners['bottom_left'])))
    elif bridge.bracing.is_k_braced:
        meeting_point = model.k_brace_nodes[k, n]
        members.append(('k_top_left', (corners['top_left'], meeting_point)))
        members.append(('k_top_right', (corners['top_right'], meeting_point)))
        members.append(('k_bottom_left', (corners['bottom_left'], meeting_point)))
        members.append(('k_bottom_right', (meeting_point, corners['bottom_right'])))
    if bridge.bracing.has_top_chord:
        members.append(('top_chord', (corners['top_left'], corners['top_right'])))
    if bridge.bracing.has_bottom_chord:
        members.append(('bottom_chord', (corners['bottom_left'], corners['bottom_right'])))
    return members

PINNED = (1, 1, 1, 0, 0, 0)
ROLLER = (0, 1, 1, 0, 0, 0)
FREE_TO_MOVE_WITH_THE_DECK = (1, 0, 0, 1, 1, 1)

def tie_deck_to_girders(ops, mesh, deck_nodes, girder_nodes):
    for k in range(len(mesh.girder_lines_m)):
        j = mesh.width_station_of_girder(k)
        for i in range(mesh.stations_along_span):
            ops.rigidLink('beam', girder_nodes[k, i], deck_nodes[i, j])

def tie_braces_to_girders(ops, bridge, mesh, girder_nodes, bottom_brace_nodes, top_brace_nodes):
    for k in range(bridge.girders.count):
        for n, x_m in enumerate(mesh.brace_lines_m):
            i = station_at(mesh.length_mesh_m, x_m)
            ops.rigidLink('beam', girder_nodes[k, i], bottom_brace_nodes[k, n])
            ops.rigidLink('beam', girder_nodes[k, i], top_brace_nodes[k, n])

def support_the_girders(ops, bridge, mesh, girder_nodes, k_brace_nodes):
    near_end = 0
    far_end = mesh.stations_along_span - 1
    for k in range(bridge.girders.count):
        ops.fix(girder_nodes[k, near_end], *PINNED)
        ops.fix(girder_nodes[k, far_end], *ROLLER)
    for tag in k_brace_nodes.values():
        ops.fix(tag, *FREE_TO_MOVE_WITH_THE_DECK)

import numpy as np

DEGREES_OF_FREEDOM = 12
AXIAL_DOFS = (0, 6)
TORSION_DOFS = (3, 9)
STRONG_AXIS_SHEAR_DOFS = (1, 7)
STRONG_AXIS_ROTATION_DOFS = (5, 11)
WEAK_AXIS_SHEAR_DOFS = (2, 8)
WEAK_AXIS_ROTATION_DOFS = (4, 10)
BENDING_MOMENT_ABOUT_STRONG_AXIS = STRONG_AXIS_ROTATION_DOFS[0]
BENDING_MOMENT_ABOUT_WEAK_AXIS = WEAK_AXIS_ROTATION_DOFS[0]
GIRDER_LOCAL_AXIS_ALONG_Z = (0.0, 0.0, 1.0)

def beam_stiffness_matrix(length_m, section):
    length = float(length_m)
    modulus = section.elastic_modulus_kpa
    stiffness = np.zeros((DEGREES_OF_FREEDOM, DEGREES_OF_FREEDOM))
    axial_i, axial_j = AXIAL_DOFS
    axial = modulus * section.area_m2 / length
    stiffness[axial_i, axial_i] = stiffness[axial_j, axial_j] = axial
    stiffness[axial_i, axial_j] = stiffness[axial_j, axial_i] = -axial
    torsion_i, torsion_j = TORSION_DOFS
    torsion = section.shear_modulus_kpa * section.torsion_constant_m4 / length
    stiffness[torsion_i, torsion_i] = stiffness[torsion_j, torsion_j] = torsion
    stiffness[torsion_i, torsion_j] = stiffness[torsion_j, torsion_i] = -torsion
    add_bending_terms(stiffness, modulus, section.strong_axis_inertia_m4, length, shear_dofs=STRONG_AXIS_SHEAR_DOFS, rotation_dofs=STRONG_AXIS_ROTATION_DOFS, coupling_sign=+1)
    add_bending_terms(stiffness, modulus, section.weak_axis_inertia_m4, length, shear_dofs=WEAK_AXIS_SHEAR_DOFS, rotation_dofs=WEAK_AXIS_ROTATION_DOFS, coupling_sign=-1)
    return stiffness

def add_bending_terms(stiffness, modulus, inertia_m4, length, *, shear_dofs, rotation_dofs, coupling_sign):
    shear = 12 * modulus * inertia_m4 / length ** 3
    coupling = coupling_sign * 6 * modulus * inertia_m4 / length ** 2
    near_rotation = 4 * modulus * inertia_m4 / length
    far_rotation = 2 * modulus * inertia_m4 / length
    shear_i, shear_j = shear_dofs
    rotation_i, rotation_j = rotation_dofs
    stiffness[shear_i, shear_i] = stiffness[shear_j, shear_j] = shear
    stiffness[shear_i, shear_j] = stiffness[shear_j, shear_i] = -shear
    coupled_pairs = ((shear_i, rotation_i, +1), (shear_i, rotation_j, +1), (shear_j, rotation_i, -1), (shear_j, rotation_j, -1))
    for shear_dof, rotation_dof, sign in coupled_pairs:
        stiffness[shear_dof, rotation_dof] = sign * coupling
        stiffness[rotation_dof, shear_dof] = sign * coupling
    stiffness[rotation_i, rotation_i] = stiffness[rotation_j, rotation_j] = near_rotation
    stiffness[rotation_i, rotation_j] = stiffness[rotation_j, rotation_i] = far_rotation

def element_rotation_matrix(local_axis, along=(1.0, 0.0, 0.0)):
    x_axis = np.array(along, float)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(np.array(local_axis, float), x_axis)
    y_axis = y_axis / np.linalg.norm(y_axis)
    z_axis = np.cross(x_axis, y_axis)
    axes = np.vstack([x_axis, y_axis, z_axis])
    rotation = np.zeros((DEGREES_OF_FREEDOM, DEGREES_OF_FREEDOM))
    for corner in range(4):
        starts_at = 3 * corner
        rotation[starts_at:starts_at + 3, starts_at:starts_at + 3] = axes
    return rotation

def moment_dof_for(local_axis):
    if tuple(local_axis) == GIRDER_LOCAL_AXIS_ALONG_Z:
        return BENDING_MOMENT_ABOUT_STRONG_AXIS
    return BENDING_MOMENT_ABOUT_WEAK_AXIS

import numpy as np

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
    mesh = model.mesh
    bridge = model.bridge
    slab_kpa = bridge.concrete.unit_weight_kn_m3 * bridge.deck.thickness_m
    applied_kn = 0.0
    for i in range(mesh.stations_along_span):
        along_span_m = tributary_length_m(mesh.length_mesh_m, i)
        for j in range(mesh.stations_across_width):
            across_width_m = tributary_length_m(mesh.width_mesh_m, j)
            area_m2 = along_span_m * across_width_m
            z_m = float(mesh.width_mesh_m[j])
            load_kn = (slab_kpa + surfacing_pressure_at(model, z_m)) * area_m2
            ops.load(model.deck_nodes[i, j], *downward_force(load_kn))
            applied_kn += load_kn
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
    unit_weight_kn_m3 = model.bridge.steel.unit_weight_kn_m3
    area_m2 = model.bridge.bracing.area_m2
    applied_kn = 0.0
    for element in model.brace_elements.values():
        start, end = ops.eleNodes(element)
        start_m = np.array(ops.nodeCoord(start))
        end_m = np.array(ops.nodeCoord(end))
        length_m = float(np.linalg.norm(end_m - start_m))
        weight_kn = area_m2 * unit_weight_kn_m3 * length_m
        half_of_it_kn = weight_kn / 2
        ops.load(start, *downward_force(half_of_it_kn))
        ops.load(end, *downward_force(half_of_it_kn))
        applied_kn += weight_kn
    return applied_kn

def tributary_length_m(stations_m, station):
    first_station = 0
    last_station = len(stations_m) - 1
    if station == first_station:
        return float(stations_m[1] - stations_m[0]) / 2
    if station == last_station:
        return float(stations_m[-1] - stations_m[-2]) / 2
    return float(stations_m[station + 1] - stations_m[station - 1]) / 2

def report_dead_loads(model, totals):
    bridge = model.bridge
    added = bridge.added_dead_loads
    slab_kpa = bridge.concrete.unit_weight_kn_m3 * bridge.deck.thickness_m
    girder_kn_per_m = bridge.steel.unit_weight_kn_m3 * model.girder.area_m2
    report('DEAD LOADS APPLIED', {'Deck slab': f'{slab_kpa:8.3f} kN/m2', 'Wearing course': f'{bridge.wearing_course.pressure_kpa:8.3f} kN/m2', 'Footpath': f'{added.footpath.pressure_kpa:8.3f} kN/m2', 'Kerb': f'{added.kerb.pressure_kpa:8.3f} kN/m2', 'Median': f'{added.median.pressure_kpa:8.3f} kN/m2', 'Girder self weight': f'{girder_kn_per_m:8.3f} kN/m', 'Deck and surfacing': f'{totals.deck_and_surfacing_kn:8.1f} kN', 'Girders': f'{totals.girders_kn:8.1f} kN', 'Bracing': f'{totals.bracing_kn:8.1f} kN', 'Total dead load': f'{totals.total_kn:8.1f} kN'})

def load_opensees():
    from src.services.opensees import import_opensees as load
    return load()

import numpy as np


class BridgeModel:
    def __init__(self, bridge, mesh, girder, deck_nodes, supports=None, **kwargs):
        self.bridge = bridge
        self.mesh = mesh
        self.girder = girder
        self.deck_nodes = deck_nodes
        self.supports = supports
        for name, value in kwargs.items():
            setattr(self, name, value)
        self.k_brace_nodes = {}
        self.deck_elements = {}
        self.girder_elements = {}
        self.brace_elements = {}

    def as_deck_model(self):
        return DeckModel(length_mesh_m=self.mesh.length_mesh_m, width_mesh_m=self.mesh.width_mesh_m, deck_nodes=self.deck_nodes, girder_section=self.girder.for_solver(self.bridge.steel), girder_local_axis=GIRDER_LOCAL_AXIS, girder_elements=self.girder_elements)

    def midspan_element_of_girder(self, girder):
        return self.girder_elements[girder, self.mesh.stations_along_span // 2]

def build_bridge_model(bridge, ops=None):
    ops = load_opensees() if ops is None else ops
    mesh = build_mesh(bridge)
    girder = girder_properties(bridge.girders.section)
    report_layout(bridge, mesh)
    ops.wipe()
    ops.model('basic', '-ndm', DIMENSIONS, '-ndf', DEGREES_OF_FREEDOM_PER_NODE)
    deck_nodes = place_deck_nodes(ops, mesh)
    girder_nodes = place_girder_nodes(ops, bridge, mesh, girder)
    bottom_brace_nodes, top_brace_nodes = place_brace_nodes(ops, bridge, mesh, girder)
    k_brace_nodes = place_k_brace_nodes(ops, bridge, mesh, girder)
    model = BridgeModel(bridge=bridge, mesh=mesh, girder=girder, deck_nodes=deck_nodes, girder_nodes=girder_nodes, bottom_brace_nodes=bottom_brace_nodes, top_brace_nodes=top_brace_nodes, k_brace_nodes=k_brace_nodes)
    model.deck_elements.update(build_deck_shells(ops, bridge, mesh, deck_nodes))
    model.girder_elements.update(build_girder_beams(ops, bridge, mesh, girder, girder_nodes))
    tie_deck_to_girders(ops, mesh, deck_nodes, girder_nodes)
    tie_braces_to_girders(ops, bridge, mesh, girder_nodes, bottom_brace_nodes, top_brace_nodes)
    model.brace_elements.update(build_bracing(ops, bridge, mesh, model))
    support_the_girders(ops, bridge, mesh, girder_nodes, k_brace_nodes)
    report_what_was_built(model)
    return model

def report_layout(bridge, mesh):
    report('BRIDGE LAYOUT', {'Span': f'{bridge.span_m:.3f} m', 'Deck width': f'{bridge.width_m():.3f} m', 'Girders': f'{bridge.girders.count} at {mesh.girder_spacing_m:.3f} m centres', 'Bracing': f'{bridge.bracing.station_count} stations, {bridge.bracing.arrangement}', 'Stations along span': f'{mesh.stations_along_span}', 'Stations across width': f'{mesh.stations_across_width}', 'Mesh size along span': f'{np.min(np.diff(mesh.length_mesh_m)):.3f} to {np.max(np.diff(mesh.length_mesh_m)):.3f} m', 'Mesh size across width': f'{np.min(np.diff(mesh.width_mesh_m)):.3f} to {np.max(np.diff(mesh.width_mesh_m)):.3f} m'})

def report_what_was_built(model):
    brace_nodes = len(model.bottom_brace_nodes) + len(model.top_brace_nodes) + len(model.k_brace_nodes)
    report('MODEL BUILT', {'Deck nodes': f'{len(model.deck_nodes)}', 'Girder nodes': f'{len(model.girder_nodes)}', 'Brace nodes': f'{brace_nodes}', 'Deck shell elements': f'{len(model.deck_elements)}', 'Girder elements': f'{len(model.girder_elements)}', 'Brace elements': f'{len(model.brace_elements)}'})
    log.info('')

def load_opensees():
    from src.services.opensees import import_opensees as load
    return load()