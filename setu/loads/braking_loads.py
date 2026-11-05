import math

import numpy as np
from setu.irc6.braking import braking_force_kn, wheels_on_the_span
from setu.irc6.irc_constants import BRAKING_ACTS_ABOVE_ROAD_M
from setu.irc6.vehicles import find_vehicle_or_its_reverse
from setu.loads.load_builders import share_between_nodes
from setu.loads.load_cases import LoadCase
from setu.utils.constants import TOLERANCE_M

FORWARDS = 1.0
BACKWARDS = -1.0


class BrakingLoadCases(dict):
    # braking load cases, and the total braking force
    def __init__(self, cases, force_kn):
        super().__init__(cases)
        self.force_kn = force_kn


# braking force spread over the wheels of the critical position, both directions
def braking_load_cases(model, critical_position, *, height_above_deck_m=None):
    if height_above_deck_m is not None and (not math.isfinite(height_above_deck_m) or height_above_deck_m < 0):
        raise ValueError("braking height_above_deck_m must be finite and nonnegative")
    bridge = model.bridge
    force_kn = braking_force_kn(critical_position, bridge.span_m, bridge.skew)
    wheels = []
    for placed in critical_position.vehicles:
        vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
        for x_front_m in placed.train_x_front_m:
            wheels += wheels_on_the_span(vehicle, x_front_m, placed.z_centre_m, bridge.span_m, bridge.skew, bridge.wearing_course_thickness_m)
    weight_kn = sum(load_kn for _, _, load_kn in wheels)
    shares = {}
    for x_m, z_m, load_kn in wheels:
        share_between_nodes(model, x_m, z_m, load_kn / weight_kn, shares)
    height = bridge.wearing_course_thickness_m + BRAKING_ACTS_ABOVE_ROAD_M if height_above_deck_m is None else height_above_deck_m
    above_deck_nodes_m = bridge.deck.thickness_m / 2 + height
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


class BrakingField:
    # the response to a unit braking force at each deck node: the longitudinal ordinate less the braking arm times the rotation
    # ordinate, both read off a solved surface; a braking case is a load-weighted mix of these, so a candidate's braking can be
    # estimated without building its load case
    def __init__(self, model, surface, height_above_deck_m=None):
        bridge = model.bridge
        mesh = model.mesh
        height = bridge.wearing_course_thickness_m + BRAKING_ACTS_ABOVE_ROAD_M if height_above_deck_m is None else height_above_deck_m
        arm_m = bridge.deck.thickness_m / 2 + height
        tags = np.array([[model.deck_nodes[i, j] for j in range(mesh.stations_across_width)] for i in range(mesh.stations_along_span)])
        ordinates = surface.displacements_of(tags.ravel())
        self.field = (ordinates[:, 0] - arm_m * ordinates[:, 5]).reshape(tags.shape)
        self.length_mesh_m = np.asarray(mesh.length_mesh_m, float)
        self.width_mesh_m = np.asarray(mesh.width_mesh_m, float)
        self.bridge = bridge
        self.by_placement = {}

    # one placed vehicle's wheels on the deck, load-weighted over the field and interpolated as share_between_nodes shares them,
    # and its weight on the span; remembered, since one placement serves many lane layouts
    def weighted_and_weight(self, placed):
        key = id(placed)
        if key not in self.by_placement:
            bridge = self.bridge
            vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
            wheels = [wheel for x_front_m in placed.train_x_front_m
                      for wheel in wheels_on_the_span(vehicle, x_front_m, placed.z_centre_m, bridge.span_m, bridge.skew, bridge.wearing_course_thickness_m)]
            self.by_placement[key] = (self.weighted_field(wheels), float(sum(load_kn for _, _, load_kn in wheels)), placed)
        weighted, weight, _ = self.by_placement[key]
        return weighted, weight

    # sum of load times the field under each wheel on the deck
    def weighted_field(self, wheels):
        if not wheels:
            return 0.0
        x_m, z_m, load_kn = (np.array(column, float) for column in zip(*wheels))
        stations_m, strips_m = self.length_mesh_m, self.width_mesh_m
        along_m = x_m - self.bridge.skew * z_m
        on_the_deck = ((along_m >= stations_m[0] - TOLERANCE_M) & (along_m <= stations_m[-1] + TOLERANCE_M)
                       & (z_m >= strips_m[0] - TOLERANCE_M) & (z_m <= strips_m[-1] + TOLERANCE_M))
        along_m = np.clip(along_m[on_the_deck], stations_m[0], stations_m[-1])
        z_m = np.clip(z_m[on_the_deck], strips_m[0], strips_m[-1])
        i = np.clip(np.searchsorted(stations_m, along_m) - 1, 0, len(stations_m) - 2)
        j = np.clip(np.searchsorted(strips_m, z_m) - 1, 0, len(strips_m) - 2)
        fraction_along = (along_m - stations_m[i]) / (stations_m[i + 1] - stations_m[i])
        fraction_across = (z_m - strips_m[j]) / (strips_m[j + 1] - strips_m[j])
        f = self.field
        under = ((1 - fraction_along) * (1 - fraction_across) * f[i, j] + fraction_along * (1 - fraction_across) * f[i + 1, j]
                 + fraction_along * fraction_across * f[i + 1, j + 1] + (1 - fraction_along) * fraction_across * f[i, j + 1])
        return float(np.sum(load_kn[on_the_deck] * under))

    # estimated live load plus braking, taking the braking direction live_with_braking would
    def estimate(self, critical, adverse_is_bigger):
        if not critical.takes_braking or not critical.vehicles:
            return critical.response
        weighted = weight = 0.0
        for placed in critical.vehicles:
            placed_weighted, placed_weight = self.weighted_and_weight(placed)
            weighted += placed_weighted
            weight += placed_weight
        if weight == 0.0:
            return critical.response
        braking = abs(braking_force_kn(critical, self.bridge.span_m, self.bridge.skew) * weighted / weight)
        return critical.response + (braking if adverse_is_bigger else -braking)
