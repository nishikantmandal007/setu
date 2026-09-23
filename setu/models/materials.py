import numpy as np
from setu.utils.constants import KPA_PER_GPA, LONG_TERM, SHORT_TERM

# IRC:22-2015 Table III.1 - secant modulus of concrete by cube strength
CUBE_STRENGTHS_MPA = (15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90)
SECANT_MODULI_GPA = (27, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 38, 39, 40, 40, 41)

# IRC:22-2015 Clause 604.3 - modular ratio by how long the load stays on
CREEP_FACTOR = 0.5
SMALLEST_MODULAR_RATIO = {SHORT_TERM: 7.5, LONG_TERM: 15.0}
CONCRETE_STIFFNESS_THAT_STAYS = {SHORT_TERM: 1.0, LONG_TERM: CREEP_FACTOR}


class Steel:
    def __init__(self, elastic_modulus_kpa=200000000.0, poissons_ratio=0.3, unit_weight_kn_m3=78.5, **kwargs):
        self.elastic_modulus_kpa = elastic_modulus_kpa
        self.poissons_ratio = poissons_ratio
        self.unit_weight_kn_m3 = unit_weight_kn_m3

    @property
    def shear_modulus_kpa(self):
        return self.elastic_modulus_kpa / (2 * (1 + self.poissons_ratio))


class Concrete:
    def __init__(self, characteristic_strength_mpa=35, poissons_ratio=0.2, unit_weight_kn_m3=25.0, **kwargs):
        self.characteristic_strength_mpa = characteristic_strength_mpa
        self.poissons_ratio = poissons_ratio
        self.unit_weight_kn_m3 = unit_weight_kn_m3

    @property
    def elastic_modulus_kpa(self):
        return float(np.interp(self.characteristic_strength_mpa, CUBE_STRENGTHS_MPA, SECANT_MODULI_GPA)) * KPA_PER_GPA

    def modulus_for(self, load_duration, steel_modulus_kpa):
        stays_kpa = CONCRETE_STIFFNESS_THAT_STAYS[load_duration] * self.elastic_modulus_kpa
        modular_ratio = max(steel_modulus_kpa / stays_kpa, SMALLEST_MODULAR_RATIO[load_duration])
        return steel_modulus_kpa / modular_ratio

    @property
    def shear_modulus_kpa(self):
        return self.elastic_modulus_kpa / (2 * (1 + self.poissons_ratio))


class SurfacingLayer:
    def __init__(self, thickness_m, unit_weight_kn_m3, **kwargs):
        self.thickness_m = thickness_m
        self.unit_weight_kn_m3 = unit_weight_kn_m3

    @property
    def pressure_kpa(self):
        return self.unit_weight_kn_m3 * self.thickness_m
