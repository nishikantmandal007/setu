import numpy as np
from setu.solver import backend
from setu.builder.mesh import DeckModel
from setu.models.sections import girder_properties
from setu.helpers import report, log
from setu.builder.mesh import build_mesh, station_at
from setu.utils.constants import SHORT_TERM


DECK_NODE_BASE = 1000
DECK_ELEMENT_BASE = 1000
DECK_SECTION = 1
GIRDER_TRANSFORM = 1
BRACE_MATERIAL = 10
BEARING_MATERIAL = 11
STEEL_TRANSLATION_MATERIAL = 12
BEARING_VERTICAL_STIFFNESS_KN_PER_M = 1.0e9
VERTICAL_DOF = 2
LONGITUDINAL_DOF = 1
ALL_FIXED = (1, 1, 1, 1, 1, 1)
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
def place_deck_nodes(bridge, mesh):
    deck_level_m = 0.0
    nodes = {}
    for i, x_m in enumerate(mesh.length_mesh_m):
        for j, z_m in enumerate(mesh.width_mesh_m):
            tag = DECK_NODE_BASE + i * mesh.stations_across_width + j
            x_skewed = float(x_m) + float(z_m) * bridge.skew
            backend.add_node(tag, x_skewed, deck_level_m, float(z_m))
            nodes[i, j] = tag
    return nodes

# girder nodes at the girder centroid, below the slab
def place_girder_nodes(bridge, mesh, girders):
    base = first_girder_node_tag(mesh)
    nodes = {}
    for k, z_m in enumerate(mesh.girder_lines_m):
        level_m = girder_centroid_level_m(bridge, girders[k])
        for i, x_m in enumerate(mesh.length_mesh_m):
            tag = base + k * mesh.stations_along_span + i
            x_skewed = float(x_m) + float(z_m) * bridge.skew
            backend.add_node(tag, x_skewed, level_m, float(z_m))
            nodes[k, i] = tag
    return nodes

# brace nodes at the bottom and top of each girder at every brace line
def place_brace_nodes(bridge, mesh, girders):
    stations = bridge.bracing.station_count
    bottom_base = first_bottom_brace_node_tag(bridge, mesh)
    top_base = first_top_brace_node_tag(bridge, mesh)
    bottom_nodes, top_nodes = ({}, {})
    for k, z_m in enumerate(mesh.girder_lines_m):
        girder = girders[k]
        centroid_m = girder_centroid_level_m(bridge, girder)
        bottom_m = centroid_m - girder.neutral_axis_from_bottom_m
        top_m = centroid_m + (girder.depth_m - girder.neutral_axis_from_bottom_m)
        for n, x_m in enumerate(mesh.brace_lines_m):
            bottom_tag = bottom_base + k * stations + n
            x_skewed = float(x_m) + float(z_m) * bridge.skew
            backend.add_node(bottom_tag, x_skewed, bottom_m, float(z_m))
            bottom_nodes[k, n] = bottom_tag
            top_tag = top_base + k * stations + n
            backend.add_node(top_tag, x_skewed, top_m, float(z_m))
            top_nodes[k, n] = top_tag
    return (bottom_nodes, top_nodes)

# the meeting point of each K brace, midway between girders at the bottom
def place_k_brace_nodes(bridge, mesh, girders):
    if not bridge.bracing.is_k_braced:
        return {}
    count = bridge.girders.count
    base = first_k_brace_node_tag(bridge, mesh)
    nodes = {}
    for n, x_m in enumerate(mesh.brace_lines_m):
        for k in range(count - 1):
            # The meeting point bisects the line between the two bottom flanges.
            level_m = -bridge.deck.thickness_m / 2 - (girders[k].depth_m + girders[k + 1].depth_m) / 2
            between_girders_m = 0.5 * (mesh.girder_lines_m[k] + mesh.girder_lines_m[k + 1])
            tag = base + n * (count - 1) + k
            x_skewed = float(x_m) + float(between_girders_m) * bridge.skew
            backend.add_node(tag, x_skewed, level_m, float(between_girders_m))
            nodes[k, n] = tag
    return nodes

# girder centroid level below the slab mid-plane (negative)
def girder_centroid_level_m(bridge, girder):
    top_of_girder_to_centroid_m = girder.depth_m - girder.neutral_axis_from_bottom_m
    return -(top_of_girder_to_centroid_m + bridge.deck.thickness_m / 2)

# slab shells with the short or long term concrete modulus
def build_deck_shells(bridge, mesh, deck_nodes, load_duration):
    slab_modulus_kpa = bridge.concrete.modulus_for(load_duration, bridge.steel.elastic_modulus_kpa)
    backend.shell_section(DECK_SECTION, slab_modulus_kpa, bridge.concrete.poissons_ratio, bridge.deck.thickness_m)
    elements = {}
    tag = DECK_ELEMENT_BASE
    for i in range(mesh.stations_along_span - 1):
        for j in range(mesh.stations_across_width - 1):
            backend.add_shell(tag, deck_nodes[i, j], deck_nodes[i + 1, j], deck_nodes[i + 1, j + 1], deck_nodes[i, j + 1], DECK_SECTION)
            elements[i, j] = tag
            tag += 1
    return elements

# girder beam elements between girder nodes
def build_girder_beams(bridge, mesh, girders, girder_nodes):
    backend.linear_transform(GIRDER_TRANSFORM, *GIRDER_LOCAL_AXIS)
    tag = first_girder_element_tag(mesh)
    elements = {}
    for k in range(bridge.girders.count):
        girder = girders[k]
        for i in range(mesh.stations_along_span - 1):
            backend.add_beam(tag, girder_nodes[k, i], girder_nodes[k, i + 1], girder.area_m2, bridge.steel.elastic_modulus_kpa, bridge.steel.shear_modulus_kpa, girder.torsion_constant_m4, girder.weak_axis_inertia_m4, girder.strong_axis_inertia_m4, GIRDER_TRANSFORM)
            elements[k, i] = tag
            tag += 1
    return elements

# truss brace members in every panel between girders
def build_bracing(bridge, mesh, model):
    backend.elastic_material(BRACE_MATERIAL, bridge.steel.elastic_modulus_kpa)
    tag = first_brace_element_tag(bridge, mesh)
    elements = {}
    for n in range(bridge.bracing.station_count):
        for k in range(bridge.girders.count - 1):
            corners = brace_panel_corners(model, k, n)
            for role, (start, end) in brace_members(bridge, model, corners, k, n):
                backend.add_truss(tag, start, end, bridge.bracing.area_m2, BRACE_MATERIAL)
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

NEAR_LONGITUDINAL_AND_TRANSVERSE_BEARING = (1, 0, 1, 0, 0, 0)
FAR_TRANSVERSE_BEARING = (0, 0, 1, 0, 0, 0)
UNUSED_TRUSS_ROTATIONS = (0, 0, 0, 1, 1, 1)

# rigid links from each girder node up to the deck node above
def tie_deck_to_girders(mesh, deck_nodes, girder_nodes):
    for k in range(len(mesh.girder_lines_m)):
        j = mesh.width_station_of_girder(k)
        for i in range(mesh.stations_along_span):
            backend.rigid_beam(girder_nodes[k, i], deck_nodes[i, j])

# rigid links from girder nodes to their brace nodes
def tie_braces_to_girders(bridge, mesh, girder_nodes, bottom_brace_nodes, top_brace_nodes):
    for k in range(bridge.girders.count):
        for n, x_m in enumerate(mesh.brace_lines_m):
            i = station_at(mesh.length_mesh_m, x_m)
            backend.rigid_beam(girder_nodes[k, i], bottom_brace_nodes[k, n])
            backend.rigid_beam(girder_nodes[k, i], top_brace_nodes[k, n])

# vertical springs everywhere, with only three horizontal rigid-body restraints
def support_the_girders(bridge, mesh, girder_nodes, first_free_node_tag, first_free_element_tag):
    backend.elastic_material(BEARING_MATERIAL, BEARING_VERTICAL_STIFFNESS_KN_PER_M)
    near_end = 0
    far_end = mesh.stations_along_span - 1
    fixed_girder = (bridge.girders.count - 1) // 2
    backend.fix_node(girder_nodes[fixed_girder, near_end], *NEAR_LONGITUDINAL_AND_TRANSVERSE_BEARING)
    backend.fix_node(girder_nodes[fixed_girder, far_end], *FAR_TRANSVERSE_BEARING)
    bearings = {}
    for k in range(bridge.girders.count):
        for end in (near_end, far_end):
            girder_node = girder_nodes[k, end]
            ground = first_free_node_tag + len(bearings)
            backend.add_node(ground, *backend.node_coordinates(girder_node))
            backend.fix_node(ground, *ALL_FIXED)
            backend.add_spring(first_free_element_tag + len(bearings), ground, girder_node, BEARING_MATERIAL, VERTICAL_DOF)
            bearings[k, end] = girder_node
    return bearings

# remove the truss joint's unused DOFs without grounding its longitudinal movement
def tie_k_braces_to_girders(mesh, girder_nodes, k_brace_nodes):
    for (k, n), tag in k_brace_nodes.items():
        i = station_at(mesh.length_mesh_m, mesh.brace_lines_m[n])
        backend.equal_dofs(girder_nodes[k, i], tag, LONGITUDINAL_DOF)
        backend.fix_node(tag, *UNUSED_TRUSS_ROTATIONS)

# internal links stabilize bare-steel axial modes without chained rigid-link constraints
def tie_steel_girder_translations(bridge, girders, girder_nodes):
    fixed_girder = (bridge.girders.count - 1) // 2
    axial_stiffness = bridge.steel.elastic_modulus_kpa * girders[fixed_girder].area_m2 / bridge.span_m
    backend.elastic_material(STEEL_TRANSLATION_MATERIAL, axial_stiffness)
    tag = max(backend.element_tags()) + 1
    for k in range(bridge.girders.count):
        if k != fixed_girder:
            backend.add_link(tag, girder_nodes[fixed_girder, 0], girder_nodes[k, 0],
                        STEEL_TRANSLATION_MATERIAL, LONGITUDINAL_DOF,
                        1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
            tag += 1


class BridgeModel:
    # the built OpenSees model: bridge, mesh, girder and every node and element tag
    def __init__(self, bridge, mesh, girders, deck_nodes, girder_nodes, bottom_brace_nodes, top_brace_nodes, k_brace_nodes, load_duration, composite):
        self.bridge = bridge
        self.load_duration = load_duration
        self.composite = composite
        self.mesh = mesh
        self.girders = girders
        self.girder = girders[0]  # representative section for existing uniform-model callers
        self.deck_nodes = deck_nodes
        self.girder_nodes = girder_nodes
        self.bottom_brace_nodes = bottom_brace_nodes
        self.top_brace_nodes = top_brace_nodes
        self.k_brace_nodes = k_brace_nodes
        self.deck_elements = {}
        self.girder_elements = {}
        self.brace_elements = {}
        self.bearings = {}

    # the numbers the influence solver needs from this model
    def as_deck_model(self):
        sections = [g.for_solver(self.bridge.steel) for g in self.girders]
        return DeckModel(length_mesh_m=self.mesh.length_mesh_m, width_mesh_m=self.mesh.width_mesh_m, deck_nodes=self.deck_nodes,
                         girder_section=sections[0], girder_local_axis=GIRDER_LOCAL_AXIS, girder_elements=self.girder_elements,
                         composite_lever_arm_m=self.composite_lever_arm_m(), skew=self.bridge.skew,
                         girder_sections={tag: sections[k] for (k, _), tag in self.girder_elements.items()},
                         composite_lever_arms_m={tag: self.composite_lever_arm_m(k) for (k, _), tag in self.girder_elements.items()},
                         brace_area_m2=self.bridge.bracing.area_m2)

    # slab mid-plane to girder centroid, for the composite moment
    def composite_lever_arm_m(self, girder=0):
        return -girder_centroid_level_m(self.bridge, self.girders[girder])

    # girder element tag at a station
    def element_of_girder_at(self, girder, station):
        return self.girder_elements[girder, station]

    # girder element at midspan
    def midspan_element_of_girder(self, girder):
        return self.element_of_girder_at(girder, self.mesh.stations_along_span // 2)

# build the whole grillage in OpenSees: steel alone or composite
def build_bridge_model(bridge, load_duration=SHORT_TERM, composite=True):
    mesh = build_mesh(bridge)
    girders = [girder_properties(bridge.girders.section_at(k)) for k in range(bridge.girders.count)]
    report_layout(bridge, mesh)
    backend.start_model()
    deck_nodes = place_deck_nodes(bridge, mesh) if composite else {}
    girder_nodes = place_girder_nodes(bridge, mesh, girders)
    bottom_brace_nodes, top_brace_nodes = place_brace_nodes(bridge, mesh, girders)
    k_brace_nodes = place_k_brace_nodes(bridge, mesh, girders)
    model = BridgeModel(bridge=bridge, mesh=mesh, girders=girders, deck_nodes=deck_nodes, girder_nodes=girder_nodes, bottom_brace_nodes=bottom_brace_nodes, top_brace_nodes=top_brace_nodes, k_brace_nodes=k_brace_nodes,
                        load_duration=load_duration, composite=composite)
    if composite:
        model.deck_elements.update(build_deck_shells(bridge, mesh, deck_nodes, load_duration))
    model.girder_elements.update(build_girder_beams(bridge, mesh, girders, girder_nodes))
    if composite:
        tie_deck_to_girders(mesh, deck_nodes, girder_nodes)
    tie_braces_to_girders(bridge, mesh, girder_nodes, bottom_brace_nodes, top_brace_nodes)
    tie_k_braces_to_girders(mesh, girder_nodes, k_brace_nodes)
    model.brace_elements.update(build_bracing(bridge, mesh, model))
    if not composite:
        tie_steel_girder_translations(bridge, girders, girder_nodes)
    model.bearings = support_the_girders(bridge, mesh, girder_nodes, max(backend.node_tags()) + 1, max(backend.element_tags()) + 1)
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
