import numpy as np
from setu.helpers import DEFAULT_SAMPLING, where_a_load_hurts
from setu.irc6.irc_constants import RESIDUAL_UDL_KPA
from setu.irc6.lanes import cell_centres
from setu.irc6.vehicles import find_vehicle_or_its_reverse
from setu.irc6.wheel_loads import wheel_load_offsets
from setu.loads.load_cases import LoadCase
from setu.builder.mesh import tributary_length_m
from setu.utils.constants import NOTHING_THERE_M, TOLERANCE_M


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


def fatigue_moving_load(model, vehicle, path_z_m, span_m, n_positions=50, name="fatigue"):
    from setu.irc6.irc_constants import GRAVITY_KN_PER_TONNE
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


def live_load(model, critical_position, surface, sampling=DEFAULT_SAMPLING, name="live"):
    forces_kn = vehicle_forces(model, critical_position, critical_position.wearing_course_thickness_m, sampling)
    area_loads = [(RESIDUAL_UDL_KPA, critical_position.residual_udl_strips)]
    area_loads += [(pressure_kpa, [(from_m, to_m)]) for from_m, to_m, pressure_kpa in critical_position.footway_strips]
    on_the_mesh = surface.along_the_mesh()
    for pressure_kpa, strips in area_loads:
        for from_m, to_m in strips:
            where_it_hurts(model, on_the_mesh, from_m, to_m, pressure_kpa * critical_position.lane_reduction, critical_position.adverse, sampling, forces_kn)
    return as_a_load_case(model, forces_kn, name)


def where_it_hurts(model, surface, from_m, to_m, pressure_kpa, adverse, sampling, forces_kn):
    if to_m - from_m <= NOTHING_THERE_M:
        return
    x_centres_m, x_widths_m = cell_centres(surface.length_mesh_m, sampling.udl_cells_per_mesh_interval_along_span)
    z_centres_m, z_widths_m = cell_centres([from_m, to_m], sampling.udl_cells_per_mesh_interval_across_width)
    ordinates = surface.influence_at(x_centres_m[:, None], z_centres_m[None, :])
    hurts = where_a_load_hurts(ordinates, adverse)
    for i, j in zip(*np.nonzero(hurts), strict=True):
        along_m = float(x_centres_m[i])
        z_m = float(z_centres_m[j])
        share_between_nodes(model, along_m + model.bridge.skew * z_m, z_m, pressure_kpa * x_widths_m[i] * z_widths_m[j], forces_kn)


def vehicle_load(model, critical_position, wearing_course_thickness_m=None, sampling=DEFAULT_SAMPLING, name="vehicles"):
    if wearing_course_thickness_m is None:
        wearing_course_thickness_m = critical_position.wearing_course_thickness_m
    return as_a_load_case(model, vehicle_forces(model, critical_position, wearing_course_thickness_m, sampling), name)


def as_a_load_case(model, forces_kn, name):
    nodal_loads = [(model.deck_nodes[i, j], 0.0, -force_kn, 0.0, 0.0, 0.0, 0.0) for (i, j), force_kn in forces_kn.items()]
    return LoadCase(name=name, nodal_loads=nodal_loads)


def vehicle_forces(model, critical_position, wearing_course_thickness_m, sampling):
    forces_kn = {}
    for placed in critical_position.vehicles:
        vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
        offsets = wheel_load_offsets(vehicle, wearing_course_thickness_m, sampling)
        factor = placed.impact_factor * critical_position.lane_reduction
        for x_front_m in placed.train_x_front_m:
            for dx_m, dz_m, load_kn in offsets:
                share_between_nodes(model, x_front_m + dx_m, placed.z_centre_m + dz_m, factor * load_kn, forces_kn)
    return forces_kn


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


def _cell_containing(stations_m, position_m):
    last_cell = len(stations_m) - 2
    return int(np.clip(np.searchsorted(stations_m, position_m) - 1, 0, last_cell))


def _nearest_width_station(width_mesh_m, z_m):
    return int(np.argmin(np.abs(np.asarray(width_mesh_m) - z_m)))


def _nearest_span_station(length_mesh_m, x_m):
    return int(np.argmin(np.abs(np.asarray(length_mesh_m) - x_m)))
