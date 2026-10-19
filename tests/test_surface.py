"""Reading an influence surface: between stations, off the deck, and on a skew."""


import numpy as np
import pytest

from setu.analysis.influence_surface import InfluenceSurface
from setu.errors import InfluenceSurfaceError


def flat_surface(gradient_along: float = 2.0, gradient_across: float = 3.0):
    """A surface that is exactly a plane, so interpolation has a known answer."""
    length_mesh_m = np.linspace(0.0, 10.0, 11)
    width_mesh_m = np.linspace(0.0, 5.0, 6)
    values = gradient_along * length_mesh_m[:, None] + gradient_across * width_mesh_m[None, :]
    return InfluenceSurface(
        values=values, length_mesh_m=length_mesh_m, width_mesh_m=width_mesh_m, name="a plane", skew=0.0
    )


def test_reads_back_the_value_at_a_station():
    surface = flat_surface()
    assert surface.influence_at(4.0, 3.0) == pytest.approx(2 * 4.0 + 3 * 3.0)


def test_interpolates_exactly_on_a_plane():
    """Bilinear reading is exact for a plane, so any point in between is known."""
    surface = flat_surface()
    for x_m, z_m in [(4.37, 2.81), (0.05, 4.99), (9.5, 0.5)]:
        assert surface.influence_at(x_m, z_m) == pytest.approx(2 * x_m + 3 * z_m)


def test_off_the_deck_reads_zero():
    """So a vehicle only part-way onto the bridge needs no special case."""
    surface = flat_surface()
    assert surface.influence_at(-1.0, 2.0) == 0.0
    assert surface.influence_at(11.0, 2.0) == 0.0
    assert surface.influence_at(5.0, -0.5) == 0.0
    assert surface.influence_at(5.0, 5.5) == 0.0


def test_reads_many_points_at_once():
    surface = flat_surface()
    x_m = np.array([1.0, 2.0, 3.0])
    z_m = np.array([1.0, 1.0, 1.0])

    read_together = surface.influence_at(x_m, z_m)
    read_singly = [
        surface.influence_at(float(x), float(z)) for x, z in zip(x_m, z_m, strict=True)
    ]

    assert read_together == pytest.approx(read_singly)


def test_a_skewed_deck_is_read_on_its_own_grid():
    """The mesh is a parallelogram, so a global point is sheared back onto it."""
    length_mesh_m = np.linspace(0.0, 10.0, 11)
    width_mesh_m = np.linspace(0.0, 5.0, 6)
    values = np.tile(length_mesh_m[:, None], (1, len(width_mesh_m)))

    square = InfluenceSurface(values=values, length_mesh_m=length_mesh_m, width_mesh_m=width_mesh_m, name="square", skew=0.0)
    skewed = InfluenceSurface(values=values, length_mesh_m=length_mesh_m, width_mesh_m=width_mesh_m, name="skewed", skew=0.5)

    # a point 0.5 * z further along the skewed deck is the same point on its grid
    assert skewed.influence_at(4.0 + 0.5 * 3.0, 3.0) == pytest.approx(
        square.influence_at(4.0, 3.0)
    )


def test_a_grid_that_does_not_match_the_mesh_is_refused():
    with pytest.raises(InfluenceSurfaceError, match="deck mesh"):
        InfluenceSurface(
            values=np.zeros((3, 3)),
            length_mesh_m=np.linspace(0, 1, 4),
            width_mesh_m=np.linspace(0, 1, 3),
            name="mismatched",
            skew=0.0,
        )


# a surface carrying the six adjoint displacements of a few nodes, for reciprocity
def surface_with_nodes(node_tags, displacements):
    plane = flat_surface()
    return InfluenceSurface(plane.values, plane.length_mesh_m, plane.width_mesh_m, "with nodes", 0.0,
                            node_tags=np.asarray(node_tags, int), every_node_displacement=np.asarray(displacements, float))


# reciprocity is the sum of every force times its node's adjoint displacement, whatever order the loads come in
def test_reciprocity_adds_force_times_displacement():
    from setu.analysis.influence_surface import response_to_load_case
    from setu.loads.load_cases import LoadCase

    rng = np.random.default_rng(71)
    displacements = rng.normal(size=(40, 6))
    forces = rng.normal(size=(40, 6))
    surface = surface_with_nodes(100 + np.arange(40), displacements)
    loads = [(100 + row, *force.tolist()) for row, force in enumerate(forces)][::-1]
    expected = sum(float(f @ d) for f, d in zip(forces, displacements))
    assert response_to_load_case(surface, LoadCase("random", loads)) == pytest.approx(expected, rel=1e-12)
    assert response_to_load_case(surface, LoadCase("twice", loads + loads[:1])) == pytest.approx(expected + float(forces[-1] @ displacements[-1]), rel=1e-12)


# empty cases, absent nodes, deck-only surfaces and element loads keep their boundary behaviour
def test_reciprocity_validates_loads():
    from setu.analysis.influence_surface import response_to_load_case
    from setu.loads.load_cases import LoadCase

    surface = surface_with_nodes([7], np.zeros((1, 6)))
    assert response_to_load_case(surface, LoadCase("empty")) == 0.0
    for missing in (8, 6):
        with pytest.raises(KeyError):
            response_to_load_case(surface, LoadCase("missing", [(missing, 0., 1., 0., 0., 0., 0.)]))
    with pytest.raises(ValueError, match="deck ordinates"):
        response_to_load_case(flat_surface(), LoadCase("one", [(7, 0., 1., 0., 0., 0., 0.)]))
    with pytest.raises(ValueError, match="element loads"):
        response_to_load_case(surface, LoadCase("elements", element_loads=[(1, "-beamUniform", (1., 0.))]))
