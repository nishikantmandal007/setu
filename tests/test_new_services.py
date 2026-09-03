import numpy as np
import pytest
from setu.services.girder_response import GirderForces, GirderDeflections
from setu.services.load_cases import LoadCase, combine
from setu.services.envelope import Envelope, envelope, irc6_uls_recipes, irc6_sls_recipes


def test_girder_forces_stores_arrays():
    f = GirderForces(
        stations_m=[0, 5, 10],
        moment_kn_m=[0, -100, 0],
        shear_kn=[50, 0, -50],
        torsion_kn_m=[1, 2, 3],
        axial_kn=[0, 0, 0],
    )
    assert len(f.stations_m) == 3
    assert f.moment_kn_m[1] == -100


def test_girder_deflections_stores_arrays():
    d = GirderDeflections(stations_m=[0, 5, 10], vertical_m=[0, -0.01, 0])
    assert d.vertical_m[1] == pytest.approx(-0.01)


def test_load_case_combine_sums_nodal_loads():
    dl = LoadCase("dead", nodal_loads=[(1, 0, -10, 0, 0, 0, 0)])
    ll = LoadCase("live", nodal_loads=[(1, 0, -5, 0, 0, 0, 0)])
    combined = combine([dl, ll], [1.35, 1.50])
    assert len(combined.nodal_loads) == 1
    _, _, fy, _, _, _, _ = combined.nodal_loads[0]
    assert fy == pytest.approx(1.35 * (-10) + 1.50 * (-5))


def test_load_case_combine_different_nodes():
    a = LoadCase("a", nodal_loads=[(1, 0, -10, 0, 0, 0, 0)])
    b = LoadCase("b", nodal_loads=[(2, 0, -5, 0, 0, 0, 0)])
    combined = combine([a, b], [1.0, 1.0])
    assert len(combined.nodal_loads) == 2


def test_envelope_picks_max():
    forces_a = GirderForces([0, 5, 10], [10, 50, 10], [5, 0, -5], [0, 0, 0], [0, 0, 0])
    forces_b = GirderForces([0, 5, 10], [20, 30, 20], [8, 0, -8], [0, 0, 0], [0, 0, 0])
    env = envelope({"case_a": forces_a, "case_b": forces_b}, adverse="maximum")
    assert env.moment_kn_m[0] == pytest.approx(20)
    assert env.governing_case[0] == "case_b"
    assert env.moment_kn_m[1] == pytest.approx(50)
    assert env.governing_case[1] == "case_a"


def test_envelope_picks_min():
    forces_a = GirderForces([0, 5, 10], [-10, -50, -10], [5, 0, -5], [0, 0, 0], [0, 0, 0])
    forces_b = GirderForces([0, 5, 10], [-20, -30, -20], [8, 0, -8], [0, 0, 0], [0, 0, 0])
    env = envelope({"case_a": forces_a, "case_b": forces_b}, adverse="minimum")
    assert env.moment_kn_m[0] == pytest.approx(-20)
    assert env.governing_case[0] == "case_b"
    assert env.moment_kn_m[1] == pytest.approx(-50)
    assert env.governing_case[1] == "case_a"


def test_uls_recipes_have_dead_and_live():
    recipes = irc6_uls_recipes()
    assert len(recipes) >= 1
    first = next(iter(recipes.values()))
    assert "dead" in first


def test_sls_recipes_exist():
    recipes = irc6_sls_recipes()
    assert len(recipes) >= 1


def test_plots_importable():
    plotly = pytest.importorskip("plotly", reason="plotly not installed")
    from setu.services.plots import (
        plot_bending_moment,
        plot_shear_force,
        plot_torsion,
        plot_deflection,
        plot_girder_summary,
        plot_envelope,
    )
    assert callable(plot_bending_moment)


def test_load_builders_importable():
    from setu.services.load_builders import (
        pressure_load,
        line_load,
        point_load,
        temperature_gradient,
    )
    assert callable(pressure_load)
