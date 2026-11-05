import pytest

from setu.builder.assembly import build_bridge_model
from setu.loads.load_cases import LoadCase
from setu.postprocess.design_values import surface_for
from setu.analysis.influence_surface import InfluenceSolver, response_to_load_case
from setu.postprocess.girder_response import analyze_load_case
from setu.solver import backend
from setu.utils.constants import MAX_MOMENT

from test_design_forces import BRIDGE

LOAD_KN = 100.0


@pytest.fixture(scope="module")
def built():
    model = build_bridge_model(BRIDGE)
    solver = InfluenceSolver(model.as_deck_model())
    station = model.mesh.stations_along_span // 2
    surfaces = [surface_for(solver, model, girder, (MAX_MOMENT, station)) for girder in range(BRIDGE.girders.count)]
    return model, station, surfaces


# The deck is simply supported as a whole, so across any section the girders' composite moments (steel moment, axial couple and
# each girder's share of the slab's own bending) must add up to the beam moment P a b / L of the load: nothing is left in the slab.
@pytest.mark.parametrize("probe", [(3, 1), (5, 4), (9, 2), (12, 6), (6, 0)])
def test_the_girders_carry_the_whole_moment_across_a_section(built, probe):
    model, station, surfaces = built
    node = model.deck_nodes[probe]
    load = LoadCase("point", [(node, 0.0, -LOAD_KN, 0.0, 0.0, 0.0, 0.0)])
    x_m = backend.node_coordinates(node)[0]
    at_m = float(model.mesh.length_mesh_m[station])
    span_m = BRIDGE.span_m
    beam = LOAD_KN * (x_m * (span_m - at_m) if x_m <= at_m else at_m * (span_m - x_m)) / span_m
    forces = analyze_load_case(model, load)
    girders = sum(float(forces[g].composite_moment_kn_m[station]) for g in range(BRIDGE.girders.count))
    assert girders == pytest.approx(beam, rel=1e-6)
    by_reciprocity = sum(response_to_load_case(surface, load) for surface in surfaces)
    assert by_reciprocity == pytest.approx(girders, rel=1e-8)


# The slab's share is counted: a measurable part of a deck load's moment (its size depends on how stiff the slab is beside the girders).
def test_the_slab_share_is_counted(built):
    model, station, _ = built
    load = LoadCase("point", [(model.deck_nodes[model.mesh.stations_along_span // 2, 3], 0.0, -LOAD_KN, 0.0, 0.0, 0.0, 0.0)])
    forces = analyze_load_case(model, load)
    slab = sum(float(forces[g].slab_moment_kn_m[station]) for g in range(BRIDGE.girders.count))
    total = sum(float(forces[g].composite_moment_kn_m[station]) for g in range(BRIDGE.girders.count))
    assert 0.001 < slab / total < 0.2
