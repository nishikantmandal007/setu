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


def test_the_braking_field_estimate_keeps_the_same_choice():
    """With the solved surface, settle_braking estimates every candidate from its braking field and works out exactly only those
    that could be the worst. It must keep the very candidate, and the very total, that working every candidate out exactly keeps:
    straight and skewed decks, girder places and brace members, both directions."""
    import copy
    from setu.analysis.critical_position import find_critical_position
    from setu.loads.braking_loads import BrakingField
    from setu.postprocess.design_values import places_to_design, reader, surface_for
    from setu.utils.constants import BIGGER_IS_WORSE
    compared = 0
    for skew in (0.0, 0.25):
        bridge = BridgeInput(**{**vars(BRIDGE), "cross_section": THREE_LANE_DECK, "added_dead_loads": NO_MEDIAN, "skew": skew,
                                "bracing": Bracing(station_count=3, area_m2=0.01, arrangement="XT"), "mesh": MeshSettings(2, 0.5)})
        with analysis_for(bridge, None, (), (), 1, girders=True, braces=True) as analysis:
            model = analysis.model
            jobs = []
            for girder in range(bridge.girders.count):
                for place in places_to_design(model):
                    surface = surface_for(analysis.solver, model, girder, place)
                    found = {adverse: find_critical_position(surface, bridge.cross_section, bridge.span_m, adverse, bridge.wearing_course_thickness_m)
                             for adverse in BOTH_DIRECTIONS}
                    jobs.append((surface, reader({(girder, place): surface}), (girder, place), found))
            for member, surface, found in solved_members(analysis, bridge, None):
                jobs.append((surface, brace_reader({member: surface}), (member, None), found))
            for surface, read, target, found in jobs:
                exact = settle_braking(model, copy.deepcopy(found), read, target, None)
                fast = settle_braking(model, copy.deepcopy(found), read, target, None, surface)
                field = BrakingField(model, surface)
                for adverse in BOTH_DIRECTIONS:
                    a, b = exact[adverse], fast[adverse]
                    assert live_with_braking(model, a, read, *target) == live_with_braking(model, b, read, *target)
                    assert (a.lane_pattern, [(v.vehicle_name, v.z_centre_m, v.train_x_front_m) for v in a.vehicles]) == \
                           (b.lane_pattern, [(v.vehicle_name, v.z_centre_m, v.train_x_front_m) for v in b.vehicles])
                    for candidate in [found[adverse], *found[adverse].alternatives]:
                        estimate = field.estimate(candidate, adverse == BIGGER_IS_WORSE)
                        assert abs(estimate - live_with_braking(model, candidate, read, *target)) < 1e-10 * (1 + abs(estimate))
                    compared += 1
    assert compared > 40
