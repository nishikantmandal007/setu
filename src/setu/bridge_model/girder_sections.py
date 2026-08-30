from __future__ import annotations

from dataclasses import dataclass

from ..deck_model import GirderSection
from .bridge_input import PlateGirderSection, Steel


@dataclass(frozen=True)
class GirderProperties:
    area_m2: float
    neutral_axis_from_bottom_m: float
    strong_axis_inertia_m4: float
    weak_axis_inertia_m4: float
    torsion_constant_m4: float
    depth_m: float

    def for_solver(self, steel: Steel) -> GirderSection:
        return GirderSection(
            area_m2=self.area_m2,
            torsion_constant_m4=self.torsion_constant_m4,
            weak_axis_inertia_m4=self.weak_axis_inertia_m4,
            strong_axis_inertia_m4=self.strong_axis_inertia_m4,
            elastic_modulus_kpa=steel.elastic_modulus_kpa,
            shear_modulus_kpa=steel.shear_modulus_kpa,
        )


def inertia_about_its_own_centre_m4(width_m: float, depth_m: float) -> float:
    return width_m * depth_m**3 / 12


def girder_properties(section: PlateGirderSection) -> GirderProperties:
    top_flange_area_m2 = section.top_flange_width_m * section.top_flange_thickness_m
    bottom_flange_area_m2 = section.bottom_flange_width_m * section.bottom_flange_thickness_m
    web_area_m2 = section.web_thickness_m * section.web_height_m
    area_m2 = top_flange_area_m2 + bottom_flange_area_m2 + web_area_m2

    bottom_flange_centre_m = section.bottom_flange_thickness_m / 2
    web_centre_m = section.bottom_flange_thickness_m + section.web_height_m / 2
    top_flange_centre_m = (
        section.bottom_flange_thickness_m
        + section.web_height_m
        + section.top_flange_thickness_m / 2
    )

    neutral_axis_m = (
        bottom_flange_area_m2 * bottom_flange_centre_m
        + web_area_m2 * web_centre_m
        + top_flange_area_m2 * top_flange_centre_m
    ) / area_m2

    # Parallel axis theorem, plate by plate.
    strong_axis_inertia_m4 = (
        inertia_about_its_own_centre_m4(
            section.bottom_flange_width_m, section.bottom_flange_thickness_m
        )
        + bottom_flange_area_m2 * (neutral_axis_m - bottom_flange_centre_m) ** 2
        + inertia_about_its_own_centre_m4(section.web_thickness_m, section.web_height_m)
        + web_area_m2 * (neutral_axis_m - web_centre_m) ** 2
        + inertia_about_its_own_centre_m4(
            section.top_flange_width_m, section.top_flange_thickness_m
        )
        + top_flange_area_m2 * (top_flange_centre_m - neutral_axis_m) ** 2
    )

    # Sideways every plate is centred on the girder centreline, so no parallel axis term.
    weak_axis_inertia_m4 = (
        inertia_about_its_own_centre_m4(
            section.top_flange_thickness_m, section.top_flange_width_m
        )
        + inertia_about_its_own_centre_m4(
            section.bottom_flange_thickness_m, section.bottom_flange_width_m
        )
        + inertia_about_its_own_centre_m4(section.web_height_m, section.web_thickness_m)
    )

    # An open section built of thin plates twists as the sum of its plates.
    torsion_constant_m4 = (
        section.top_flange_width_m * section.top_flange_thickness_m**3
        + section.bottom_flange_width_m * section.bottom_flange_thickness_m**3
        + section.web_height_m * section.web_thickness_m**3
    ) / 3

    return GirderProperties(
        area_m2=area_m2,
        neutral_axis_from_bottom_m=neutral_axis_m,
        strong_axis_inertia_m4=strong_axis_inertia_m4,
        weak_axis_inertia_m4=weak_axis_inertia_m4,
        torsion_constant_m4=torsion_constant_m4,
        depth_m=section.depth_m,
    )
