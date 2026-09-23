from setu.builder.mesh import tributary_length_m
from setu.irc6.irc_constants import WIND_ON_LIVE_LOAD_ACTS_ABOVE_ROAD_M
from setu.irc6.wind import (
    drag_coefficient,
    hourly_mean_wind,
    longitudinal_wind_force_kn,
    transverse_wind_force_kn,
    vertical_wind_force_kn,
    wind_on_live_load_kn,
)
from setu.loads.load_cases import LoadCase

KPA_PER_PA = 1e-3
BLOWING_TOWARDS_PLUS_Z = 1.0
BLOWING_TOWARDS_MINUS_Z = -1.0
UPWARD = 1.0
DOWNWARD = -1.0


class WindLoadCases(dict):
    def __init__(self, cases, forces_kn, speed_at_deck_mps):
        super().__init__(cases)
        self.forces_kn = forces_kn
        self.speed_at_deck_mps = speed_at_deck_mps


def wind_load_cases(model, site):
    bridge = model.bridge
    span_m = bridge.span_m
    speed_mps, pressure_pa = hourly_mean_wind(site.height_m, site.terrain, site.basic_wind_speed_mps, site.funnelling, site.construction)
    pressure_kpa = pressure_pa * KPA_PER_PA
    girder_depth_m = model.girder.depth_m
    exposed_area_m2 = site.exposed_area_m2
    if exposed_area_m2 is None:
        exposed_area_m2 = span_m * (girder_depth_m + bridge.deck.thickness_m + site.solid_barrier_height_m)
    plan_area_m2 = span_m * bridge.width_m() if site.plan_area_m2 is None else site.plan_area_m2
    drag = site.drag
    if drag is None:
        drag = drag_coefficient(bridge.girders.count, model.mesh.girder_spacing_m, girder_depth_m)
    transverse_kn = transverse_wind_force_kn(pressure_kpa, exposed_area_m2, drag, span_m, site.gust)
    longitudinal_kn = longitudinal_wind_force_kn(transverse_kn)
    vertical_kn = vertical_wind_force_kn(pressure_kpa, plan_area_m2, span_m, site.gust, site.lift)
    on_live_transverse_kn, on_live_longitudinal_kn = wind_on_live_load_kn(
        pressure_kpa, span_m, site.solid_barrier_height_m, site.gust, site.drag_on_live_load, site.live_load_exposed_area_m2
    )
    centroid_above_deck_nodes_m = (site.solid_barrier_height_m - girder_depth_m) / 2
    live_load_wind_above_deck_nodes_m = bridge.deck.thickness_m / 2 + bridge.wearing_course_thickness_m + WIND_ON_LIVE_LOAD_ACTS_ABOVE_ROAD_M
    edges = (0, model.mesh.stations_across_width - 1)
    cases = {
        "transverse from the left": edge_line_load(model, edges[0], BLOWING_TOWARDS_PLUS_Z * transverse_kn, centroid_above_deck_nodes_m, "wind, transverse from the left"),
        "transverse from the right": edge_line_load(model, edges[1], BLOWING_TOWARDS_MINUS_Z * transverse_kn, centroid_above_deck_nodes_m, "wind, transverse from the right"),
        "longitudinal": spread_along(model, longitudinal_kn, centroid_above_deck_nodes_m, everywhere, "wind, longitudinal"),
        "vertical upward": spread_up(model, UPWARD * vertical_kn, "wind, vertical upward"),
        "vertical downward": spread_up(model, DOWNWARD * vertical_kn, "wind, vertical downward"),
        "on live load from the left": spread_across(model, BLOWING_TOWARDS_PLUS_Z * on_live_transverse_kn, live_load_wind_above_deck_nodes_m, "wind on live load, from the left"),
        "on live load from the right": spread_across(model, BLOWING_TOWARDS_MINUS_Z * on_live_transverse_kn, live_load_wind_above_deck_nodes_m, "wind on live load, from the right"),
        "on live load, longitudinal": spread_along(model, on_live_longitudinal_kn, live_load_wind_above_deck_nodes_m, on_the_carriageway, "wind on live load, longitudinal"),
    }
    forces_kn = {"transverse": transverse_kn, "longitudinal": longitudinal_kn, "vertical": vertical_kn,
                 "on live load, transverse": on_live_transverse_kn, "on live load, longitudinal": on_live_longitudinal_kn}
    return WindLoadCases(cases, forces_kn, speed_mps)


def edge_line_load(model, edge_station, total_kn, above_deck_nodes_m, name):
    mesh = model.mesh
    kn_per_m = total_kn / model.bridge.span_m
    nodal_loads = []
    for i in range(mesh.stations_along_span):
        force_kn = kn_per_m * tributary_length_m(mesh.length_mesh_m, i)
        nodal_loads.append((model.deck_nodes[i, edge_station], 0.0, 0.0, force_kn, above_deck_nodes_m * force_kn, 0.0, 0.0))
    return LoadCase(name=name, nodal_loads=nodal_loads)


def everywhere(model, z_m):
    return True


def on_the_carriageway(model, z_m):
    return any(strip.carries_traffic() and strip.z_from_m <= z_m <= strip.z_to_m for strip in model.bridge.cross_section.strips)


def shares_of_the_area(model, counts):
    mesh = model.mesh
    areas = {}
    for i in range(mesh.stations_along_span):
        for j in range(mesh.stations_across_width):
            if counts(model, float(mesh.width_mesh_m[j])):
                areas[i, j] = tributary_length_m(mesh.length_mesh_m, i) * tributary_length_m(mesh.width_mesh_m, j)
    total_m2 = sum(areas.values())
    return {node: area_m2 / total_m2 for node, area_m2 in areas.items()}


def spread_along(model, total_kn, above_deck_nodes_m, counts, name):
    nodal_loads = []
    for (i, j), share in shares_of_the_area(model, counts).items():
        force_kn = share * total_kn
        nodal_loads.append((model.deck_nodes[i, j], force_kn, 0.0, 0.0, 0.0, 0.0, -above_deck_nodes_m * force_kn))
    return LoadCase(name=name, nodal_loads=nodal_loads)


def spread_across(model, total_kn, above_deck_nodes_m, name):
    nodal_loads = []
    for (i, j), share in shares_of_the_area(model, on_the_carriageway).items():
        force_kn = share * total_kn
        nodal_loads.append((model.deck_nodes[i, j], 0.0, 0.0, force_kn, above_deck_nodes_m * force_kn, 0.0, 0.0))
    return LoadCase(name=name, nodal_loads=nodal_loads)


def spread_up(model, total_kn, name):
    nodal_loads = [(model.deck_nodes[i, j], 0.0, share * total_kn, 0.0, 0.0, 0.0, 0.0) for (i, j), share in shares_of_the_area(model, everywhere).items()]
    return LoadCase(name=name, nodal_loads=nodal_loads)
