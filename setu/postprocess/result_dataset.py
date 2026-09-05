import numpy as np
import xarray as xr
from setu.postprocess.girder_response import girder_forces, girder_deflections


FORCE_COMPONENTS = [
    "Mx_i", "Vy_i", "Vz_i", "Tx_i", "My_i", "Mz_i",
    "Mx_j", "Vy_j", "Vz_j", "Tx_j", "My_j", "Mz_j",
]

DISPLACEMENT_COMPONENTS = ["x", "y", "z", "theta_x", "theta_y", "theta_z"]


def forces_dataset(model, ops, load_case_name):
    n_girders = model.bridge.girders.count
    n_elements = model.mesh.stations_along_span - 1
    elements = []
    data = []
    for k in range(n_girders):
        for e in range(n_elements):
            tag = model.girder_elements[k, e]
            elements.append(tag)
            f = ops.eleResponse(tag, "localForce")
            data.append(f[:12])
    return xr.Dataset(
        {"forces": (["Element", "Component", "Loadcase"], np.array(data)[:, :, np.newaxis])},
        coords={
            "Element": elements,
            "Component": FORCE_COMPONENTS,
            "Loadcase": [load_case_name],
        },
    )


def displacements_dataset(model, ops, load_case_name):
    nodes = []
    data = []
    for k in range(model.bridge.girders.count):
        for i in range(model.mesh.stations_along_span):
            node = model.girder_nodes[k, i]
            nodes.append(node)
            disp = [ops.nodeDisp(node, dof) for dof in range(1, 7)]
            data.append(disp)
    return xr.Dataset(
        {"displacements": (["Node", "Component", "Loadcase"], np.array(data)[:, :, np.newaxis])},
        coords={
            "Node": nodes,
            "Component": DISPLACEMENT_COMPONENTS,
            "Loadcase": [load_case_name],
        },
    )


def full_dataset(model, ops, load_case_name):
    forces = forces_dataset(model, ops, load_case_name)
    displacements = displacements_dataset(model, ops, load_case_name)
    return xr.merge([forces, displacements])


def merge_datasets(datasets):
    return xr.concat(datasets, dim="Loadcase")
