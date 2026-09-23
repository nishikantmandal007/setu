"""Braking per IRC:6-2017 clauses 211.2 and 211.3.

211.2 (a): one lane only - 20 % of the first train plus 10 % of the trains after it; where the
first train is not all on the span, 20 % of the loads actually on it. (b) more than two lanes:
as (a) for the first two lanes plus 5 % of the loads on the lanes beyond two. No impact.
211.3: acts parallel to the road, 1.2 m above it.

A Class A train carries 2.7 + 2.7 + 11.4 + 11.4 + 4 x 6.8 = 55.4 t = 543.474 kN.
"""

import pytest

from setu.analysis.results import CriticalPosition, VehiclePlacement
from setu.builder.assembly import build_bridge_model
from setu.irc6.braking import braking_force_kn
from setu.loads.braking_loads import braking_load_cases
from setu.loads.load_cases import apply_load_case

pytest.importorskip("openseespy.opensees", reason="needs a finite element solver")
import openseespy.opensees as ops  # noqa: E402

from test_design_forces import BRIDGE, SPAN_M, _configure_a_static_analysis  # noqa: E402

CLASS_A_KN = 55.4 * 9.81
CLASS_A_PITCH_M = 0.6 + 18.8 + 0.9 + 18.5


def _lanes(*trains_per_lane, impact=1.3):
    vehicles = [
        VehiclePlacement("Class_A", z_centre_m=3.0 + 3.5 * lane, x_front_m=trains[0], impact_factor=impact, train_x_front_m=tuple(trains))
        for lane, trains in enumerate(trains_per_lane)
    ]
    return CriticalPosition("test", "maximum", 0.0, 0.0, 1.0, len(vehicles), "", "separate", vehicles=vehicles)


def test_one_train_all_on_the_span():
    """20 % of 543.474 kN = 108.695 kN, and impact plays no part."""
    assert braking_force_kn(_lanes((5.0,)), span_m=35.0) == pytest.approx(0.2 * CLASS_A_KN)


def test_part_of_the_first_train_off_the_span():
    """Front axle at 30 m: axles at 30, 31.1, 34.2 m are on (2.7 + 2.7 + 11.4 t); the rest is past the far end."""
    on_the_span_kn = (2.7 + 2.7 + 11.4) * 9.81

    assert braking_force_kn(_lanes((30.0,)), span_m=35.0) == pytest.approx(0.2 * on_the_span_kn)


def test_a_train_following_the_first():
    """90 m span, two trains a pitch apart: 20 % of the first plus 10 % of the second."""
    assert braking_force_kn(_lanes((5.0, 5.0 + CLASS_A_PITCH_M)), span_m=90.0) == pytest.approx(0.3 * CLASS_A_KN)


def test_two_lanes_count_one_lane_only():
    assert braking_force_kn(_lanes((5.0,), (5.0,)), span_m=35.0) == pytest.approx(0.2 * CLASS_A_KN)


def test_three_lanes_add_five_percent_of_the_third():
    assert braking_force_kn(_lanes((5.0,), (5.0,), (5.0,)), span_m=35.0) == pytest.approx(0.2 * CLASS_A_KN + 0.05 * CLASS_A_KN)


@pytest.fixture(scope="module")
def braking():
    model = build_bridge_model(BRIDGE)
    critical = _lanes((5.0,), (5.0,))
    return model, braking_load_cases(model, critical)


def _totals(case):
    _configure_a_static_analysis()
    apply_load_case(case, ops, pattern_tag=102)
    ops.reset()
    ops.setTime(0.0)
    ops.analyze(1)
    ops.reactions()
    tags = ops.getNodeTags()
    along_kn = sum(ops.nodeReaction(node, 1) for node in tags)
    up_kn = sum(ops.nodeReaction(node, 2) for node in tags)
    ops.remove("loadPattern", 102)
    ops.remove("timeSeries", 102)
    return along_kn, up_kn


def test_the_supports_take_the_braking_force(braking):
    _, cases = braking
    along_kn, up_kn = _totals(cases["forwards"])

    assert -along_kn == pytest.approx(cases.force_kn, rel=1e-9)
    assert abs(up_kn) < 1e-9 * cases.force_kn


def test_braking_acts_1_2_m_above_the_road(braking):
    """Taken to the deck nodes (slab mid-depth), the force carries a moment of F x (slab/2 + wearing course + 1.2 m)."""
    model, cases = braking
    lever_m = BRIDGE.deck.thickness_m / 2 + BRIDGE.wearing_course_thickness_m + 1.2
    case = cases["forwards"]

    assert sum(fx for _, fx, *_ in case.nodal_loads) == pytest.approx(cases.force_kn)
    assert sum(mz for *_, mz in case.nodal_loads) == pytest.approx(-lever_m * cases.force_kn)


def test_braking_either_way(braking):
    _, cases = braking

    assert [load[1] for load in cases["backwards"].nodal_loads] == pytest.approx([-load[1] for load in cases["forwards"].nodal_loads])
