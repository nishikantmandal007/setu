import numpy as np
from setu.errors import InfluenceSurfaceError, ModelAlreadyLoadedError
from setu.utils.constants import END_I_FORCE_TO_INTERNAL_FORCE, N_I, OFF_THE_DECK
from setu.solver.backend import OpenSeesBackend
from setu.solver.stiffness import beam_stiffness_matrix, element_rotation_matrix, moment_dof_for, shear_dof_for

VERTICAL_DOF = 2

class InfluenceSurface:
    # response to a unit load at every deck node
    def __init__(self, values, length_mesh_m, width_mesh_m, name, skew, node_tags=None, every_node_displacement=None):
        self.values = np.asarray(values, float)
        self.length_mesh_m = np.asarray(length_mesh_m, float)
        self.width_mesh_m = np.asarray(width_mesh_m, float)
        self.name = name
        self.skew = skew
        self.node_tags = node_tags  # every node of the solved model, increasing; None for a surface given only on the deck
        self.every_node_displacement = every_node_displacement  # six adjoint displacements per node, rows as node_tags

        expected_shape = (len(self.length_mesh_m), len(self.width_mesh_m))
        if self.values.shape != expected_shape:
            raise InfluenceSurfaceError(f"influence values have shape {self.values.shape}, but the deck mesh is {expected_shape}")

    # the six adjoint displacements of each node, for reading a nodal load case by reciprocity
    def displacements_of(self, nodes):
        if self.node_tags is None or self.every_node_displacement is None:
            raise ValueError(f"{self.name!r} holds only deck ordinates, so it cannot read a load case by reciprocity")
        rows = np.minimum(np.searchsorted(self.node_tags, nodes), len(self.node_tags) - 1)
        if not np.array_equal(self.node_tags[rows], nodes):
            raise KeyError(f"load on node(s) {sorted(set(np.asarray(nodes).tolist()) - set(self.node_tags.tolist()))} that the model does not have")
        return self.every_node_displacement[rows]

    # influence at any (x, z), zero off the deck
    def influence_at(self, x_m, z_m):
        x_m = np.asarray(x_m, float)
        z_m = np.asarray(z_m, float)
        asked_for_one_point = x_m.ndim == 0 and z_m.ndim == 0
        along, across = np.broadcast_arrays(x_m - self.skew * z_m, z_m)
        is_on_the_deck = (along >= self.length_mesh_m[0]) & (along <= self.length_mesh_m[-1]) & (across >= self.width_mesh_m[0]) & (across <= self.width_mesh_m[-1])
        interpolated = self.bilinear(along, across)
        response = np.where(is_on_the_deck, interpolated, OFF_THE_DECK)
        return float(response) if asked_for_one_point else response

    # bilinear interpolation inside the mesh cell
    def bilinear(self, along, across):
        i = cell_containing(self.length_mesh_m, along)
        j = cell_containing(self.width_mesh_m, across)
        fraction_along = (along - self.length_mesh_m[i]) / (self.length_mesh_m[i + 1] - self.length_mesh_m[i])
        fraction_across = (across - self.width_mesh_m[j]) / (self.width_mesh_m[j + 1] - self.width_mesh_m[j])
        return (1 - fraction_along) * (1 - fraction_across) * self.values[i, j] + fraction_along * (1 - fraction_across) * self.values[i + 1, j] + fraction_along * fraction_across * self.values[i + 1, j + 1] + (1 - fraction_along) * fraction_across * self.values[i, j + 1]

    # same surface read in mesh coordinates, skew taken out
    def along_the_mesh(self):
        return InfluenceSurface(values=self.values, length_mesh_m=self.length_mesh_m, width_mesh_m=self.width_mesh_m, name=self.name, skew=0.0)

# response to a nodal load case by reciprocity: sum of force times adjoint displacement
def response_to_load_case(surface, load_case):
    if load_case.element_loads:
        raise ValueError(f"{load_case.name!r} has element loads; reciprocity here covers nodal loads only - solve it with analyze_load_case")
    nodes, forces = load_case.nodal_arrays
    return float(np.sum(forces * surface.displacements_of(nodes)))

# index of the mesh cell each position falls in
def cell_containing(stations_m, positions_m):
    last_cell = len(stations_m) - 2
    return np.clip(np.searchsorted(stations_m, positions_m) - 1, 0, last_cell)

NODE_I_COMPONENTS = slice(0, 6)
NODE_J_COMPONENTS = slice(6, 12)
NO_LOADS = []
UNIT_LOAD_DOWNWARDS = [0.0, -1.0, 0.0, 0.0, 0.0, 0.0]
STILL_AT_REST_M = 1e-12

class InfluenceSolver:

    # solves influence surfaces on one deck model
    def __init__(self, deck, backend=None):
        self.deck = deck
        self.backend = backend if backend is not None else default_backend()
        self.surfaces = {}
        self._model_was_checked = False

    # influence surface of a girder's composite moment: steel moment plus axial couple
    def for_girder_composite_moment(self, name, element, *, end="i"):
        self.check_nothing_else_is_loading_the_model()
        moment_dof = moment_dof_for(self.deck.girder_local_axis)
        steel_moment_and_axial_couple = [(moment_dof, 1.0), (N_I, self.deck.lever_arm_for_element(element))]
        adjoint_loads = self.adjoint_loads_for_girder_force(element, steel_moment_and_axial_couple, end=end)
        with self.backend.solved(adjoint_loads):
            return self.surface_from_solved_deck(name)

    # influence surface of a girder's shear
    def for_girder_shear(self, name, element, *, end="i"):
        self.check_nothing_else_is_loading_the_model()
        response_dof = shear_dof_for(self.deck.girder_local_axis)
        adjoint_loads = self.adjoint_loads_for_girder_force(element, [(response_dof, 1.0)], end=end)
        with self.backend.solved(adjoint_loads):
            return self.surface_from_solved_deck(name)

    # nominal longitudinal steel stress, tension positive: N/A + M(y_NA - y)/I, in MPa
    def for_girder_stress_mpa(self, name, element, section, y_from_bottom_m):
        self.check_nothing_else_is_loading_the_model()
        moment_weight = (section.neutral_axis_from_bottom_m - y_from_bottom_m) / section.strong_axis_inertia_m4 / 1000
        weighted_dofs = [(N_I, 1 / section.area_m2 / 1000), (moment_dof_for(self.deck.girder_local_axis), moment_weight)]
        with self.backend.solved(self.adjoint_loads_for_girder_force(element, weighted_dofs)):
            return self.surface_from_solved_deck(name)

    # influence surface of the downward deflection of a node: the deflections under a unit load at that node
    def for_deflection(self, name, node):
        self.check_nothing_else_is_loading_the_model()
        with self.backend.solved([(node, UNIT_LOAD_DOWNWARDS)]):
            return self.surface_from_solved_deck(name)

    # influence surface of a bearing's upward reaction: its spring stiffness times the deflections under a unit load on the bearing
    def for_bearing_reaction(self, name, bearing_node, bearing_stiffness_kn_per_m):
        self.check_nothing_else_is_loading_the_model()
        with self.backend.solved([(bearing_node, UNIT_LOAD_DOWNWARDS)]):
            return self.surface_from_solved_deck(name, bearing_stiffness_kn_per_m)

    # influence surface of a brace truss member's axial force, tension positive
    def for_brace_axial(self, name, element):
        adjoint_loads = self.adjoint_loads_for_truss_axial(element)
        self.check_nothing_else_is_loading_the_model()
        with self.backend.solved(adjoint_loads):
            return self.surface_from_solved_deck(name)

    # equal and opposite axial stiffness forces along the truss; Transformation maps rigid-linked brace ends to their girders
    def adjoint_loads_for_truss_axial(self, element):
        if self.deck.brace_area_m2 is None:
            raise ValueError("brace_area_m2 is missing from the deck model")
        node_i, node_j = self.backend.element_nodes(element)
        start = np.array(self.backend.node_coordinates(node_i), float)
        finish = np.array(self.backend.node_coordinates(node_j), float)
        span_m = finish - start
        length_m = float(np.linalg.norm(span_m))
        unit_vector = span_m / length_m
        axial_stiffness_kn_per_m = self.deck.girder_section.elastic_modulus_kpa * self.deck.brace_area_m2 / length_m
        force_kn = axial_stiffness_kn_per_m * unit_vector
        return [(node_i, (-force_kn).tolist() + [0.0, 0.0, 0.0]), (node_j, force_kn.tolist() + [0.0, 0.0, 0.0])]

    # the nodal loads whose deflections are the girder force's influence surface
    def adjoint_loads_for_girder_force(self, element, weighted_dofs, *, end="i"):
        if end not in ("i", "j"):
            raise ValueError("element end must be 'i' or 'j'")
        deck = self.deck
        node_i, node_j = self.backend.element_nodes(element)
        start = np.array(self.backend.node_coordinates(node_i), float)
        finish = np.array(self.backend.node_coordinates(node_j), float)
        element_length_m = float(np.linalg.norm(finish - start))
        stiffness = beam_stiffness_matrix(element_length_m, deck.section_for_element(element))
        rotation = element_rotation_matrix(deck.girder_local_axis)
        offset = 0 if end == "i" else 6
        response_row = sum(weight * stiffness[:, dof + offset] for dof, weight in weighted_dofs)
        sign = END_I_FORCE_TO_INTERNAL_FORCE if end == "i" else 1.0
        nodal_forces = sign * (rotation.T @ response_row)
        return [(node_i, nodal_forces[NODE_I_COMPONENTS].tolist()), (node_j, nodal_forces[NODE_J_COMPONENTS].tolist())]

    # refuse to start if some other load is still on the model
    def check_nothing_else_is_loading_the_model(self):
        if self._model_was_checked:
            return
        with self.backend.solved(NO_LOADS):
            moved_m = float(np.abs(self.deck_deflections()).max())
        if moved_m > STILL_AT_REST_M:
            raise ModelAlreadyLoadedError(f'the deck moves by up to {moved_m:.3e} m with no load applied, so another load pattern is still acting on the model. An influence surface read from it would include that load and be wrong. Solve influence surfaces before applying any other load case, or remove the other load pattern first.')
        self._model_was_checked = True

    # read the deck deflections off the solve as a surface (times a scale, for a bearing reaction)
    def surface_from_solved_deck(self, name, scale=1.0):
        node_tags, displacements = self.backend.every_node_displacement()
        deck_rows = np.searchsorted(node_tags, [[self.deck.deck_nodes[i, j] for j in range(self.deck.stations_across_width)]
                                                for i in range(self.deck.stations_along_span)])
        surface = InfluenceSurface(values=scale * -displacements[deck_rows, VERTICAL_DOF - 1], length_mesh_m=self.deck.length_mesh_m,
                                   width_mesh_m=self.deck.width_mesh_m, name=name, skew=self.deck.skew,
                                   node_tags=node_tags, every_node_displacement=scale * displacements)
        self.surfaces[name] = surface
        return surface

    # downward deflection of every deck node
    def deck_deflections(self):
        deck = self.deck
        rows = []
        for i in range(deck.stations_along_span):
            row = [-self.backend.node_displacement(deck.deck_nodes[i, j], VERTICAL_DOF) for j in range(deck.stations_across_width)]
            rows.append(row)
        return np.array(rows)

    # a solved surface by name
    def __getitem__(self, name):
        return self.surfaces[name]

    # how many surfaces were solved
    def __len__(self):
        return len(self.surfaces)

# OpenSees
def default_backend():
    return OpenSeesBackend()
