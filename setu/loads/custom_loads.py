import math

import numpy as np

from setu.loads.load_builders import as_a_load_case, share_between_nodes
from setu.utils.constants import LINE, POINT, TOLERANCE_M

PIECES_PER_MESH_CELL = 4


# one load case per custom load group
def custom_load_cases(model, loads):
    forces_by_group = {}
    for load in loads:
        forces_kn = forces_by_group.setdefault(load.group, {})
        for along_m, z_m, load_kn in pieces_of(model, load):
            check_on_the_deck(model, along_m, z_m, load)
            share_between_nodes(model, along_m + model.bridge.skew * z_m, z_m, load_kn, forces_kn)
    return {group: as_a_load_case(model, forces_kn, f"custom, {group}") for group, forces_kn in forces_by_group.items()}


# the custom load cut into point loads: one, along a line, or over an area
def pieces_of(model, load):
    if load.shape == POINT:
        return [(load.x_from_bearing_m, load.z_from_left_edge_m, load.magnitude)]
    piece_m = smallest_mesh_cell_m(model) / PIECES_PER_MESH_CELL
    if load.shape == LINE:
        length_m = math.hypot(load.x_end_m - load.x_from_bearing_m, load.z_end_m - load.z_from_left_edge_m)
        count = max(1, math.ceil(length_m / piece_m))
        fractions = (np.arange(count) + 0.5) / count
        return [(load.x_from_bearing_m + f * (load.x_end_m - load.x_from_bearing_m), load.z_from_left_edge_m + f * (load.z_end_m - load.z_from_left_edge_m), load.magnitude * length_m / count) for f in fractions]
    along = cells_between(load.x_from_bearing_m, load.x_end_m, piece_m)
    across = cells_between(load.z_from_left_edge_m, load.z_end_m, piece_m)
    return [(x_m, z_m, load.magnitude * dx_m * dz_m) for x_m, dx_m in along for z_m, dz_m in across]


# centres and widths of equal cells from..to
def cells_between(from_m, to_m, piece_m):
    count = max(1, math.ceil((to_m - from_m) / piece_m))
    width_m = (to_m - from_m) / count
    return [(from_m + (k + 0.5) * width_m, width_m) for k in range(count)]


# smallest mesh spacing either way
def smallest_mesh_cell_m(model):
    return float(min(np.diff(model.mesh.length_mesh_m).min(), np.diff(model.mesh.width_mesh_m).min()))


# refuse a custom load that reaches off the deck
def check_on_the_deck(model, along_m, z_m, load):
    mesh = model.mesh
    on_it = mesh.length_mesh_m[0] - TOLERANCE_M <= along_m <= mesh.length_mesh_m[-1] + TOLERANCE_M and mesh.width_mesh_m[0] - TOLERANCE_M <= z_m <= mesh.width_mesh_m[-1] + TOLERANCE_M
    if not on_it:
        raise ValueError(f"custom {load.group} {load.shape} load reaches ({along_m:.3f} m along, {z_m:.3f} m across), which is off the deck")
