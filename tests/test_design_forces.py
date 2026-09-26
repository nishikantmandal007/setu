"""From influence surface to design force, checked against real FE solves.

Three claims:

    a shear surface, and a moment surface away from midspan, are the response to a unit load,
    the live load built from a critical position gives back the response the search reported, and
    every girder gets its own answer.
"""

import pytest

from setu.analysis.critical_position import find_critical_position
from setu.analysis.influence_surface import InfluenceSolver
from setu.builder.assembly import build_bridge_model
from setu.loads.load_builders import vehicle_load
from setu.loads.load_cases import apply_load_case
from setu.models.bridge import AddedDeadLoads, Bracing, BridgeInput, DeckSlab, Girders, MeshSettings
from setu.models.materials import Concrete, Steel, SurfacingLayer
from setu.models.sections import PlateGirderSection
from setu.models.deck import DeckCrossSection

ops = pytest.importorskip("openseespy.opensees", reason="needs a finite element solver")

SPAN_M = 35.0
SHEAR_AT_END_I = 1
MOMENT_AT_END_I = 5
AXIAL_AT_END_I = 0
PROBE_NODES = [(3, 10), (6, 20), (12, 5), (12, 30), (20, 15)]
UNIT_LOAD_PATTERN = 99
LIVE_LOAD_PATTERN = 100
END_I_FORCE_TO_INTERNAL_FORCE = -1.0
ONLY_THE_VEHICLES = dict(apply_residual_udl=False, apply_footway_load=False)

CROSS_SECTION = DeckCrossSection.from_widths(
    {
        "footpath_left": 1.50,
        "kerb_left": 0.45,
        "carriageway_1": 4.50,
        "median": 0.60,
        "carriageway_2": 4.50,
        "kerb_right": 0.45,
        "footpath_right": 1.50,
    }
)

STEEL = Steel(elastic_modulus_mpa=200000.0, poissons_ratio=0.3, unit_weight_kn_m3=78.5)
CONCRETE = Concrete(elastic_modulus_mpa=32000.0, poissons_ratio=0.2, unit_weight_kn_m3=25.0)
ADDED_DEAD_LOADS = AddedDeadLoads(
    footpath=SurfacingLayer(0.15, 24.0), kerb=SurfacingLayer(0.3, 24.0),
    median=SurfacingLayer(0.25, 24.0), crash_barrier=SurfacingLayer(0.3, 24.0),
)

BRIDGE = BridgeInput(
    span_m=SPAN_M,
    skew=0.0,
    cross_section=CROSS_SECTION,
    deck=DeckSlab(thickness_m=0.23, overhang_m=1.25, wearing_course_thickness_m=0.0),
    girders=Girders(
        count=5,
        section=PlateGirderSection(
            top_flange_width_m=0.550,
            top_flange_thickness_m=0.025,
            bottom_flange_width_m=0.650,
            bottom_flange_thickness_m=0.040,
            web_thickness_m=0.014,
            web_height_m=2.100,
        ),
    ),
    bracing=Bracing(station_count=7, area_m2=0.01, arrangement="XT"),
    mesh=MeshSettings(panels_between_braces=4, target_size_across_width_m=0.6),
    steel=STEEL,
    concrete=CONCRETE,
    wearing_course_unit_weight_kn_m3=22.0,
    added_dead_loads=ADDED_DEAD_LOADS,
)


def _configure_a_static_analysis():
    ops.wipeAnalysis()
    ops.system("UmfPack")
    ops.numberer("RCM")
    ops.constraints("Transformation")
    ops.integrator("LoadControl", 1.0)
    ops.algorithm("Linear")
    ops.analysis("Static")


def _read_directly(element, component, pattern_tag):
    ops.reset()
    ops.setTime(0.0)
    ops.analyze(1)
    force = END_I_FORCE_TO_INTERNAL_FORCE * ops.eleResponse(element, "localForce")[component]
    ops.remove("loadPattern", pattern_tag)
    ops.remove("timeSeries", pattern_tag)
    return force


def _unit_load_response(deck, node, element, component):
    ops.timeSeries("Linear", UNIT_LOAD_PATTERN)
    ops.pattern("Plain", UNIT_LOAD_PATTERN, UNIT_LOAD_PATTERN)
    ops.load(node, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0)
    return _read_directly(element, component, UNIT_LOAD_PATTERN)


def _live_load_response(model, critical, element, component):
    apply_load_case(vehicle_load(model, critical), ops, pattern_tag=LIVE_LOAD_PATTERN)
    return _read_directly(element, component, LIVE_LOAD_PATTERN)


@pytest.fixture(scope="module")
def built():
    """Every surface is solved first: nothing else may load the model while they are."""
    model = build_bridge_model(BRIDGE)
    deck = model.as_deck_model()
    solver = InfluenceSolver(deck)
    quarter_span = model.mesh.stations_along_span // 4
    outer_girder = 0
    middle_girder = BRIDGE.girders.count // 2

    checks = {
        "outer girder, quarter-span moment": (
            model.element_of_girder_at(outer_girder, quarter_span), MOMENT_AT_END_I, solver.for_girder_moment
        ),
        "outer girder, support shear": (
            model.element_of_girder_at(outer_girder, 0), SHEAR_AT_END_I, solver.for_girder_shear
        ),
        "middle girder, support shear": (
            model.element_of_girder_at(middle_girder, 0), SHEAR_AT_END_I, solver.for_girder_shear
        ),
    }
    for girder in range(BRIDGE.girders.count):
        checks[f"girder {girder}, midspan moment"] = (
            model.midspan_element_of_girder(girder), MOMENT_AT_END_I, solver.for_girder_moment
        )

    surfaces = {name: solve(name, element) for name, (element, _, solve) in checks.items()}

    _configure_a_static_analysis()
    reciprocity = {}
    for name, (element, component, _) in checks.items():
        for station_along, station_across in PROBE_NODES:
            node = deck.deck_nodes[(station_along, station_across)]
            from_the_surface = surfaces[name].influence_at(
                float(deck.length_mesh_m[station_along]), float(deck.width_mesh_m[station_across])
            )
            reciprocity[name, (station_along, station_across)] = (
                from_the_surface, _unit_load_response(deck, node, element, component)
            )

    return model, checks, surfaces, reciprocity


@pytest.mark.parametrize(
    "name", ["outer girder, quarter-span moment", "outer girder, support shear", "middle girder, support shear"]
)
@pytest.mark.parametrize("probe", PROBE_NODES)
def test_reciprocity_away_from_midspan_and_for_shear(built, name, probe):
    *_, reciprocity = built
    from_the_surface, directly = reciprocity[name, probe]

    assert from_the_surface == pytest.approx(directly, rel=1e-8, abs=1e-10)


@pytest.mark.parametrize(
    "name", ["outer girder, quarter-span moment", "outer girder, support shear", "middle girder, support shear"]
)
def test_the_new_surfaces_are_not_trivially_zero(built, name):
    *_, reciprocity = built

    assert max(abs(directly) for (checked, _), (_, directly) in reciprocity.items() if checked == name) > 0.01


def test_midspan_is_one_of_the_stations(built):
    model, *_ = built
    midspan = model.mesh.stations_along_span // 2

    assert model.midspan_element_of_girder(1) == model.element_of_girder_at(1, midspan)


@pytest.mark.parametrize(
    "name", ["girder 0, midspan moment", "girder 2, midspan moment", "outer girder, support shear"]
)
@pytest.mark.parametrize("adverse", ["maximum", "minimum"])
def test_the_live_load_gives_back_the_searched_response(built, name, adverse):
    """The search adds up influence x wheel load; the FE model must agree when the load is really applied."""
    model, checks, surfaces, _ = built
    element, component, _ = checks[name]
    critical = find_critical_position(surfaces[name], CROSS_SECTION, span_m=SPAN_M, adverse=adverse, **ONLY_THE_VEHICLES)

    _configure_a_static_analysis()
    directly = _live_load_response(model, critical, element, component)

    assert directly == pytest.approx(critical.response, rel=1e-6)


def test_each_girder_gets_its_own_critical_position(built):
    """The outer girder is loaded by vehicles near its edge, the middle one by vehicles near the centre."""
    _, _, surfaces, _ = built
    worst = {
        girder: find_critical_position(surfaces[f"girder {girder}, midspan moment"], CROSS_SECTION, span_m=SPAN_M)
        for girder in range(BRIDGE.girders.count)
    }

    responses = [worst[girder].response for girder in worst]
    assert len({round(response, 6) for response in responses}) > 1
    outer_vehicle_m = min(placed.z_centre_m for placed in worst[0].vehicles)
    middle_vehicle_m = min(placed.z_centre_m for placed in worst[BRIDGE.girders.count // 2].vehicles)
    assert outer_vehicle_m <= middle_vehicle_m


def test_a_load_case_after_the_surfaces_is_not_polluted_by_them(built):
    """Influence solves leave the model deflected; a load case solved next must not see that."""
    from setu.postprocess.girder_response import analyze_load_case

    model, checks, surfaces, _ = built
    element, component, _ = checks["girder 2, midspan moment"]
    critical = find_critical_position(surfaces["girder 2, midspan moment"], CROSS_SECTION, span_m=SPAN_M, **ONLY_THE_VEHICLES)
    midspan = model.mesh.stations_along_span // 2
    solver = InfluenceSolver(model.as_deck_model())
    solver.for_girder_moment("pollute the model first", element)

    forces = analyze_load_case(model, vehicle_load(model, critical), ops)

    assert forces[2].moment_kn_m[midspan] == pytest.approx(critical.response, rel=1e-6)


def test_a_load_case_refuses_to_run_on_top_of_another(built):
    from setu.errors import OtherLoadsStillActiveError
    from setu.postprocess.girder_response import analyze_load_case

    model, checks, surfaces, _ = built
    critical = find_critical_position(surfaces["girder 2, midspan moment"], CROSS_SECTION, span_m=SPAN_M, **ONLY_THE_VEHICLES)
    ops.timeSeries("Constant", UNIT_LOAD_PATTERN)
    ops.pattern("Plain", UNIT_LOAD_PATTERN, UNIT_LOAD_PATTERN)
    try:
        with pytest.raises(OtherLoadsStillActiveError):
            analyze_load_case(model, vehicle_load(model, critical), ops)
    finally:
        ops.remove("loadPattern", UNIT_LOAD_PATTERN)
        ops.remove("timeSeries", UNIT_LOAD_PATTERN)


def test_girder_forces_use_one_sign_along_the_whole_girder(built):
    """Shear just inside the support and at the support itself must agree in sign."""
    from setu.loads.load_cases import LoadCase
    from setu.postprocess.girder_response import analyze_load_case

    model, *_ = built
    midspan = model.mesh.stations_along_span // 2
    downwards_at_midspan = LoadCase("point", nodal_loads=[
        (model.deck_nodes[midspan, model.mesh.width_station_of_girder(2)], 0.0, -100.0, 0.0, 0.0, 0.0, 0.0)
    ])

    forces = analyze_load_case(model, downwards_at_midspan, ops)[2]

    assert forces.shear_kn[0] * forces.shear_kn[1] > 0
    assert forces.moment_kn_m[midspan] > 0, "sagging is positive"


def test_composite_moment_surface_is_the_response_to_a_unit_load():
    """Composite moment = steel moment + steel axial force x its lever arm to the slab mid-plane."""
    from setu.builder.assembly import girder_centroid_level_m

    model = build_bridge_model(BRIDGE)
    deck = model.as_deck_model()
    element = model.midspan_element_of_girder(1)
    surface = InfluenceSolver(deck).for_girder_composite_moment("girder 1, composite midspan moment", element)
    lever_arm_m = -girder_centroid_level_m(model.bridge, model.girder)

    _configure_a_static_analysis()
    for station_along, station_across in PROBE_NODES:
        node = deck.deck_nodes[(station_along, station_across)]
        steel_moment = _unit_load_response(deck, node, element, MOMENT_AT_END_I)
        steel_axial = _unit_load_response(deck, node, element, AXIAL_AT_END_I)
        from_the_surface = surface.influence_at(float(deck.length_mesh_m[station_along]), float(deck.width_mesh_m[station_across]))
        assert from_the_surface == pytest.approx(steel_moment + lever_arm_m * steel_axial, rel=1e-8, abs=1e-10)


def test_composite_moments_of_all_girders_add_up_to_statics():
    """A point load P at midspan of a simple span makes P L / 4 across the whole deck.

    The girders' composite moments carry nearly all of it; the slab's own plate bending the rest.
    """
    from setu.loads.load_cases import LoadCase
    from setu.postprocess.girder_response import analyze_load_case

    model = build_bridge_model(BRIDGE)
    midspan = model.mesh.stations_along_span // 2
    load_kn = 100.0
    point = LoadCase("point", nodal_loads=[(model.deck_nodes[midspan, model.mesh.width_station_of_girder(1)], 0.0, -load_kn, 0.0, 0.0, 0.0, 0.0)])

    forces = analyze_load_case(model, point, ops)
    carried_by_the_girders = sum(forces[girder].composite_moment_kn_m[midspan] for girder in forces)
    steel_alone = sum(forces[girder].moment_kn_m[midspan] for girder in forces)

    assert carried_by_the_girders == pytest.approx(load_kn * SPAN_M / 4, rel=0.01)
    assert steel_alone < 0.5 * load_kn * SPAN_M / 4, "the steel alone must not look like the whole section"


def test_long_term_concrete_leaves_more_to_the_steel():
    """Creep softens the slab, so under a sustained load the steel carries more of the moment."""
    from setu.loads.load_cases import LoadCase
    from setu.utils.constants import LONG_TERM
    from setu.postprocess.girder_response import analyze_load_case

    steel_moment = {}
    for load_duration in ("short_term", LONG_TERM):
        model = build_bridge_model(BRIDGE, load_duration=load_duration)
        midspan = model.mesh.stations_along_span // 2
        point = LoadCase("point", nodal_loads=[(model.deck_nodes[midspan, model.mesh.width_station_of_girder(1)], 0.0, -100.0, 0.0, 0.0, 0.0, 0.0)])
        forces = analyze_load_case(model, point, ops)
        steel_moment[load_duration] = forces[1].moment_kn_m[midspan]
        assert sum(forces[g].composite_moment_kn_m[midspan] for g in forces) == pytest.approx(100.0 * SPAN_M / 4, rel=0.01)

    assert steel_moment[LONG_TERM] > steel_moment["short_term"]


def test_a_k_braced_bridge_builds():
    k_braced = BridgeInput(**{**BRIDGE.__dict__, "bracing": Bracing(station_count=7, area_m2=0.01, arrangement="KT")})

    model = build_bridge_model(k_braced)

    assert len(model.k_brace_nodes) == (BRIDGE.girders.count - 1) * 7


@pytest.mark.parametrize("name", ["girder 0, midspan moment", "girder 2, midspan moment", "outer girder, support shear"])
@pytest.mark.parametrize("adverse", ["maximum", "minimum"])
def test_the_full_live_load_gives_back_the_searched_response(name, adverse):
    """Vehicles, the residual UDL beside Class A on the 4.5 m carriageways, and the footway crowd."""
    from setu.loads.load_builders import live_load

    model = build_bridge_model(BRIDGE)
    element = {"girder 0, midspan moment": model.midspan_element_of_girder(0),
               "girder 2, midspan moment": model.midspan_element_of_girder(2),
               "outer girder, support shear": model.element_of_girder_at(0, 0)}[name]
    solve = InfluenceSolver(model.as_deck_model())
    surface = solve.for_girder_shear(name, element) if "shear" in name else solve.for_girder_moment(name, element)
    component = SHEAR_AT_END_I if "shear" in name else MOMENT_AT_END_I
    critical = find_critical_position(surface, CROSS_SECTION, span_m=SPAN_M, adverse=adverse)

    assert critical.residual_udl_applied and critical.footway_strips, "this bridge must exercise both area loads"

    _configure_a_static_analysis()
    apply_load_case(live_load(model, critical, surface), ops, pattern_tag=LIVE_LOAD_PATTERN)
    directly = _read_directly(element, component, LIVE_LOAD_PATTERN)

    assert directly == pytest.approx(critical.response, rel=1e-6)


def test_footways_are_loaded_by_default():
    model = build_bridge_model(BRIDGE)
    surface = InfluenceSolver(model.as_deck_model()).for_girder_moment("m", model.midspan_element_of_girder(0))

    assert find_critical_position(surface, CROSS_SECTION, span_m=SPAN_M).footway_response != 0.0
