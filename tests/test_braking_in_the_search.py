"""Clause 204.1.2: vehicles take the position producing the maximum load effect, and braking (cl. 211.2) is part of it.

The traffic search ranks placements by their vertical response; braking is added on the real solve. Of every lane
arrangement's worst placement, the one with the worst live load plus braking is the one kept, and the search's own
placement still gives its live mass to the seismic combination.
"""

from setu.helpers import adverse_sign
from setu.models.bridge import BridgeInput, Bracing, MeshSettings
from setu.postprocess.brace_design_values import brace_reader, solved_members
from setu.postprocess.design_values import BOTH_DIRECTIONS, live_with_braking, settle_braking
from setu.postprocess.parallel import analysis_for

from test_brace_lane_reduction import NO_MEDIAN
from test_design_forces import BRIDGE
from setu.models.deck import DeckCrossSection

THREE_LANE_DECK = DeckCrossSection.from_widths({"footpath_left": 1.5, "kerb_left": 0.45, "carriageway_1": 11.0, "kerb_right": 0.45, "footpath_right": 1.5})


def test_the_kept_placement_has_the_worst_live_load_plus_braking():
    bridge = BridgeInput(**{**vars(BRIDGE), "cross_section": THREE_LANE_DECK, "added_dead_loads": NO_MEDIAN,
                            "bracing": Bracing(station_count=3, area_m2=0.01, arrangement="XT"), "mesh": MeshSettings(2, 1.0)})
    moved = 0
    with analysis_for(bridge, None, (), (), 1, girders=False, braces=True) as analysis:
        for member, surface, found in solved_members(analysis, bridge, None):
            read = brace_reader({member: surface})
            settled = settle_braking(analysis.model, found, read, (member, None), None)
            for adverse in BOTH_DIRECTIONS:
                sign = adverse_sign(adverse)
                candidates = [found[adverse], *found[adverse].alternatives]
                totals = [sign * live_with_braking(analysis.model, c, read, member, None) for c in candidates]
                kept = sign * live_with_braking(analysis.model, settled[adverse], read, member, None)
                assert kept >= max(totals) - 1e-9
                if settled[adverse] is not found[adverse]:
                    moved += 1
                    assert settled[adverse].searched is found[adverse]
    assert moved > 0, "no member changed placement: the test proves nothing on this deck"
