# The beam element stiffness and rotation matrices influence_solver builds each adjoint
# load from. Pure linear algebra, with no solver dependency, so it can be tested and used
# on a machine with no finite element backend installed at all.

from __future__ import annotations

import numpy as np

from ..deck_model import GirderSection

# Degree of freedom that carries the span bending moment, once the response is read off a
# column of the stiffness matrix built below. 5 is the local rotation of the element's
# first node in the strong-axis group (1, 5, 7, 11) that beam_stiffness_matrix builds; 4 is
# the same node's rotation in the weak-axis group (2, 4, 8, 10).
BENDING_MOMENT_ABOUT_STRONG_AXIS = 5
BENDING_MOMENT_ABOUT_WEAK_AXIS = 4


def beam_stiffness_matrix(length_m: float, section: GirderSection) -> np.ndarray:
    # Returns the 12x12 stiffness matrix of a beam element, in its own axes.
    #
    # Degrees of freedom run node i then node j, each as three displacements then three
    # rotations. Bending about the strong axis pairs degrees of freedom (1, 5, 7, 11);
    # about the weak axis, (2, 4, 8, 10).
    length = float(length_m)
    modulus = section.elastic_modulus_kpa
    stiffness = np.zeros((12, 12))

    axial = modulus * section.area_m2 / length
    stiffness[0, 0] = stiffness[6, 6] = axial
    stiffness[0, 6] = stiffness[6, 0] = -axial

    torsion = section.shear_modulus_kpa * section.torsion_constant_m4 / length
    stiffness[3, 3] = stiffness[9, 9] = torsion
    stiffness[3, 9] = stiffness[9, 3] = -torsion

    add_bending_terms(
        stiffness,
        modulus,
        section.strong_axis_inertia_m4,
        length,
        shear_dofs=(1, 7),
        rotation_dofs=(5, 11),
        coupling_sign=+1,
    )
    add_bending_terms(
        stiffness,
        modulus,
        section.weak_axis_inertia_m4,
        length,
        shear_dofs=(2, 8),
        rotation_dofs=(4, 10),
        coupling_sign=-1,
    )
    return stiffness


def add_bending_terms(
    stiffness: np.ndarray,
    modulus: float,
    inertia_m4: float,
    length: float,
    *,
    shear_dofs: tuple[int, int],
    rotation_dofs: tuple[int, int],
    coupling_sign: int,
) -> None:
    # Fills in one bending plane of the beam stiffness matrix.
    #
    # The two planes have the same four terms and differ only in which degrees of freedom
    # they act on and in the sign of the shear-rotation coupling, which flips because the
    # two local axes point opposite ways round the member.
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
    # Returns the 12x12 matrix turning local element axes into global axes.
    #
    # For a girder running along the span with the usual local axis this is the identity,
    # but a skewed or transverse member needs the real rotation.
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


def moment_dof_for(local_axis: tuple[float, float, float]) -> int:
    # Returns which degree of freedom carries the span bending moment.
    #
    # Which of the two bending planes carries the span moment depends on how the girder's
    # local axes were set up in the solver.
    if tuple(local_axis) == (0.0, 0.0, 1.0):
        return BENDING_MOMENT_ABOUT_STRONG_AXIS
    return BENDING_MOMENT_ABOUT_WEAK_AXIS
