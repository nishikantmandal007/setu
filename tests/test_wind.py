"""Wind per IRC:6-2017 clause 209 as replaced by Amendment 10 (MoRTH Notification 83, in force 1 Oct 2026).

Every expected value is the code's own: Table 1 (k1), Table 3 (k2), Table 4 (k2bar), Table 8 (CD), Tables A3.1 and A3.2
(pressures for Vb = 33 m/s, 50 years, k3 = k4 = 1), Table 5 (forces), Fig. 5 / Table 7 (exposed depth), Fig. 7 (CD depth),
209.5.2.2 (CL = 0.9, G by terrain category), 209.5.2.3 (wind on live load).
"""

import pytest

from setu.builder.assembly import build_bridge_model
from setu.irc6.wind import (
    CYCLONE_COAST,
    INLAND,
    OFFSHORE,
    check_scope,
    construction_drag_coefficient,
    cyclonic_importance_factor,
    design_wind_speed_mps,
    drag_depth_m,
    exposed_depth_m,
    gust_factor,
    hourly_mean_wind_speed_mps,
    needs_hourly_mean_method,
    risk_coefficient,
    service_drag_coefficient,
    terrain_height_factor,
    wind_pressure_pa,
)
from setu.postprocess.girder_response import analyze_load_case
from setu.loads.wind_loads import wind_load_cases
from setu.models.site import WindSite

pytest.importorskip("setu.solver.backend", reason="needs a finite element solver")
from setu.solver import backend  # noqa: E402

from test_design_forces import BRIDGE, SPAN_M  # noqa: E402

PA_PER_KPA = 1000.0
TABLE_A3_HEIGHTS_M = (10, 15, 20, 30, 50, 100, 150, 200, 250, 300)
TABLE_A3_1 = {  # Appendix 3 Table A3.1: peak gust pressure Pz, N/m2
    1: (720.37, 776.30, 819.62, 864.12, 940.90, 1037.34, 1104.25, 1138.48, 1173.25, 1190.82),
    2: (653.40, 720.37, 748.08, 819.62, 894.44, 1004.67, 1070.53, 1104.25, 1138.48, 1173.25),
    3: (541.08, 614.78, 666.53, 734.16, 819.62, 940.90, 1004.67, 1053.87, 1087.32, 1121.30),
    4: (418.18, 418.18, 418.18, 614.78, 790.61, 940.90, 1004.67, 1053.87, 1070.53, 1104.25),
}
TABLE_A3_2 = {  # Appendix 3 Table A3.2: hourly mean pressure pbar_z, N/m2
    1: (397.53, 439.35, 472.08, 505.99, 565.13, 640.40, 693.19, 734.16, 762.13, 776.30),
    2: (293.31, 329.38, 367.54, 407.79, 461.04, 553.04, 602.17, 640.40, 679.80, 706.72),
    3: (163.35, 197.65, 219.80, 267.63, 320.17, 407.79, 461.04, 505.99, 541.08, 565.13),
    4: (37.64, 58.81, 75.53, 104.54, 150.54, 219.80, 276.06, 311.08, 338.72, 367.54),
}


def site(**changes):
    values = dict(basic_wind_speed_mps=33.0, terrain_category=2, superstructure_top_m=12.0, road_level_m=10.0, pier_height_m=8.0,
                  return_period_years=50, valley_or_leeward_hill=False, cyclonic_region=INLAND, deck_cross_slope_deg=0.0,
                  solid_barrier_height_m=1.1)
    values.update(changes)
    return WindSite(**values)


@pytest.mark.parametrize("terrain_category", [1, 2, 3, 4])
def test_table_a3_1_peak_gust_pressures(terrain_category):
    for height_m, expected_pa in zip(TABLE_A3_HEIGHTS_M, TABLE_A3_1[terrain_category], strict=True):
        speed = design_wind_speed_mps(site(terrain_category=terrain_category), height_m, 50)
        assert wind_pressure_pa(speed) == pytest.approx(expected_pa, abs=0.01)


@pytest.mark.parametrize("terrain_category", [1, 2, 3, 4])
def test_table_a3_2_hourly_mean_pressures(terrain_category):
    for height_m, expected_pa in zip(TABLE_A3_HEIGHTS_M, TABLE_A3_2[terrain_category], strict=True):
        speed = hourly_mean_wind_speed_mps(site(terrain_category=terrain_category), height_m, 50)
        assert wind_pressure_pa(speed) == pytest.approx(expected_pa, abs=0.01)


def test_k2_is_constant_up_to_10_m_and_interpolated_between_rows():
    assert terrain_height_factor(4.0, 2) == pytest.approx(1.00)
    assert terrain_height_factor(12.5, 2) == pytest.approx((1.00 + 1.05) / 2)


@pytest.mark.parametrize("speed, years, k1", [(33.0, 100, 1.05), (44.0, 100, 1.07), (55.0, 10, 0.77), (47.0, 25, 0.91), (41.0, 50, 1.0)])
def test_table_1_risk_coefficient(speed, years, k1):
    assert risk_coefficient(speed, years) == pytest.approx(k1)


@pytest.mark.parametrize("speed, years", [(41.0, 100), (33.0, 75)])
def test_table_1_is_not_extrapolated(speed, years):
    with pytest.raises(ValueError, match="Table 1"):
        risk_coefficient(speed, years)


def test_k4_cyclonic_region():
    assert cyclonic_importance_factor(CYCLONE_COAST, 50.0) == pytest.approx(1.30)
    assert cyclonic_importance_factor(CYCLONE_COAST, 47.0) == pytest.approx(1.0)
    assert cyclonic_importance_factor(OFFSHORE, 33.0) == pytest.approx(1.5)
    assert cyclonic_importance_factor(INLAND, 55.0) == pytest.approx(1.0)


def test_k3_and_k4_multiply_the_speed():
    plain = design_wind_speed_mps(site(), 10.0, 50)
    assert design_wind_speed_mps(site(valley_or_leeward_hill=True), 10.0, 50) == pytest.approx(1.2 * plain)
    assert design_wind_speed_mps(site(basic_wind_speed_mps=50.0, cyclonic_region=CYCLONE_COAST), 10.0, 50) == pytest.approx(1.3 * 50.0)


@pytest.mark.parametrize("b_over_d, drag", [(0.5, 2.2), (1.0, 2.2), (1.5, 1.85), (2.0, 1.5), (4.0, 1.4), (6.0, 1.3), (10.0, 1.3)])
def test_table_8_service_drag_by_b_over_d(b_over_d, drag):
    assert service_drag_coefficient(b_over_d * 2.0, 2.0, 0.0) == pytest.approx(drag)


def test_table_8_note_7_camber_raises_drag_3_percent_per_degree_up_to_25():
    assert service_drag_coefficient(12.0, 2.0, 2.0) == pytest.approx(1.3 * 1.06)
    assert service_drag_coefficient(12.0, 2.0, 12.0) == pytest.approx(1.3 * 1.25)


def test_table_8_construction_drag():
    assert construction_drag_coefficient(1, 0.0, 2.0) == pytest.approx(2.5)
    assert construction_drag_coefficient(4, 3.0, 2.0) == pytest.approx(2.0 * (1 + 3.0 / 40.0))
    assert construction_drag_coefficient(4, 200.0, 2.0) == pytest.approx(4.0)


def test_fig_5_table_7_and_fig_7_depths():
    """Solid parapet 1.1 m on a 2.5 m deck: A1 depth 3.6 m without live load, max(3.6, 5.5) with it; CD depth d2 = 3.6 m > dL.
    Open parapet on a 2.5 m deck: d1 = 2.5 without, d3 = 5.5 with; CD depth d1 = 2.5 without, dL = 3.0 with (d1 < dL)."""
    assert exposed_depth_m(2.5, 1.1, False) == pytest.approx(3.6)
    assert exposed_depth_m(2.5, 1.1, True) == pytest.approx(5.5)
    assert drag_depth_m(2.5, 1.1, True) == pytest.approx(3.6)
    assert exposed_depth_m(2.5, 0.0, False) == pytest.approx(2.5)
    assert exposed_depth_m(2.5, 0.0, True) == pytest.approx(5.5)
    assert drag_depth_m(2.5, 0.0, False) == pytest.approx(2.5)
    assert drag_depth_m(2.5, 0.0, True) == pytest.approx(3.0)


def test_table_5_method_choice_and_scope():
    assert not needs_hourly_mean_method(40.0, 20.0)
    assert needs_hourly_mean_method(40.1, 8.0)
    assert needs_hourly_mean_method(35.0, 20.5)
    assert gust_factor(2) == 2.0 and gust_factor(3) == 2.5 and gust_factor(4) == 3.5
    with pytest.raises(ValueError, match="209.1"):
        check_scope(201.0, 10.0)


SITE = site(basic_wind_speed_mps=39.0, return_period_years=100)


@pytest.mark.parametrize("key,value", [("drag", -1.), ("exposed_area_m2", float("nan")),
                                       ("plan_area_m2", -1.), ("live_load_exposed_area_m2", float("inf")),
                                       ("force_height_above_deck_m", float("nan")), ("terrain_category", 5), ("pier_height_m", 0.0)])
def test_invalid_wind_inputs_are_rejected(key, value):
    with pytest.raises(ValueError, match=key):
        WindSite(**{**vars(SITE), key: value})


def _reactions_under(model, case):
    """Total support reactions: every node's reaction summed, so the rigid links' internal pairs cancel."""
    with backend.solved(case.nodal_loads, case.element_loads, pattern=101):
        backend.calculate_reactions()
        tags = backend.node_tags()
        totals = [sum(backend.node_reaction(node, dof) for node in tags) for dof in (1, 2, 3)]

    return totals


def _support_shear_of_each_girder(model, case):
    """Per girder: internal shear just inside the first support. A girder pushed down reads negative, one lifted reads positive.

    Reactions at single nodes are not used here: OpenSees reports rigid-link constraint forces
    as nodal reactions too, so only the total over all nodes is a clean reaction.
    """
    forces = analyze_load_case(model, case)
    return [forces[girder].shear_kn[0] for girder in sorted(forces)]


@pytest.fixture(scope="module")
def wind_cases():
    model = build_bridge_model(BRIDGE)
    return model, wind_load_cases(model, SITE)


def test_the_supports_take_the_transverse_force(wind_cases):
    model, cases = wind_cases
    _, up_kn, across_kn = _reactions_under(model, cases["transverse from the left"])

    assert -across_kn == pytest.approx(cases.forces_kn["transverse"], rel=1e-9)
    assert abs(up_kn) < 1e-6 * cases.forces_kn["transverse"]


def test_transverse_wind_acts_at_the_centroid_of_its_area(wind_cases):
    """209.5.2.1: F_T acts at the centroid of A1, halfway between the girder soffit and the barrier top (Fig. 5, d2 above the road).

    Taken to the deck nodes (at slab mid-depth), that is a moment of F_T x (barrier - girder depth) / 2 about the span.
    """
    model, cases = wind_cases
    case = cases["transverse from the left"]
    pushed_kn = sum(fz for _, _, _, fz, *_ in case.nodal_loads)
    twisted_kn_m = sum(mx for _, _, _, _, mx, _, _ in case.nodal_loads)

    assert pushed_kn == pytest.approx(cases.forces_kn["transverse"])
    assert twisted_kn_m == pytest.approx(cases.forces_kn["transverse"] * (SITE.solid_barrier_height_m + BRIDGE.deck.wearing_course_thickness_m - model.girder.depth_m) / 2)


def test_transverse_wind_is_in_equilibrium_about_the_span(wind_cases):
    """Applied moment about the span axis, force heights included, is balanced by the supports.

    Checked to 1e-3 of F_T x deck width. The model closes moment balance to about 2e-4 of that
    scale for any load at all (a plain vertical force shows the same), from how OpenSees reports
    reactions at rigid-linked nodes, so a tighter check would test OpenSees, not the wind load.
    """
    _, cases = wind_cases
    case = cases["transverse from the left"]
    applied_kn_m = 0.0
    for node, _, fy, fz, mx, _, _ in case.nodal_loads:
        _, y_m, z_m = backend.node_coordinates(node)
        applied_kn_m += y_m * fz - z_m * fy + mx
    with backend.solved(case.nodal_loads, case.element_loads, pattern=101):
        backend.calculate_reactions()
        resisted_kn_m = 0.0
        for node in backend.node_tags():
            _, ry, rz, rmx, _, _ = backend.node_reactions(node)
            _, y_m, z_m = backend.node_coordinates(node)
            resisted_kn_m += y_m * rz - z_m * ry + rmx


    assert applied_kn_m + resisted_kn_m == pytest.approx(0.0, abs=1e-3 * cases.forces_kn["transverse"] * BRIDGE.width_m())


def test_wind_from_either_side_mirrors(wind_cases):
    model, cases = wind_cases
    from_left = _support_shear_of_each_girder(model, cases["transverse from the left"])
    from_right = _support_shear_of_each_girder(model, cases["transverse from the right"])

    assert from_left == pytest.approx(from_right[::-1], rel=1e-9, abs=1e-9)


def test_the_supports_take_the_vertical_and_longitudinal_forces(wind_cases):
    """The longitudinal case carries the full F_T; Table 5 column 2 takes 25 % of it (the coefficient pair (1, 0.25))."""
    model, cases = wind_cases
    _, up_kn, _ = _reactions_under(model, cases["vertical upward, B/4 left"])
    _, down_kn, _ = _reactions_under(model, cases["vertical downward, B/4 right"])
    along_kn, _, _ = _reactions_under(model, cases["longitudinal"])

    assert up_kn == pytest.approx(-cases.forces_kn["vertical"], rel=1e-9)
    assert down_kn == pytest.approx(cases.forces_kn["vertical"], rel=1e-9)
    assert -along_kn == pytest.approx(cases.forces_kn["transverse"], rel=1e-9)
    assert cases.directions == [(1.0, 0.25)]
    assert cases.forces_kn["longitudinal"] == pytest.approx(0.25 * cases.forces_kn["transverse"])


def test_vertical_wind_acts_at_b_over_4(wind_cases):
    """Table 5: the eccentricity of F_V is B/4 from the deck centre."""
    model, cases = wind_cases
    case = cases["vertical upward, B/4 left"]
    total_kn = sum(fy for _, _, fy, *_ in case.nodal_loads)
    moment_kn_m = sum(fy * backend.node_coordinates(node)[2] for node, _, fy, *_ in case.nodal_loads)

    assert moment_kn_m / total_kn == pytest.approx(BRIDGE.width_m() / 2 - BRIDGE.width_m() / 4, rel=1e-9)


def test_the_forces_by_hand(wind_cases):
    """35 m span on 8 m piers: Table 5 column 2. Vb 39 m/s, 100 years (k1 1.06), TC2 at 12 m (k2 = 1.00 + 0.4 x 0.05 = 1.02).
    Vz = 39 x 1.06 x 1.02; Pz = 0.6 Vz^2. A1 depth = girder + slab + surfacing + 1.1 m barrier (Fig. 5, solid, no live load);
    CD from Table 8 at B / d with d the same depth (> dL = 3 m). F_V = Pz x span x width x 0.9. Wind on live load: 1.2 x span x
    (3.0 - 1.1) at z = road level 10 m + 3 m = 13 m (k2 = 1.00 + 0.6 x 0.05 = 1.03)."""
    model, cases = wind_cases
    pz_kpa = 0.6 * (39 * 1.06 * 1.02) ** 2 / PA_PER_KPA
    depth_m = model.girder.depth_m + BRIDGE.deck.thickness_m + BRIDGE.deck.wearing_course_thickness_m + 1.1
    b_over_d = BRIDGE.width_m() / depth_m
    drag = 1.5 + (b_over_d - 2.0) * (1.3 - 1.5) / 4.0
    pz_live_kpa = 0.6 * (39 * 1.06 * 1.03) ** 2 / PA_PER_KPA

    assert 2.0 < b_over_d < 6.0
    assert cases.forces_kn["transverse"] == pytest.approx(pz_kpa * SPAN_M * depth_m * drag)
    assert cases.forces_kn["vertical"] == pytest.approx(pz_kpa * SPAN_M * BRIDGE.width_m() * 0.9)
    assert cases.forces_kn["on live load, transverse"] == pytest.approx(pz_live_kpa * SPAN_M * (3.0 - 1.1) * 1.2)


def test_with_live_load_the_area_reaches_the_top_of_the_vehicles(wind_cases):
    """Table 7, solid parapet: with live load dtot = max(d2, d3), d3 = road depth + 3 m."""
    model, cases = wind_cases
    road_m = model.girder.depth_m + BRIDGE.deck.thickness_m + BRIDGE.deck.wearing_course_thickness_m
    ratio = cases.forces_kn["transverse, with live load"] / cases.forces_kn["transverse"]

    assert ratio == pytest.approx((road_m + 3.0) / (road_m + 1.1))


def test_a_long_span_takes_the_larger_method_and_the_skew_directions():
    """Table 5 column 3 (span > 40 m): max of Pz A1 CD and pbar A1 G CD, resolved by the Table 6 'other spans' pairs."""
    long_bridge = type(BRIDGE)(**{**vars(BRIDGE), "span_m": 50.0})
    model = build_bridge_model(long_bridge)
    cases = wind_load_cases(model, SITE)
    pz = wind_pressure_pa(design_wind_speed_mps(SITE, 12.0, 100))
    pbar_g = wind_pressure_pa(hourly_mean_wind_speed_mps(SITE, 12.0, 100)) * 2.0

    assert cases.directions == [(1.00, 0.00), (0.88, 0.12), (0.82, 0.24), (0.66, 0.32), (0.34, 0.38)]
    depth_m = model.girder.depth_m + BRIDGE.deck.thickness_m + BRIDGE.deck.wearing_course_thickness_m + 1.1
    drag = 1.5 + (BRIDGE.width_m() / depth_m - 2.0) * (1.3 - 1.5) / 4.0
    assert pbar_g != pytest.approx(pz)
    assert cases.forces_kn["transverse"] == pytest.approx(max(pz, pbar_g) / PA_PER_KPA * 50.0 * depth_m * drag)


@pytest.mark.parametrize("name", ["transverse from the left", "longitudinal", "vertical upward, B/4 left", "on live load from the right", "transverse from the right, with live load"])
def test_a_load_case_read_through_its_influence_surface_matches_a_real_solve(wind_cases, name):
    """Reciprocity: response = (adjoint displacements) . (nodal loads), the same as solving the load case."""
    from setu.analysis.influence_surface import InfluenceSolver, response_to_load_case

    model, cases = wind_cases
    midspan = model.mesh.stations_along_span // 2
    surface = InfluenceSolver(model.as_deck_model()).for_girder_composite_moment("m", model.midspan_element_of_girder(1))

    solved = analyze_load_case(model, cases[name])[1].composite_moment_kn_m[midspan]

    assert response_to_load_case(surface, cases[name]) == pytest.approx(solved, rel=1e-9, abs=1e-9)
