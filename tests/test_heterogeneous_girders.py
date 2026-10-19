"""Individual sections must reach the FE model, influence responses and staged results."""

import copy

import numpy as np
import pytest

from setu import Girders, analyze_load_case, bearing_reactions, brace_forces, build_bridge_model
from setu.analysis.influence_surface import InfluenceSolver
from setu.loads.dead_loads import steel_self_weight_load
from setu.loads.load_cases import LoadCase
from setu.loads.seismic_loads import dead_weight_at_nodes
from setu.models.bridge import Bracing, BridgeInput, MeshSettings
from setu.postprocess.design_values import places_to_design, surface_for, reader, girder_design_values
from setu.postprocess.thermal_stresses import primary_thermal_stresses
from setu.utils.constants import MAX_MOMENT, SUPPORT_SHEAR, BEARING_REACTION

backend = pytest.importorskip("setu.solver.backend")
from test_design_forces import BRIDGE


def bridge_with_sections(*, skew=0.2, arrangement="XT", uniform=False):
    sections = [copy.copy(BRIDGE.girders.section_at(0)) for _ in range(BRIDGE.girders.count)]
    if not uniform:
        for index, section in enumerate(sections):
            section.web_height_m += index * 0.12
            section.bottom_flange_thickness_m += index * 0.003
    return BridgeInput(**{**vars(BRIDGE), "skew": skew,
                          "girders": Girders(len(sections), sections=sections),
                          "bracing": Bracing(arrangement, 3, 0.01),
                          "mesh": MeshSettings(2, 1.5)})


@pytest.mark.parametrize("kwargs", [{}, {"section": BRIDGE.girders.section, "sections": []}, {"sections": []},
                                  {"sections": [None] * 5}])
def test_sections_must_be_unambiguous_and_match_the_count(kwargs):
    with pytest.raises(ValueError):
        Girders(5, **kwargs)


@pytest.mark.parametrize("count", [0, 1, 2.5, True])
def test_invalid_girder_count_is_rejected(count):
    with pytest.raises(ValueError):
        Girders(count, BRIDGE.girders.section)


def test_section_lookup_rejects_an_out_of_range_girder():
    with pytest.raises(IndexError):
        BRIDGE.girders.section_at(-1)
    with pytest.raises(IndexError):
        BRIDGE.girders.section_at(5)


@pytest.mark.parametrize("arrangement", ["XTB", "KT"])
def test_unequal_depths_keep_the_girder_tops_under_the_slab(arrangement):
    bridge = bridge_with_sections(arrangement=arrangement)
    model = build_bridge_model(bridge)
    for k, section in enumerate(bridge.girders.sections):
        assert backend.node_coordinates(model.top_brace_nodes[k, 0])[1] == pytest.approx(-bridge.deck.thickness_m / 2)
        assert backend.node_coordinates(model.bottom_brace_nodes[k, 0])[1] == pytest.approx(-bridge.deck.thickness_m / 2 - section.depth_m)
        assert backend.node_coordinates(model.girder_nodes[k, 0])[1] == pytest.approx(-model.composite_lever_arm_m(k))
    for (k, station), node in model.k_brace_nodes.items():
        ends = [backend.node_coordinates(model.bottom_brace_nodes[g, station])[1] for g in (k, k + 1)]
        assert backend.node_coordinates(node)[1] == pytest.approx(sum(ends) / 2)


def test_each_girder_contributes_its_own_self_weight_and_seismic_weight():
    bridge = bridge_with_sections()
    model = build_bridge_model(bridge)
    case = steel_self_weight_load(model)
    by_element = {tag: -parameters[0] for tag, _, parameters in case.element_loads}
    for k, section in enumerate(bridge.girders.sections):
        area = (section.top_flange_width_m * section.top_flange_thickness_m
                + section.bottom_flange_width_m * section.bottom_flange_thickness_m
                + section.web_height_m * section.web_thickness_m)
        assert by_element[model.girder_elements[k, 0]] == pytest.approx(area * bridge.steel.unit_weight_kn_m3)
    from setu.loads.dead_loads import wet_slab_load, superimposed_dead_load, surfacing_load
    vertical = case.nodal_loads + wet_slab_load(model).nodal_loads + superimposed_dead_load(model).nodal_loads + surfacing_load(model).nodal_loads
    expected = sum(by_element.values()) * bridge.span_m / (model.mesh.stations_along_span - 1) - sum(load[2] for load in vertical)
    assert sum(dead_weight_at_nodes(model).values()) == pytest.approx(expected, rel=1e-10)


@pytest.mark.parametrize("skew", [0.0, 0.2])
def test_uniform_section_list_reproduces_the_existing_input(skew):
    listed = bridge_with_sections(skew=skew, uniform=True)
    shared = BridgeInput(**{**vars(listed), "girders": BRIDGE.girders})
    solved = []
    for bridge in (listed, shared):
        model = build_bridge_model(bridge)
        node = model.deck_nodes[2, 4]
        forces = analyze_load_case(model, LoadCase("point", [(node, 0., -100., 0., 0., 0., 0.)]))
        solved.append({k: (f.composite_moment_kn_m.copy(), f.deflection_m.copy()) for k, f in forces.items()})
    for k in solved[0]:
        np.testing.assert_allclose(solved[0][k], solved[1][k], rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("skew", [0.0, 0.2])
def test_heterogeneous_influence_responses_match_direct_solves(skew):
    model = build_bridge_model(bridge_with_sections(skew=skew))
    solver = InfluenceSolver(model.as_deck_model())
    station = model.mesh.stations_along_span // 2
    far = model.mesh.stations_along_span - 1
    probe = (2, model.mesh.width_station_of_girder(3))
    node = model.deck_nodes[probe]
    for k in (0, 3):
        for place in ((MAX_MOMENT, station), (SUPPORT_SHEAR, 0), (SUPPORT_SHEAR, far), (BEARING_REACTION, far)):
            surface = surface_for(solver, model, k, place)
            forces = analyze_load_case(model, LoadCase("unit", [(node, 0., -1., 0., 0., 0., 0.)]))
            direct = reader({})(forces, k, place)
            assert surface.values[probe] == pytest.approx(direct, rel=1e-7, abs=1e-10)
        element = model.girder_elements[k, station]
        section = model.girders[k]
        stress = solver.for_girder_stress_mpa("flange stress", element, section, section.depth_m)
        forces = analyze_load_case(model, LoadCase("unit", [(node, 0., -1., 0., 0., 0., 0.)]))[k]
        direct_mpa = (forces.axial_kn[station] / section.area_m2 + forces.moment_kn_m[station]
                      * (section.neutral_axis_from_bottom_m - section.depth_m) / section.strong_axis_inertia_m4) / 1000
        assert stress.values[probe] == pytest.approx(direct_mpa, rel=1e-7, abs=1e-10)
        end_moment = solver.for_girder_composite_moment("end j moment", element, end="j")
        analyze_load_case(model, LoadCase("unit", [(node, 0., -1., 0., 0., 0., 0.)]))
        end_forces = backend.element_local_forces(element)
        direct_moment = end_forces[11] + model.composite_lever_arm_m(k) * end_forces[6]
        assert end_moment.values[probe] == pytest.approx(direct_moment, rel=1e-7, abs=1e-10)


def test_heterogeneous_design_covers_both_halves_and_bearings():
    model = build_bridge_model(bridge_with_sections())
    places = places_to_design(model)
    far = model.mesh.stations_along_span - 1
    moment_stations = {station for response, station in places if response == MAX_MOMENT}
    assert moment_stations == {far - station for station in moment_stations}
    assert (SUPPORT_SHEAR, far) in places and (BEARING_REACTION, far) in places


def test_thermal_layers_use_the_requested_girder():
    bridge = bridge_with_sections(skew=0.)
    profile = [(0., 20.), (3., 0.)]
    first = primary_thermal_stresses(bridge, 0, profile)
    last = primary_thermal_stresses(bridge, 4, profile)
    assert last.layers[-1][0] > first.layers[-1][0]
    assert last.steel_bottom_kpa != pytest.approx(first.steel_bottom_kpa)


def test_unequal_depth_wind_requires_engineer_supplied_geometry_and_drag():
    from setu.loads.wind_loads import wind_load_cases
    from setu import WindSite
    from test_design_values import WIND_SITE
    bridge = bridge_with_sections()
    model = build_bridge_model(bridge)
    overrides = dict(exposed_area_m2=100., drag=2.1270207852193996, force_height_above_deck_m=-0.4)
    for missing in overrides:
        incomplete = {k: v for k, v in overrides.items() if k != missing}
        with pytest.raises(ValueError, match="unequal-depth wind requires"):
            wind_load_cases(model, WindSite(**{**vars(WIND_SITE), **incomplete}))
    site = WindSite(**{**vars(WIND_SITE), **overrides})
    cases = wind_load_cases(model, site)
    from setu.irc6.wind import hourly_mean_wind
    _, pressure_pa = hourly_mean_wind(site.height_m, site.terrain, site.basic_wind_speed_mps, site.funnelling)
    expected = pressure_pa / 1000 * 2 * 100 * overrides["drag"]
    assert cases.forces_kn["transverse"] == pytest.approx(expected)
    for name, sign in (("transverse from the left", 1), ("transverse from the right", -1)):
        assert sum(load[3] for load in cases[name].nodal_loads) == pytest.approx(sign * expected)
        assert sum(load[4] for load in cases[name].nodal_loads) == pytest.approx(
            sign * expected * (site.force_height_above_deck_m + bridge.deck.thickness_m / 2))


@pytest.mark.parametrize("arrangement", ["XTB", "KT"])
def test_native_reactions_and_brace_forces_obey_equilibrium(arrangement):
    model = build_bridge_model(bridge_with_sections(arrangement=arrangement))
    node = model.deck_nodes[1, model.mesh.width_station_of_girder(1)]
    point = LoadCase("eccentric point", [(node, 0., -100., 0., 0., 0., 0.)])
    forces = analyze_load_case(model, point)
    reactions = bearing_reactions(model)
    braces = brace_forces(model)
    assert sum(reactions.values()) == pytest.approx(100., rel=1e-8)
    far = model.mesh.stations_along_span - 1
    assert sum(r for (_, end), r in reactions.items() if end == 0) > sum(r for (_, end), r in reactions.items() if end == far)
    assert forces[1].end_reaction_kn == pytest.approx(reactions[1, far])
    assert set(braces) == set(model.brace_elements)
    assert any(station == 0 for _, station, _ in braces) and any(station == 2 for _, station, _ in braces)
    assert min(braces.values()) < 0 < max(braces.values())
    backend.calculate_reactions()
    # For a corotTruss, positive axial force pulls node i towards node j.
    key = max(braces, key=lambda key: abs(braces[key]))
    tag = model.brace_elements[key]
    start, end = backend.element_nodes(tag)
    direction = np.subtract(backend.node_coordinates(end), backend.node_coordinates(start))
    direction /= np.linalg.norm(direction)
    global_force = backend.element_forces(tag)
    assert np.dot(global_force[:3], direction) == pytest.approx(-braces[key], rel=1e-7)


def test_high_level_heterogeneous_results_are_finite():
    results = girder_design_values(bridge_with_sections(), braking_height_above_deck_m=0.)
    for k, by_response in results.girders.items():
        for by_state in by_response.values():
            for by_direction in by_state.values():
                for value in by_direction.values():
                    assert np.isfinite(value.value)
        assert results.fatigue_stresses_mpa[k]["steel top"].range > 0
        for stage in results.dead.stages.values():
            assert stage[k].end_reaction_kn is not None

