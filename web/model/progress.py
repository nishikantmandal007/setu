"""JSON previews of completed analysis operations; no extra solver runs."""

import numpy as np
from setu.solver import backend

from setu.irc6.irc_constants import FATIGUE_TRUCK_AXLE_LOADS_T, FATIGUE_TRUCK_AXLE_SPACING_M, FATIGUE_TRUCK_OVERALL_WIDTH_M, FATIGUE_TRUCK_TYRE_PAIR_WIDTH_M
from setu.utils.constants import MAX_MOMENT, MIDSPAN_DEFLECTION, SUPPORT_SHEAR, BEARING_REACTION
from setu.builder.assembly import BEARING_VERTICAL_STIFFNESS_KN_PER_M
from setu.irc6.lanes import count_design_lanes

from model.drawing import body_of


# bridge geometry sent once per progress stream
def geometry(bridge, mesh):
    return {"span_m": bridge.span_m, "width_m": bridge.width_m(), "skew": bridge.skew,
            "slab_m": bridge.deck.thickness_m, "wearing_m": bridge.wearing_course_thickness_m,
            "girder_lines_m": mesh.girder_lines_m.tolist(), "brace_lines_m": mesh.brace_lines_m.tolist(),
            "depths_m": [bridge.girders.section_at(g).depth_m for g in range(bridge.girders.count)],
            "sections": [dict(vars(bridge.girders.section_at(g))) for g in range(bridge.girders.count)],
            "bracing": bridge.bracing.arrangement, "brace_area_m2": bridge.bracing.area_m2,
            "bearing_stiffness_kn_m": BEARING_VERTICAL_STIFFNESS_KN_PER_M,
            "strips": [{"name": s.name, "from_m": s.z_from_m, "to_m": s.z_to_m, "width_m": s.width_m} for s in bridge.cross_section.strips],
            "carriageways": [{"from_m": c.left_m, "to_m": c.right_m, "width_m": c.width_m(),
                               "design_lanes": count_design_lanes(c.width_m())} for c in bridge.cross_section.carriageways()]}


# units of the checked response
def response_unit(name):
    if "stress" in name:
        return "MPa"
    if MAX_MOMENT in name:
        return "kN·m"
    if MIDSPAN_DEFLECTION in name:
        return "m"
    if SUPPORT_SHEAR in name or BEARING_REACTION in name:
        return "kN"
    return "response units"


# original surface nodes and exact extrema
def surface(surface):
    # Display a bounded set of original nodes, without interpolating new ordinates.
    along = np.unique(np.linspace(0, len(surface.length_mesh_m)-1, min(41, len(surface.length_mesh_m))).round().astype(int))
    across = np.unique(np.linspace(0, len(surface.width_mesh_m)-1, min(25, len(surface.width_mesh_m))).round().astype(int))
    return {"name": surface.name, "unit": response_unit(surface.name) + " / kN",
            "full_shape": list(surface.values.shape),
            "x_m": surface.length_mesh_m[along].tolist(), "z_m": surface.width_mesh_m[across].tolist(),
            "values": surface.values[np.ix_(along, across)].tolist(),
            "minimum": float(surface.values.min()), "maximum": float(surface.values.max())}


# vehicle bodies at the solved critical positions
def vehicles(critical):
    return [body_of(v.vehicle_name, float(x), v.z_centre_m, v.impact_factor)
            for v in critical.vehicles for x in v.train_x_front_m]


# solved girder forces and bearing reactions
def forces(forces, girder=0):
    return {"girder": girder, "x_m": forces.stations_m.tolist(),
            "moment_kn_m": forces.composite_moment_kn_m.tolist(), "shear_kn": forces.shear_kn.tolist(),
            "axial_kn": forces.axial_kn.tolist(), "torsion_kn_m": forces.torsion_kn_m.tolist(),
            "deflection_mm": (1000 * forces.deflection_m).tolist(),
            "near_reaction_kn": forces.reaction_kn, "far_reaction_kn": forces.end_reaction_kn}


# preview of a completed analysis operation
def completed(name, value, args):
    if name == "dead_load_forces":
        return {"kind": "dead", "forces": forces(value.total[0]), "construction_stages": list(value.stages)}
    if name == "surface_for":
        return {"kind": "surface", "surface": surface(value), "girder": args[2], "station_m": float(args[1].mesh.length_mesh_m[args[3][1]])}
    if name == "fatigue_range":
        axles = np.r_[0., np.cumsum(FATIGUE_TRUCK_AXLE_SPACING_M)].tolist()
        return {"kind": "fatigue", "name": args[0].name, "unit": response_unit(args[0].name),
                "largest": value.largest, "smallest": value.smallest, "range": value.range,
                "minimum_front_m": value.x_front_at_smallest_m, "maximum_front_m": value.x_front_at_largest_m,
                "vehicles": [{"name": "Fatigue truck", "x_m": value.x_front_at_largest_m, "z_m": value.z_centre_m,
                              "heading": -1, "tracked": False, "width_m": FATIGUE_TRUCK_OVERALL_WIDTH_M,
                              "gauge_m": FATIGUE_TRUCK_OVERALL_WIDTH_M - FATIGUE_TRUCK_TYRE_PAIR_WIDTH_M,
                              "body_m": [-FATIGUE_TRUCK_TYRE_PAIR_WIDTH_M, axles[-1] + FATIGUE_TRUCK_TYRE_PAIR_WIDTH_M],
                              "axles_m": axles, "axle_loads_t": list(FATIGUE_TRUCK_AXLE_LOADS_T), "impact_factor": value.impact_factor,
                              "axle_positions_only": True}]}
    return None


# total downward load in the exact construction case
def applied_loads(model, load_case):
    total = sum(-fy for _, _, fy, *_ in load_case.nodal_loads)
    for element, kind, parameters in load_case.element_loads:
        if kind == "-beamUniform":
            ends = [backend.node_coordinates(node) for node in backend.element_nodes(element)]
            total -= parameters[0] * float(np.linalg.norm(np.subtract(*ends)))
    return float(total)
