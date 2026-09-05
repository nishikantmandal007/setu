import math


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
        return 5000 * math.sqrt(self.characteristic_strength_mpa) * 1000

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
