"""Building an influence surface with one solve instead of thousands.

The usual way to find where a vehicle does the most damage is to move it, solve,
move it again, and solve again - once per position. On a real deck that is tens
of thousands of analyses.

There is a shortcut, and it is exact. For a linear model the response R to a
load f is R = a'u = a'K^-1 f, and since K is symmetric that equals (K^-1 a)'f.
So solving the model **once** with `a` applied as an imaginary load gives a
displaced shape whose ordinate at every node is the response to a unit load at
that node. That shape is the influence surface. This is Maxwell and Betti's
reciprocal theorem, and it is why setu solves once per response quantity rather
than once per vehicle position.

`a` is the "adjoint load" - the nodal forces that extract the response being
asked about. For a girder end moment it is a column of the element stiffness
matrix; for a deflection it is simply a unit load at that node.

Sign convention: an influence ordinate is the response to a unit load pointing
**down**, and wheel loads are positive downwards.
"""

from __future__ import annotations

import numpy as np

from ..deck_model import DeckModel, GirderSection
from ..errors import ModelAlreadyLoadedError
from .fe_backend import FEBackend
from .opensees_backend import VERTICAL_DOF
from .surface import InfluenceSurface

BENDING_MOMENT_ABOUT_STRONG_AXIS = 5
BENDING_MOMENT_ABOUT_WEAK_AXIS = 4


def beam_stiffness_matrix(length_m: float, section: GirderSection) -> np.ndarray:
    """Returns the 12x12 stiffness matrix of a beam element, in its own axes.

    Degrees of freedom run node i then node j, each as three displacements then
    three rotations. Bending about the strong axis pairs degrees of freedom
    (1, 5, 7, 11); about the weak axis, (2, 4, 8, 10).
    """
    length = float(length_m)
    modulus = section.elastic_modulus_kpa
    stiffness = np.zeros((12, 12))

    axial = modulus * section.area_m2 / length
    stiffness[0, 0] = stiffness[6, 6] = axial
    stiffness[0, 6] = stiffness[6, 0] = -axial

    torsion = section.shear_modulus_kpa * section.torsion_constant_m4 / length
    stiffness[3, 3] = stiffness[9, 9] = torsion
    stiffness[3, 9] = stiffness[9, 3] = -torsion

    _add_bending_terms(
        stiffness,
        modulus,
        section.strong_axis_inertia_m4,
        length,
        shear_dofs=(1, 7),
        rotation_dofs=(5, 11),
        coupling_sign=+1,
    )
    _add_bending_terms(
        stiffness,
        modulus,
        section.weak_axis_inertia_m4,
        length,
        shear_dofs=(2, 8),
        rotation_dofs=(4, 10),
        coupling_sign=-1,
    )
    return stiffness


def _add_bending_terms(
    stiffness: np.ndarray,
    modulus: float,
    inertia_m4: float,
    length: float,
    *,
    shear_dofs: tuple[int, int],
    rotation_dofs: tuple[int, int],
    coupling_sign: int,
) -> None:
    """Fills in one bending plane of the beam stiffness matrix.

    The two planes have the same four terms and differ only in which degrees of
    freedom they act on and in the sign of the shear-rotation coupling, which
    flips because the two local axes point opposite ways round the member.
    """
    shear = 12 * modulus * inertia_m4 / length**3
    coupling = coupling_sign * 6 * modulus * inertia_m4 / length**2
    near_rotation = 4 * modulus * inertia_m4 / length
    far_rotation = 2 * modulus * inertia_m4 / length

    shear_i, shear_j = shear_dofs
    rotation_i, rotation_j = rotation_dofs

    stiffness[shear_i, shear_i] = stiffness[shear_j, shear_j] = shear
    stiffness[shear_i, shear_j] = stiffness[shear_j, shear_i] = -shear

    for shear_dof, rotation_dof, sign in (
        (shear_i, rotation_i, +1),
        (shear_i, rotation_j, +1),
        (shear_j, rotation_i, -1),
        (shear_j, rotation_j, -1),
    ):
        stiffness[shear_dof, rotation_dof] = sign * coupling
        stiffness[rotation_dof, shear_dof] = sign * coupling

    stiffness[rotation_i, rotation_i] = stiffness[rotation_j, rotation_j] = near_rotation
    stiffness[rotation_i, rotation_j] = stiffness[rotation_j, rotation_i] = far_rotation


def element_rotation_matrix(
    local_axis: tuple[float, float, float], along: tuple[float, float, float] = (1.0, 0.0, 0.0)
) -> np.ndarray:
    """Returns the 12x12 matrix turning local element axes into global axes.

    For a girder running along the span with the usual local axis this is the
    identity, but a skewed or transverse member needs the real rotation.
    """
    x_axis = np.array(along, float)
    x_axis = x_axis / np.linalg.norm(x_axis)

    y_axis = np.cross(np.array(local_axis, float), x_axis)
    y_axis = y_axis / np.linalg.norm(y_axis)
    z_axis = np.cross(x_axis, y_axis)

    axes = np.vstack([x_axis, y_axis, z_axis])

    rotation = np.zeros((12, 12))
    for corner in range(4):
        rotation[3 * corner : 3 * corner + 3, 3 * corner : 3 * corner + 3] = axes
    return rotation


class InfluenceSolver:
    """Builds one influence surface per response quantity, on one deck model.

    Reads as what it does::

        influence = InfluenceSolver(deck)
        surface = influence.for_girder_moment("girder 3 midspan", element)
    """

    def __init__(self, deck: DeckModel, backend: FEBackend | None = None) -> None:
        self.deck = deck
        self.backend = backend if backend is not None else _default_backend()
        self.surfaces: dict[str, InfluenceSurface] = {}
        self._model_was_checked = False

    def for_girder_moment(
        self, name: str, element: int, response_dof: int | None = None
    ) -> InfluenceSurface:
        """Returns the influence surface for the bending moment at a girder element's end."""
        self.check_nothing_else_is_loading_the_model()

        if response_dof is None:
            response_dof = _moment_dof_for(self.deck.girder_local_axis)

        adjoint_loads = self._adjoint_loads_for_girder_moment(element, response_dof)
        self.backend.solve_with_loads(adjoint_loads)

        return self._surface_from_solved_deck(
            name,
            describes={"response": "girder_moment", "element": element, "dof": response_dof},
        )

    def for_deflection(self, name: str, node: int) -> InfluenceSurface:
        """Returns the influence surface for the vertical deflection of one node.

        Reciprocity makes this the simplest case of all: the adjoint load *is* a
        unit downward load at the node whose deflection is wanted.
        """
        self.check_nothing_else_is_loading_the_model()

        self.backend.solve_with_loads([(node, [0.0, -1.0, 0.0, 0.0, 0.0, 0.0])])

        return self._surface_from_solved_deck(
            name, describes={"response": "deflection", "node": node}
        )

    def for_truss_axial(
        self, name: str, element: int, area_m2: float, elastic_modulus_kpa: float | None = None
    ) -> InfluenceSurface:
        """Returns the influence surface for the axial force in a truss element."""
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

        return self._surface_from_solved_deck(
            name, describes={"response": "truss_axial", "element": element}
        )

    def _adjoint_loads_for_girder_moment(
        self, element: int, response_dof: int
    ) -> list[tuple[int, list[float]]]:
        """Returns the nodal forces that extract one end moment of a girder element.

        The moment at an element end is one row of `stiffness @ displacements`,
        so the load that extracts it is that same column of the stiffness matrix,
        rotated into global axes.
        """
        deck = self.deck
        midspan = deck.stations_along_span // 2
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
        """Makes sure the deck stands still when setu applies no load at all.

        Worth one extra solve. A dead load pattern left switched on adds its own
        deflections to every influence surface, and the numbers come out wrong
        by a per cent or two with nothing at all to show that they have.
        """
        if self._model_was_checked:
            return

        self.backend.solve_with_loads([])
        moved_m = float(np.abs(self._deck_deflections()).max())
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

    def _surface_from_solved_deck(self, name: str, describes: dict) -> InfluenceSurface:
        """Reads the solved deck deflections off the model as an influence surface."""
        surface = InfluenceSurface(
            values=self._deck_deflections(),
            length_mesh_m=self.deck.length_mesh_m,
            width_mesh_m=self.deck.width_mesh_m,
            name=name,
            skew=self.deck.skew,
            describes=describes,
        )
        self.surfaces[name] = surface
        self.backend.clear_loads()
        return surface

    def _deck_deflections(self) -> np.ndarray:
        """Returns the vertical deflection of every deck node, positive downwards."""
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


def _moment_dof_for(local_axis: tuple[float, float, float]) -> int:
    """Returns which degree of freedom carries the span bending moment.

    Which of the two bending planes carries the span moment depends on how the
    girder's local axes were set up in the solver.
    """
    if tuple(local_axis) == (0.0, 0.0, 1.0):
        return BENDING_MOMENT_ABOUT_STRONG_AXIS
    return BENDING_MOMENT_ABOUT_WEAK_AXIS


def _default_backend() -> FEBackend:
    from .opensees_backend import OpenSeesBackend

    return OpenSeesBackend()
