import copy
import itertools

from setu.analysis.critical_position import rank_all_positions
from setu.analysis.fatigue import fatigue_range
from setu.helpers import DEFAULT_SAMPLING, adverse_sign, import_opensees
from setu.analysis.influence_surface import InfluenceSolver, response_to_load_case
from setu.builder.assembly import BEARING_VERTICAL_STIFFNESS_KN_PER_M, build_bridge_model
from setu.irc6.combinations import design_value, irc6_combinations
from setu.irc6.seismic import combine_directions
from setu.irc6.temperature import effective_temperature_range, temperature_difference_profiles
from setu.loads.braking_loads import braking_load_cases
from setu.loads.custom_loads import custom_load_cases
from setu.loads.load_builders import applied_live_loads
from setu.loads.load_cases import LoadCase
from setu.loads.seismic_loads import seismic_load_cases
from setu.loads.wind_loads import wind_load_cases
from setu.postprocess.girder_response import STAGE_IS_FACTORED_AS, dead_load_forces
from setu.postprocess.thermal_stresses import free_bearing_movement_m, primary_thermal_stresses
from setu.utils.constants import (
    BEARING_REACTION,
    BIGGER_IS_WORSE,
    BOTH_WAYS,
    DEAD,
    LIVE,
    MAX_MOMENT,
    MIDSPAN_DEFLECTION,
    RESPONSES,
    SEISMIC,
    SMALLER_IS_WORSE,
    SUPPORT,
    SUPPORT_SHEAR,
    SURFACING,
    WIND,
)

NO_EFFECT = 0.0
# the maximum live moment on a simply supported span stands a little off midspan, so the moment is checked at midspan and at
# these fractions of the span towards the first bearing; the deck is symmetric end to end (point-symmetric across the girders
# when skewed), so the other side of midspan gives nothing new
MOMENT_SECTIONS_OFF_MIDSPAN = (0.0, 0.02, 0.04, 0.06)
BOTH_DIRECTIONS = (BIGGER_IS_WORSE, SMALLER_IS_WORSE)


class GoverningValue:
    # the governing design value, the combination it came from, each group's share, and the station along the girder where it governs
    def __init__(self, value, combination, adverse, shares, at_m):
        self.value = value
        self.combination = combination
        self.adverse = adverse
        self.shares = shares
        self.at_m = at_m

    # plain dict for the JSON output
    def to_dict(self):
        return self.__dict__


class DesignValues:
    # design values for every girder, response and limit state, plus the dead load by stage, deflections, fatigue ranges,
    # the live shear range, temperature, and the surfaces, critical positions and stations behind the live load
    def __init__(self, girders, dead, deflections, fatigue, live_shear_range_kn, thermal, surfaces, criticals, stations):
        self.girders = girders
        self.dead = dead
        self.deflections = deflections
        self.fatigue = fatigue
        self.live_shear_range_kn = live_shear_range_kn
        self.thermal = thermal
        self.surfaces = surfaces
        self.criticals = criticals
        self.stations = stations

    # the girder with the biggest value for this response and limit state
    def governing(self, response, limit_state, adverse):
        return max(((girder, by_response[response][limit_state][adverse]) for girder, by_response in self.girders.items()), key=lambda pair: abs(pair[1].value))


# every critical position's wheels and UDL/footway patches, keyed (girder, response, adverse), to rebuild the live load in MIDAS
def midas_loads(bridge, design_values):
    return {key: applied_live_loads(bridge, critical, design_values.surfaces[key]) for key, critical in design_values.criticals.items()}


# every load on every girder, combined per IRC:6 Annex B, at every place a design value is read
def girder_design_values(bridge, wind=None, seismic=None, temperature=None, custom_loads=(), custom_combinations=(), ops=None):
    ops = import_opensees() if ops is None else ops
    dead = dead_load_forces(bridge, ops)
    model = build_bridge_model(bridge, ops)
    girders = range(bridge.girders.count)
    solver = InfluenceSolver(model.as_deck_model())
    places = places_to_design(model)
    surfaces = {(girder, place): surface_for(solver, model, girder, place) for girder in girders for place in places}
    deflection_surfaces = {girder: solver.for_deflection(f"girder {girder}, {MIDSPAN_DEFLECTION}", midspan_deck_node_over(model, girder)) for girder in girders}

    # the worst legal traffic on this bridge for one surface
    def search(surface, adverse):
        return rank_all_positions(surface, bridge.cross_section, bridge.span_m, adverse, bridge.wearing_course_thickness_m)

    live = {(girder, place, adverse): search(surfaces[girder, place], adverse)[0] for girder in girders for place in places for adverse in BOTH_DIRECTIONS}
    read = reader(surfaces)
    wind_cases = wind_load_cases(model, wind) if wind is not None else None
    wind_forces = dict(wind_cases or {})
    custom_forces = custom_load_cases(model, custom_loads)
    combinations = irc6_combinations(wind_cases.speed_at_deck_mps if wind_cases is not None else None) + list(custom_combinations)
    by_place = {}
    for girder in girders:
        for place in places:
            effects = {
                DEAD: sum(read(dead.stages[stage], girder, place) for stage in dead.stages if STAGE_IS_FACTORED_AS[stage] == DEAD),
                SURFACING: sum(read(dead.stages[stage], girder, place) for stage in dead.stages if STAGE_IS_FACTORED_AS[stage] == SURFACING),
                LIVE: [live_with_braking(model, live[girder, place, adverse], read, girder, place) for adverse in BOTH_DIRECTIONS],
            }
            if wind_forces:
                effects[WIND] = wind_alternatives(wind_forces, read, girder, place, with_the_live_load=False)
            if seismic is not None:
                own = seismic_load_cases(model, seismic, live[girder, place, BIGGER_IS_WORSE], ops)
                effects[SEISMIC] = combine_directions(*[read(own[name], girder, place) for name in ("longitudinal", "transverse", "vertical") if name in own])
            for group, forces in custom_forces.items():
                effects[group] = add_to(effects.get(group, NO_EFFECT), read(forces, girder, place))
            by_place[girder, place] = governing_by_limit_state(effects, combinations, wind_forces, read, girder, place, model.mesh.length_mesh_m[place[1]])
    results = {girder: {response: worst_over_places([by_place[girder, place] for place in places if place[0] == response]) for response in RESPONSES} for girder in girders}
    surfaces_out, criticals, stations = worst_live_places(live, surfaces, places, girders)
    deflections = {}
    for girder in girders:
        deflections[girder], without_footway = girder_deflection(deflection_surfaces[girder], dead, girder, model, search)
        surfaces_out[girder, MIDSPAN_DEFLECTION, BIGGER_IS_WORSE] = deflection_surfaces[girder]
        criticals[girder, MIDSPAN_DEFLECTION, BIGGER_IS_WORSE] = without_footway
        stations[girder, MIDSPAN_DEFLECTION, BIGGER_IS_WORSE] = model.mesh.stations_along_span // 2
    fatigue = {girder: fatigue_ranges(surfaces, girder, places, bridge, model) for girder in girders}
    live_shear_range_kn = {girder: max(live[girder, (SUPPORT_SHEAR, SUPPORT), BIGGER_IS_WORSE].response, 0.0) - min(live[girder, (SUPPORT_SHEAR, SUPPORT), SMALLER_IS_WORSE].response, 0.0)
                           for girder in girders}
    return DesignValues(results, dead, deflections, fatigue, live_shear_range_kn, thermal_results(bridge, temperature), surfaces_out, criticals, stations)


# (response, station) of every place a design value is read: the moment at the sections near midspan, shear and reaction at the first bearing
def places_to_design(model):
    stations_m = model.mesh.length_mesh_m
    span_m = stations_m[-1] - stations_m[0]
    moment_stations = sorted({int(abs(stations_m - (span_m / 2 - fraction * span_m)).argmin()) for fraction in MOMENT_SECTIONS_OFF_MIDSPAN})
    return [(MAX_MOMENT, station) for station in moment_stations] + [(SUPPORT_SHEAR, SUPPORT), (BEARING_REACTION, SUPPORT)]


# the influence surface for one place on one girder
def surface_for(solver, model, girder, place):
    response, station = place
    name = f"girder {girder}, {response} at {model.mesh.length_mesh_m[station]:.3f} m"
    if response == MAX_MOMENT:
        return solver.for_girder_composite_moment(name, model.element_of_girder_at(girder, station))
    if response == SUPPORT_SHEAR:
        return solver.for_girder_shear(name, model.element_of_girder_at(girder, station))
    return solver.for_bearing_reaction(name, model.bearings[girder, station], BEARING_VERTICAL_STIFFNESS_KN_PER_M)


# the deck node over a girder at midspan
def midspan_deck_node_over(model, girder):
    return model.deck_nodes[model.mesh.stations_along_span // 2, model.mesh.width_station_of_girder(girder)]


# a function that reads one place on one girder off a load case (by reciprocity) or off solved girder forces
def reader(surfaces):

    # the response at this place
    def read(forces, girder, place):
        if isinstance(forces, LoadCase):
            return response_to_load_case(surfaces[girder, place], forces)
        response, station = place
        if response == MAX_MOMENT:
            return float(forces[girder].composite_moment_kn_m[station])
        if response == SUPPORT_SHEAR:
            return float(forces[girder].shear_kn[station])
        return forces[girder].reaction_kn
    return read


# for each limit state and direction, the most adverse value over the places of one response
def worst_over_places(governing_at_each_place):
    worst = {}
    for governing in governing_at_each_place:
        for limit_state, by_direction in governing.items():
            for adverse, value in by_direction.items():
                best = worst.setdefault(limit_state, {}).get(adverse)
                if best is None or adverse_sign(adverse) * value.value > adverse_sign(adverse) * best.value:
                    worst[limit_state][adverse] = value
    return worst


# for each girder, response and direction, the place whose live load is most adverse: its surface, critical position and station
def worst_live_places(live, surfaces, places, girders):
    surfaces_out, criticals, stations = {}, {}, {}
    for girder in girders:
        for response in RESPONSES:
            for adverse in BOTH_DIRECTIONS:
                place = max((p for p in places if p[0] == response), key=lambda p: adverse_sign(adverse) * live[girder, p, adverse].response)
                surfaces_out[girder, response, adverse] = surfaces[girder, place]
                criticals[girder, response, adverse] = live[girder, place, adverse]
                stations[girder, response, adverse] = place[1]
    return surfaces_out, criticals, stations


# IRC:22 deflections at midspan: live load with impact but without the footway load (which the clause lets you leave out),
# each dead load stage, and the total; also the live critical position without its footway, for tracing
def girder_deflection(surface, dead, girder, model, search):
    ranked = search(surface, BIGGER_IS_WORSE)
    worst = max(ranked, key=lambda position: position.response - position.footway_response * position.lane_reduction)
    without_footway = copy.copy(worst)
    without_footway.response = worst.response - worst.footway_response * worst.lane_reduction
    without_footway.response_before_reduction = worst.response_before_reduction - worst.footway_response
    without_footway.footway_response, without_footway.footway_strips = 0.0, []
    midspan = model.mesh.stations_along_span // 2
    dead_m = {stage: float(forces[girder].deflection_m[midspan]) for stage, forces in dead.stages.items()}
    return {"live_m": without_footway.response, "dead_m": dead_m, "total_m": sum(dead_m.values()) + without_footway.response}, without_footway


# clause 204.6 fatigue ranges on one girder: the moment range at the worst section near midspan, and the shear range at the bearing
def fatigue_ranges(surfaces, girder, places, bridge, model):
    ranges = {}
    for response in (MAX_MOMENT, SUPPORT_SHEAR):
        found = [(fatigue_range(surfaces[girder, place], bridge.cross_section, bridge.span_m, DEFAULT_SAMPLING), place) for place in places if place[0] == response]
        worst, place = max(found, key=lambda pair: pair[0].range)
        worst.at_m = float(model.mesh.length_mesh_m[place[1]])
        ranges[response] = worst
    return ranges


# live load response plus the worse of the two braking directions
def live_with_braking(model, critical, read, girder, place):
    braking = [read(case, girder, place) for case in braking_load_cases(model, critical).values()]
    adding = max(braking) if critical.adverse == BIGGER_IS_WORSE else min(braking)
    return critical.response + adding


# every mix of wind sides and directions, with wind on the vehicles if asked
def wind_alternatives(wind_forces, read, girder, place, with_the_live_load):
    alternatives = []
    for side, along, vertical in itertools.product(("from the left", "from the right"), BOTH_WAYS, ("upward", "downward")):
        effect = read(wind_forces[f"transverse {side}"], girder, place) + along * read(wind_forces["longitudinal"], girder, place)
        effect += read(wind_forces[f"vertical {vertical}"], girder, place)
        if with_the_live_load:
            effect += read(wind_forces[f"on live load {side}"], girder, place) + along * read(wind_forces["on live load, longitudinal"], girder, place)
        alternatives.append(effect)
    return alternatives


# add a number to one effect or to each of its alternatives
def add_to(effect, extra):
    if isinstance(effect, list):
        return [value + extra for value in effect]
    return effect + extra


# worst combination in each limit state, both directions, at one place
def governing_by_limit_state(effects, combinations, wind_forces, read, girder, place, at_m):
    governing = {}
    for combination in combinations:
        in_this_combination = dict(effects)
        if wind_forces and LIVE in combination.factors and WIND in combination.factors:
            in_this_combination[WIND] = wind_alternatives(wind_forces, read, girder, place, with_the_live_load=True)
        for adverse in BOTH_DIRECTIONS:
            value, shares = design_value(in_this_combination, combination, adverse)
            by_direction = governing.setdefault(combination.limit_state, {})
            best = by_direction.get(adverse)
            if best is None or adverse_sign(adverse) * value > adverse_sign(adverse) * best.value:
                by_direction[adverse] = GoverningValue(value, combination.name, adverse, shares, float(at_m))
    return governing


# Fig. 17b heating and cooling primary stresses in every girder, and the bearing movement; None with no temperature input
def thermal_results(bridge, temperature):
    if temperature is None:
        return None
    profiles = temperature_difference_profiles(bridge.deck.thickness_m, bridge.wearing_course_thickness_m)
    results = {"profiles": profiles,
               "girders": {girder: {kind: primary_thermal_stresses(bridge, girder, profile) for kind, profile in profiles.items()}
                           for girder in range(bridge.girders.count)}}
    temperature_range_c = effective_temperature_range(temperature.shade_max_c, temperature.shade_min_c)
    results["effective range c"] = temperature_range_c
    results["free bearing movement m"] = free_bearing_movement_m(bridge.span_m, temperature_range_c)
    return results
