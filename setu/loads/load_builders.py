import numpy as np
from setu.helpers import DEFAULT_SAMPLING
from setu.irc6.irc_constants import RESIDUAL_UDL_KPA
from setu.irc6.lanes import cell_centres, cells_where_it_hurts
from setu.irc6.vehicles import find_vehicle_or_its_reverse
from setu.irc6.wheel_loads import wheel_load_offsets
from setu.loads.load_cases import LoadCase
from setu.utils.constants import TOLERANCE_M


RESIDUAL_UDL = "residual UDL"
FOOTWAY = "footway"


# every load a critical position puts on the deck, as plain rows another program can take in:
# one row per wheel, and one row per patch of residual UDL or footway load where it makes the response worse.
# x is global (along the first bearing line, skew included), z is across from the left edge.
def applied_live_loads(bridge, critical_position, surface, sampling=DEFAULT_SAMPLING):
    return wheel_rows(bridge, critical_position, sampling), patch_rows(bridge, critical_position, surface, sampling)


# one row per wheel of every placed vehicle, with its impact and lane reduction
def wheel_rows(bridge, critical_position, sampling):
    rows = []
    for placed in critical_position.vehicles:
        vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
        for train, x_front_m in enumerate(placed.train_x_front_m):
            for dx_m, dz_m, load_kn in wheel_load_offsets(vehicle, critical_position.wearing_course_thickness_m, sampling):
                x_m, z_m = x_front_m + dx_m, placed.z_centre_m + dz_m
                rows.append({"vehicle": placed.vehicle_name, "train": train, "x_m": float(x_m), "z_m": float(z_m),
                             "wheel_load_kn": float(load_kn), "impact_factor": placed.impact_factor, "lane_reduction": critical_position.lane_reduction,
                             "applied_kn": float(load_kn * placed.impact_factor * critical_position.lane_reduction),
                             "on_span": bool(-TOLERANCE_M <= x_m - bridge.skew * z_m <= bridge.span_m + TOLERANCE_M)})
    return rows


# residual UDL and footway patches: cells where the load hurts, joined into runs along the span
def patch_rows(bridge, critical_position, surface, sampling):
    on_the_mesh = surface.along_the_mesh()
    strips = [(RESIDUAL_UDL, RESIDUAL_UDL_KPA, from_m, to_m) for from_m, to_m in critical_position.residual_udl_strips]
    strips += [(FOOTWAY, pressure_kpa, from_m, to_m) for from_m, to_m, pressure_kpa in critical_position.footway_strips]
    rows = []
    for kind, pressure_kpa, from_m, to_m in strips:
        cells = cells_where_it_hurts(on_the_mesh, from_m, to_m, critical_position.adverse, sampling)
        if cells is None:
            continue
        for j, z_centre_m in enumerate(cells.z_centres_m):
            z_from_m, z_to_m = z_centre_m - cells.z_widths_m[j] / 2, z_centre_m + cells.z_widths_m[j] / 2
            for first, last in runs_of_true(cells.hurts[:, j]):
                along_from_m = cells.x_centres_m[first] - cells.x_widths_m[first] / 2
                along_to_m = cells.x_centres_m[last] + cells.x_widths_m[last] / 2
                rows.append({"kind": kind, "pressure_kpa": float(pressure_kpa * critical_position.lane_reduction),
                             "along_from_m": float(along_from_m), "along_to_m": float(along_to_m), "z_from_m": float(z_from_m), "z_to_m": float(z_to_m),
                             "corners_x_z_m": [(float(along_m + bridge.skew * z_m), float(z_m)) for along_m, z_m in
                                               ((along_from_m, z_from_m), (along_to_m, z_from_m), (along_to_m, z_to_m), (along_from_m, z_to_m))]})
    return rows


# (first, last) index of every run of True values
def runs_of_true(flags):
    runs = []
    first = None
    for i, flag in enumerate(flags):
        if flag and first is None:
            first = i
        if not flag and first is not None:
            runs.append((first, i - 1))
            first = None
    if first is not None:
        runs.append((first, len(flags) - 1))
    return runs


# the load case OpenSees solves for a critical position: exactly the rows of applied_live_loads, shared onto the deck nodes
def live_load(model, critical_position, surface, sampling=DEFAULT_SAMPLING):
    wheels, patches = applied_live_loads(model.bridge, critical_position, surface, sampling)
    forces_kn = {}
    for wheel in wheels:
        share_between_nodes(model, wheel["x_m"], wheel["z_m"], wheel["applied_kn"], forces_kn)
    x_centres_m, x_widths_m = cell_centres(model.mesh.length_mesh_m, sampling.udl_cells_per_mesh_interval_along_span)
    for patch in patches:
        z_m = (patch["z_from_m"] + patch["z_to_m"]) / 2
        width_m = patch["z_to_m"] - patch["z_from_m"]
        inside = (x_centres_m > patch["along_from_m"]) & (x_centres_m < patch["along_to_m"])
        for along_m, length_m in zip(x_centres_m[inside], x_widths_m[inside], strict=True):
            share_between_nodes(model, along_m + model.bridge.skew * z_m, z_m, patch["pressure_kpa"] * length_m * width_m, forces_kn)
    return as_a_load_case(model, forces_kn, "live")


# nodal forces dict to a LoadCase
def as_a_load_case(model, forces_kn, name):
    nodal_loads = [(model.deck_nodes[i, j], 0.0, -force_kn, 0.0, 0.0, 0.0, 0.0) for (i, j), force_kn in forces_kn.items()]
    return LoadCase(name=name, nodal_loads=nodal_loads)


# split a point load onto the four corners of its mesh cell
def share_between_nodes(model, x_m, z_m, load_kn, forces_kn):
    length_mesh_m = model.mesh.length_mesh_m
    width_mesh_m = model.mesh.width_mesh_m
    along_m = x_m - model.bridge.skew * z_m
    is_on_the_deck = length_mesh_m[0] - TOLERANCE_M <= along_m <= length_mesh_m[-1] + TOLERANCE_M and width_mesh_m[0] - TOLERANCE_M <= z_m <= width_mesh_m[-1] + TOLERANCE_M
    if not is_on_the_deck:
        return
    along_m = min(max(along_m, length_mesh_m[0]), length_mesh_m[-1])
    z_m = min(max(z_m, width_mesh_m[0]), width_mesh_m[-1])
    i = _cell_containing(length_mesh_m, along_m)
    j = _cell_containing(width_mesh_m, z_m)
    fraction_along = (along_m - length_mesh_m[i]) / (length_mesh_m[i + 1] - length_mesh_m[i])
    fraction_across = (z_m - width_mesh_m[j]) / (width_mesh_m[j + 1] - width_mesh_m[j])
    corners = (
        ((i, j), (1 - fraction_along) * (1 - fraction_across)),
        ((i + 1, j), fraction_along * (1 - fraction_across)),
        ((i + 1, j + 1), fraction_along * fraction_across),
        ((i, j + 1), (1 - fraction_along) * fraction_across),
    )
    for node, weight in corners:
        forces_kn[node] = forces_kn.get(node, 0.0) + weight * load_kn


# index of the mesh cell a position falls in
def _cell_containing(stations_m, position_m):
    last_cell = len(stations_m) - 2
    return int(np.clip(np.searchsorted(stations_m, position_m) - 1, 0, last_cell))


