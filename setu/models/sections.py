class GirderSection:
    # the girder numbers the solver needs: area, inertias, J, E and G
    def __init__(self, area_m2, torsion_constant_m4, weak_axis_inertia_m4,
                 strong_axis_inertia_m4, elastic_modulus_kpa, shear_modulus_kpa):
        self.area_m2 = area_m2
        self.torsion_constant_m4 = torsion_constant_m4
        self.weak_axis_inertia_m4 = weak_axis_inertia_m4
        self.strong_axis_inertia_m4 = strong_axis_inertia_m4
        self.elastic_modulus_kpa = elastic_modulus_kpa
        self.shear_modulus_kpa = shear_modulus_kpa

class PlateGirderSection:
    # an I girder by its plates, as OsdagBridge sizes it
    def __init__(self, top_flange_width_m, top_flange_thickness_m, bottom_flange_width_m, bottom_flange_thickness_m, web_height_m, web_thickness_m):
        self.top_flange_width_m = top_flange_width_m
        self.top_flange_thickness_m = top_flange_thickness_m
        self.bottom_flange_width_m = bottom_flange_width_m
        self.bottom_flange_thickness_m = bottom_flange_thickness_m
        self.web_height_m = web_height_m
        self.web_thickness_m = web_thickness_m

    # overall depth, flange to flange
    @property
    def depth_m(self):
        return self.top_flange_thickness_m + self.web_height_m + self.bottom_flange_thickness_m


class ExtendedGirderSection(GirderSection):
    # section properties worked out from the plates
    def __init__(self, area_m2, neutral_axis_from_bottom_m, strong_axis_inertia_m4, weak_axis_inertia_m4, torsion_constant_m4, depth_m):
        self.area_m2 = area_m2
        self.neutral_axis_from_bottom_m = neutral_axis_from_bottom_m
        self.strong_axis_inertia_m4 = strong_axis_inertia_m4
        self.weak_axis_inertia_m4 = weak_axis_inertia_m4
        self.torsion_constant_m4 = torsion_constant_m4
        self.depth_m = depth_m

    # same section with the steel's E and G, ready for the solver
    def for_solver(self, steel):
        return GirderSection(
            area_m2=self.area_m2,
            torsion_constant_m4=self.torsion_constant_m4,
            weak_axis_inertia_m4=self.weak_axis_inertia_m4,
            strong_axis_inertia_m4=self.strong_axis_inertia_m4,
            elastic_modulus_kpa=steel.elastic_modulus_kpa,
            shear_modulus_kpa=steel.shear_modulus_kpa
        )


# b d^3 / 12 of a rectangle
def inertia_about_its_own_centre_m4(width_m, depth_m):
    return width_m * depth_m ** 3 / 12


# area, neutral axis, both inertias and J of the plate girder
def girder_properties(section):
    top_flange_area_m2 = section.top_flange_width_m * section.top_flange_thickness_m
    bottom_flange_area_m2 = section.bottom_flange_width_m * section.bottom_flange_thickness_m
    web_area_m2 = section.web_thickness_m * section.web_height_m
    area_m2 = top_flange_area_m2 + bottom_flange_area_m2 + web_area_m2
    bottom_flange_centre_m = section.bottom_flange_thickness_m / 2
    web_centre_m = section.bottom_flange_thickness_m + section.web_height_m / 2
    top_flange_centre_m = section.bottom_flange_thickness_m + section.web_height_m + section.top_flange_thickness_m / 2
    neutral_axis_m = (bottom_flange_area_m2 * bottom_flange_centre_m + web_area_m2 * web_centre_m + top_flange_area_m2 * top_flange_centre_m) / area_m2
    strong_axis_inertia_m4 = inertia_about_its_own_centre_m4(section.bottom_flange_width_m, section.bottom_flange_thickness_m) + bottom_flange_area_m2 * (neutral_axis_m - bottom_flange_centre_m) ** 2 + inertia_about_its_own_centre_m4(section.web_thickness_m, section.web_height_m) + web_area_m2 * (neutral_axis_m - web_centre_m) ** 2 + inertia_about_its_own_centre_m4(section.top_flange_width_m, section.top_flange_thickness_m) + top_flange_area_m2 * (top_flange_centre_m - neutral_axis_m) ** 2
    weak_axis_inertia_m4 = inertia_about_its_own_centre_m4(section.top_flange_thickness_m, section.top_flange_width_m) + inertia_about_its_own_centre_m4(section.bottom_flange_thickness_m, section.bottom_flange_width_m) + inertia_about_its_own_centre_m4(section.web_height_m, section.web_thickness_m)
    torsion_constant_m4 = (section.top_flange_width_m * section.top_flange_thickness_m ** 3 + section.bottom_flange_width_m * section.bottom_flange_thickness_m ** 3 + section.web_height_m * section.web_thickness_m ** 3) / 3
    return ExtendedGirderSection(area_m2=area_m2, neutral_axis_from_bottom_m=neutral_axis_m, strong_axis_inertia_m4=strong_axis_inertia_m4, weak_axis_inertia_m4=weak_axis_inertia_m4, torsion_constant_m4=torsion_constant_m4, depth_m=section.depth_m)
