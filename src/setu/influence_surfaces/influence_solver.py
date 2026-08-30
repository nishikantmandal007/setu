from __future__ import annotations

import numpy as np

from ..deck_model import DeckModel
from ..errors import ModelAlreadyLoadedError
from .beam_stiffness import beam_stiffness_matrix, element_rotation_matrix, moment_dof_for
from .fe_backend import FEBackend
from .opensees_backend import VERTICAL_DOF
from .surface import InfluenceSurface

NODE_I_COMPONENTS = slice(0, 6)
NODE_J_COMPONENTS = slice(6, 12)

UNIT_LOAD_DOWNWARDS = [0.0, -1.0, 0.0, 0.0, 0.0, 0.0]
NO_LOADS: list[tuple[int, list[float]]] = []

STILL_AT_REST_M = 1e-12


class InfluenceSolver:
    # One solve per response quantity. Applying the adjoint load `a` and reading the
    # deflected shape gives the response to a unit load at every node at once, because
    # a'K^-1 f = (K^-1 a)'f - Maxwell and Betti's reciprocal theorem.

    def __init__(self, deck: DeckModel, backend: FEBackend | None = None) -> None:
        self.deck = deck
        self.backend = backend if backend is not None else default_backend()
        self.surfaces: dict[str, InfluenceSurface] = {}
        self._model_was_checked = False

    def for_girder_moment(
        self, name: str, element: int, response_dof: int | None = None
    ) -> InfluenceSurface:
        self.check_nothing_else_is_loading_the_model()

        if response_dof is None:
            response_dof = moment_dof_for(self.deck.girder_local_axis)

        adjoint_loads = self.adjoint_loads_for_girder_moment(element, response_dof)
        self.backend.solve_with_loads(adjoint_loads)

        return self.surface_from_solved_deck(
            name,
            describes={"response": "girder_moment", "element": element, "dof": response_dof},
        )

    def for_deflection(self, name: str, node: int) -> InfluenceSurface:
        self.check_nothing_else_is_loading_the_model()

        self.backend.solve_with_loads([(node, UNIT_LOAD_DOWNWARDS)])

        return self.surface_from_solved_deck(
            name, describes={"response": "deflection", "node": node}
        )

    def for_truss_axial(
        self, name: str, element: int, area_m2: float, elastic_modulus_kpa: float | None = None
    ) -> InfluenceSurface:
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
        self.backend.solve_with_loads(
            [
                (node_i, list(-axial_stiffness * direction) + no_moments),
                (node_j, list(+axial_stiffness * direction) + no_moments),
            ]
        )

        return self.surface_from_solved_deck(
            name, describes={"response": "truss_axial", "element": element}
        )

    def adjoint_loads_for_girder_moment(
        self, element: int, response_dof: int
    ) -> list[tuple[int, list[float]]]:
        deck = self.deck

        # Assumes every element is as long as the midspan one, which is true on a uniform
        # mesh but not on the uneven one deck_mesh can produce. Not fixed here.
        midspan = deck.stations_along_span // 2
        element_length_m = float(
            deck.length_mesh_m[midspan + 1] - deck.length_mesh_m[midspan]
        )

        stiffness = beam_stiffness_matrix(element_length_m, deck.girder_section)
        rotation = element_rotation_matrix(deck.girder_local_axis)
        nodal_forces = rotation.T @ stiffness[:, response_dof]

        node_i, node_j = self.backend.element_nodes(element)
        return [
            (node_i, nodal_forces[NODE_I_COMPONENTS].tolist()),
            (node_j, nodal_forces[NODE_J_COMPONENTS].tolist()),
        ]

    def check_nothing_else_is_loading_the_model(self) -> None:
        if self._model_was_checked:
            return

        self.backend.solve_with_loads(NO_LOADS)
        moved_m = float(np.abs(self.deck_deflections()).max())
        self.backend.clear_loads()

        if moved_m > STILL_AT_REST_M:
            raise ModelAlreadyLoadedError(
                f"the deck moves by up to {moved_m:.3e} m with no load applied, so "
                "another load pattern is still acting on the model. An influence "
                "surface read from it would include that load and be wrong. Solve "
                "influence surfaces before applying any other load case, or remove "
                "the other load pattern first."
            )

        self._model_was_checked = True

    def surface_from_solved_deck(self, name: str, describes: dict) -> InfluenceSurface:
        surface = InfluenceSurface(
            values=self.deck_deflections(),
            length_mesh_m=self.deck.length_mesh_m,
            width_mesh_m=self.deck.width_mesh_m,
            name=name,
            skew=self.deck.skew,
            describes=describes,
        )
        self.surfaces[name] = surface
        self.backend.clear_loads()
        return surface

    def deck_deflections(self) -> np.ndarray:
        # Negated so that the surface is positive downwards, matching wheel loads.
        deck = self.deck

        rows = []
        for i in range(deck.stations_along_span):
            row = [
                -self.backend.node_displacement(deck.deck_nodes[(i, j)], VERTICAL_DOF)
                for j in range(deck.stations_across_width)
            ]
            rows.append(row)

        return np.array(rows)

    def __getitem__(self, name: str) -> InfluenceSurface:
        return self.surfaces[name]

    def __len__(self) -> int:
        return len(self.surfaces)


def default_backend() -> FEBackend:
    from .opensees_backend import OpenSeesBackend

    return OpenSeesBackend()
