import numpy as np
from src.services.load_cases import LoadCase
from src.services.bridge_geometry import tributary_length_m


def pressure_load(model, z_from_m, z_to_m, pressure_kpa, name):
    mesh = model.mesh
    nodal_loads = []
    for i in range(mesh.stations_along_span):
        along_m = tributary_length_m(mesh.length_mesh_m, i)
        for j in range(mesh.stations_across_width):
            z_m = float(mesh.width_mesh_m[j])
            if z_m < z_from_m or z_m > z_to_m:
                continue
            across_m = tributary_length_m(mesh.width_mesh_m, j)
            force_kn = pressure_kpa * along_m * across_m
            nodal_loads.append((model.deck_nodes[i, j], 0.0, -force_kn, 0.0, 0.0, 0.0, 0.0))
    return LoadCase(name=name, nodal_loads=nodal_loads)


def line_load(model, z_m, intensity_kn_m, name):
    mesh = model.mesh
    j = _nearest_width_station(mesh.width_mesh_m, z_m)
    nodal_loads = []
    for i in range(mesh.stations_along_span):
        along_m = tributary_length_m(mesh.length_mesh_m, i)
        force_kn = intensity_kn_m * along_m
        nodal_loads.append((model.deck_nodes[i, j], 0.0, -force_kn, 0.0, 0.0, 0.0, 0.0))
    return LoadCase(name=name, nodal_loads=nodal_loads)


def point_load(model, node_tag, force_kn, name):
    nodal_loads = [(node_tag, 0.0, -force_kn, 0.0, 0.0, 0.0, 0.0)]
    return LoadCase(name=name, nodal_loads=nodal_loads)


def temperature_gradient(model, delta_t_top, delta_t_bottom, name):
    mesh = model.mesh
    bridge = model.bridge
    alpha = bridge.steel.thermal_expansion if hasattr(bridge.steel, "thermal_expansion") else 12e-6
    depth_m = model.girder.depth_m
    delta_t = delta_t_top - delta_t_bottom
    curvature = alpha * delta_t / depth_m
    modulus = bridge.steel.elastic_modulus_kpa
    inertia = model.girder.strong_axis_inertia_m4
    equivalent_moment = modulus * inertia * curvature
    element_loads = []
    for element in model.girder_elements.values():
        element_loads.append((element, "-beamUniform", (0.0, 0.0)))
    nodal_loads = []
    for k in range(bridge.girders.count):
        n_stations = mesh.stations_along_span
        for i in [0, n_stations - 1]:
            node = model.girder_nodes[k, i]
            sign = 1.0 if i == 0 else -1.0
            nodal_loads.append((node, 0.0, 0.0, 0.0, 0.0, 0.0, sign * equivalent_moment))
    return LoadCase(name=name, nodal_loads=nodal_loads)


def _nearest_width_station(width_mesh_m, z_m):
    return int(np.argmin(np.abs(np.asarray(width_mesh_m) - z_m)))
