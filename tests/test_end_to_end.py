"""The whole thing, on a real bridge solved in OpenSees.

Three questions, in order of how much they matter:

    does the bridge stand up under its own weight,
    is the influence surface actually the response to a unit load, and
    does the search find a position that makes sense?
"""


import numpy as np
import pytest

from setu.models.deck import DeckCrossSection
from setu.analysis.influence_surface import InfluenceSolver
from setu.analysis.critical_position import find_critical_position, rank_all_positions
from setu.models.bridge import Bracing, BridgeInput, DeckSlab, Girders, MeshSettings
from setu.models.sections import PlateGirderSection
from test_design_forces import ADDED_DEAD_LOADS, CONCRETE, STEEL
from setu.builder.assembly import build_bridge_model as build_model
from setu.loads.dead_loads import construction_stage_load
from setu.loads.load_cases import apply_load_case

ops = pytest.importorskip("openseespy.opensees", reason="needs a finite element solver")

SPAN_M = 35.0
MOMENT_ABOUT_STRONG_AXIS = 5
AXIAL = 0
DEAD_LOAD_PATTERN = 50
WEARING_COURSE_M = 0.075


@pytest.fixture(scope="module")
def deck_cross_section() -> DeckCrossSection:
    return DeckCrossSection.from_widths(
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


@pytest.fixture(scope="module")
def bridge(deck_cross_section) -> BridgeInput:
    return BridgeInput(
        span_m=SPAN_M,
        skew=0.0,
        cross_section=deck_cross_section,
        deck=DeckSlab(thickness_m=0.23, overhang_m=1.25, wearing_course_thickness_m=0.075),
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


PROBE_NODES = [(6, 10), (6, 20), (12, 10), (12, 15), (12, 30), (18, 20)]
UNIT_LOAD_PATTERN = 99


def _configure_a_static_analysis() -> None:
    ops.wipeAnalysis()
    ops.system("UmfPack")
    ops.numberer("RCM")
    ops.constraints("Transformation")
    ops.integrator("LoadControl", 1.0)
    ops.algorithm("Linear")
    ops.analysis("Static")


@pytest.fixture(scope="module")
def built(bridge):
    """The bridge, its influence surface, a reciprocity check, and its dead load.

    In that order, and the order matters: an influence surface has to be solved
    on a model nothing else is loading, so the dead load goes on last.
    """
    model = build_model(bridge)
    deck = model.as_deck_model()
    element = model.midspan_element_of_girder(bridge.girders.count // 2)

    surface = InfluenceSolver(deck).for_girder_composite_moment("middle girder, midspan moment", element)

    reciprocity = _check_against_real_unit_loads(deck, surface, element, model.composite_lever_arm_m())

    dead_load = construction_stage_load(model)
    apply_load_case(dead_load, ops, pattern_tag=DEAD_LOAD_PATTERN)
    _configure_a_static_analysis()
    ops.analyze(1)
    ops.reactions()
    reactions = {
        "vertical_kn": sum(ops.nodeReaction(node, 2) for node in ops.getNodeTags()),
        "sideways_kn": sum(ops.nodeReaction(node, 3) for node in ops.getNodeTags()),
        "along_span_kn": sum(ops.nodeReaction(node, 1) for node in ops.getNodeTags()),
    }

    return model, dead_load, reactions, surface, element, reciprocity


def _check_against_real_unit_loads(deck, surface, element, lever_arm_m):
    """Puts a real unit load at each probe node and reads the composite moment M + N e it causes."""
    _configure_a_static_analysis()
    ops.timeSeries("Linear", UNIT_LOAD_PATTERN)

    measured = {}
    for station_along, station_across in PROBE_NODES:
        ops.remove("loadPattern", UNIT_LOAD_PATTERN)
        ops.pattern("Plain", UNIT_LOAD_PATTERN, UNIT_LOAD_PATTERN)
        ops.load(
            deck.deck_nodes[(station_along, station_across)], 0.0, -1.0, 0.0, 0.0, 0.0, 0.0
        )
        ops.reset()
        ops.setTime(0.0)
        ops.analyze(1)

        forces = ops.eleResponse(element, "localForce")
        directly = -(forces[MOMENT_ABOUT_STRONG_AXIS] + lever_arm_m * forces[AXIAL])
        from_the_surface = surface.influence_at(
            float(deck.length_mesh_m[station_along]),
            float(deck.width_mesh_m[station_across]),
        )
        measured[(station_along, station_across)] = (from_the_surface, directly)

    ops.remove("loadPattern", UNIT_LOAD_PATTERN)
    return measured


# ---------------------------------------------------------------------------
# Does the bridge stand up?
# ---------------------------------------------------------------------------


def _applied_kn(model, load_case):
    on_the_nodes_kn = -sum(fy for _, _, fy, *_ in load_case.nodal_loads)
    on_the_girders_kn = -sum(parameters[0] for _, _, parameters in load_case.element_loads) * SPAN_M / (model.mesh.stations_along_span - 1)
    return on_the_nodes_kn, on_the_girders_kn


def test_the_supports_carry_exactly_what_was_applied(built):
    model, dead_load, reactions, _, _, _ = built

    assert reactions["vertical_kn"] == pytest.approx(sum(_applied_kn(model, dead_load)), rel=1e-9)


def test_no_dead_load_leaks_sideways(built):
    """Girder self weight is given in the element's local axes.

    Putting it in the wrong component points it sideways instead of down, which
    once took 18 per cent of the dead load out of the vertical load path with no
    error raised anywhere - only a quiet sideways reaction like this one.
    """
    model, dead_load, reactions, _, _, _ = built
    total_kn = sum(_applied_kn(model, dead_load))

    assert abs(reactions["sideways_kn"]) < 1e-6 * total_kn
    assert abs(reactions["along_span_kn"]) < 1e-6 * total_kn


def test_the_girders_carry_a_real_share_of_the_weight(built):
    model, dead_load, _, _, _, _ = built
    _, on_the_girders_kn = _applied_kn(model, dead_load)

    assert on_the_girders_kn > 0.15 * sum(_applied_kn(model, dead_load))


# ---------------------------------------------------------------------------
# Is the influence surface really the response to a unit load?
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("probe", PROBE_NODES)
def test_reciprocity(built, probe):
    """The influence ordinate must equal what a unit load there actually does.

    This is the claim the whole method rests on: one solve with the response
    applied as an imaginary load answers for a load anywhere on the deck. Here
    it is checked the slow way - a real unit load at a node, solved, and the
    girder moment read straight off the element.
    """
    *_, reciprocity = built
    from_the_surface, directly = reciprocity[probe]

    assert from_the_surface == pytest.approx(directly, rel=1e-8, abs=1e-10)


def test_reciprocity_is_not_trivially_zero(built):
    """The check above is only worth anything if the moments are real."""
    *_, reciprocity = built

    assert max(abs(directly) for _, directly in reciprocity.values()) > 0.1


# ---------------------------------------------------------------------------
# Does the search find something sensible?
# ---------------------------------------------------------------------------


def test_every_vehicle_lands_on_its_own_carriageway(built, deck_cross_section):
    """A vehicle must never be placed on the median, a kerb or a footpath."""
    *_, surface, _, _ = built

    worst = find_critical_position(surface, deck_cross_section, SPAN_M, "maximum", WEARING_COURSE_M)
    carriageways = deck_cross_section.carriageways()

    for placed in worst.vehicles:
        assert any(
            carriageway.left_m - 1e-6 <= placed.z_centre_m <= carriageway.right_m + 1e-6
            for carriageway in carriageways
        ), f"{placed.vehicle_name} at z = {placed.z_centre_m:.3f} m is off the carriageway"


def test_two_vehicles_in_one_carriageway_keep_their_distance(built, deck_cross_section):
    """Table 3 sets a gap between adjacent Class A vehicles, and it must hold."""
    *_, surface, _, _ = built

    worst = find_critical_position(surface, deck_cross_section, SPAN_M, "maximum", WEARING_COURSE_M)
    positions_m = sorted(placed.z_centre_m for placed in worst.vehicles)

    for left_m, right_m in zip(positions_m, positions_m[1:], strict=False):
        assert right_m - left_m >= 2.30 - 1e-6


def test_the_result_says_how_it_was_reached(built, deck_cross_section):
    *_, surface, _, _ = built

    worst = find_critical_position(surface, deck_cross_section, SPAN_M, "maximum", WEARING_COURSE_M)

    assert worst.vehicles, "a governing case with no vehicles in it is not a result"
    assert worst.design_lanes >= 1
    assert 0.8 <= worst.lane_reduction <= 1.0
    for placed in worst.vehicles:
        assert placed.impact_factor > 1.0
        assert placed.train_x_front_m, "every vehicle must say where it stopped"
    assert "moment" in worst.describe()


def test_the_worst_case_is_the_one_returned(built, deck_cross_section):
    *_, surface, _, _ = built

    ranked = rank_all_positions(surface, deck_cross_section, SPAN_M, "minimum", WEARING_COURSE_M)

    assert ranked[0].response == min(case.response for case in ranked)


def test_a_two_lane_carriageway_has_a_case_left_empty(built):
    """Table 6A note (b): a partly loaded carriageway is a load case of its own.

    Each 4.50 m carriageway of the main deck holds one lane, so it has only one
    arrangement. A 9.00 m carriageway holds two - Table 6 gives it a third only
    from 9.60 m - and leaving one of the two empty has to be searched as well.
    """
    *_, surface, _, _ = built
    wide = DeckCrossSection.from_widths(
        {"kerb_left": 0.45, "carriageway": 9.00, "kerb_right": 0.45}
    )

    ranked = rank_all_positions(surface, wide, SPAN_M, "minimum", WEARING_COURSE_M)
    lanes_loaded = {case.design_lanes for case in ranked}

    assert lanes_loaded == {1, 2}
    assert ranked[0].response == min(case.response for case in ranked)


def test_a_deck_with_no_room_for_a_vehicle_says_so(built):
    from setu.errors import NoAdmissibleArrangementError

    *_, surface, _, _ = built
    too_narrow = DeckCrossSection.from_widths({"kerb": 0.5, "carriageway": 3.0})

    with pytest.raises(NoAdmissibleArrangementError, match="no IRC:6 lane arrangement"):
        find_critical_position(surface, too_narrow, SPAN_M, "maximum", WEARING_COURSE_M)


def test_the_surface_looks_like_a_bridge_influence_surface(built):
    """Sanity: it must be smooth, bounded, and zero at the supports."""
    model, _, _, surface, _, _ = built

    assert np.isfinite(surface.values).all()
    assert np.abs(surface.values).max() > 0

    # A load standing directly over a girder support causes no moment at all.
    for girder in range(model.bridge.girders.count):
        j = model.mesh.width_station_of_girder(girder)
        assert surface.values[0, j] == pytest.approx(0.0, abs=1e-9)
        assert surface.values[-1, j] == pytest.approx(0.0, abs=1e-9)

    # Between the girders the deck spans transversely, so a load at the support
    # line still finds its way to a girder - but only barely.
    peak = np.abs(surface.values).max()
    assert np.abs(surface.values[0, :]).max() < 0.01 * peak
    assert np.abs(surface.values[-1, :]).max() < 0.01 * peak
