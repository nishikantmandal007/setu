"""Bearing reactions, deflections, fatigue and the moment sections: each checked against a real solve or the clause."""

import numpy as np
import pytest

from setu.analysis.critical_position import find_critical_position
from setu.analysis.fatigue import fatigue_range
from setu.analysis.influence_surface import InfluenceSolver
from setu.builder.assembly import BEARING_VERTICAL_STIFFNESS_KN_PER_M, build_bridge_model
from setu.helpers import DEFAULT_SAMPLING
from setu.irc6.fatigue import centreline_band_m, fatigue_impact_factor, fatigue_truck_offsets
from setu.loads.load_cases import LoadCase
from setu.postprocess.design_values import places_to_design
from setu.postprocess.girder_response import analyze_load_case, dead_load_forces
from setu.utils.constants import MAX_MOMENT

pytest.importorskip("openseespy.opensees", reason="needs a finite element solver")
import openseespy.opensees as ops  # noqa: E402

from test_design_forces import BRIDGE, CROSS_SECTION, PROBE_NODES, SPAN_M  # noqa: E402


@pytest.fixture(scope="module")
def solved():
    """Reaction and deflection surfaces of girder 1, then real unit loads at the probe nodes."""
    model = build_bridge_model(BRIDGE)
    deck = model.as_deck_model()
    solver = InfluenceSolver(deck)
    midspan = model.mesh.stations_along_span // 2
    deflection_node = model.deck_nodes[midspan, model.mesh.width_station_of_girder(1)]
    reaction = solver.for_bearing_reaction("girder 1 bearing", model.bearings[1, 0], BEARING_VERTICAL_STIFFNESS_KN_PER_M)
    deflection = solver.for_deflection("girder 1 midspan deflection", deflection_node)
    measured = {}
    for probe in PROBE_NODES:
        unit = LoadCase("unit", nodal_loads=[(deck.deck_nodes[probe], 0.0, -1.0, 0.0, 0.0, 0.0, 0.0)])
        forces = analyze_load_case(model, unit, ops)[1]
        x_m, z_m = float(deck.length_mesh_m[probe[0]]), float(deck.width_mesh_m[probe[1]])
        measured[probe] = (reaction.influence_at(x_m, z_m), forces.reaction_kn, deflection.influence_at(x_m, z_m), forces.deflection_m[midspan])
    return model, measured


@pytest.mark.parametrize("probe", PROBE_NODES)
def test_the_reaction_surface_is_the_reaction_to_a_unit_load(solved, probe):
    _, measured = solved
    from_the_surface, directly, *_ = measured[probe]

    assert from_the_surface == pytest.approx(directly, rel=1e-6, abs=1e-9)


@pytest.mark.parametrize("probe", PROBE_NODES)
def test_the_deflection_surface_is_the_deflection_under_a_unit_load(solved, probe):
    _, measured = solved
    *_, from_the_surface, directly = measured[probe]

    assert from_the_surface == pytest.approx(directly, rel=1e-8, abs=1e-15)


def test_the_bearings_carry_the_whole_dead_load():
    """Every girder's near-end reaction, doubled by symmetry, adds up to all the SIDL put on the deck."""
    from setu.loads.dead_loads import superimposed_dead_load

    dead = dead_load_forces(BRIDGE)
    model = build_bridge_model(BRIDGE)
    applied_kn = -sum(fy for _, _, fy, *_ in superimposed_dead_load(model).nodal_loads)

    carried_kn = 2 * sum(dead.stages["superimposed"][girder].reaction_kn for girder in range(BRIDGE.girders.count))

    assert carried_kn == pytest.approx(applied_kn, rel=1e-6)


def test_the_moment_is_checked_near_midspan_on_one_side():
    places = places_to_design(build_bridge_model(BRIDGE))
    moment_stations = [station for response, station in places if response == MAX_MOMENT]

    assert len(moment_stations) >= 2
    assert max(moment_stations) == build_bridge_model(BRIDGE).mesh.stations_along_span // 2


def test_the_deck_is_symmetric_end_to_end_so_one_side_of_midspan_is_enough():
    model = build_bridge_model(BRIDGE)
    solver = InfluenceSolver(model.as_deck_model())
    last = model.mesh.stations_along_span - 2
    station = model.mesh.stations_along_span // 2 - 2
    near = solver.for_girder_composite_moment("near", model.element_of_girder_at(1, station))
    far = solver.for_girder_composite_moment("far", model.element_of_girder_at(1, last - station))

    worst_near = find_critical_position(near, CROSS_SECTION, SPAN_M, "maximum", BRIDGE.wearing_course_thickness_m).response
    worst_far = find_critical_position(far, CROSS_SECTION, SPAN_M, "maximum", BRIDGE.wearing_course_thickness_m).response

    assert worst_near == pytest.approx(worst_far, rel=0.02)


def test_the_fatigue_truck_is_clause_204_6():
    """12, 14 and 14 t on four tyres per axle, pair centres 1.68 m apart; 50% of the clause 208 impact."""
    offsets = fatigue_truck_offsets()

    assert offsets[:, 2].sum() == pytest.approx(40.0 * 9.81)
    assert sorted(set(np.round(offsets[:, 0], 6))) == [0.0, 4.5, 5.9]
    assert sorted(set(np.round(np.abs(offsets[:, 1]), 6))) == [0.64, 1.04]
    assert fatigue_impact_factor(35.0) == pytest.approx(1.0 + 0.5 * 9.0 / (13.5 + 35.0))


def test_the_fatigue_truck_keeps_150_mm_off_the_kerbs():
    carriageway = CROSS_SECTION.carriageways()[0]
    z_from_m, z_to_m = centreline_band_m(carriageway)

    assert z_from_m - 2.39 / 2 == pytest.approx(carriageway.left_m + 0.15)
    assert z_to_m + 2.39 / 2 == pytest.approx(carriageway.right_m - 0.15)


def test_a_fatigue_range_on_a_sagging_surface_is_its_largest_value(sagging_surface, cross_section):
    """Sagging everywhere, so the unloaded 0 is the smallest and the range is the peak."""
    found = fatigue_range(sagging_surface, cross_section, SPAN_M, DEFAULT_SAMPLING)

    assert found.smallest == 0.0
    assert found.range == pytest.approx(found.largest)
    assert found.range > 0
