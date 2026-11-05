import numpy as np

from setu.analysis.along_span import along_the_mesh, positions_along_span, response_to_one_vehicle_everywhere
from setu.helpers import adverse_sign
from setu.irc6.irc_constants import (
    SPECIAL_VEHICLE_AXLE_LOADS_KN,
    SPECIAL_VEHICLE_AXLE_SPACING_M,
    SPECIAL_VEHICLE_ECCENTRICITY_M,
    SPECIAL_VEHICLE_TYRE_OFFSETS_M,
)
from setu.models.deck import DeckCrossSection, DeckStrip
from setu.utils.constants import KERB_PREFIX

TYRES_PER_AXLE = 2 * len(SPECIAL_VEHICLE_TYRE_OFFSETS_M)
POSITIONS_ACROSS_THE_BAND = 13
BESIDE_THE_SPECIAL_VEHICLE = "beside the special vehicle"


class SpecialVehiclePlacement:
    # the Class SV's worst response on one carriageway (no impact, cl. 204.5.4), where its front axle and centreline stood
    def __init__(self, response, carriageway, x_front_m, z_centre_m):
        self.response = response
        self.carriageway = carriageway
        self.x_front_m = x_front_m
        self.z_centre_m = z_centre_m


# every tyre of the Class SV as (dx behind the front axle, dz from the vehicle centreline, load kN): Fig. 6 and 6A
def special_vehicle_offsets():
    axle_positions_m = np.concatenate([[0.0], np.cumsum(SPECIAL_VEHICLE_AXLE_SPACING_M)])
    tyres_dz_m = [side * offset_m for side in (-1.0, 1.0) for offset_m in SPECIAL_VEHICLE_TYRE_OFFSETS_M]
    return np.array([(dx_m, dz_m, axle_kn / TYRES_PER_AXLE)
                     for dx_m, axle_kn in zip(axle_positions_m, SPECIAL_VEHICLE_AXLE_LOADS_KN, strict=True) for dz_m in tyres_dz_m])


# the worst Class SV response on each carriageway, its centreline within 300 mm of the carriageway centreline (204.5.3, Fig. 6B)
def special_vehicle_on_each_carriageway(surface, cross_section, adverse, sampling):
    on_the_mesh = surface.along_the_mesh()
    sheared = along_the_mesh(special_vehicle_offsets(), surface.skew)
    x_front_m = positions_along_span(on_the_mesh, sheared)
    sign = adverse_sign(adverse)
    found = []
    for k, carriageway in enumerate(cross_section.carriageways()):
        centre_m = (carriageway.left_m + carriageway.right_m) / 2
        z_centre_m = np.linspace(centre_m - SPECIAL_VEHICLE_ECCENTRICITY_M, centre_m + SPECIAL_VEHICLE_ECCENTRICITY_M, POSITIONS_ACROSS_THE_BAND)
        responses = response_to_one_vehicle_everywhere(on_the_mesh, sheared, x_front_m, z_centre_m, sampling)
        i, j = np.unravel_index(int(np.argmax(sign * responses)), responses.shape)
        found.append(SpecialVehiclePlacement(float(responses[i, j]), k, float(x_front_m[i] + surface.skew * z_centre_m[j]), float(z_centre_m[j])))
    return found


# the deck as normal traffic sees it while the Class SV crosses carriageway k: that carriageway and the footways and kerbs beside it
# take no other live load (204.5.4, Fig. 6B notes); every other carriageway keeps its traffic and footways (Fig. 6B case 4)
def without_the_special_vehicle_carriageway(cross_section, k):
    carriageways = [strip for strip in cross_section.strips if strip.carries_traffic()]
    centres_m = [(strip.z_from_m + strip.z_to_m) / 2 for strip in carriageways]
    strips = []
    for strip in cross_section.strips:
        centre_m = (strip.z_from_m + strip.z_to_m) / 2
        nearest = int(np.argmin([abs(centre_m - c) for c in centres_m]))
        beside = strip.carries_traffic() or strip.carries_pedestrians() or strip.name.startswith(KERB_PREFIX)
        renamed = f"{BESIDE_THE_SPECIAL_VEHICLE} ({strip.name})" if beside and nearest == k else strip.name
        strips.append(DeckStrip(renamed, strip.width_m, strip.z_from_m, strip.z_to_m))
    return DeckCrossSection(strips)
