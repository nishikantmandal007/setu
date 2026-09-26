import numpy as np
from setu.builder.mesh import DeckModel
from setu.models.sections import girder_properties
from setu.helpers import import_opensees, report, log
from setu.builder.mesh import build_mesh, station_at
from setu.utils.constants import SHORT_TERM


DECK_NODE_BASE = 1000
DECK_ELEMENT_BASE = 1000
DECK_SECTION = 1
GIRDER_TRANSFORM = 1
BRACE_MATERIAL = 10
DIMENSIONS = 3
DEGREES_OF_FREEDOM_PER_NODE = 6
GIRDER_LOCAL_AXIS = (0.0, 0.0, 1.0)

# how many deck nodes the mesh makes
def deck_node_count(mesh):
    return mesh.stations_along_span * mesh.stations_across_width

# how many girder nodes, all girders
def girder_node_count(bridge, mesh):
    return bridge.girders.count * mesh.stations_along_span

# how many brace nodes on one level
def brace_node_count(bridge):
    return bridge.girders.count * bridge.bracing.station_count

# girder node tags start after the deck nodes
def first_girder_node_tag(mesh):
    return DECK_NODE_BASE + deck_node_count(mesh)

# bottom brace node tags start after the girder nodes
def first_bottom_brace_node_tag(bridge, mesh):
    return first_girder_node_tag(mesh) + girder_node_count(bridge, mesh)

# top brace node tags start after the bottom ones
def first_top_brace_node_tag(bridge, mesh):
    return first_bottom_brace_node_tag(bridge, mesh) + brace_node_count(bridge)

# K brace meeting point tags start after the top brace nodes
def first_k_brace_node_tag(bridge, mesh):
    return first_top_brace_node_tag(bridge, mesh) + brace_node_count(bridge)

# how many deck shell panels
def deck_panel_count(mesh):
    return (mesh.stations_along_span - 1) * (mesh.stations_across_width - 1)

# girder element tags start after the deck shells
def first_girder_element_tag(mesh):
    return DECK_ELEMENT_BASE + deck_panel_count(mesh)

# brace element tags start after the girder beams
def first_brace_element_tag(bridge, mesh):
    beams_per_girder = mesh.stations_along_span - 1
    return first_girder_element_tag(mesh) + bridge.girders.count * beams_per_girder

# a deck node at every mesh station, shifted along for skew
def place_deck_nodes(ops, bridge, mesh):
    deck_level_m = 0.0
    nodes = {}
    for i, x_m in enumerate(mesh.length_mesh_m):
        for j, z_m in enumerate(mesh.width_mesh_m):
            tag = DECK_NODE_BASE + i * mesh.stations_across_width + j
            x_skewed = float(x_m) + float(z_m) * bridge.skew
            ops.node(tag, x_skewed, deck_level_m, float(z_m))
            nodes[i, j] = tag
    return nodes

# girder nodes at the girder centroid, below the slab
def place_girder_nodes(ops, bridge, mesh, girder):
    base = first_girder_node_tag(mesh)
    level_m = girder_centroid_level_m(bridge, girder)
    nodes = {}
    for k, z_m in enumerate(mesh.girder_lines_m):
        for i, x_m in enumerate(mesh.length_mesh_m):
            tag = base + k * mesh.stations_along_span + i
            x_skewed = float(x_m) + float(z_m) * bridge.skew
            ops.node(tag, x_skewed, level_m, float(z_m))
            nodes[k, i] = tag
    return nodes

# brace nodes at the bottom and top of each girder at every brace line
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
            x_skewed = float(x_m) + float(z_m) * bridge.skew
            ops.node(bottom_tag, x_skewed, bottom_m, float(z_m))
            bottom_nodes[k, n] = bottom_tag
            top_tag = top_base + k * stations + n
            ops.node(top_tag, x_skewed, top_m, float(z_m))
            top_nodes[k, n] = top_tag
    return (bottom_nodes, top_nodes)

# the meeting point of each K brace, midway between girders at the bottom
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
            x_skewed = float(x_m) + float(between_girders_m) * bridge.skew
            ops.node(tag, x_skewed, level_m, float(between_girders_m))
            nodes[k, n] = tag
    return nodes

# girder centroid level below the slab mid-plane (negative)
def girder_centroid_level_m(bridge, girder):
    top_of_girder_to_centroid_m = girder.depth_m - girder.neutral_axis_from_bottom_m
    return -(top_of_girder_to_centroid_m + bridge.deck.thickness_m / 2)

# slab shells with the short or long term concrete modulus
def build_deck_shells(ops, bridge, mesh, deck_nodes, load_duration):
    slab_modulus_kpa = bridge.concrete.modulus_for(load_duration, bridge.steel.elastic_modulus_kpa)
    ops.section('ElasticMembranePlateSection', DECK_SECTION, slab_modulus_kpa, bridge.concrete.poissons_ratio, bridge.deck.thickness_m)
    elements = {}
    tag = DECK_ELEMENT_BASE
    for i in range(mesh.stations_along_span - 1):
        for j in range(mesh.stations_across_width - 1):
            ops.element('ShellMITC4', tag, deck_nodes[i, j], deck_nodes[i + 1, j], deck_nodes[i + 1, j + 1], deck_nodes[i, j + 1], DECK_SECTION)
            elements[i, j] = tag
            tag += 1
    return elements

# girder beam elements between girder nodes
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

# truss brace members in every panel between girders
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

# the four brace nodes around one panel
def brace_panel_corners(model, k, n):
    return {'top_left': model.top_brace_nodes[k, n], 'top_right': model.top_brace_nodes[k + 1, n], 'bottom_left': model.bottom_brace_nodes[k, n], 'bottom_right': model.bottom_brace_nodes[k + 1, n]}

# the members of one panel for its X or K arrangement, with chords
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

# rigid links from each girder node up to the deck node above
def tie_deck_to_girders(ops, mesh, deck_nodes, girder_nodes):
    for k in range(len(mesh.girder_lines_m)):
        j = mesh.width_station_of_girder(k)
        for i in range(mesh.stations_along_span):
            ops.rigidLink('beam', girder_nodes[k, i], deck_nodes[i, j])

# rigid links from girder nodes to their brace nodes
def tie_braces_to_girders(ops, bridge, mesh, girder_nodes, bottom_brace_nodes, top_brace_nodes):
    for k in range(bridge.girders.count):
        for n, x_m in enumerate(mesh.brace_lines_m):
            i = station_at(mesh.length_mesh_m, x_m)
            ops.rigidLink('beam', girder_nodes[k, i], bottom_brace_nodes[k, n])
            ops.rigidLink('beam', girder_nodes[k, i], top_brace_nodes[k, n])

# pinned at one end, roller at the other; K brace points move with the deck
def support_the_girders(ops, bridge, mesh, girder_nodes, k_brace_nodes):
    near_end = 0
    far_end = mesh.stations_along_span - 1
    for k in range(bridge.girders.count):
        ops.fix(girder_nodes[k, near_end], *PINNED)
        ops.fix(girder_nodes[k, far_end], *ROLLER)
    for tag in k_brace_nodes.values():
        ops.fix(tag, *FREE_TO_MOVE_WITH_THE_DECK)


class BridgeModel:
    # the built OpenSees model: bridge, mesh, girder and every node and element tag
    def __init__(self, bridge, mesh, girder, deck_nodes, girder_nodes, bottom_brace_nodes, top_brace_nodes, k_brace_nodes):
        self.bridge = bridge
        self.mesh = mesh
        self.girder = girder
        self.deck_nodes = deck_nodes
        self.girder_nodes = girder_nodes
        self.bottom_brace_nodes = bottom_brace_nodes
        self.top_brace_nodes = top_brace_nodes
        self.k_brace_nodes = k_brace_nodes
        self.deck_elements = {}
        self.girder_elements = {}
        self.brace_elements = {}

    # the numbers the influence solver needs from this model
    def as_deck_model(self):
        return DeckModel(length_mesh_m=self.mesh.length_mesh_m, width_mesh_m=self.mesh.width_mesh_m, deck_nodes=self.deck_nodes, girder_section=self.girder.for_solver(self.bridge.steel), girder_local_axis=GIRDER_LOCAL_AXIS, girder_elements=self.girder_elements, composite_lever_arm_m=self.composite_lever_arm_m(), skew=self.bridge.skew)

    # slab mid-plane to girder centroid, for the composite moment
    def composite_lever_arm_m(self):
        return -girder_centroid_level_m(self.bridge, self.girder)

    # girder element tag at a station
    def element_of_girder_at(self, girder, station):
        return self.girder_elements[girder, station]

    # girder element at midspan
    def midspan_element_of_girder(self, girder):
        return self.element_of_girder_at(girder, self.mesh.stations_along_span // 2)

# build the whole grillage in OpenSees: steel alone or composite
def build_bridge_model(bridge, ops=None, load_duration=SHORT_TERM, composite=True):
    ops = import_opensees() if ops is None else ops
    mesh = build_mesh(bridge)
    girder = girder_properties(bridge.girders.section)
    report_layout(bridge, mesh)
    ops.wipe()
    ops.model('basic', '-ndm', DIMENSIONS, '-ndf', DEGREES_OF_FREEDOM_PER_NODE)
    deck_nodes = place_deck_nodes(ops, bridge, mesh) if composite else {}
    girder_nodes = place_girder_nodes(ops, bridge, mesh, girder)
    bottom_brace_nodes, top_brace_nodes = place_brace_nodes(ops, bridge, mesh, girder)
    k_brace_nodes = place_k_brace_nodes(ops, bridge, mesh, girder)
    model = BridgeModel(bridge=bridge, mesh=mesh, girder=girder, deck_nodes=deck_nodes, girder_nodes=girder_nodes, bottom_brace_nodes=bottom_brace_nodes, top_brace_nodes=top_brace_nodes, k_brace_nodes=k_brace_nodes)
    model.load_duration = load_duration
    model.composite = composite
    if composite:
        model.deck_elements.update(build_deck_shells(ops, bridge, mesh, deck_nodes, load_duration))
    model.girder_elements.update(build_girder_beams(ops, bridge, mesh, girder, girder_nodes))
    if composite:
        tie_deck_to_girders(ops, mesh, deck_nodes, girder_nodes)
    tie_braces_to_girders(ops, bridge, mesh, girder_nodes, bottom_brace_nodes, top_brace_nodes)
    model.brace_elements.update(build_bracing(ops, bridge, mesh, model))
    support_the_girders(ops, bridge, mesh, girder_nodes, k_brace_nodes)
    report_what_was_built(model)
    return model

# log the layout that was meshed
def report_layout(bridge, mesh):
    report('BRIDGE LAYOUT', {'Span': f'{bridge.span_m:.3f} m', 'Deck width': f'{bridge.width_m():.3f} m', 'Girders': f'{bridge.girders.count} at {mesh.girder_spacing_m:.3f} m centres', 'Bracing': f'{bridge.bracing.station_count} stations, {bridge.bracing.arrangement}', 'Stations along span': f'{mesh.stations_along_span}', 'Stations across width': f'{mesh.stations_across_width}', 'Mesh size along span': f'{np.min(np.diff(mesh.length_mesh_m)):.3f} to {np.max(np.diff(mesh.length_mesh_m)):.3f} m', 'Mesh size across width': f'{np.min(np.diff(mesh.width_mesh_m)):.3f} to {np.max(np.diff(mesh.width_mesh_m)):.3f} m'})

# log how many nodes and elements were made
def report_what_was_built(model):
    brace_nodes = len(model.bottom_brace_nodes) + len(model.top_brace_nodes) + len(model.k_brace_nodes)
    report('MODEL BUILT', {'Deck nodes': f'{len(model.deck_nodes)}', 'Girder nodes': f'{len(model.girder_nodes)}', 'Brace nodes': f'{brace_nodes}', 'Deck shell elements': f'{len(model.deck_elements)}', 'Girder elements': f'{len(model.girder_elements)}', 'Brace elements': f'{len(model.brace_elements)}'})
    log.info('')
