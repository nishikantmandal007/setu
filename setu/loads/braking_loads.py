from setu.irc6.braking import braking_force_kn, wheels_on_the_span
from setu.irc6.irc_constants import BRAKING_ACTS_ABOVE_ROAD_M
from setu.irc6.vehicles import find_vehicle_or_its_reverse
from setu.loads.load_builders import share_between_nodes
from setu.loads.load_cases import LoadCase

FORWARDS = 1.0
BACKWARDS = -1.0


class BrakingLoadCases(dict):
    # braking load cases, and the total braking force
    def __init__(self, cases, force_kn):
        super().__init__(cases)
        self.force_kn = force_kn


# braking force spread over the wheels of the critical position, both directions
def braking_load_cases(model, critical_position):
    bridge = model.bridge
    force_kn = braking_force_kn(critical_position, bridge.span_m, bridge.skew)
    wheels = []
    for placed in critical_position.vehicles:
        vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
        for x_front_m in placed.train_x_front_m:
            wheels += wheels_on_the_span(vehicle, x_front_m, placed.z_centre_m, bridge.span_m, bridge.skew)
    weight_kn = sum(load_kn for _, _, load_kn in wheels)
    shares = {}
    for x_m, z_m, load_kn in wheels:
        share_between_nodes(model, x_m, z_m, load_kn / weight_kn, shares)
    above_deck_nodes_m = bridge.deck.thickness_m / 2 + bridge.wearing_course_thickness_m + BRAKING_ACTS_ABOVE_ROAD_M
    cases = {name: along_the_road(model, shares, direction * force_kn, above_deck_nodes_m, f"braking, {name}")
             for name, direction in (("forwards", FORWARDS), ("backwards", BACKWARDS))}
    return BrakingLoadCases(cases, force_kn)


# a braking force along the span at road level above the deck nodes
def along_the_road(model, shares, total_kn, above_deck_nodes_m, name):
    nodal_loads = []
    for (i, j), share in shares.items():
        force_kn = share * total_kn
        nodal_loads.append((model.deck_nodes[i, j], force_kn, 0.0, 0.0, 0.0, 0.0, -above_deck_nodes_m * force_kn))
    return LoadCase(name=name, nodal_loads=nodal_loads)
