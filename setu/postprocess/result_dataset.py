import xarray as xr

# OpenSees localForce order, named the way OsdagBridge reads ds["forces"]
FORCE_COMPONENTS = ["Vx_i", "Vy_i", "Vz_i", "Mx_i", "My_i", "Mz_i", "Vx_j", "Vy_j", "Vz_j", "Mx_j", "My_j", "Mz_j"]
DISPLACEMENT_COMPONENTS = ["x", "y", "z", "theta_x", "theta_y", "theta_z"]
UNITS = "forces kN, moments kN·m, displacements m, rotations rad"


# girder element end forces and girder node displacements of the load case just solved, in OsdagBridge's xarray layout
def result_dataset(model, ops, load_case_name):
    elements = list(model.girder_elements.values())
    nodes = list(model.girder_nodes.values())
    forces = xr.DataArray([[ops.eleResponse(tag, "localForce")[:len(FORCE_COMPONENTS)] for tag in elements]],
                          dims=["Loadcase", "Element", "Component"],
                          coords={"Loadcase": [load_case_name], "Element": elements, "Component": FORCE_COMPONENTS}, name="forces")
    displacements = xr.DataArray([[ops.nodeDisp(node) for node in nodes]],
                                 dims=["Loadcase", "Node", "Component"],
                                 coords={"Loadcase": [load_case_name], "Node": nodes, "Component": DISPLACEMENT_COMPONENTS}, name="displacements")
    dataset = xr.merge([forces, displacements], join="outer")
    dataset.attrs["units"] = UNITS
    return dataset


# stack the load cases into one dataset
def merge_datasets(datasets):
    merged = xr.concat(datasets, dim="Loadcase")
    merged.attrs["units"] = UNITS
    return merged
