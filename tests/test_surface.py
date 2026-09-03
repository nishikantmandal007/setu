"""Reading an influence surface: between stations, off the deck, and on a skew."""


import numpy as np
import pytest

from setu.services.influence_surface import InfluenceSurface
from setu.utils.errors import InfluenceSurfaceError


def flat_surface(gradient_along: float = 2.0, gradient_across: float = 3.0):
    """A surface that is exactly a plane, so interpolation has a known answer."""
    length_mesh_m = np.linspace(0.0, 10.0, 11)
    width_mesh_m = np.linspace(0.0, 5.0, 6)
    values = gradient_along * length_mesh_m[:, None] + gradient_across * width_mesh_m[None, :]
    return InfluenceSurface(
        values=values, length_mesh_m=length_mesh_m, width_mesh_m=width_mesh_m, name="a plane"
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

    square = InfluenceSurface(
        values=values, length_mesh_m=length_mesh_m, width_mesh_m=width_mesh_m
    )
    skewed = InfluenceSurface(
        values=values, length_mesh_m=length_mesh_m, width_mesh_m=width_mesh_m, skew=0.5
    )

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
        )


def test_a_saved_surface_reads_back_the_same(tmp_path):
    surface = flat_surface()
    path = tmp_path / "surface.npz"
    surface.save(str(path))

    read_back = InfluenceSurface.load(str(path))

    assert read_back.values == pytest.approx(surface.values)
    assert read_back.name == surface.name


def test_a_saved_surface_keeps_what_it_describes(tmp_path):
    """describes must round-trip too, not just the grid and the name."""
    surface = InfluenceSurface(
        values=np.zeros((3, 3)),
        length_mesh_m=np.linspace(0.0, 1.0, 3),
        width_mesh_m=np.linspace(0.0, 1.0, 3),
        describes={"response": "girder_moment", "element": 12, "dof": 5},
    )
    path = tmp_path / "surface.npz"
    surface.save(str(path))

    read_back = InfluenceSurface.load(str(path))

    assert read_back.describes == surface.describes
