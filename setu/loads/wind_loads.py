from setu.builder.mesh import tributary_length_m
from setu.irc6.irc_constants import (
    LIFT_COEFFICIENT,
    LIVE_LOAD_DRAG_COEFFICIENT,
    LIVE_LOAD_EXPOSED_HEIGHT_M,
    LIVE_LOAD_LONGITUDINAL_WIND_FRACTION,
    LONGITUDINAL_WIND_FRACTION,
    SKEW_COEFFICIENTS_OTHER_SPANS,
    VERTICAL_WIND_ECCENTRICITY_OF_WIDTH,
    WIND_ON_LIVE_LOAD_ACTS_ABOVE_ROAD_M,
)
from setu.irc6.wind import (
    check_scope,
    design_wind_speed_mps,
    drag_depth_m,
    exposed_depth_m,
    gust_factor,
    hourly_mean_wind_speed_mps,
    needs_hourly_mean_method,
    service_drag_coefficient,
    wind_pressure_pa,
)
from setu.loads.load_builders import share_between_nodes
from setu.loads.load_cases import LoadCase
from setu.utils.constants import KPA_PER_PA

BLOWING_TOWARDS_PLUS_Z = 1.0
BLOWING_TOWARDS_MINUS_Z = -1.0
UPWARD = 1.0
DOWNWARD = -1.0
LEFT_OF_CENTRE = -1.0
RIGHT_OF_CENTRE = 1.0
WITH_LIVE_LOAD = ", with live load"
WITHOUT_LIVE_LOAD = ""


class WindLoadCases(dict):
    # wind load cases, the forces behind them, the deck-level design wind speed, and the (transverse, longitudinal) coefficient pairs
    # each wind direction takes: (1, 0.25) under Table 5 column 2, the Table 6 skew pairs otherwise
    def __init__(self, cases, forces_kn, speed_at_deck_mps, directions):
        super().__init__(cases)
        self.forces_kn = forces_kn
        self.speed_at_deck_mps = speed_at_deck_mps
        self.directions = directions


# pressure in kPa at a height: Table 5 column 2 (3 s gust) and, where Table 5 asks for it, column 3 (hourly mean x G)
def pressures_kpa(site, height_m, return_period_years, hourly):
    gust_kpa = wind_pressure_pa(design_wind_speed_mps(site, height_m, return_period_years)) * KPA_PER_PA
    if not hourly:
        return gust_kpa, None
    gust = gust_factor(site.terrain_category) if site.gust is None else site.gust
    return gust_kpa, wind_pressure_pa(hourly_mean_wind_speed_mps(site, height_m, return_period_years)) * KPA_PER_PA * gust


# F = P A C under column 2, the larger of that and pbar A G C under column 3 (Table 5)
def larger_of_the_methods_kn(pressures, area_m2, coefficient):
    gust_kpa, hourly_kpa_times_g = pressures
    column_2_kn = gust_kpa * area_m2 * coefficient
    return column_2_kn if hourly_kpa_times_g is None else max(column_2_kn, hourly_kpa_times_g * area_m2 * coefficient)


# clause 209 as replaced by IRC:6-2017 Amendment 10: superstructure wind without and with live load, vertical wind at B/4 either side,
# and wind on the live load, for the service stage
def wind_load_cases(model, site):
    bridge = model.bridge
    span_m = bridge.span_m
    check_scope(span_m, site.pier_height_m)
    hourly = needs_hourly_mean_method(span_m, site.pier_height_m)
    girder_depth_m = model.girders[0].depth_m
    if any(girder.depth_m != girder_depth_m for girder in model.girders[1:]):
        if any(value is None for value in (site.exposed_area_m2, site.drag, site.force_height_above_deck_m)):
            raise ValueError("unequal-depth wind requires explicit exposed_area_m2, drag and force_height_above_deck_m; "
                             "automatic shielding and application height are not supported")
    road_depth_m = girder_depth_m + bridge.deck.thickness_m + bridge.wearing_course_thickness_m
    width_m = bridge.width_m()
    on_superstructure = pressures_kpa(site, site.superstructure_top_m, site.return_period_years, hourly)
    on_live_load = pressures_kpa(site, site.road_level_m + LIVE_LOAD_EXPOSED_HEIGHT_M, site.return_period_years, hourly)
    bottom_above_deck_nodes_m = -(girder_depth_m + bridge.deck.thickness_m / 2)
    forces_kn, cases = {}, {}
    for suffix, with_live_load in ((WITHOUT_LIVE_LOAD, False), (WITH_LIVE_LOAD, True)):
        depth_m = exposed_depth_m(road_depth_m, site.solid_barrier_height_m, with_live_load)
        area_m2 = span_m * depth_m if site.exposed_area_m2 is None else site.exposed_area_m2
        drag = site.drag
        if drag is None:
            drag = service_drag_coefficient(width_m, drag_depth_m(road_depth_m, site.solid_barrier_height_m, with_live_load), site.deck_cross_slope_deg)
        transverse_kn = larger_of_the_methods_kn(on_superstructure, area_m2, drag)
        centroid_m = bottom_above_deck_nodes_m + depth_m / 2
        if site.force_height_above_deck_m is not None:
            centroid_m = site.force_height_above_deck_m + bridge.deck.thickness_m / 2
        edges = (0, model.mesh.stations_across_width - 1)
        cases[f"transverse from the left{suffix}"] = edge_line_load(model, edges[0], BLOWING_TOWARDS_PLUS_Z * transverse_kn, centroid_m, f"wind, transverse from the left{suffix}")
        cases[f"transverse from the right{suffix}"] = edge_line_load(model, edges[1], BLOWING_TOWARDS_MINUS_Z * transverse_kn, centroid_m, f"wind, transverse from the right{suffix}")
        cases[f"longitudinal{suffix}"] = spread_along(model, transverse_kn, centroid_m, everywhere, f"wind, longitudinal at full transverse force{suffix}")
        forces_kn[f"transverse{suffix}"] = transverse_kn
    plan_area_m2 = span_m * width_m if site.plan_area_m2 is None else site.plan_area_m2
    vertical_kn = larger_of_the_methods_kn(on_superstructure, plan_area_m2, LIFT_COEFFICIENT if site.lift is None else site.lift)
    for vertical_name, vertical_sign in (("upward", UPWARD), ("downward", DOWNWARD)):
        for side_name, side in (("left", LEFT_OF_CENTRE), ("right", RIGHT_OF_CENTRE)):
            z_m = width_m / 2 + side * VERTICAL_WIND_ECCENTRICITY_OF_WIDTH * width_m
            cases[f"vertical {vertical_name}, B/4 {side_name}"] = line_along_span(model, z_m, vertical_sign * vertical_kn, f"wind, vertical {vertical_name} at B/4 {side_name}")
    live_area_m2 = site.live_load_exposed_area_m2
    if live_area_m2 is None:
        live_area_m2 = span_m * max(LIVE_LOAD_EXPOSED_HEIGHT_M - site.solid_barrier_height_m, 0.0)
    live_drag = LIVE_LOAD_DRAG_COEFFICIENT if site.drag_on_live_load is None else site.drag_on_live_load
    on_live_transverse_kn = larger_of_the_methods_kn(on_live_load, live_area_m2, live_drag)
    live_load_wind_above_deck_nodes_m = bridge.deck.thickness_m / 2 + bridge.wearing_course_thickness_m + WIND_ON_LIVE_LOAD_ACTS_ABOVE_ROAD_M
    cases["on live load from the left"] = spread_across(model, BLOWING_TOWARDS_PLUS_Z * on_live_transverse_kn, live_load_wind_above_deck_nodes_m, "wind on live load, from the left")
    cases["on live load from the right"] = spread_across(model, BLOWING_TOWARDS_MINUS_Z * on_live_transverse_kn, live_load_wind_above_deck_nodes_m, "wind on live load, from the right")
    cases["on live load, longitudinal"] = spread_along(model, on_live_transverse_kn, live_load_wind_above_deck_nodes_m, on_the_carriageway, "wind on live load, longitudinal at full transverse force")
    if hourly:
        directions = list(SKEW_COEFFICIENTS_OTHER_SPANS.values())
        live_directions = directions
    else:
        directions = [(1.0, LONGITUDINAL_WIND_FRACTION)]
        live_directions = [(1.0, LIVE_LOAD_LONGITUDINAL_WIND_FRACTION)]
    forces_kn.update({"transverse": forces_kn["transverse"], "longitudinal": max(along for _, along in directions) * forces_kn["transverse"],
                      "vertical": vertical_kn, "on live load, transverse": on_live_transverse_kn,
                      "on live load, longitudinal": max(along for _, along in live_directions) * on_live_transverse_kn})
    speed_at_deck_mps = design_wind_speed_mps(site, site.road_level_m, site.return_period_years)
    return WindLoadCases(cases, forces_kn, speed_at_deck_mps, directions)


# a vertical line load along the span at one position across the deck, shared onto the mesh nodes
def line_along_span(model, z_m, total_kn, name):
    mesh = model.mesh
    shares_kn = {}
    for i in range(mesh.stations_along_span):
        x_m = float(mesh.length_mesh_m[i]) + model.bridge.skew * z_m
        share_between_nodes(model, x_m, z_m, total_kn * tributary_length_m(mesh.length_mesh_m, i) / model.bridge.span_m, shares_kn)
    return LoadCase(name=name, nodal_loads=[(model.deck_nodes[i, j], 0.0, force_kn, 0.0, 0.0, 0.0, 0.0) for (i, j), force_kn in shares_kn.items()])


# a sideways wind force along one deck edge, at the centroid of the exposed area
def edge_line_load(model, edge_station, total_kn, above_deck_nodes_m, name):
    mesh = model.mesh
    kn_per_m = total_kn / model.bridge.span_m
    nodal_loads = []
    for i in range(mesh.stations_along_span):
        force_kn = kn_per_m * tributary_length_m(mesh.length_mesh_m, i)
        nodal_loads.append((model.deck_nodes[i, edge_station], 0.0, 0.0, force_kn, above_deck_nodes_m * force_kn, 0.0, 0.0))
    return LoadCase(name=name, nodal_loads=nodal_loads)


# every deck node counts
def everywhere(model, z_m):
    return True


# only nodes on the road count
def on_the_carriageway(model, z_m):
    return any(strip.carries_traffic() and strip.z_from_m <= z_m <= strip.z_to_m for strip in model.bridge.cross_section.strips)


# each counted node's share of the counted area
def shares_of_the_area(model, counts):
    mesh = model.mesh
    areas = {}
    for i in range(mesh.stations_along_span):
        for j in range(mesh.stations_across_width):
            if counts(model, float(mesh.width_mesh_m[j])):
                areas[i, j] = tributary_length_m(mesh.length_mesh_m, i) * tributary_length_m(mesh.width_mesh_m, j)
    total_m2 = sum(areas.values())
    return {node: area_m2 / total_m2 for node, area_m2 in areas.items()}


# a force along the span spread by area, at a height above the deck nodes
def spread_along(model, total_kn, above_deck_nodes_m, counts, name):
    nodal_loads = []
    for (i, j), share in shares_of_the_area(model, counts).items():
        force_kn = share * total_kn
        nodal_loads.append((model.deck_nodes[i, j], force_kn, 0.0, 0.0, 0.0, 0.0, -above_deck_nodes_m * force_kn))
    return LoadCase(name=name, nodal_loads=nodal_loads)


# a sideways force spread over the carriageway, at a height above the deck nodes
def spread_across(model, total_kn, above_deck_nodes_m, name):
    nodal_loads = []
    for (i, j), share in shares_of_the_area(model, on_the_carriageway).items():
        force_kn = share * total_kn
        nodal_loads.append((model.deck_nodes[i, j], 0.0, 0.0, force_kn, above_deck_nodes_m * force_kn, 0.0, 0.0))
    return LoadCase(name=name, nodal_loads=nodal_loads)


