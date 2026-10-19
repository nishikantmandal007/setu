import numpy as np
import pytest

from setu import Bracing, BridgeInput, Girders, MeshSettings, analyze_load_case, build_bridge_model
from setu.analysis.influence_surface import InfluenceSolver
from setu.loads.braking_loads import braking_load_cases
from setu.loads.dead_loads import deck_loads, steel_self_weight_load, superimposed_dead_load, surfacing_load, wet_slab_load
from setu.loads.load_builders import live_load
from setu.loads.load_cases import LoadCase
from setu.loads.seismic_loads import seismic_load_cases
from setu.loads.wind_loads import wind_load_cases
from setu.utils.constants import LONG_TERM

backend = pytest.importorskip("setu.solver.backend", reason="needs a finite element solver")

from test_braking import _lanes
from test_design_forces import BRIDGE
from test_seismic import SITE as SEISMIC_SITE
from test_wind import SITE as WIND_SITE

HORIZONTAL_REACTION_TOLERANCE_KN = 1e-6
SUPPORT_MOMENT_TOLERANCE_KN_M = 0.1
UNIFORM_LOAD_MOMENT_TOLERANCE = 0.005


# use the documented mesh for bearing moments and the girder-only statics check
def bearing_bridge(arrangement, count=5, skew=0.0):
    return BridgeInput(**{**vars(BRIDGE), "girders": Girders(count, BRIDGE.girders.section), "skew": skew,
                          "bracing": Bracing(arrangement, 7, 0.01), "mesh": MeshSettings(16, 0.25)})


# collect constraint forces onto their master; individual rigid-link reactions are internal
def horizontal_bearing_reactions(model):
    backend.calculate_reactions()
    reactions = {}
    for key, node in model.bearings.items():
        for dof in (1, 3):
            if dof not in backend.fixed_dofs(node):
                reactions[key, dof] = 0.0
                continue
            children = [child for child in backend.constrained_nodes(node) if dof in backend.constrained_dofs(child, node)]
            reactions[key, dof] = sum(backend.node_reaction(tag, dof) for tag in [node] + children)
    return reactions


# read reactions while the loads are still active
def solve_with_reactions(model, case):
    reactions = {}

    # capture the external reactions before analyze_load_case removes its pattern
    def capture(forces):
        reactions.update(horizontal_bearing_reactions(model))

    return analyze_load_case(model, case, on_solved=capture), reactions


# inspect every physical restraint, including the unused K-joint rotations
@pytest.mark.parametrize("count", [4, 5])
@pytest.mark.parametrize("composite", [False, True])
def test_only_three_horizontal_bearing_dofs_are_fixed(count, composite):
    model = build_bridge_model(bearing_bridge("KT", count), composite=composite)
    middle = (count - 1) // 2
    far = model.mesh.stations_along_span - 1
    horizontal = {(node, dof) for node in backend.fixed_nodes() for dof in backend.fixed_dofs(node) if dof in (1, 3)}
    ground = set(backend.node_tags()) - set(model.girder_nodes.values()) - set(model.deck_nodes.values())
    ground -= set(model.top_brace_nodes.values()) | set(model.bottom_brace_nodes.values()) | set(model.k_brace_nodes.values())

    assert horizontal - {(node, dof) for node in ground for dof in (1, 3)} == {
        (model.bearings[middle, 0], 1), (model.bearings[middle, 0], 3), (model.bearings[middle, far], 3)}
    assert len(ground) == 2 * count
    assert len(model.bearings) == 2 * count
    for node in model.k_brace_nodes.values():
        assert backend.fixed_dofs(node) == [4, 5, 6]


# each construction and composite dead stage must be free of bearing restraint couples
@pytest.mark.parametrize("arrangement", ["XT", "KT"])
@pytest.mark.parametrize("stage", ["steel", "wet slab", "superimposed", "surfacing"])
def test_gravity_dead_stages_have_no_horizontal_bearing_force_or_end_moment(arrangement, stage):
    builders = {"steel": steel_self_weight_load, "wet slab": wet_slab_load,
                "superimposed": superimposed_dead_load, "surfacing": surfacing_load}
    model = build_bridge_model(bearing_bridge(arrangement), composite=stage not in ("steel", "wet slab"), load_duration=LONG_TERM)

    forces, reactions = solve_with_reactions(model, builders[stage](model))

    assert max(map(abs, reactions.values())) < HORIZONTAL_REACTION_TOLERANCE_KN
    for force in forces.values():
        np.testing.assert_allclose(force.composite_moment_kn_m[[0, -1]], 0.0, atol=SUPPORT_MOMENT_TOLERANCE_KN_M)
    if not model.composite:
        links = set(backend.element_tags()) - set(model.girder_elements.values()) - set(model.brace_elements.values())
        for element in links:
            if backend.element_type(element) == "TwoNodeLink":
                np.testing.assert_allclose(backend.element_basic_forces(element), 0.0, atol=HORIZONTAL_REACTION_TOLERANCE_KN)


# an eccentric two-lane Class A placement must not create opposing horizontal bearing forces
@pytest.mark.parametrize("arrangement", ["XT", "KT"])
def test_placed_class_a_has_no_horizontal_bearing_force_or_end_moment(arrangement):
    model = build_bridge_model(bearing_bridge(arrangement))
    surface = InfluenceSolver(model.as_deck_model()).for_girder_composite_moment("edge moment", model.midspan_element_of_girder(0))
    critical = _lanes((5.0,), (5.0,))
    critical.wearing_course_thickness_m = model.bridge.wearing_course_thickness_m

    forces, reactions = solve_with_reactions(model, live_load(model, critical, surface))

    assert max(map(abs, reactions.values())) < HORIZONTAL_REACTION_TOLERANCE_KN
    for force in forces.values():
        np.testing.assert_allclose(force.composite_moment_kn_m[[0, -1]], 0.0, atol=SUPPORT_MOMENT_TOLERANCE_KN_M)
    if model.k_brace_nodes:
        assert max(abs(backend.node_displacement(node, 1)) for node in model.k_brace_nodes.values()) > 1e-6


# girder composite moments omit the slab's small longitudinal plate-bending share
@pytest.mark.parametrize("arrangement", ["XT", "KT"])
def test_uniform_deck_load_sums_to_the_simply_supported_midspan_moment(arrangement):
    model = build_bridge_model(bearing_bridge(arrangement))
    pressure_kpa = 1.0
    case = LoadCase("uniform deck load", deck_loads(model, lambda z: pressure_kpa))

    forces = analyze_load_case(model, case)
    midspan = model.mesh.stations_along_span // 2
    moment = sum(force.composite_moment_kn_m[midspan] for force in forces.values())
    expected = pressure_kpa * model.bridge.width_m() * model.bridge.span_m ** 2 / 8

    assert moment == pytest.approx(expected, rel=UNIFORM_LOAD_MOMENT_TOLERANCE)


# horizontal load paths must end at the designated bearings for straight and skew decks
@pytest.mark.parametrize("arrangement", ["XT", "KT"])
@pytest.mark.parametrize("skew", [0.0, 0.2])
@pytest.mark.parametrize("loading", ["braking", "wind", "longitudinal seismic", "transverse seismic"])
def test_horizontal_bearings_balance_the_applied_force(arrangement, skew, loading):
    model = build_bridge_model(bearing_bridge(arrangement, 4, skew))
    critical = _lanes((5.0,), (5.0,))
    if loading == "braking":
        case, dof = braking_load_cases(model, critical)["forwards"], 1
    elif loading == "wind":
        case, dof = wind_load_cases(model, WIND_SITE)["transverse from the left"], 3
    else:
        direction = loading.split()[0]
        case = seismic_load_cases(model, SEISMIC_SITE, critical)[direction]
        dof = 1 if direction == "longitudinal" else 3

    _, reactions = solve_with_reactions(model, case)
    applied = sum(load[dof] for load in case.nodal_loads)

    assert applied > 0
    assert sum(value for (_, direction), value in reactions.items() if direction == dof) == pytest.approx(-applied, abs=HORIZONTAL_REACTION_TOLERANCE_KN)
