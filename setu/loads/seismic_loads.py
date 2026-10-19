from functools import lru_cache
from setu.builder.mesh import tributary_length_m
from setu.irc6.braking import wheels_on_the_span
from setu.irc6.irc_constants import LIVE_LOAD_SEISMIC_FRACTION
from setu.irc6.seismic import horizontal_seismic_coefficient, vertical_seismic_coefficient
from setu.irc6.vehicles import find_vehicle_or_its_reverse
from setu.loads.dead_loads import bracing_weight_at_its_ends, deck_loads, superimposed_dead_load, surfacing_load
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
def seismic_load_cases(model, site, live_critical=None):
    dead_kn, longitudinal = dead_weight_inertia(model, site)
    live_total = None if site.live_weight_kn is None else LIVE_LOAD_SEISMIC_FRACTION * site.live_weight_kn
    live_kn = override_weight(model, live_weight_at_nodes(model, live_critical), live_total)
    with_live_kn = dict(dead_kn)
    for node, weight_kn in live_kn.items():
        with_live_kn[node] = with_live_kn.get(node, 0.0) + weight_kn
    ah = horizontal_seismic_coefficient(site)
    av = vertical_seismic_coefficient(site)
    cases = {
        "longitudinal": longitudinal,
        "transverse": inertia(with_live_kn, ah, 3, "seismic, transverse"),
    }
    if site.include_vertical:
        cases["vertical"] = inertia(with_live_kn, -av, 2, "seismic, vertical")
    return SeismicLoadCases(cases, sum(dead_kn.values()), sum(live_kn.values()), ah, av)


# the dead weight at the nodes and its longitudinal inertia, which no live load joins: worked out once per model and site, only read after
@lru_cache(maxsize=2)
def dead_weight_inertia(model, site):
    dead_kn = override_weight(model, dead_weight_at_nodes(model), site.dead_weight_kn)
    return dead_kn, inertia(dead_kn, horizontal_seismic_coefficient(site), 1, "seismic, longitudinal")


# the whole dead weight lumped at the nodes: slab, SIDL, surfacing, girders and bracing; worked out once per model and only read after
@lru_cache(maxsize=2)
def dead_weight_at_nodes(model):
    bridge = model.bridge
    slab_kpa = bridge.concrete.unit_weight_kn_m3 * bridge.deck.thickness_m
    weights_kn = {}
    on_the_deck = deck_loads(model, lambda z_m: slab_kpa) + superimposed_dead_load(model).nodal_loads + surfacing_load(model).nodal_loads
    for node, _, fy, *_ in on_the_deck:
        weights_kn[node] = weights_kn.get(node, 0.0) - fy
    for (k, i), node in model.girder_nodes.items():
        girder_kn_per_m = bridge.steel.unit_weight_kn_m3 * model.girders[k].area_m2
        weights_kn[node] = weights_kn.get(node, 0.0) + girder_kn_per_m * tributary_length_m(model.mesh.length_mesh_m, i)
    for node, weight_kn in bracing_weight_at_its_ends(model):
        weights_kn[node] = weights_kn.get(node, 0.0) + weight_kn
    return weights_kn


# 20% of the critical position's vehicles at the nodes
def live_weight_at_nodes(model, live_critical):
    bridge = model.bridge
    shares = {}
    if live_critical is None:
        return shares
    for placed in live_critical.vehicles:
        vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
        for x_front_m in placed.train_x_front_m:
            for x_m, z_m, load_kn in wheels_on_the_span(vehicle, x_front_m, placed.z_centre_m, bridge.span_m, bridge.skew, bridge.wearing_course_thickness_m):
                share_between_nodes(model, x_m, z_m, LIVE_LOAD_SEISMIC_FRACTION * load_kn, shares)
    return {model.deck_nodes[i, j]: weight_kn for (i, j), weight_kn in shares.items()}


# Keep the native mass distribution; without a native weight use tributary deck area.
def override_weight(model, weights_kn, total_kn):
    if total_kn is None:
        return weights_kn
    current_kn = sum(weights_kn.values())
    if current_kn:
        return {node: weight * total_kn / current_kn for node, weight in weights_kn.items()}
    pressure_kpa = total_kn / (model.bridge.span_m * model.bridge.width_m())
    return {node: -fy for node, _, fy, *_ in deck_loads(model, lambda _: pressure_kpa)}


# coefficient times weight at every node, in one direction
def inertia(weights_kn, coefficient, direction, name):
    nodal_loads = []
    for node, weight_kn in weights_kn.items():
        force = [0.0] * 6
        force[direction - 1] = coefficient * weight_kn
        nodal_loads.append((node, *force))
    return LoadCase(name=name, nodal_loads=nodal_loads)
