"""Dead load in the stages IRC:22-2015 clauses 601.1 and 604.1.1 ask for, un-propped as OsdagBridge builds it.

The bare steel carries its own weight and the wet slab; the composite section, with
long-term concrete, carries the surfacing that goes on afterwards.
"""

import pytest

from setu.builder.assembly import build_bridge_model
from setu.loads.dead_loads import construction_stage_load, superimposed_dead_load
from setu.models.bridge import Bracing, BridgeInput, DeckSlab
from setu.postprocess.girder_response import analyze_load_case, dead_load_forces

pytest.importorskip("openseespy.opensees", reason="needs a finite element solver")
import openseespy.opensees as ops  # noqa: E402

from test_design_forces import BRIDGE, CROSS_SECTION, SPAN_M  # noqa: E402

SLAB_UNIT_WEIGHT_KN_M3 = 25.0
NEARLY_WEIGHTLESS_BRACING_M2 = 1e-4


def _bridge():
    return BridgeInput(**{**BRIDGE.__dict__, "deck": DeckSlab(thickness_m=0.23, overhang_m=1.25, wearing_course_thickness_m=0.075),
                          "bracing": Bracing(station_count=7, area_m2=NEARLY_WEIGHTLESS_BRACING_M2, arrangement="XT")})


def test_the_steel_alone_carries_the_wet_slab():
    """An inner girder of the bare steel frame is a simple beam: M = w L^2 / 8 at midspan."""
    bridge = _bridge()
    model = build_bridge_model(bridge, composite=False)
    midspan = model.mesh.stations_along_span // 2
    girder = 2
    spacing_m = model.mesh.girder_lines_m[girder + 1] - model.mesh.girder_lines_m[girder]
    w_kn_m = SLAB_UNIT_WEIGHT_KN_M3 * bridge.deck.thickness_m * spacing_m + bridge.steel.unit_weight_kn_m3 * model.girder.area_m2

    forces = analyze_load_case(model, construction_stage_load(model), ops)

    assert forces[girder].moment_kn_m[midspan] == pytest.approx(w_kn_m * SPAN_M ** 2 / 8, rel=0.01)


def test_the_construction_stage_puts_down_the_whole_slab():
    bridge = _bridge()
    model = build_bridge_model(bridge, composite=False)
    slab_kn = SLAB_UNIT_WEIGHT_KN_M3 * bridge.deck.thickness_m * bridge.width_m() * SPAN_M
    steel_kn = bridge.steel.unit_weight_kn_m3 * model.girder.area_m2 * SPAN_M * bridge.girders.count

    case = construction_stage_load(model)
    on_the_nodes_kn = -sum(fy for _, _, fy, *_ in case.nodal_loads)
    on_the_elements_kn = -sum(parameters[0] for _, _, parameters in case.element_loads) * SPAN_M / (model.mesh.stations_along_span - 1)

    assert on_the_nodes_kn + on_the_elements_kn == pytest.approx(slab_kn + steel_kn, rel=0.01)


def test_surfacing_goes_on_the_composite_deck():
    bridge = _bridge()
    model = build_bridge_model(bridge)

    case = superimposed_dead_load(model)

    assert case.nodal_loads
    assert {node for node, *_ in case.nodal_loads} <= set(model.deck_nodes.values())


def test_three_stages():
    assert set(dead_load_forces(_bridge()).stages) == {"construction", "superimposed", "surfacing"}


def test_surfacing_is_kept_apart_for_its_own_factor():
    """Table B.2 factors surfacing at 1.75 and the rest of the dead load at 1.35, so they cannot be lumped."""
    result = dead_load_forces(_bridge())
    midspan = len(result.total[2].moment_kn_m) // 2
    surfacing = result.stages["surfacing"][2].composite_moment_kn_m[midspan]
    everything_else = sum(result.stages[stage][2].composite_moment_kn_m[midspan] for stage in ("construction", "superimposed"))

    factored = result.factored({"dead": 1.35, "surfacing": 1.75})[2].composite_moment_kn_m[midspan]

    assert surfacing > 0
    assert factored == pytest.approx(1.35 * everything_else + 1.75 * surfacing, rel=1e-12)


def test_superimposed_load_puts_down_exactly_what_the_strips_carry():
    """A node on a strip boundary takes each strip's pressure over its own share of the node's width."""
    bridge = _bridge()
    model = build_bridge_model(bridge)
    added = bridge.added_dead_loads
    pressures = {"footpath": added.footpath.pressure_kpa, "kerb": added.kerb.pressure_kpa, "median": added.median.pressure_kpa}
    expected_kn = sum(strip.width_m * SPAN_M * pressures.get(strip.name.split("_")[0], 0.0) for strip in CROSS_SECTION.strips)

    applied_kn = -sum(fy for _, _, fy, *_ in superimposed_dead_load(model).nodal_loads)

    assert applied_kn == pytest.approx(expected_kn, rel=1e-9)


def test_a_symmetric_deck_loads_its_girders_symmetrically():
    result = dead_load_forces(_bridge())
    midspan = len(result.total[0].moment_kn_m) // 2
    last = len(result.total) - 1

    for girder in range(len(result.total) // 2):
        assert result.total[girder].composite_moment_kn_m[midspan] == pytest.approx(result.total[last - girder].composite_moment_kn_m[midspan], rel=1e-6)


def test_the_wearing_course_on_the_deck_is_loaded():
    model = build_bridge_model(_bridge())
    from setu.loads.dead_loads import surfacing_load
    carriageway_m = sum(strip.width_m for strip in CROSS_SECTION.strips if strip.carries_traffic())

    applied_kn = -sum(fy for _, _, fy, *_ in surfacing_load(model).nodal_loads)

    assert applied_kn == pytest.approx(0.075 * 22.0 * carriageway_m * SPAN_M, rel=1e-9)
