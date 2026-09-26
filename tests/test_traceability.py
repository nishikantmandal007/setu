"""Traceability: what setu exports for MIDAS is exactly what it solved, and results reach OsdagBridge in its xarray layout."""

import pytest

from setu.analysis.critical_position import find_critical_position
from setu.analysis.influence_surface import InfluenceSolver
from setu.builder.assembly import build_bridge_model
from setu.loads.load_builders import applied_live_loads, live_load
from setu.models.bridge import BridgeInput
from setu.postprocess.girder_response import analyze_load_case
from setu.postprocess.result_dataset import FORCE_COMPONENTS, result_dataset

pytest.importorskip("openseespy.opensees", reason="needs a finite element solver")
import openseespy.opensees as ops  # noqa: E402

from test_design_forces import BRIDGE, CROSS_SECTION, SPAN_M  # noqa: E402

SKEW = 0.2


def _critical_on(bridge):
    model = build_bridge_model(bridge)
    surface = InfluenceSolver(model.as_deck_model()).for_girder_composite_moment("girder 0", model.midspan_element_of_girder(0))
    return model, surface, find_critical_position(surface, CROSS_SECTION, SPAN_M, "maximum", bridge.wearing_course_thickness_m)


@pytest.fixture(scope="module", params=[0.0, SKEW], ids=["square", "skewed"])
def traced(request):
    bridge = BridgeInput(**{**BRIDGE.__dict__, "skew": request.param})
    model, surface, critical = _critical_on(bridge)
    wheels, patches = applied_live_loads(bridge, critical, surface)
    return bridge, model, surface, critical, wheels, patches


def test_the_exported_rows_add_up_to_the_load_that_was_solved(traced):
    _, model, surface, critical, wheels, patches = traced
    exported_kn = sum(w["applied_kn"] for w in wheels if w["on_span"])
    exported_kn += sum(p["pressure_kpa"] * (p["along_to_m"] - p["along_from_m"]) * (p["z_to_m"] - p["z_from_m"]) for p in patches)

    solved_kn = -sum(fy for _, _, fy, *_ in live_load(model, critical, surface).nodal_loads)

    assert exported_kn == pytest.approx(solved_kn, rel=1e-9)


def test_every_kind_of_live_load_is_exported(traced):
    *_, wheels, patches = traced

    assert wheels and all(w["applied_kn"] == pytest.approx(w["wheel_load_kn"] * w["impact_factor"] * w["lane_reduction"]) for w in wheels)
    assert {p["kind"] for p in patches} == {"residual UDL", "footway"}


def test_patch_corners_follow_the_skew(traced):
    bridge, *_, patches = traced
    for patch in patches:
        (x1, z1), (x2, _), (x3, z3), (x4, _) = patch["corners_x_z_m"]
        assert x1 == pytest.approx(patch["along_from_m"] + bridge.skew * z1)
        assert x2 == pytest.approx(patch["along_to_m"] + bridge.skew * z1)
        assert x3 == pytest.approx(patch["along_to_m"] + bridge.skew * z3)
        assert x4 == pytest.approx(patch["along_from_m"] + bridge.skew * z3)


def test_the_result_dataset_is_in_osdagbridge_layout(traced):
    _, model, surface, critical, *_ = traced
    forces = analyze_load_case(model, live_load(model, critical, surface), ops)
    dataset = result_dataset(model, ops, "live")
    midspan_element = model.midspan_element_of_girder(0)

    assert dataset["forces"].dims == ("Loadcase", "Element", "Component")
    assert dataset["displacements"].dims == ("Loadcase", "Node", "Component")
    assert set(FORCE_COMPONENTS) <= set(dataset["Component"].values)
    # OpenSees end-i forces act on the element, so the internal moment is minus Mz_i
    mz_i = float(dataset["forces"].sel(Loadcase="live", Element=midspan_element, Component="Mz_i"))
    assert -mz_i == pytest.approx(forces[0].moment_kn_m[model.mesh.stations_along_span // 2], rel=1e-9)
