"""Working out what a plate girder's section is worth.

Area, where its neutral axis sits, how stiff it is about each axis, and how much
it resists twist - all from the plate sizes, by the parallel axis theorem,
written out one plate at a time.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..deck_model import GirderSection
from .inputs import PlateGirderSection, Steel


@dataclass(frozen=True)
class GirderProperties:
    """What a girder section is worth, structurally."""

    area_m2: float
    neutral_axis_from_bottom_m: float
    strong_axis_inertia_m4: float
    """Izz - resists bending along the span. This is the one that carries the load."""

    weak_axis_inertia_m4: float
    """Iyy - resists bending sideways."""

    torsion_constant_m4: float
    depth_m: float

    def for_solver(self, steel: Steel) -> GirderSection:
        """Returns these properties in the form the influence solver needs."""
        return GirderSection(
            area_m2=self.area_m2,
            torsion_constant_m4=self.torsion_constant_m4,
            weak_axis_inertia_m4=self.weak_axis_inertia_m4,
            strong_axis_inertia_m4=self.strong_axis_inertia_m4,
            elastic_modulus_kpa=steel.elastic_modulus_kpa,
            shear_modulus_kpa=steel.shear_modulus_kpa,
        )


def properties_of(section: PlateGirderSection) -> GirderProperties:
    """Returns the structural properties of a welded plate girder."""
    top_flange_area_m2 = section.top_flange_width_m * section.top_flange_thickness_m
    bottom_flange_area_m2 = section.bottom_flange_width_m * section.bottom_flange_thickness_m
    web_area_m2 = section.web_thickness_m * section.web_height_m
    area_m2 = top_flange_area_m2 + bottom_flange_area_m2 + web_area_m2

    # Height of each plate's own centre above the bottom of the girder.
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

    # Parallel axis theorem, plate by plate: each plate's own stiffness about its
    # own centre, plus its area times how far that centre is from the neutral axis.
    strong_axis_inertia_m4 = (
        section.bottom_flange_width_m * section.bottom_flange_thickness_m**3 / 12
        + bottom_flange_area_m2 * (neutral_axis_m - bottom_flange_centre_m) ** 2
        + section.web_thickness_m * section.web_height_m**3 / 12
        + web_area_m2 * (neutral_axis_m - web_centre_m) ** 2
        + section.top_flange_width_m * section.top_flange_thickness_m**3 / 12
        + top_flange_area_m2 * (top_flange_centre_m - neutral_axis_m) ** 2
    )

    # Sideways, every plate is centred on the girder's own centreline, so there
    # is no parallel axis term to add.
    weak_axis_inertia_m4 = (
        section.top_flange_thickness_m * section.top_flange_width_m**3 / 12
        + section.bottom_flange_thickness_m * section.bottom_flange_width_m**3 / 12
        + section.web_height_m * section.web_thickness_m**3 / 12
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
