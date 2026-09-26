from setu.utils.constants import KPA_PER_MPA, LONG_TERM, SHORT_TERM

# IRC:22-2015 Clause 604.3 - modular ratio by how long the load stays on
CREEP_FACTOR = 0.5
SMALLEST_MODULAR_RATIO = {SHORT_TERM: 7.5, LONG_TERM: 15.0}
CONCRETE_STIFFNESS_THAT_STAYS = {SHORT_TERM: 1.0, LONG_TERM: CREEP_FACTOR}


class Steel:
    # structural steel as OsdagBridge gives it: E in MPa, unit weight in kN/m3
    def __init__(self, elastic_modulus_mpa, poissons_ratio, unit_weight_kn_m3):
        self.elastic_modulus_mpa = elastic_modulus_mpa
        self.poissons_ratio = poissons_ratio
        self.unit_weight_kn_m3 = unit_weight_kn_m3

    # E in kN/m2, the unit the solver works in
    @property
    def elastic_modulus_kpa(self):
        return self.elastic_modulus_mpa * KPA_PER_MPA

    # G = E / 2(1 + v), in kN/m2
    @property
    def shear_modulus_kpa(self):
        return self.elastic_modulus_kpa / (2 * (1 + self.poissons_ratio))


class Concrete:
    # deck concrete as OsdagBridge gives it: Ecm in MPa, unit weight in kN/m3
    def __init__(self, elastic_modulus_mpa, poissons_ratio, unit_weight_kn_m3):
        self.elastic_modulus_mpa = elastic_modulus_mpa
        self.poissons_ratio = poissons_ratio
        self.unit_weight_kn_m3 = unit_weight_kn_m3

    # Ecm in kN/m2, the unit the solver works in
    @property
    def elastic_modulus_kpa(self):
        return self.elastic_modulus_mpa * KPA_PER_MPA

    # slab modulus through the modular ratio for short or long term load
    def modulus_for(self, load_duration, steel_modulus_kpa):
        stays_kpa = CONCRETE_STIFFNESS_THAT_STAYS[load_duration] * self.elastic_modulus_kpa
        modular_ratio = max(steel_modulus_kpa / stays_kpa, SMALLEST_MODULAR_RATIO[load_duration])
        return steel_modulus_kpa / modular_ratio


class SurfacingLayer:
    # a layer on the deck: thickness and unit weight
    def __init__(self, thickness_m, unit_weight_kn_m3):
        self.thickness_m = thickness_m
        self.unit_weight_kn_m3 = unit_weight_kn_m3

    # weight per square metre of deck
    @property
    def pressure_kpa(self):
        return self.unit_weight_kn_m3 * self.thickness_m
