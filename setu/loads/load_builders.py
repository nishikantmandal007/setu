import numpy as np
from setu.helpers import DEFAULT_SAMPLING
from setu.irc6.vehicles import find_vehicle_or_its_reverse
from setu.irc6.wheel_loads import wheel_load_offsets
from setu.loads.load_cases import LoadCase
from setu.builder.mesh import tributary_length_m


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


def braking_load(model, force_kn, name):
    mesh = model.mesh
    n_girders = model.bridge.girders.count
    force_per_girder = force_kn / n_girders
    nodal_loads = []
    for k in range(n_girders):
        mid = mesh.stations_along_span // 2
        node = model.girder_nodes[k, mid]
        nodal_loads.append((node, force_per_girder, 0.0, 0.0, 0.0, 0.0, 0.0))
    return LoadCase(name=name, nodal_loads=nodal_loads)


def seismic_load(model, ah, name):
    mesh = model.mesh
    nodal_loads = []
    for i in range(mesh.stations_along_span):
        along_m = tributary_length_m(mesh.length_mesh_m, i)
        for j in range(mesh.stations_across_width):
            across_m = tributary_length_m(mesh.width_mesh_m, j)
            area_m2 = along_m * across_m
            weight_kn = model.bridge.concrete.unit_weight_kn_m3 * model.bridge.deck.thickness_m * area_m2
            horizontal_kn = ah * weight_kn
            nodal_loads.append((model.deck_nodes[i, j], horizontal_kn, 0.0, 0.0, 0.0, 0.0, 0.0))
    return LoadCase(name=name, nodal_loads=nodal_loads)


def wind_load(model, pressure_kpa, name):
    mesh = model.mesh
    exposed_depth_m = model.girder.depth_m + model.bridge.deck.thickness_m
    nodal_loads = []
    for k in range(model.bridge.girders.count):
        for i in range(mesh.stations_along_span):
            along_m = tributary_length_m(mesh.length_mesh_m, i)
            force_kn = pressure_kpa * exposed_depth_m * along_m
            node = model.girder_nodes[k, i]
            nodal_loads.append((node, 0.0, 0.0, force_kn, 0.0, 0.0, 0.0))
    return LoadCase(name=name, nodal_loads=nodal_loads)


def fatigue_moving_load(model, vehicle, path_z_m, span_m, n_positions=50, name="fatigue"):
    from setu.irc6.constants import GRAVITY_KN_PER_TONNE
    mesh = model.mesh
    j = _nearest_width_station(mesh.width_mesh_m, path_z_m)
    positions = np.linspace(0, span_m, n_positions)
    axle_offsets_m = vehicle.axle_positions_m()
    axle_loads_kn = [t * GRAVITY_KN_PER_TONNE for t in vehicle.axle_loads_t]
    cases = []
    for p, x_front_m in enumerate(positions):
        nodal_loads = []
        for offset_m, load_kn in zip(axle_offsets_m, axle_loads_kn):
            x_m = x_front_m - offset_m
            if x_m < 0 or x_m > span_m:
                continue
            i = _nearest_span_station(mesh.length_mesh_m, x_m)
            node = model.deck_nodes[i, j]
            nodal_loads.append((node, 0.0, -load_kn, 0.0, 0.0, 0.0, 0.0))
        cases.append(LoadCase(name=f"{name}_{p}", nodal_loads=nodal_loads))
    return cases


def vehicle_load(model, critical_position, wearing_course_thickness_m=0.0, sampling=DEFAULT_SAMPLING, name="live"):
    # ponytail: vehicles only - the residual UDL and footway load are not placed yet, so this matches
    # critical_position.response only when it was searched with apply_residual_udl=False and apply_footway_load=False
    forces_kn = {}
    for placed in critical_position.vehicles:
        vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
        offsets = wheel_load_offsets(vehicle, wearing_course_thickness_m, sampling)
        factor = placed.impact_factor * critical_position.lane_reduction
        for x_front_m in placed.train_x_front_m:
            for dx_m, dz_m, load_kn in offsets:
                share_between_nodes(model, x_front_m + dx_m, placed.z_centre_m + dz_m, factor * load_kn, forces_kn)
    nodal_loads = [(model.deck_nodes[i, j], 0.0, -force_kn, 0.0, 0.0, 0.0, 0.0) for (i, j), force_kn in forces_kn.items()]
    return LoadCase(name=name, nodal_loads=nodal_loads)


def share_between_nodes(model, x_m, z_m, load_kn, forces_kn):
    length_mesh_m = model.mesh.length_mesh_m
    width_mesh_m = model.mesh.width_mesh_m
    is_on_the_deck = length_mesh_m[0] <= x_m <= length_mesh_m[-1] and width_mesh_m[0] <= z_m <= width_mesh_m[-1]
    if not is_on_the_deck:
        return
    i = _cell_containing(length_mesh_m, x_m)
    j = _cell_containing(width_mesh_m, z_m)
    fraction_along = (x_m - length_mesh_m[i]) / (length_mesh_m[i + 1] - length_mesh_m[i])
    fraction_across = (z_m - width_mesh_m[j]) / (width_mesh_m[j + 1] - width_mesh_m[j])
    corners = (
        ((i, j), (1 - fraction_along) * (1 - fraction_across)),
        ((i + 1, j), fraction_along * (1 - fraction_across)),
        ((i + 1, j + 1), fraction_along * fraction_across),
        ((i, j + 1), (1 - fraction_along) * fraction_across),
    )
    for node, weight in corners:
        forces_kn[node] = forces_kn.get(node, 0.0) + weight * load_kn


def _cell_containing(stations_m, position_m):
    last_cell = len(stations_m) - 2
    return int(np.clip(np.searchsorted(stations_m, position_m) - 1, 0, last_cell))


def _nearest_width_station(width_mesh_m, z_m):
    return int(np.argmin(np.abs(np.asarray(width_mesh_m) - z_m)))


def _nearest_span_station(length_mesh_m, x_m):
    return int(np.argmin(np.abs(np.asarray(length_mesh_m) - x_m)))
