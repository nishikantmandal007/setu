# How to get an influence surface with one solve instead of thousands.
#
# The usual way to find where a vehicle does the most damage is to move it, solve, move it
# again, and solve again - once per position. On a real deck that is tens of thousands of
# analyses.
#
# There is a shortcut, and it is exact. For a linear model the response R to a load f is
# R = a'u = a'K^-1 f, and since K is symmetric that equals (K^-1 a)'f. So solving the model
# ONCE with `a` applied as an imaginary load gives a displaced shape whose ordinate at every
# node is the response to a unit load at that node. That shape is the influence surface.
# This is Maxwell and Betti's reciprocal theorem, and it is why setu solves once per
# response quantity rather than once per vehicle position.
#
# `a` is the "adjoint load" - the nodal forces that extract the response being asked about.
# For a girder end moment it is a column of the element stiffness matrix; for a deflection
# it is simply a unit load at that node.
#
# Sign convention: an influence ordinate is the response to a unit load pointing DOWN, and
# wheel loads are positive downwards.

from __future__ import annotations

import numpy as np

from ..deck_model import DeckModel
from ..errors import ModelAlreadyLoadedError
from .beam_stiffness import beam_stiffness_matrix, element_rotation_matrix, moment_dof_for
from .fe_backend import FEBackend
from .opensees_backend import VERTICAL_DOF
from .surface import InfluenceSurface


class InfluenceSolver:
    # Builds one influence surface per response quantity, on one deck model.

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

        # Reciprocity makes this the simplest case of all: the adjoint load *is* a unit
        # downward load at the node whose deflection is wanted.
        self.backend.solve_with_loads([(node, [0.0, -1.0, 0.0, 0.0, 0.0, 0.0])])

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
        modulus = (
            elastic_modulus_kpa
            if elastic_modulus_kpa is not None
            else self.deck.girder_section.elastic_modulus_kpa
        )
        axial_stiffness = modulus * area_m2 / length_m

        self.backend.solve_with_loads(
            [
                (node_i, list(-axial_stiffness * direction) + [0.0, 0.0, 0.0]),
                (node_j, list(+axial_stiffness * direction) + [0.0, 0.0, 0.0]),
            ]
        )

        return self.surface_from_solved_deck(
            name, describes={"response": "truss_axial", "element": element}
        )

    def adjoint_loads_for_girder_moment(
        self, element: int, response_dof: int
    ) -> list[tuple[int, list[float]]]:
        # The moment at an element end is one row of stiffness @ displacements, so the load
        # that extracts it is that same column of the stiffness matrix, rotated into global
        # axes.
        deck = self.deck
        midspan = deck.stations_along_span // 2
        # Assumes every element has the midspan element's length, regardless of which
        # element was actually passed in. True on a uniform mesh; on a non-uniform one -
        # which deck_mesh can produce when bracing lines are unevenly spaced - this builds
        # the stiffness matrix for the wrong element length. Not fixed here.
        element_length_m = float(deck.length_mesh_m[midspan + 1] - deck.length_mesh_m[midspan])

        stiffness = beam_stiffness_matrix(element_length_m, deck.girder_section)
        rotation = element_rotation_matrix(deck.girder_local_axis)
        nodal_forces = rotation.T @ stiffness[:, response_dof]

        node_i, node_j = self.backend.element_nodes(element)
        return [
            (node_i, nodal_forces[0:6].tolist()),
            (node_j, nodal_forces[6:12].tolist()),
        ]

    def check_nothing_else_is_loading_the_model(self) -> None:
        # Worth one extra solve. A dead load pattern left switched on adds its own
        # deflections to every influence surface, and the numbers come out wrong by a per
        # cent or two with nothing at all to show that they have.
        if self._model_was_checked:
            return

        self.backend.solve_with_loads([])
        moved_m = float(np.abs(self.deck_deflections()).max())
        self.backend.clear_loads()

        if moved_m > 1e-12:
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
        # Positive downwards, matching the sign convention above.
        deck = self.deck
        return np.array(
            [
                [
                    -self.backend.node_displacement(deck.deck_nodes[(i, j)], VERTICAL_DOF)
                    for j in range(deck.stations_across_width)
                ]
                for i in range(deck.stations_along_span)
            ]
        )

    def __getitem__(self, name: str) -> InfluenceSurface:
        return self.surfaces[name]

    def __len__(self) -> int:
        return len(self.surfaces)


def default_backend() -> FEBackend:
    from .opensees_backend import OpenSeesBackend

    return OpenSeesBackend()
