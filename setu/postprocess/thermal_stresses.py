import numpy as np

from setu.irc6.irc_constants import THERMAL_EXPANSION_PER_C
from setu.utils.constants import SHORT_TERM

LAYERS_PER_PLATE = 40
NOTHING_BEYOND_THE_PROFILE_C = 0.0


class ThermalStresses:
    # primary stress through the depth, with slab and steel top and bottom picked out, and the slab width it was worked on
    def __init__(self, layers, stresses, slab_thickness_m, slab_width_m):
        self.layers = layers
        self.slab_width_m = slab_width_m
        self.stresses = stresses
        depths_m = [depth_m for depth_m, _, _ in layers]
        self.slab_top_kpa = stresses[0]
        self.slab_bottom_kpa = stresses[int(np.searchsorted(depths_m, slab_thickness_m)) - 1]
        self.steel_top_kpa = stresses[int(np.searchsorted(depths_m, slab_thickness_m))]
        self.steel_bottom_kpa = stresses[-1]

# self-balancing stresses in one girder's composite section from a temperature difference profile
def primary_thermal_stresses(bridge, girder, profile):
    slab_width_m = effective_slab_width_m(bridge, girder)
    layers = composite_layers(bridge, slab_width_m)
    return ThermalStresses(layers, primary_stresses(layers, profile), bridge.deck.thickness_m, slab_width_m)


# IRC:22 clause 603.2.1: inner girder min(L/4, spacing); outer girder min(L/8, spacing/2) + min(overhang, L/8)
def effective_slab_width_m(bridge, girder):
    spacing_m = (bridge.width_m() - 2 * bridge.deck.overhang_m) / (bridge.girders.count - 1)
    eighth_of_span_m = bridge.span_m / 8
    if girder in (0, bridge.girders.count - 1):
        return min(eighth_of_span_m, spacing_m / 2) + min(bridge.deck.overhang_m, eighth_of_span_m)
    return min(2 * eighth_of_span_m, spacing_m)


# the slab over its effective width and the girder plates, cut into thin layers with their moduli
def composite_layers(bridge, slab_width_m):
    girder = bridge.girders.section
    concrete_kpa = bridge.concrete.modulus_for(SHORT_TERM, bridge.steel.elastic_modulus_kpa)
    steel_kpa = bridge.steel.elastic_modulus_kpa
    plates = [
        (bridge.deck.thickness_m, slab_width_m, concrete_kpa),
        (girder.top_flange_thickness_m, girder.top_flange_width_m, steel_kpa),
        (girder.web_height_m, girder.web_thickness_m, steel_kpa),
        (girder.bottom_flange_thickness_m, girder.bottom_flange_width_m, steel_kpa),
    ]
    layers = []
    top_m = 0.0
    for thickness_m, width_m, modulus_kpa in plates:
        step_m = thickness_m / LAYERS_PER_PLATE
        layers += [(top_m + (k + 0.5) * step_m, width_m * step_m, modulus_kpa) for k in range(LAYERS_PER_PLATE)]
        top_m += thickness_m
    return layers


# free strain minus the plane that balances it, times E
def primary_stresses(layers, profile, alpha_per_c=THERMAL_EXPANSION_PER_C):
    depths_m = np.array([depth_m for depth_m, _, _ in layers])
    stiffness = np.array([area_m2 * modulus_kpa for _, area_m2, modulus_kpa in layers])
    profile_depths_m, profile_c = zip(*profile, strict=True)
    free_strain = alpha_per_c * np.interp(depths_m, profile_depths_m, profile_c, right=NOTHING_BEYOND_THE_PROFILE_C)
    balance = np.array([[stiffness.sum(), (stiffness * depths_m).sum()], [(stiffness * depths_m).sum(), (stiffness * depths_m ** 2).sum()]])
    pulled = np.array([(stiffness * free_strain).sum(), (stiffness * free_strain * depths_m).sum()])
    at_top, per_metre = np.linalg.solve(balance, pulled)
    moduli = np.array([modulus_kpa for _, _, modulus_kpa in layers])
    return list(moduli * (at_top + per_metre * depths_m - free_strain))


# alpha L delta T at the free bearing
def free_bearing_movement_m(span_m, temperature_range_c, alpha_per_c=THERMAL_EXPANSION_PER_C):
    low_c, high_c = temperature_range_c
    return alpha_per_c * span_m * (high_c - low_c)
