"""The beam element stiffness and rotation matrices."""


import numpy as np
import pytest

from src.models.deck import GirderSection
from src.services.bridge_builder import (
    beam_stiffness_matrix,
    element_rotation_matrix,
)

SECTION = GirderSection(
    area_m2=0.1,
    torsion_constant_m4=1e-3,
    weak_axis_inertia_m4=2e-3,
    strong_axis_inertia_m4=5e-2,
    elastic_modulus_kpa=2.0e8,
    shear_modulus_kpa=7.7e7,
)


def test_the_stiffness_matrix_is_symmetric():
    stiffness = beam_stiffness_matrix(2.5, SECTION)
    assert stiffness == pytest.approx(stiffness.T)


def test_axial_and_torsional_terms_are_the_textbook_ones():
    length_m = 2.5
    stiffness = beam_stiffness_matrix(length_m, SECTION)

    assert stiffness[0, 0] == pytest.approx(
        SECTION.elastic_modulus_kpa * SECTION.area_m2 / length_m
    )
    assert stiffness[3, 3] == pytest.approx(
        SECTION.shear_modulus_kpa * SECTION.torsion_constant_m4 / length_m
    )


def test_bending_terms_are_the_textbook_ones():
    length_m = 2.5
    stiffness = beam_stiffness_matrix(length_m, SECTION)
    modulus, inertia = SECTION.elastic_modulus_kpa, SECTION.strong_axis_inertia_m4

    assert stiffness[1, 1] == pytest.approx(12 * modulus * inertia / length_m**3)
    assert stiffness[1, 5] == pytest.approx(6 * modulus * inertia / length_m**2)
    assert stiffness[5, 5] == pytest.approx(4 * modulus * inertia / length_m)
    assert stiffness[5, 11] == pytest.approx(2 * modulus * inertia / length_m)


@pytest.mark.parametrize("dof", [0, 1, 2])
def test_moving_the_whole_element_costs_nothing(dof):
    """A rigid body translation must produce no force - the classic sanity check."""
    stiffness = beam_stiffness_matrix(2.5, SECTION)

    both_ends_move = np.zeros(12)
    both_ends_move[dof] = 1.0
    both_ends_move[dof + 6] = 1.0

    assert stiffness @ both_ends_move == pytest.approx(np.zeros(12), abs=1e-6)


def test_the_default_axis_needs_no_rotation():
    """A girder along the span with the usual local axis is already in global axes."""
    assert element_rotation_matrix((0.0, 0.0, 1.0)) == pytest.approx(np.eye(12))


def test_the_rotation_matrix_is_orthogonal():
    rotation = element_rotation_matrix((0.0, 1.0, 0.0))
    assert rotation @ rotation.T == pytest.approx(np.eye(12))
