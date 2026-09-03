from setu.services.critical_position import CriticalPositionService
"""The whole thing, on a real bridge solved in OpenSees.

Three questions, in order of how much they matter:

    does the bridge stand up under its own weight,
    is the influence surface actually the response to a unit load, and
    does the search find a position that makes sense?
"""


import numpy as np
import pytest

from setu.models.deck import DeckCrossSection
from setu.services.influence_surface import InfluenceSolver
from setu.services.critical_position import CriticalPositionService
find_critical_position = CriticalPositionService.find_critical_position
rank_all_positions = CriticalPositionService.rank_all_positions
from setu.models.bridge import (
    Bracing,
    BridgeInput,
    DeckSlab,
    Girders,
    MeshSettings,
    PlateGirderSection,
)
from setu.models.bridge import (
    Bracing,
    BridgeInput,
    DeckSlab,
    Girders,
    MeshSettings,
    PlateGirderSection,
)
from setu.services.bridge_geometry import build_bridge_model as build_model, apply_dead_loads

ops = pytest.importorskip("openseespy.opensees", reason="needs a finite element solver")

SPAN_M = 35.0
MOMENT_ABOUT_STRONG_AXIS = 5


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

    surface = InfluenceSolver(deck).for_girder_moment("middle girder, midspan moment", element)

    reciprocity = _check_against_real_unit_loads(deck, surface, element)

    dead_load = apply_dead_loads(model)
    _configure_a_static_analysis()
    ops.analyze(1)
    ops.reactions()
    reactions = {
        "vertical_kn": sum(ops.nodeReaction(node, 2) for node in ops.getNodeTags()),
        "sideways_kn": sum(ops.nodeReaction(node, 3) for node in ops.getNodeTags()),
        "along_span_kn": sum(ops.nodeReaction(node, 1) for node in ops.getNodeTags()),
    }

    return model, dead_load, reactions, surface, element, reciprocity


def _check_against_real_unit_loads(deck, surface, element):
    """Puts a real unit load at each probe node and reads the moment it causes."""
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

        directly = ops.eleResponse(element, "localForce")[MOMENT_ABOUT_STRONG_AXIS]
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


def test_the_supports_carry_exactly_what_was_applied(built):
    _, dead_load, reactions, _, _, _ = built

    assert reactions["vertical_kn"] == pytest.approx(dead_load.total_kn, rel=1e-9)


def test_no_dead_load_leaks_sideways(built):
    """Girder self weight is given in the element's local axes.

    Putting it in the wrong component points it sideways instead of down, which
    once took 18 per cent of the dead load out of the vertical load path with no
    error raised anywhere - only a quiet sideways reaction like this one.
    """
    _, dead_load, reactions, _, _, _ = built

    assert abs(reactions["sideways_kn"]) < 1e-6 * dead_load.total_kn
    assert abs(reactions["along_span_kn"]) < 1e-6 * dead_load.total_kn


def test_the_girders_carry_a_real_share_of_the_weight(built):
    _, dead_load, _, _, _, _ = built

    assert dead_load.girders_kn > 0.15 * dead_load.total_kn


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


@pytest.mark.parametrize("adverse", ["maximum", "minimum"])
def test_the_fixes_can_only_make_it_worse(built, deck_cross_section, adverse):
    """Trains and reversal add load cases to the search; they remove none.

    So the answer can only become more adverse. If it ever became less, a case
    the old search could reach would have gone missing.
    """
    *_, surface, _, _ = built

    without = CriticalPositionService.find_critical_position(
        surface,
        deck_cross_section,
        span_m=SPAN_M,
        adverse=adverse,
        allow_trains=False,
        allow_reversed_vehicles=False,
    )
    with_them = CriticalPositionService.find_critical_position(
        surface, deck_cross_section, span_m=SPAN_M, adverse=adverse
    )

    if adverse == "maximum":
        assert with_them.response >= without.response - 1e-9
    else:
        assert with_them.response <= without.response + 1e-9


def test_every_vehicle_lands_on_its_own_carriageway(built, deck_cross_section):
    """A vehicle must never be placed on the median, a kerb or a footpath."""
    *_, surface, _, _ = built

    worst = CriticalPositionService.find_critical_position(surface, deck_cross_section, span_m=SPAN_M)
    carriageways = deck_cross_section.carriageways()

    for placed in worst.vehicles:
        assert any(
            carriageway.left_m - 1e-6 <= placed.z_centre_m <= carriageway.right_m + 1e-6
            for carriageway in carriageways
        ), f"{placed.vehicle_name} at z = {placed.z_centre_m:.3f} m is off the carriageway"


def test_two_vehicles_in_one_carriageway_keep_their_distance(built, deck_cross_section):
    """Table 3 sets a gap between adjacent Class A vehicles, and it must hold."""
    *_, surface, _, _ = built

    worst = CriticalPositionService.find_critical_position(surface, deck_cross_section, span_m=SPAN_M)
    positions_m = sorted(placed.z_centre_m for placed in worst.vehicles)

    for left_m, right_m in zip(positions_m, positions_m[1:], strict=False):
        assert right_m - left_m >= 2.30 - 1e-6


def test_the_result_says_how_it_was_reached(built, deck_cross_section):
    *_, surface, _, _ = built

    worst = CriticalPositionService.find_critical_position(surface, deck_cross_section, span_m=SPAN_M)

    assert worst.vehicles, "a governing case with no vehicles in it is not a result"
    assert worst.design_lanes >= 1
    assert 0.8 <= worst.lane_reduction <= 1.0
    for placed in worst.vehicles:
        assert placed.impact_factor > 1.0
        assert placed.train_x_front_m, "every vehicle must say where it stopped"
    assert "moment" in worst.describe()


def test_the_worst_case_is_the_one_returned(built, deck_cross_section):
    *_, surface, _, _ = built

    ranked = CriticalPositionService.rank_all_positions(surface, deck_cross_section, span_m=SPAN_M, adverse="minimum")

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

    ranked = CriticalPositionService.rank_all_positions(surface, wide, span_m=SPAN_M, adverse="minimum")
    lanes_loaded = {case.design_lanes for case in ranked}

    assert lanes_loaded == {1, 2}
    assert ranked[0].response == min(case.response for case in ranked)


def test_lifting_the_combination_drawings_reaches_the_sweep(built):
    """The flag has to change the arrangements the sweep searches, not just the report.

    A 70R between two Class A lanes fits a 13.10 m carriageway but is never drawn,
    so `follow_combination_drawings=True` must leave it out and `False` must find
    it. The flag was once accepted and then not forwarded, which made it a no-op.
    """
    *_, surface, _, _ = built
    wide = DeckCrossSection.from_widths(
        {"kerb_left": 0.45, "carriageway": 13.10, "kerb_right": 0.45}
    )

    as_drawn = CriticalPositionService.rank_all_positions(surface, wide, span_m=SPAN_M, adverse="minimum")
    every_arrangement = CriticalPositionService.rank_all_positions(
        surface, wide, span_m=SPAN_M, adverse="minimum", follow_combination_drawings=False
    )

    boxed_in_70r = "class_a + zone_70r + class_a"
    assert boxed_in_70r not in {case.lane_pattern for case in as_drawn}
    assert boxed_in_70r in {case.lane_pattern for case in every_arrangement}
    assert len(every_arrangement) > len(as_drawn)


def test_impact_falls_as_the_member_gets_longer(built, deck_cross_section):
    """Clause 208.5 - the member's own span, which is not always the bridge's."""
    *_, surface, _, _ = built

    short = CriticalPositionService.find_critical_position(
        surface, deck_cross_section, span_m=SPAN_M, member_span_m=5.0
    )
    long = CriticalPositionService.find_critical_position(
        surface, deck_cross_section, span_m=SPAN_M, member_span_m=45.0
    )

    assert short.vehicles[0].impact_factor > long.vehicles[0].impact_factor


def test_a_deck_with_no_room_for_a_vehicle_says_so(built):
    from setu.utils.errors import NoAdmissibleArrangementError

    *_, surface, _, _ = built
    too_narrow = DeckCrossSection.from_widths({"kerb": 0.5, "carriageway": 3.0})

    with pytest.raises(NoAdmissibleArrangementError, match="no IRC:6 lane arrangement"):
        CriticalPositionService.find_critical_position(surface, too_narrow, span_m=SPAN_M)


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


@pytest.mark.parametrize("adverse", ["maximum", "minimum"])
def test_the_resultant_centred_case_can_never_govern(built, deck_cross_section, adverse):
    """It is one position inside the set the sweep already searches.

    So the sweep either lands on it or finds something worse. If the centred
    position ever came out more adverse than the swept answer, the sweep would
    have missed a placement it was supposed to cover.
    """
    *_, surface, _, _ = built

    worst = CriticalPositionService.find_critical_position(
        surface, deck_cross_section, span_m=SPAN_M, adverse=adverse
    )

    assert worst.resultant_centred_response is not None
    assert abs(worst.resultant_centred_response) <= abs(worst.response) + 1e-9
    assert worst.resultant_centred_shortfall() >= -1e-9


def test_the_report_shows_both_transverse_conditions(built, deck_cross_section):
    """The code asks for both to be analysed and the governing one identified."""
    *_, surface, _, _ = built

    described = CriticalPositionService.find_critical_position(
        surface, deck_cross_section, span_m=SPAN_M, adverse="minimum"
    ).describe()

    assert "Resultant at mid-width" in described
    assert "lower" in described
