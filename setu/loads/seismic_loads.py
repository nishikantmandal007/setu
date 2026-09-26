from setu.builder.mesh import tributary_length_m
from setu.helpers import import_opensees
from setu.irc6.braking import wheels_on_the_span
from setu.irc6.irc_constants import LIVE_LOAD_SEISMIC_FRACTION
from setu.irc6.seismic import horizontal_seismic_coefficient, vertical_seismic_coefficient
from setu.irc6.vehicles import find_vehicle_or_its_reverse
from setu.loads.dead_loads import bracing_weight_at_its_ends, deck_loads, surfacing_pressure_at
from setu.loads.load_builders import share_between_nodes
from setu.loads.load_cases import LoadCase


class SeismicLoadCases(dict):
    # seismic load cases plus the weights and coefficients behind them
    def __init__(self, cases, dead_weight_kn, live_weight_kn, horizontal_coefficient, vertical_coefficient):
        super().__init__(cases)
        self.dead_weight_kn = dead_weight_kn
        self.live_weight_kn = live_weight_kn
        self.horizontal_coefficient = horizontal_coefficient
        self.vertical_coefficient = vertical_coefficient


# longitudinal, transverse and (zones IV, V) vertical seismic load cases
def seismic_load_cases(model, site, live_critical=None, ops=None):
    dead_kn = dead_weight_at_nodes(model, ops)
    live_kn = live_weight_at_nodes(model, live_critical)
    with_live_kn = dict(dead_kn)
    for node, weight_kn in live_kn.items():
        with_live_kn[node] = with_live_kn.get(node, 0.0) + weight_kn
    ah = horizontal_seismic_coefficient(site)
    av = vertical_seismic_coefficient(site)
    cases = {
        "longitudinal": inertia(dead_kn, ah, 1, "seismic, longitudinal"),
        "transverse": inertia(with_live_kn, ah, 3, "seismic, transverse"),
    }
    if site.include_vertical:
        cases["vertical"] = inertia(with_live_kn, -av, 2, "seismic, vertical")
    return SeismicLoadCases(cases, sum(dead_kn.values()), sum(live_kn.values()), ah, av)


# the whole dead weight lumped at the nodes
def dead_weight_at_nodes(model, ops=None):
    ops = import_opensees() if ops is None else ops
    bridge = model.bridge
    slab_kpa = bridge.concrete.unit_weight_kn_m3 * bridge.deck.thickness_m
    weights_kn = {}
    for node, _, fy, *_ in deck_loads(model, lambda z_m: slab_kpa + surfacing_pressure_at(model, z_m)):
        weights_kn[node] = weights_kn.get(node, 0.0) - fy
    girder_kn_per_m = bridge.steel.unit_weight_kn_m3 * model.girder.area_m2
    for (_, i), node in model.girder_nodes.items():
        weights_kn[node] = weights_kn.get(node, 0.0) + girder_kn_per_m * tributary_length_m(model.mesh.length_mesh_m, i)
    for node, weight_kn in bracing_weight_at_its_ends(ops, model):
        weights_kn[node] = weights_kn.get(node, 0.0) + weight_kn
    return weights_kn


# 20% of the critical position's vehicles at the nodes
def live_weight_at_nodes(model, live_critical):
    if live_critical is None:
        return {}
    bridge = model.bridge
    shares = {}
    for placed in live_critical.vehicles:
        vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
        for x_front_m in placed.train_x_front_m:
            for x_m, z_m, load_kn in wheels_on_the_span(vehicle, x_front_m, placed.z_centre_m, bridge.span_m, bridge.skew):
                share_between_nodes(model, x_m, z_m, LIVE_LOAD_SEISMIC_FRACTION * load_kn, shares)
    return {model.deck_nodes[i, j]: weight_kn for (i, j), weight_kn in shares.items()}


# coefficient times weight at every node, in one direction
def inertia(weights_kn, coefficient, direction, name):
    nodal_loads = []
    for node, weight_kn in weights_kn.items():
        force = [0.0] * 6
        force[direction - 1] = coefficient * weight_kn
        nodal_loads.append((node, *force))
    return LoadCase(name=name, nodal_loads=nodal_loads)
