import json
import numpy as np
from setu.utils.errors import InfluenceSurfaceError, ModelAlreadyLoadedError
from setu.services.opensees import FEBackend, OpenSeesBackend
from setu.models.deck import DeckModel
from setu.services.bridge_geometry import beam_stiffness_matrix, element_rotation_matrix, moment_dof_for

VERTICAL_DOF = 2
import json
import numpy as np
OFF_THE_DECK = 0.0

class InfluenceSurface:
    def __init__(self, values, length_mesh_m, width_mesh_m, name="", skew=0.0, describes=None):
        self.values = np.asarray(values, float)
        self.length_mesh_m = np.asarray(length_mesh_m, float)
        self.width_mesh_m = np.asarray(width_mesh_m, float)
        self.name = name
        self.skew = skew
        self.describes = describes or {}

        expected_shape = (len(self.length_mesh_m), len(self.width_mesh_m))
        if self.values.shape != expected_shape:
            raise InfluenceSurfaceError(f"influence values have shape {self.values.shape}, but the deck mesh is {expected_shape}")

    def to_dict(self):
        return self.__dict__

        self.values = np.asarray(self.values, float)
        self.length_mesh_m = np.asarray(self.length_mesh_m, float)
        self.width_mesh_m = np.asarray(self.width_mesh_m, float)
        expected_shape = (len(self.length_mesh_m), len(self.width_mesh_m))
        if self.values.shape != expected_shape:
            raise InfluenceSurfaceError(f'influence values have shape {self.values.shape}, but the deck mesh is {expected_shape}')

    def influence_at(self, x_m, z_m):
        x_m = np.asarray(x_m, float)
        z_m = np.asarray(z_m, float)
        asked_for_one_point = x_m.ndim == 0 and z_m.ndim == 0
        along, across = np.broadcast_arrays(x_m - self.skew * z_m, z_m)
        is_on_the_deck = (along >= self.length_mesh_m[0]) & (along <= self.length_mesh_m[-1]) & (across >= self.width_mesh_m[0]) & (across <= self.width_mesh_m[-1])
        interpolated = self.bilinear(along, across)
        response = np.where(is_on_the_deck, interpolated, OFF_THE_DECK)
        return float(response) if asked_for_one_point else response

    def bilinear(self, along, across):
        i = cell_containing(self.length_mesh_m, along)
        j = cell_containing(self.width_mesh_m, across)
        fraction_along = (along - self.length_mesh_m[i]) / (self.length_mesh_m[i + 1] - self.length_mesh_m[i])
        fraction_across = (across - self.width_mesh_m[j]) / (self.width_mesh_m[j + 1] - self.width_mesh_m[j])
        return (1 - fraction_along) * (1 - fraction_across) * self.values[i, j] + fraction_along * (1 - fraction_across) * self.values[i + 1, j] + fraction_along * fraction_across * self.values[i + 1, j + 1] + (1 - fraction_along) * fraction_across * self.values[i, j + 1]

    def save(self, path):
        np.savez(path, values=self.values, length_mesh_m=self.length_mesh_m, width_mesh_m=self.width_mesh_m, skew=self.skew, name=str(self.name), describes=json.dumps(self.describes))

    @classmethod
    def load(cls, path):
        stored = np.load(path, allow_pickle=False)
        if 'describes' in stored.files:
            describes = json.loads(str(stored['describes']))
        else:
            describes = {}
        return cls(values=stored['values'], length_mesh_m=stored['length_mesh_m'], width_mesh_m=stored['width_mesh_m'], name=str(stored['name']), skew=float(stored['skew']), describes=describes)

def cell_containing(stations_m, positions_m):
    last_cell = len(stations_m) - 2
    return np.clip(np.searchsorted(stations_m, positions_m) - 1, 0, last_cell)

import numpy as np
NODE_I_COMPONENTS = slice(0, 6)
NODE_J_COMPONENTS = slice(6, 12)
UNIT_LOAD_DOWNWARDS = [0.0, -1.0, 0.0, 0.0, 0.0, 0.0]
NO_LOADS = []
STILL_AT_REST_M = 1e-12

class InfluenceSolver:

    def __init__(self, deck, backend=None):
        self.deck = deck
        self.backend = backend if backend is not None else default_backend()
        self.surfaces = {}
        self._model_was_checked = False

    def for_girder_moment(self, name, element, response_dof=None):
        self.check_nothing_else_is_loading_the_model()
        if response_dof is None:
            response_dof = moment_dof_for(self.deck.girder_local_axis)
        adjoint_loads = self.adjoint_loads_for_girder_moment(element, response_dof)
        self.backend.solve_with_loads(adjoint_loads)
        return self.surface_from_solved_deck(name, describes={'response': 'girder_moment', 'element': element, 'dof': response_dof})

    def for_deflection(self, name, node):
        self.check_nothing_else_is_loading_the_model()
        self.backend.solve_with_loads([(node, UNIT_LOAD_DOWNWARDS)])
        return self.surface_from_solved_deck(name, describes={'response': 'deflection', 'node': node})

    def for_truss_axial(self, name, element, area_m2, elastic_modulus_kpa=None):
        self.check_nothing_else_is_loading_the_model()
        node_i, node_j = self.backend.element_nodes(element)
        start = np.array(self.backend.node_coordinates(node_i), float)
        end = np.array(self.backend.node_coordinates(node_j), float)
        length_m = float(np.linalg.norm(end - start))
        direction = (end - start) / length_m
        if elastic_modulus_kpa is None:
            elastic_modulus_kpa = self.deck.girder_section.elastic_modulus_kpa
        axial_stiffness = elastic_modulus_kpa * area_m2 / length_m
        no_moments = [0.0, 0.0, 0.0]
        self.backend.solve_with_loads([(node_i, list(-axial_stiffness * direction) + no_moments), (node_j, list(+axial_stiffness * direction) + no_moments)])
        return self.surface_from_solved_deck(name, describes={'response': 'truss_axial', 'element': element})

    def adjoint_loads_for_girder_moment(self, element, response_dof):
        deck = self.deck
        midspan = deck.stations_along_span // 2
        element_length_m = float(deck.length_mesh_m[midspan + 1] - deck.length_mesh_m[midspan])
        stiffness = beam_stiffness_matrix(element_length_m, deck.girder_section)
        rotation = element_rotation_matrix(deck.girder_local_axis)
        nodal_forces = rotation.T @ stiffness[:, response_dof]
        node_i, node_j = self.backend.element_nodes(element)
        return [(node_i, nodal_forces[NODE_I_COMPONENTS].tolist()), (node_j, nodal_forces[NODE_J_COMPONENTS].tolist())]

    def check_nothing_else_is_loading_the_model(self):
        if self._model_was_checked:
            return
        self.backend.solve_with_loads(NO_LOADS)
        moved_m = float(np.abs(self.deck_deflections()).max())
        self.backend.clear_loads()
        if moved_m > STILL_AT_REST_M:
            raise ModelAlreadyLoadedError(f'the deck moves by up to {moved_m:.3e} m with no load applied, so another load pattern is still acting on the model. An influence surface read from it would include that load and be wrong. Solve influence surfaces before applying any other load case, or remove the other load pattern first.')
        self._model_was_checked = True

    def surface_from_solved_deck(self, name, describes):
        surface = InfluenceSurface(values=self.deck_deflections(), length_mesh_m=self.deck.length_mesh_m, width_mesh_m=self.deck.width_mesh_m, name=name, skew=self.deck.skew, describes=describes)
        self.surfaces[name] = surface
        self.backend.clear_loads()
        return surface

    def deck_deflections(self):
        deck = self.deck
        rows = []
        for i in range(deck.stations_along_span):
            row = [-self.backend.node_displacement(deck.deck_nodes[i, j], VERTICAL_DOF) for j in range(deck.stations_across_width)]
            rows.append(row)
        return np.array(rows)

    def __getitem__(self, name):
        return self.surfaces[name]

    def __len__(self):
        return len(self.surfaces)

def default_backend():
    return OpenSeesBackend()