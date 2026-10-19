"""Failed solves must not export a plausible-looking result or poison the next case."""

import numpy as np
import pytest

from setu.analysis.influence_surface import InfluenceSolver
from setu.builder.assembly import build_bridge_model
from setu.errors import BackendError
from setu.loads.load_cases import LoadCase
from setu.postprocess.girder_response import analyze_load_case

ops = pytest.importorskip("openseespy.opensees")
from test_design_forces import BRIDGE


def test_solved_observer_sees_active_case_and_failure_still_cleans_up():
    model = build_bridge_model(BRIDGE)
    case = LoadCase("observed point load", [(model.deck_nodes[3, 5], 0., -100., 0., 0., 0., 0.)])

    def observe(forces):
        assert ops.getPatterns()
        assert sum(f.reaction_kn + f.end_reaction_kn for f in forces.values()) == pytest.approx(100.)
        raise RuntimeError("observer stopped")

    with pytest.raises(RuntimeError, match="observer stopped"):
        analyze_load_case(model, case, ops, on_solved=observe)
    assert not ops.getPatterns()
    forces = analyze_load_case(model, case, ops)
    assert sum(f.reaction_kn + f.end_reaction_kn for f in forces.values()) == pytest.approx(100.)


@pytest.mark.parametrize("raises", [False, True])
def test_failed_physical_case_cleans_up_and_can_be_followed_by_a_good_solve(monkeypatch, raises):
    model = build_bridge_model(BRIDGE)
    node = model.deck_nodes[3, 5]
    case = LoadCase("failed point load", [(node, 0., -100., 0., 0., 0., 0.)])

    def fail(_):
        if raises:
            raise RuntimeError("solver stopped")
        return -3

    with monkeypatch.context() as patch:
        patch.setattr(ops, "analyze", fail)
        with pytest.raises(RuntimeError if raises else BackendError):
            analyze_load_case(model, case, ops, pattern_tag=151)
    assert not ops.getPatterns()
    forces = analyze_load_case(model, case, ops)
    assert all(np.isfinite(f.composite_moment_kn_m).all() for f in forces.values())
    assert sum(f.reaction_kn + f.end_reaction_kn for f in forces.values()) == pytest.approx(100., rel=1e-8)


@pytest.mark.parametrize("raises", [False, True])
def test_failed_influence_solve_cleans_custom_pattern_and_recovers(monkeypatch, raises):
    model = build_bridge_model(BRIDGE)
    solver = InfluenceSolver(model.as_deck_model())
    backend = solver.backend
    node = model.deck_nodes[3, 5]

    def fail(_):
        if raises:
            raise RuntimeError("solver stopped")
        return -2

    with monkeypatch.context() as patch:
        patch.setattr(ops, "analyze", fail)
        with pytest.raises(RuntimeError if raises else BackendError):
            backend.solve_with_loads([(node, [0., -1., 0., 0., 0., 0.])], pattern=152)
    assert not ops.getPatterns()
    surface = solver.for_girder_composite_moment("recovered", model.midspan_element_of_girder(1))
    assert np.isfinite(surface.values).all() and np.abs(surface.values).max() > 0
    assert not ops.getPatterns()

