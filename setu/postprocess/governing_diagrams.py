import copy
import math

import numpy as np

from setu.errors import SetuError
from setu.irc6.combinations import design_value
from setu.loads.load_builders import live_load
from setu.loads.load_cases import LoadCase
from setu.postprocess.design_values import BOTH_DIRECTIONS, effects_in, load_effects, reader, wind_alternatives, wind_on_the_vehicles
from setu.postprocess.girder_response import analyze_load_case, scaled, sum_of
from setu.solver import backend

REPLAY_REL_TOLERANCE = 1e-12  # Python sums plain floats with compensation and recipes without, so the last bits can differ


class Recipe:
    # a response and the physical loads behind it, as (coefficient, source) terms; it adds, scales and compares like the number
    def __init__(self, value, terms):
        self.value = value
        self.terms = terms

    # this response plus another, or plus a number
    def __add__(self, other):
        if isinstance(other, Recipe):
            return Recipe(self.value + other.value, self.terms + other.terms)
        return Recipe(self.value + other, self.terms)

    # a number plus this response
    def __radd__(self, other):
        return Recipe(other + self.value, self.terms)

    # this response times a factor
    def __mul__(self, factor):
        return Recipe(self.value * factor, [(coefficient * factor, source) for coefficient, source in self.terms])

    # a factor times this response
    def __rmul__(self, factor):
        return Recipe(factor * self.value, [(factor * coefficient, source) for coefficient, source in self.terms])

    # compared by value with a response or a number
    def __lt__(self, other):
        return self.value < value_of(other)

    # compared by value with a response or a number
    def __gt__(self, other):
        return self.value > value_of(other)

    # compared by value with a response or a number
    def __le__(self, other):
        return self.value <= value_of(other)

    # compared by value with a response or a number
    def __ge__(self, other):
        return self.value >= value_of(other)


class LiveArrangement:
    # a critical traffic position, solved as the load case it stands for
    def __init__(self, critical, surface):
        self.critical = critical
        self.surface = surface


class GoverningDiagram:
    # one governing design value replayed along every girder: where and how it governs, and each girder's factored forces
    def __init__(self, girder, response, limit_state, adverse, governing, forces):
        self.girder = girder
        self.response = response
        self.limit_state = limit_state
        self.adverse = adverse
        self.governing = governing
        self.forces = forces


class BridgeDiagrams:
    # forces along every girder for every solved load state beyond the dead load stages: each critical live arrangement and
    # its braking, the wind cases and every governing combination; and the plan position (x, z) of every girder node and deck edge node
    def __init__(self, live, braking, wind, governing, girder_positions_m, edge_positions_m):
        self.live = live
        self.braking = braking
        self.wind = wind
        self.governing = governing
        self.girder_positions_m = girder_positions_m
        self.edge_positions_m = edge_positions_m


# the value of a response or of a number
def value_of(response):
    return response.value if isinstance(response, Recipe) else response


# the same reader, giving each response with the load it was read off
def recipe_reader(read):

    # the response here, as a recipe of one term
    def read_recipe(forces, girder, place):
        return Recipe(read(forces, girder, place), [(1.0, forces)])
    return read_recipe


# a critical position whose response remembers its arrangement
def with_its_arrangement(critical, surface):
    remembering = copy.copy(critical)
    remembering.response = Recipe(critical.response, [(1.0, LiveArrangement(critical, surface))])
    return remembering


# the station a design value governs at
def station_at(model, at_m):
    return int(np.flatnonzero(model.mesh.length_mesh_m == at_m)[0])


# solves each distinct load once and keeps every girder's forces under it
class LoadSolver:
    # nothing solved yet
    def __init__(self, model):
        self.model = model
        self.solved = {}

    # every girder's forces under one source: dead stage forces as they are, a load case or a live arrangement solved once
    def forces(self, source):
        if isinstance(source, LiveArrangement):
            key = ("live", id(source.critical), id(source.surface))
            if key not in self.solved:
                self.solved[key] = (source, analyze_load_case(self.model, live_load(self.model, source.critical, source.surface)))
            return self.solved[key][1]
        if isinstance(source, LoadCase):
            nodes, loads = source.nodal_arrays
            key = (nodes.tobytes(), loads.tobytes(), repr(source.element_loads))
            if key not in self.solved:
                self.solved[key] = (source, analyze_load_case(self.model, source))
            return self.solved[key][1]
        return source

    # every girder's forces under a sum of factored sources
    def combined(self, terms):
        parts = [(coefficient, self.forces(source)) for coefficient, source in terms]
        return {girder: sum_of(scaled(forces[girder], coefficient) for coefficient, forces in parts) for girder in parts[0][1]}


# every governing girder design value replayed as forces along all girders, with the dead stages, live arrangements, braking and wind
def bridge_diagrams(analysis, values, seismic, braking_height_above_deck_m):
    solver = LoadSolver(analysis.model)
    live = {key: solver.forces(LiveArrangement(critical, values.surfaces[key])) for key, critical in values.criticals.items()}
    braking = {}
    for (girder, response, adverse), station in values.stations.items():
        details = values.braking.get((girder, (response, station), adverse))
        if details is not None:
            braking[girder, response, adverse] = solver.forces(details["cases"][details["selected"]])
    wind = {name: solver.forces(case) for name, case in analysis.wind_forces.items()}
    governing = {}
    for girder, by_response in values.girders.items():
        for response, by_limit_state in by_response.items():
            for limit_state, by_adverse in by_limit_state.items():
                for adverse, value in by_adverse.items():
                    terms = replayed_terms(analysis, values, seismic, braking_height_above_deck_m, girder, response, adverse, value)
                    governing[girder, response, limit_state, adverse] = GoverningDiagram(girder, response, limit_state, adverse, value, solver.combined(terms))
    return BridgeDiagrams(live, braking, wind, governing, *plan_positions(analysis.model))


# plan position (x, z) of each girder's nodes and of the deck's left and right edge nodes, station by station
def plan_positions(model):
    stations = range(model.mesh.stations_along_span)
    last = model.mesh.stations_across_width - 1

    # x and z of one node
    def plan(node):
        x_m, _, z_m = backend.node_coordinates(node)
        return x_m, z_m
    girders = {girder: [plan(model.girder_nodes[girder, i]) for i in stations] for girder in range(model.bridge.girders.count)}
    edges = {side: [plan(model.deck_nodes[i, j]) for i in stations] for side, j in (("left", 0), ("right", last))}
    return girders, edges


# the factored loads behind one governing value, found by replaying its combination with recipes in place of numbers
def replayed_terms(analysis, values, seismic, braking_height_above_deck_m, girder, response, adverse, value):
    place = (response, station_at(analysis.model, value.at_m))
    read = recipe_reader(reader(values.place_surfaces))
    live = {direction: with_its_arrangement(values.place_criticals[girder, place, direction], values.place_surfaces[girder, place])
            for direction in BOTH_DIRECTIONS}
    effects = load_effects(analysis, analysis.dead.stages, live, read, (girder, place), (girder, place), seismic, braking_height_above_deck_m, {})
    combination = next(combination for combination in analysis.combinations if combination.name == value.combination)
    wind_on_traffic = wind_alternatives(analysis.wind_forces, read, girder, place, with_the_live_load=True) if wind_on_the_vehicles(analysis.wind_forces, combination) else None
    total, _ = design_value(effects_in(combination, effects, wind_on_traffic), combination, adverse)
    if not (isinstance(total, Recipe) and math.isclose(total.value, value.value, rel_tol=REPLAY_REL_TOLERANCE)):
        raise SetuError(f"girder {girder}, {response}, {value.combination}: replayed {value_of(total)} but the design value is {value.value}")
    return total.terms
