"""Wind on the superstructure per IRC:6-2017 clause 209.

Every expected value below is worked from the code text: Table 12 and its notes,
F_T = Pz A1 G C_D (209.3.3), F_L = 0.25 F_T (209.3.4), F_V = Pz A3 G C_L (209.3.5),
and wind on the live load (209.3.6).
"""

import pytest

from setu.builder.assembly import build_bridge_model
from setu.irc6.wind import (
    drag_coefficient,
    hourly_mean_wind,
    longitudinal_wind_force_kn,
    transverse_wind_force_kn,
    vertical_wind_force_kn,
    wind_on_live_load_kn,
)
from setu.loads.load_cases import apply_load_case
from setu.postprocess.girder_response import analyze_load_case
from setu.loads.wind_loads import wind_load_cases
from setu.models.site import WindSite
from setu.utils.constants import OBSTRUCTED_TERRAIN, PLAIN_TERRAIN

pytest.importorskip("openseespy.opensees", reason="needs a finite element solver")
import openseespy.opensees as ops  # noqa: E402

from test_design_forces import BRIDGE, SPAN_M, _configure_a_static_analysis  # noqa: E402

PA_PER_KPA = 1000.0


def test_table_12_up_to_10_m():
    speed_mps, pressure_pa = hourly_mean_wind(height_m=6.0, terrain=PLAIN_TERRAIN)

    assert speed_mps == pytest.approx(27.80)
    assert pressure_pa == pytest.approx(463.70)


def test_table_12_the_90_m_row():
    assert hourly_mean_wind(90.0, PLAIN_TERRAIN)[1] == pytest.approx(729.00)
    assert hourly_mean_wind(90.0, OBSTRUCTED_TERRAIN)[1] == pytest.approx(454.20)


def test_table_12_note_1_interpolates():
    """25 m sits halfway between 20 m (550.6) and 30 m (590.2): 570.4."""
    assert hourly_mean_wind(25.0, PLAIN_TERRAIN)[1] == pytest.approx(570.4)


def test_table_12_notes_3_and_4_scale_with_basic_wind_speed():
    """Vb = 39 m/s: speed x 39/33, pressure x (39/33)^2."""
    speed_mps, pressure_pa = hourly_mean_wind(10.0, PLAIN_TERRAIN, basic_wind_speed_mps=39.0)

    assert speed_mps == pytest.approx(27.80 * 39.0 / 33.0)
    assert pressure_pa == pytest.approx(463.70 * (39.0 / 33.0) ** 2)


def test_table_12_notes_5_and_6():
    """Funnelling topography: +20 %. Construction stage: 70 %."""
    assert hourly_mean_wind(10.0, PLAIN_TERRAIN, funnelling=True)[1] == pytest.approx(463.70 * 1.2)
    assert hourly_mean_wind(10.0, PLAIN_TERRAIN, construction=True)[1] == pytest.approx(463.70 * 0.7)


def test_clause_209_1_limits():
    with pytest.raises(ValueError, match="100 m"):
        hourly_mean_wind(120.0, PLAIN_TERRAIN)
    with pytest.raises(ValueError, match="150 m"):
        transverse_wind_force_kn(0.4637, exposed_area_m2=10.0, drag=2.0, span_m=160.0)


def test_drag_coefficient_for_plate_girders():
    """One girder: 2.2. Several: 2(1 + c / 20d), not more than 4."""
    assert drag_coefficient(girder_count=1, girder_spacing_m=0.0, girder_depth_m=2.0) == pytest.approx(2.2)
    assert drag_coefficient(5, 2.75, 2.2) == pytest.approx(2.0 * (1.0 + 2.75 / (20.0 * 2.2)))
    assert drag_coefficient(5, 20.0, 1.0) == pytest.approx(4.0)
    assert drag_coefficient(5, 30.0, 1.0) == pytest.approx(4.0)


def test_the_three_wind_forces():
    """Pz = 463.7 Pa, A1 = 35 x 3.5 = 122.5 m2, G = 2.0, CD = 2.125, A3 = 35 x 13.5 m2, CL = 0.75."""
    pz_kpa = 463.7 / PA_PER_KPA

    transverse = transverse_wind_force_kn(pz_kpa, exposed_area_m2=122.5, drag=2.125, span_m=35.0)
    assert transverse == pytest.approx(0.4637 * 122.5 * 2.0 * 2.125)
    assert longitudinal_wind_force_kn(transverse) == pytest.approx(0.25 * transverse)
    assert vertical_wind_force_kn(pz_kpa, plan_area_m2=35.0 * 13.5, span_m=35.0) == pytest.approx(0.4637 * 472.5 * 2.0 * 0.75)


def test_wind_on_the_live_load():
    """C_D 1.2 on a 3.0 m band above the road, less what hides behind a 1.1 m solid barrier."""
    pz_kpa = 463.7 / PA_PER_KPA

    transverse, longitudinal = wind_on_live_load_kn(pz_kpa, span_m=35.0, solid_barrier_height_m=1.1)

    assert transverse == pytest.approx(0.4637 * (35.0 * (3.0 - 1.1)) * 2.0 * 1.2)
    assert longitudinal == pytest.approx(0.25 * transverse)


def test_user_values_replace_the_code_values():
    """OsdagBridge lets the user override G, C_D and C_L; the clause then uses the user's number."""
    pz_kpa = 0.5

    assert transverse_wind_force_kn(pz_kpa, 100.0, drag=2.0, span_m=35.0, gust=2.5) == pytest.approx(0.5 * 100.0 * 2.5 * 2.0)
    assert vertical_wind_force_kn(pz_kpa, 100.0, span_m=35.0, lift=1.0) == pytest.approx(0.5 * 100.0 * 2.0 * 1.0)


SITE = WindSite(basic_wind_speed_mps=39.0, terrain=PLAIN_TERRAIN, height_m=12.0, solid_barrier_height_m=1.1)


def _reactions_under(model, case):
    """Total support reactions: every node's reaction summed, so the rigid links' internal pairs cancel."""
    _configure_a_static_analysis()
    apply_load_case(case, ops, pattern_tag=101)
    ops.reset()
    ops.setTime(0.0)
    ops.analyze(1)
    ops.reactions()
    tags = ops.getNodeTags()
    totals = [sum(ops.nodeReaction(node, dof) for node in tags) for dof in (1, 2, 3)]
    ops.remove("loadPattern", 101)
    ops.remove("timeSeries", 101)
    return totals


def _support_shear_of_each_girder(model, case):
    """Per girder: internal shear just inside the first support. A girder pushed down reads negative, one lifted reads positive.

    Reactions at single nodes are not used here: OpenSees reports rigid-link constraint forces
    as nodal reactions too, so only the total over all nodes is a clean reaction.
    """
    forces = analyze_load_case(model, case, ops)
    return [forces[girder].shear_kn[0] for girder in sorted(forces)]


@pytest.fixture(scope="module")
def wind_cases():
    model = build_bridge_model(BRIDGE)
    return model, wind_load_cases(model, SITE)


def test_the_supports_take_the_transverse_force(wind_cases):
    model, cases = wind_cases
    along_kn, up_kn, across_kn = _reactions_under(model, cases["transverse from the left"])

    assert -across_kn == pytest.approx(cases.forces_kn["transverse"], rel=1e-9)
    assert abs(up_kn) < 1e-6 * cases.forces_kn["transverse"]


def test_transverse_wind_acts_at_the_centroid_of_its_area(wind_cases):
    """209.3.3: F_T acts at the centroid of A1, halfway between the girder soffit and the barrier top.

    Taken to the deck nodes (at slab mid-depth), that is a moment of F_T x (barrier - girder depth) / 2 about the span.
    """
    model, cases = wind_cases
    case = cases["transverse from the left"]
    pushed_kn = sum(fz for _, _, _, fz, *_ in case.nodal_loads)
    twisted_kn_m = sum(mx for _, _, _, _, mx, _, _ in case.nodal_loads)

    assert pushed_kn == pytest.approx(cases.forces_kn["transverse"])
    assert twisted_kn_m == pytest.approx(cases.forces_kn["transverse"] * (SITE.solid_barrier_height_m - model.girder.depth_m) / 2)


def test_transverse_wind_is_in_equilibrium_about_the_span(wind_cases):
    """Applied moment about the span axis, force heights included, is balanced by the supports.

    Checked to 1e-3 of F_T x deck width. The model closes moment balance to about 2e-4 of that
    scale for any load at all (a plain vertical force shows the same), from how OpenSees reports
    reactions at rigid-linked nodes, so a tighter check would test OpenSees, not the wind load.
    """
    model, cases = wind_cases
    case = cases["transverse from the left"]
    applied_kn_m = 0.0
    for node, _, fy, fz, mx, _, _ in case.nodal_loads:
        _, y_m, z_m = ops.nodeCoord(node)
        applied_kn_m += y_m * fz - z_m * fy + mx
    _configure_a_static_analysis()
    apply_load_case(case, ops, pattern_tag=101)
    ops.reset()
    ops.setTime(0.0)
    ops.analyze(1)
    ops.reactions()
    resisted_kn_m = 0.0
    for node in ops.getNodeTags():
        _, ry, rz, rmx, _, _ = ops.nodeReaction(node)
        _, y_m, z_m = ops.nodeCoord(node)
        resisted_kn_m += y_m * rz - z_m * ry + rmx
    ops.remove("loadPattern", 101)
    ops.remove("timeSeries", 101)

    assert applied_kn_m + resisted_kn_m == pytest.approx(0.0, abs=1e-3 * cases.forces_kn["transverse"] * BRIDGE.width_m())


def test_wind_from_either_side_mirrors(wind_cases):
    model, cases = wind_cases
    from_left = _support_shear_of_each_girder(model, cases["transverse from the left"])
    from_right = _support_shear_of_each_girder(model, cases["transverse from the right"])

    assert from_left == pytest.approx(from_right[::-1], rel=1e-9, abs=1e-9)


def test_the_supports_take_the_vertical_and_longitudinal_forces(wind_cases):
    model, cases = wind_cases
    _, up_kn, _ = _reactions_under(model, cases["vertical upward"])
    _, down_kn, _ = _reactions_under(model, cases["vertical downward"])
    along_kn, _, _ = _reactions_under(model, cases["longitudinal"])

    assert up_kn == pytest.approx(-cases.forces_kn["vertical"], rel=1e-9)
    assert down_kn == pytest.approx(cases.forces_kn["vertical"], rel=1e-9)
    assert -along_kn == pytest.approx(cases.forces_kn["longitudinal"], rel=1e-9)


def test_the_wind_site_works_out_the_areas(wind_cases):
    """A1 = span x (girder depth + slab + solid barrier); A3 = span x deck width."""
    model, cases = wind_cases
    depth_m = model.girder.depth_m + BRIDGE.deck.thickness_m + SITE.solid_barrier_height_m
    _, pressure_pa = hourly_mean_wind(12.0, PLAIN_TERRAIN, basic_wind_speed_mps=39.0)
    drag = drag_coefficient(BRIDGE.girders.count, model.mesh.girder_spacing_m, model.girder.depth_m)

    assert cases.forces_kn["transverse"] == pytest.approx(pressure_pa / PA_PER_KPA * SPAN_M * depth_m * 2.0 * drag)
    assert cases.forces_kn["vertical"] == pytest.approx(pressure_pa / PA_PER_KPA * SPAN_M * BRIDGE.width_m() * 2.0 * 0.75)
