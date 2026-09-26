"""User loads, as OsdagBridge's Custom Load tab places them.

A point (kN), line (kN/m) or area (kPa) load, placed by its distance from the centre line of
the first bearing (along the road) and from the left edge of the deck (across it), and
filed under DL, SIDL, DW, LL, EL, WL, TL or a group of the user's own naming.
"""

import pytest

from setu.analysis.influence_surface import InfluenceSolver
from setu.builder.assembly import build_bridge_model
from setu.loads.custom_loads import custom_load_cases
from setu.models.bridge import BridgeInput
from setu.models.custom_load import CustomLoad
from setu.utils.constants import AREA, LINE, POINT
from setu.postprocess.girder_response import analyze_load_case
from setu.utils.constants import DEAD, SURFACING, WIND

pytest.importorskip("openseespy.opensees", reason="needs a finite element solver")
import openseespy.opensees as ops  # noqa: E402

from test_design_forces import BRIDGE, CROSS_SECTION, SPAN_M  # noqa: E402


def _downward_total_kn(case):
    return -sum(fy for _, _, fy, *_ in case.nodal_loads)


@pytest.fixture(scope="module")
def model():
    return build_bridge_model(BRIDGE)


def test_a_point_load_puts_down_its_magnitude(model):
    cases = custom_load_cases(model, [CustomLoad("DL", POINT, 50.0, x_from_bearing_m=12.3, z_from_left_edge_m=4.1)])

    assert _downward_total_kn(cases[DEAD]) == pytest.approx(50.0)


def test_a_line_load_puts_down_intensity_times_length(model):
    """A diagonal line from (5, 2) to (20, 10): length 17 m, at 3 kN/m = 51 kN."""
    load = CustomLoad("SIDL", LINE, 3.0, x_from_bearing_m=5.0, z_from_left_edge_m=2.0, x_end_m=20.0, z_end_m=10.0)

    assert _downward_total_kn(custom_load_cases(model, [load])[DEAD]) == pytest.approx(3.0 * 17.0)


def test_an_area_load_puts_down_pressure_times_area(model):
    """A 10 m x 4 m patch at 2.5 kPa = 100 kN."""
    load = CustomLoad("DW", AREA, 2.5, x_from_bearing_m=3.0, z_from_left_edge_m=5.0, x_end_m=13.0, z_end_m=9.0)

    assert _downward_total_kn(custom_load_cases(model, [load])[SURFACING]) == pytest.approx(100.0)


def test_loads_are_filed_under_their_groups(model):
    loads = [
        CustomLoad("DL", POINT, 10.0, 5.0, 5.0),
        CustomLoad("SIDL", POINT, 10.0, 6.0, 5.0),
        CustomLoad("WL", POINT, 10.0, 7.0, 5.0),
        CustomLoad("hoarding", POINT, 10.0, 8.0, 5.0),
    ]
    cases = custom_load_cases(model, loads)

    assert set(cases) == {DEAD, WIND, "hoarding"}
    assert _downward_total_kn(cases[DEAD]) == pytest.approx(20.0)


def test_a_load_off_the_deck_is_refused(model):
    with pytest.raises(ValueError, match="off the deck"):
        custom_load_cases(model, [CustomLoad("DL", POINT, 10.0, x_from_bearing_m=SPAN_M + 2.0, z_from_left_edge_m=4.0)])


@pytest.mark.parametrize("skew", [0.0, 0.2])
def test_a_point_load_gives_back_the_influence_surface(skew):
    """Reciprocity: the girder's moment under P at a point equals P times the surface there."""
    bridge = BridgeInput(**{**BRIDGE.__dict__, "skew": skew})
    model = build_bridge_model(bridge)
    midspan = model.mesh.stations_along_span // 2
    surface = InfluenceSolver(model.as_deck_model()).for_girder_composite_moment("m", model.midspan_element_of_girder(1))
    x_along_m, z_m = 14.7, 4.6
    cases = custom_load_cases(model, [CustomLoad("LL", POINT, 80.0, x_from_bearing_m=x_along_m, z_from_left_edge_m=z_m)])

    forces = analyze_load_case(model, cases["live"], ops)

    assert forces[1].composite_moment_kn_m[midspan] == pytest.approx(80.0 * surface.influence_at(x_along_m + skew * z_m, z_m), rel=1e-6)
