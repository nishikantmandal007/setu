from __future__ import annotations

import numpy as np

from ..deck_model import GirderSection

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


def beam_stiffness_matrix(length_m: float, section: GirderSection) -> np.ndarray:
    # Degrees of freedom run node i then node j, each three displacements then three
    # rotations.
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

    add_bending_terms(
        stiffness,
        modulus,
        section.strong_axis_inertia_m4,
        length,
        shear_dofs=STRONG_AXIS_SHEAR_DOFS,
        rotation_dofs=STRONG_AXIS_ROTATION_DOFS,
        coupling_sign=+1,
    )
    add_bending_terms(
        stiffness,
        modulus,
        section.weak_axis_inertia_m4,
        length,
        shear_dofs=WEAK_AXIS_SHEAR_DOFS,
        rotation_dofs=WEAK_AXIS_ROTATION_DOFS,
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
    # The two bending planes share these four terms and differ only in the coupling sign,
    # because their local axes point opposite ways round the member.
    shear = 12 * modulus * inertia_m4 / length**3
    coupling = coupling_sign * 6 * modulus * inertia_m4 / length**2
    near_rotation = 4 * modulus * inertia_m4 / length
    far_rotation = 2 * modulus * inertia_m4 / length

    shear_i, shear_j = shear_dofs
    rotation_i, rotation_j = rotation_dofs

    stiffness[shear_i, shear_i] = stiffness[shear_j, shear_j] = shear
    stiffness[shear_i, shear_j] = stiffness[shear_j, shear_i] = -shear

    coupled_pairs = (
        (shear_i, rotation_i, +1),
        (shear_i, rotation_j, +1),
        (shear_j, rotation_i, -1),
        (shear_j, rotation_j, -1),
    )
    for shear_dof, rotation_dof, sign in coupled_pairs:
        stiffness[shear_dof, rotation_dof] = sign * coupling
        stiffness[rotation_dof, shear_dof] = sign * coupling

    stiffness[rotation_i, rotation_i] = stiffness[rotation_j, rotation_j] = near_rotation
    stiffness[rotation_i, rotation_j] = stiffness[rotation_j, rotation_i] = far_rotation


def element_rotation_matrix(
    local_axis: tuple[float, float, float],
    along: tuple[float, float, float] = (1.0, 0.0, 0.0),
) -> np.ndarray:
    x_axis = np.array(along, float)
    x_axis = x_axis / np.linalg.norm(x_axis)

    y_axis = np.cross(np.array(local_axis, float), x_axis)
    y_axis = y_axis / np.linalg.norm(y_axis)
    z_axis = np.cross(x_axis, y_axis)

    axes = np.vstack([x_axis, y_axis, z_axis])

    rotation = np.zeros((DEGREES_OF_FREEDOM, DEGREES_OF_FREEDOM))
    for corner in range(4):
        starts_at = 3 * corner
        rotation[starts_at : starts_at + 3, starts_at : starts_at + 3] = axes
    return rotation


def moment_dof_for(local_axis: tuple[float, float, float]) -> int:
    if tuple(local_axis) == GIRDER_LOCAL_AXIS_ALONG_Z:
        return BENDING_MOMENT_ABOUT_STRONG_AXIS
    return BENDING_MOMENT_ABOUT_WEAK_AXIS
