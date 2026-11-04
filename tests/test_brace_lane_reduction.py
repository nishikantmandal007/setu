"""IRC:6-2017 Amendment 10, Table 8 note 3: the lane reduction is not applied to cross girders or diaphragms."""

import pytest

from setu.analysis.critical_position import find_critical_position, rank_all_positions
from setu.models.bridge import AddedDeadLoads, BridgeInput, Bracing, MeshSettings
from setu.models.deck import DeckCrossSection
from setu.postprocess.brace_design_values import brace_values
from setu.postprocess.parallel import analysis_for
from setu.utils.constants import BIGGER_IS_WORSE

from test_design_forces import BRIDGE
from test_golden_values import SPAN_M, WIDE_CARRIAGEWAY, sagging_surface

FOUR_LANE_DECK = DeckCrossSection.from_widths({"footpath_left": 1.5, "kerb_left": 0.45, "carriageway_1": 14.0, "kerb_right": 0.45, "footpath_right": 1.5})
NO_MEDIAN = AddedDeadLoads(footpath_kpa=3.6, kerb_kn_per_m=3.24, median_kn_per_m=0.0, crash_barrier_kn_per_m=0.0, railing_kn_per_m=0.0)


def test_without_the_reduction_the_worst_unreduced_layout_governs():
    surface = sagging_surface()
    ranked = rank_all_positions(surface, WIDE_CARRIAGEWAY, SPAN_M, BIGGER_IS_WORSE, 0.0)
    unreduced = find_critical_position(surface, WIDE_CARRIAGEWAY, SPAN_M, BIGGER_IS_WORSE, 0.0, lane_reduction=False)

    assert unreduced.lane_reduction == 1.0
    assert unreduced.response == pytest.approx(max(case.response_before_reduction for case in ranked), rel=1e-12)


def test_the_girder_search_still_reduces_four_lanes():
    reduced = find_critical_position(sagging_surface(), WIDE_CARRIAGEWAY, SPAN_M, BIGGER_IS_WORSE, 0.0)

    assert reduced.design_lanes == 4
    assert reduced.lane_reduction == pytest.approx(0.8)


def test_every_brace_member_on_a_four_lane_deck_is_searched_unreduced():
    bridge = BridgeInput(**{**vars(BRIDGE), "cross_section": FOUR_LANE_DECK, "added_dead_loads": NO_MEDIAN,
                            "bracing": Bracing(station_count=3, area_m2=0.01, arrangement="XT"), "mesh": MeshSettings(2, 1.0)})
    with analysis_for(bridge, None, (), (), 1, girders=False, braces=True) as analysis:
        braces = brace_values(analysis, bridge, None, None)

    reductions = {critical.lane_reduction for critical in braces.criticals.values()}
    assert reductions == {1.0}
    assert any(critical.design_lanes >= 3 for critical in braces.criticals.values()), "no brace is governed by 3+ lanes: the test proves nothing"

