import pytest
from setu.postprocess.girder_response import GirderForces


def test_girder_forces_stores_arrays():
    f = GirderForces(
        stations_m=[0, 5, 10],
        moment_kn_m=[0, -100, 0],
        shear_kn=[50, 0, -50],
        torsion_kn_m=[1, 2, 3],
        axial_kn=[0, 0, 0],
        composite_lever_arm_m=0.0,
        deflection_m=[0, 0.01, 0],
        reaction_kn=50.0,
    )
    assert len(f.stations_m) == 3
    assert f.moment_kn_m[1] == -100


def test_composite_moment_adds_the_axial_couple():
    f = GirderForces([0.0], [100.0], [0.0], [0.0], [-50.0], 1.2, [0.0], 0.0)
    assert f.composite_moment_kn_m[0] == pytest.approx(100.0 - 60.0)
