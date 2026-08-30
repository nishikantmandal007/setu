"""Deck geometry — cross-section strips and FE mesh grid."""
import numpy as np
from src.config.constants import ROUND_TO_DECIMALS
from src.utils.errors import CrossSectionError, InfluenceSurfaceError

class DeckStrip:
    def __init__(self, name, width_m, z_from_m, z_to_m):
        self.name = name
        self.width_m = width_m
        self.z_from_m = z_from_m
        self.z_to_m = z_to_m

    def carries_traffic(self):
        return self.name.startswith("carriageway")

    def carries_pedestrians(self):
        return self.name.startswith(("footway", "footpath"))

    def to_dict(self):
        return self.__dict__

class Carriageway:
    def __init__(self, left_m, right_m):
        self.left_m = left_m
        self.right_m = right_m

    def width_m(self):
        return round(self.right_m - self.left_m, ROUND_TO_DECIMALS)

class DeckCrossSection:
    def __init__(self, strips):
        self.strips = tuple(strips)

    @staticmethod
    def from_widths(widths):
        """Build a cross-section from a dict of strip_name -> width_m."""
        strips = []
        edge_m = 0.0
        for name, width_m in widths.items():
            if width_m < 0:
                raise CrossSectionError(f"{name}: width must not be negative, got {width_m}")
            strips.append(DeckStrip(
                name=name,
                width_m=float(width_m),
                z_from_m=round(edge_m, ROUND_TO_DECIMALS),
                z_to_m=round(edge_m + width_m, ROUND_TO_DECIMALS),
            ))
            edge_m += width_m

        cs = DeckCrossSection(strips)
        if not cs.has_carriageway():
            raise CrossSectionError("cross-section has no carriageway")
        return cs

    def total_width_m(self):
        return round(sum(s.width_m for s in self.strips), ROUND_TO_DECIMALS)

    def has_carriageway(self):
        return any(s.carries_traffic() for s in self.strips)

    def strip_named(self, name):
        for s in self.strips:
            if s.name.startswith(name):
                return s
        return None

    def footways(self):
        return [s for s in self.strips if s.carries_pedestrians()]

    def carriageways(self, split="separate"):
        stretches = [
            Carriageway(left_m=s.z_from_m, right_m=s.z_to_m)
            for s in self.strips if s.carries_traffic()
        ]
        if split == "separate":
            return stretches
        if split == "combined":
            return [Carriageway(left_m=stretches[0].left_m, right_m=stretches[-1].right_m)]
        raise CrossSectionError(f"split must be 'separate' or 'combined', got {split!r}")

class GirderSection:
    def __init__(self, area_m2, torsion_constant_m4, weak_axis_inertia_m4,
                 strong_axis_inertia_m4, elastic_modulus_kpa, shear_modulus_kpa):
        self.area_m2 = area_m2
        self.torsion_constant_m4 = torsion_constant_m4
        self.weak_axis_inertia_m4 = weak_axis_inertia_m4
        self.strong_axis_inertia_m4 = strong_axis_inertia_m4
        self.elastic_modulus_kpa = elastic_modulus_kpa
        self.shear_modulus_kpa = shear_modulus_kpa

    def to_dict(self):
        return self.__dict__

class DeckModel:
    def __init__(self, length_mesh_m, width_mesh_m, deck_nodes, girder_section,
                 girder_local_axis=(0.0, 0.0, 1.0), skew=0.0, **kwargs):
        self.length_mesh_m = length_mesh_m
        self.width_mesh_m = width_mesh_m
        self.deck_nodes = deck_nodes
        self.girder_section = girder_section
        self.girder_local_axis = girder_local_axis
        self.skew = skew
        self.girder_elements = kwargs.get("girder_elements", {})

        if len(length_mesh_m) < 2 or len(width_mesh_m) < 2:
            raise InfluenceSurfaceError(
                f"need at least 2 stations each way, got {len(length_mesh_m)} x {len(width_mesh_m)}"
            )

    def stations_along_span(self):
        return len(self.length_mesh_m)

    def stations_across_width(self):
        return len(self.width_mesh_m)

    def span_m(self):
        return float(self.length_mesh_m[-1] - self.length_mesh_m[0])

    def width_m(self):
        return float(self.width_mesh_m[-1] - self.width_mesh_m[0])

    def to_dict(self):
        return self.__dict__
