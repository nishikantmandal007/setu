"""Failed solves must not export a plausible-looking result or poison the next case."""

import numpy as np
import pytest

from setu.analysis.influence_surface import InfluenceSolver
from setu.builder.assembly import build_bridge_model
from setu.errors import BackendError, OtherLoadsStillActiveError
from setu.loads.dead_loads import steel_self_weight_load
from setu.loads.load_cases import LoadCase, apply_load_case
from setu.postprocess.girder_response import analyze_load_case

backend = pytest.importorskip("setu.solver.backend")
from test_design_forces import BRIDGE


def test_solved_observer_sees_active_case_and_failure_still_cleans_up():
    model = build_bridge_model(BRIDGE)
    case = LoadCase("observed point load", [(model.deck_nodes[3, 5], 0., -100., 0., 0., 0., 0.)])

    def observe(forces):
        assert backend.load_patterns()
        assert sum(f.reaction_kn + f.end_reaction_kn for f in forces.values()) == pytest.approx(100.)
        raise RuntimeError("observer stopped")

    with pytest.raises(RuntimeError, match="observer stopped"):
        analyze_load_case(model, case, on_solved=observe)
    assert not backend.load_patterns()
    forces = analyze_load_case(model, case)
    assert sum(f.reaction_kn + f.end_reaction_kn for f in forces.values()) == pytest.approx(100.)


def test_alternating_solves_share_one_configuration_until_a_new_model(monkeypatch):
    configured = []
    configure = backend.configure_linear_static

    def count_configuration():
        configured.append(True)
        configure()

    monkeypatch.setattr(backend, "configure_linear_static", count_configuration)
    for expected in (1, 2):
        model = build_bridge_model(BRIDGE)
        case = LoadCase("point load", [(model.deck_nodes[3, 5], 0., -100., 0., 0., 0., 0.)])
        first = analyze_load_case(model, case)
        for _ in range(2):
            solver = InfluenceSolver(model.as_deck_model())
            solver.for_deflection("deflection", model.deck_nodes[3, 5])
            again = analyze_load_case(model, case)
            for girder in first:
                np.testing.assert_array_equal(again[girder].composite_moment_kn_m, first[girder].composite_moment_kn_m)
        for _ in range(2):
            weight = steel_self_weight_load(model)
            gravity = analyze_load_case(model, weight)
            applied_kn = -sum(load[2] for load in weight.nodal_loads) + sum(
                model.bridge.steel.unit_weight_kn_m3 * girder.area_m2 * model.bridge.span_m for girder in model.girders)
            assert sum(f.reaction_kn + f.end_reaction_kn for f in gravity.values()) == pytest.approx(applied_kn)
            again = analyze_load_case(model, case)
            for girder in first:
                np.testing.assert_array_equal(again[girder].composite_moment_kn_m, first[girder].composite_moment_kn_m)
        assert len(configured) == expected


def test_influence_refuses_an_active_case_without_removing_it():
    model = build_bridge_model(BRIDGE)
    solver = InfluenceSolver(model.as_deck_model())
    apply_load_case(LoadCase("existing case"), pattern_tag=153)
    try:
        with pytest.raises(OtherLoadsStillActiveError):
            solver.for_deflection("blocked", model.deck_nodes[3, 5])
        assert backend.load_patterns() == [153]
    finally:
        backend.remove_loads(153)


def test_failed_load_application_cleans_up_and_recovers(monkeypatch):
    model = build_bridge_model(BRIDGE)
    apply = backend.apply_loads

    def interrupted(*args, **kwargs):
        apply(*args, **kwargs)
        raise RuntimeError("load application stopped")

    with monkeypatch.context() as patch:
        patch.setattr(backend, "apply_loads", interrupted)
        with pytest.raises(RuntimeError, match="load application stopped"):
            analyze_load_case(model, LoadCase("interrupted"), pattern_tag=154)
    assert not backend.load_patterns()
    analyze_load_case(model, LoadCase("recovered"), pattern_tag=154)
    assert not backend.load_patterns()


@pytest.mark.parametrize("raises", [False, True])
def test_failed_physical_case_cleans_up_and_can_be_followed_by_a_good_solve(monkeypatch, raises):
    model = build_bridge_model(BRIDGE)
    node = model.deck_nodes[3, 5]
    case = LoadCase("failed point load", [(node, 0., -100., 0., 0., 0., 0.)])

    def fail():
        if raises:
            raise RuntimeError("solver stopped")
        return -3

    with monkeypatch.context() as patch:
        patch.setattr(backend, "analyze", fail)
        with pytest.raises(RuntimeError if raises else BackendError):
            analyze_load_case(model, case, pattern_tag=151)
    assert not backend.load_patterns()
    forces = analyze_load_case(model, case)
    assert all(np.isfinite(f.composite_moment_kn_m).all() for f in forces.values())
    assert sum(f.reaction_kn + f.end_reaction_kn for f in forces.values()) == pytest.approx(100., rel=1e-8)


@pytest.mark.parametrize("raises", [False, True])
def test_failed_influence_solve_cleans_custom_pattern_and_recovers(monkeypatch, raises):
    model = build_bridge_model(BRIDGE)
    solver = InfluenceSolver(model.as_deck_model())
    influence_backend = solver.backend
    node = model.deck_nodes[3, 5]

    def fail():
        if raises:
            raise RuntimeError("solver stopped")
        return -2

    with monkeypatch.context() as patch:
        patch.setattr(backend, "analyze", fail)
        with pytest.raises(RuntimeError if raises else BackendError):
            with influence_backend.solved([(node, [0., -1., 0., 0., 0., 0.])], pattern=152):
                pytest.fail("a failed solve must not yield")
    assert not backend.load_patterns()
    surface = solver.for_girder_composite_moment("recovered", model.midspan_element_of_girder(1))
    assert np.isfinite(surface.values).all() and np.abs(surface.values).max() > 0
    assert not backend.load_patterns()

