"""A skewed deck: supports at an angle, traffic still running along x.

Nodes sit at x_mesh + skew z, and an influence surface is read at along = x - skew z.
"""

import pytest

from setu.analysis.critical_position import find_critical_position
from setu.analysis.influence_surface import InfluenceSolver
from setu.builder.assembly import build_bridge_model
from setu.models.bridge import BridgeInput

pytest.importorskip("setu.solver.backend", reason="needs a finite element solver")
from setu.solver import backend  # noqa: E402

from test_design_forces import (  # noqa: E402
    BRIDGE, CROSS_SECTION, MOMENT_AT_END_I, PROBE_NODES, SPAN_M,
    _live_load_response, _unit_load_response,
)

SKEW = 0.2
LIVE_LOAD_PATTERN = 100


@pytest.fixture(scope="module")
def skewed():
    bridge = BridgeInput(**{**BRIDGE.__dict__, "skew": SKEW})
    model = build_bridge_model(bridge)
    element = model.midspan_element_of_girder(1)
    surface = InfluenceSolver(model.as_deck_model()).for_girder_composite_moment("skewed, girder 1 midspan", element)
    return model, element, surface


def test_the_surface_knows_the_deck_is_skewed(skewed):
    _, _, surface = skewed

    assert surface.skew == SKEW


@pytest.mark.parametrize("probe", PROBE_NODES)
def test_reciprocity_at_the_real_position_of_each_node(skewed, probe):
    model, element, surface = skewed
    deck = model.as_deck_model()
    x_m, _, z_m = backend.node_coordinates(deck.deck_nodes[probe])

    directly = _unit_load_response(deck, deck.deck_nodes[probe], element, MOMENT_AT_END_I, model.composite_lever_arm_m())

    assert surface.influence_at(x_m, z_m) == pytest.approx(directly, rel=1e-8, abs=1e-10)


@pytest.mark.parametrize("adverse", ["maximum", "minimum"])
def test_the_live_load_gives_back_the_searched_response_on_a_skewed_deck(skewed, adverse):
    model, element, surface = skewed
    critical = find_critical_position(surface, CROSS_SECTION, SPAN_M, adverse, BRIDGE.wearing_course_thickness_m)

    directly = _live_load_response(model, critical, surface, element, MOMENT_AT_END_I, model.composite_lever_arm_m())

    assert directly == pytest.approx(critical.response, rel=1e-6)


def test_skew_does_not_weaken_the_search(skewed):
    """Skew is a shear of the deck: the worst sagging moment should stay close to the square deck's.

    Mainly this guards against a search that loses vehicles off the ends of a skewed deck.
    """
    _, _, surface = skewed
    square = build_bridge_model(BRIDGE)
    square_surface = InfluenceSolver(square.as_deck_model()).for_girder_composite_moment("square", square.midspan_element_of_girder(1))

    on_the_skew = find_critical_position(surface, CROSS_SECTION, SPAN_M, "maximum", BRIDGE.wearing_course_thickness_m)
    on_the_square = find_critical_position(square_surface, CROSS_SECTION, SPAN_M, "maximum", BRIDGE.wearing_course_thickness_m)

    assert on_the_skew.response == pytest.approx(on_the_square.response, rel=0.15)
