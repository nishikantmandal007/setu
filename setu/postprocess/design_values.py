import itertools

from setu.analysis.critical_position import find_critical_position
from setu.helpers import adverse_sign
from setu.analysis.influence_surface import InfluenceSolver
from setu.builder.assembly import build_bridge_model
from setu.irc6.combinations import design_value, irc6_combinations
from setu.irc6.seismic import combine_directions
from setu.irc6.temperature import effective_temperature_range, temperature_difference_profile
from setu.loads.braking_loads import braking_load_cases
from setu.loads.custom_loads import custom_load_cases
from setu.loads.seismic_loads import seismic_load_cases
from setu.loads.wind_loads import wind_load_cases
from setu.postprocess.girder_response import analyze_load_case, dead_load_forces
from setu.postprocess.thermal_stresses import free_bearing_movement_m, primary_thermal_stresses
from setu.solver.backend import import_opensees
from setu.utils.constants import (
    BIGGER_IS_WORSE,
    DEAD,
    LIVE,
    MIDSPAN_MOMENT,
    SEISMIC,
    SMALLER_IS_WORSE,
    SUPPORT_SHEAR,
    SURFACING,
    WIND,
)

RESPONSES = (MIDSPAN_MOMENT, SUPPORT_SHEAR)
SUPPORT = 0
DEAD_STAGES = ("construction", "superimposed", "dead")
BOTH_WAYS = (1.0, -1.0)
NO_EFFECT = 0.0


class GoverningValue:
    def __init__(self, value, combination, adverse, shares):
        self.value = value
        self.combination = combination
        self.adverse = adverse
        self.shares = shares

    def to_dict(self):
        return self.__dict__


class DesignValues:
    def __init__(self, girders, thermal=None):
        self.girders = girders
        self.thermal = thermal

    def governing(self, response, limit_state, adverse=BIGGER_IS_WORSE):
        return max(((girder, by_response[response][limit_state][adverse]) for girder, by_response in self.girders.items()), key=lambda pair: abs(pair[1].value))

    def to_dict(self):
        return self.__dict__


def girder_design_values(bridge, wind=None, seismic=None, temperature=None, custom_loads=(), custom_combinations=(), ops=None):
    ops = import_opensees() if ops is None else ops
    dead = dead_load_forces(bridge, ops)
    model = build_bridge_model(bridge, ops)
    girders = range(bridge.girders.count)
    solver = InfluenceSolver(model.as_deck_model())
    surfaces = {}
    for girder in girders:
        surfaces[girder, MIDSPAN_MOMENT] = solver.for_girder_composite_moment(f"girder {girder}, {MIDSPAN_MOMENT}", model.midspan_element_of_girder(girder))
        surfaces[girder, SUPPORT_SHEAR] = solver.for_girder_shear(f"girder {girder}, {SUPPORT_SHEAR}", model.element_of_girder_at(girder, SUPPORT))
    live = {(girder, response, adverse): find_critical_position(surfaces[girder, response], bridge.cross_section, span_m=bridge.span_m, adverse=adverse,
                                                                  wearing_course_thickness_m=bridge.wearing_course_thickness_m)
            for girder in girders for response in RESPONSES for adverse in (BIGGER_IS_WORSE, SMALLER_IS_WORSE)}
    read = reader(model)
    wind_cases = wind_load_cases(model, wind) if wind is not None else None
    wind_forces = {name: analyze_load_case(model, case, ops) for name, case in (wind_cases or {}).items()}
    seismic_forces = {}
    if seismic is not None:
        for girder in girders:
            for response in RESPONSES:
                with_its_traffic = seismic_load_cases(model, seismic, live[girder, response, BIGGER_IS_WORSE], ops)
                seismic_forces[girder, response] = {name: analyze_load_case(model, case, ops) for name, case in with_its_traffic.items()}
    custom_forces = {group: analyze_load_case(model, case, ops) for group, case in custom_load_cases(model, custom_loads).items()}
    combinations = irc6_combinations(wind_cases.speed_at_deck_mps if wind_cases is not None else None) + list(custom_combinations)
    results = {}
    for girder in girders:
        results[girder] = {}
        for response in RESPONSES:
            effects = {
                DEAD: sum(read(dead.stages[stage], girder, response) for stage in DEAD_STAGES if stage in dead.stages),
                SURFACING: read(dead.stages["surfacing"], girder, response),
                LIVE: [live_with_braking(model, live[girder, response, adverse], read, girder, response, ops) for adverse in (BIGGER_IS_WORSE, SMALLER_IS_WORSE)],
            }
            if wind_forces:
                effects[WIND] = wind_alternatives(wind_forces, read, girder, response, with_the_live_load=False)
            if seismic_forces:
                own = seismic_forces[girder, response]
                directions = [read(own[name], girder, response) for name in ("longitudinal", "transverse", "vertical") if name in own]
                effects[SEISMIC] = combine_directions(*directions)
            for group, forces in custom_forces.items():
                effects[group] = add_to(effects.get(group, NO_EFFECT), read(forces, girder, response))
            results[girder][response] = governing_by_limit_state(effects, combinations, wind_forces, read, girder, response)
    return DesignValues(results, thermal_results(bridge, temperature))


def reader(model):
    midspan = model.mesh.stations_along_span // 2

    def read(forces, girder, response):
        if response == MIDSPAN_MOMENT:
            return float(forces[girder].composite_moment_kn_m[midspan])
        return float(forces[girder].shear_kn[SUPPORT])
    return read


def live_with_braking(model, critical, read, girder, response, ops):
    braking = [read(analyze_load_case(model, case, ops), girder, response) for case in braking_load_cases(model, critical).values()]
    adding = max(braking) if critical.adverse == BIGGER_IS_WORSE else min(braking)
    return critical.response + adding


def wind_alternatives(wind_forces, read, girder, response, with_the_live_load):
    alternatives = []
    for side, along, vertical in itertools.product(("from the left", "from the right"), BOTH_WAYS, ("upward", "downward")):
        effect = read(wind_forces[f"transverse {side}"], girder, response) + along * read(wind_forces["longitudinal"], girder, response)
        effect += read(wind_forces[f"vertical {vertical}"], girder, response)
        if with_the_live_load:
            effect += read(wind_forces[f"on live load {side}"], girder, response) + along * read(wind_forces["on live load, longitudinal"], girder, response)
        alternatives.append(effect)
    return alternatives


def add_to(effect, extra):
    if isinstance(effect, list):
        return [value + extra for value in effect]
    return effect + extra


def governing_by_limit_state(effects, combinations, wind_forces, read, girder, response):
    governing = {}
    for combination in combinations:
        in_this_combination = dict(effects)
        if wind_forces and LIVE in combination.factors and WIND in combination.factors:
            in_this_combination[WIND] = wind_alternatives(wind_forces, read, girder, response, with_the_live_load=True)
        for adverse in (BIGGER_IS_WORSE, SMALLER_IS_WORSE):
            value, shares = design_value(in_this_combination, combination, adverse)
            by_direction = governing.setdefault(combination.limit_state, {})
            best = by_direction.get(adverse)
            if best is None or adverse_sign(adverse) * value > adverse_sign(adverse) * best.value:
                by_direction[adverse] = GoverningValue(value, combination.name, adverse, shares)
    return governing


def thermal_results(bridge, temperature):
    if temperature is None:
        return None
    positive = temperature_difference_profile(bridge.deck.thickness_m)
    results = {"positive difference": primary_thermal_stresses(bridge, positive)}
    if temperature.reverse_depths_m is not None:
        reverse = temperature_difference_profile(bridge.deck.thickness_m, positive=False, reverse_depths_m=temperature.reverse_depths_m)
        results["reverse difference"] = primary_thermal_stresses(bridge, reverse)
    temperature_range_c = effective_temperature_range(temperature.shade_max_c, temperature.shade_min_c, temperature.metallic, temperature.snowbound)
    results["effective range c"] = temperature_range_c
    results["free bearing movement m"] = free_bearing_movement_m(bridge.span_m, temperature_range_c)
    return results
