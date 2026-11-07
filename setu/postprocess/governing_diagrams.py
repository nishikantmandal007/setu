import copy
import hashlib
import math

import numpy as np

from setu.errors import SetuError
from setu.irc6.combinations import design_value
from setu.loads.load_builders import live_load
from setu.loads.load_cases import LoadCase
from setu.postprocess import progress
from setu.postprocess.design_values import BOTH_DIRECTIONS, effects_in, load_effects, reader, wind_alternatives, wind_on_the_vehicles
from setu.postprocess.girder_response import analyze_load_case, analyze_with_braces, brace_force_array, scaled, sum_of
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
    # one governing design value replayed along every girder: where and how it governs, each girder's factored forces, and every
    # brace member's factored axial force (kN, in BridgeDiagrams.brace_members order) under the same loads
    def __init__(self, girder, response, limit_state, adverse, governing, forces, brace_forces_kn=None):
        self.girder = girder
        self.response = response
        self.limit_state = limit_state
        self.adverse = adverse
        self.governing = governing
        self.forces = forces
        self.brace_forces_kn = brace_forces_kn


class BridgeDiagrams:
    # forces along every girder for every solved load state beyond the dead load stages: each critical live arrangement and
    # its braking, the wind cases and every governing combination; and the plan position (x, z) of every girder node and deck edge node
    def __init__(self, live, braking, wind, governing, girder_positions_m, edge_positions_m, brace_members=()):
        self.live = live
        self.braking = braking
        self.wind = wind
        self.governing = governing
        self.girder_positions_m = girder_positions_m
        self.edge_positions_m = edge_positions_m
        self.brace_members = list(brace_members)  # (pair, station, role) of each entry in a governing diagram's brace_forces_kn


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
    # nothing solved yet; dead: the dead load stages, whose brace forces were read when they were solved
    def __init__(self, model, dead=None):
        self.model = model
        self.solved = {}
        self.braces = {}
        order = list(model.brace_elements)
        self.dead_braces = {} if dead is None else {id(dead.stages[stage]): np.array([dead.brace_stages[stage][member] for member in order])
                                                    for stage in dead.stages}

    # every girder's forces under one source: dead stage forces as they are, a load case or a live arrangement solved once
    def forces(self, source):
        key = source_key(source)
        if key is None:
            return source
        if key not in self.solved:
            case = live_load(self.model, source.critical, source.surface) if isinstance(source, LiveArrangement) else source
            self.solved[key] = (source, analyze_load_case(self.model, case, on_solved=lambda _: self.braces.__setitem__(key, brace_force_array(self.model))))
        return self.solved[key][1]

    # every brace member's axial force under one source, read off the same solve as its girder forces
    def brace_forces(self, source):
        key = source_key(source)
        if key is None:
            if id(source) not in self.dead_braces:
                raise SetuError("a load state term is neither a solved load nor a dead load stage, so its brace forces are unknown")
            return self.dead_braces[id(source)]
        self.forces(source)
        return self.braces[key]

    # queue each distinct physical load once, then keep the solved forces in source order
    def prepare(self, sources, work):
        self.queue(sources, work)
        self.collect()

    # the sources to queue, taken one distinct load at a time (queue_next) or all at once (collect)
    def queue(self, sources, work):
        self.sources, self.work, self.pending = iter(sources), work, {}

    # queue the next source whose load is not queued yet; False when there is none left
    def queue_next(self):
        for source in self.sources:
            key = source_key(source)
            if key is not None and key not in self.pending:
                case = live_load(self.model, source.critical, source.surface) if isinstance(source, LiveArrangement) else source
                # a load case is not kept once queued: its forces are found again by its key
                self.pending[key] = (source if isinstance(source, LiveArrangement) else None, self.work.load(case))
                return True
        return False

    # queue the rest, then keep every solved load's forces in source order
    def collect(self):
        while self.queue_next():
            pass
        progress.start(len(self.pending))
        results = {key: (source, progress.passing(future.result())) for key, (source, future) in self.pending.items()}
        self.solved = {key: (source, girders) for key, (source, (girders, _)) in results.items()}
        self.braces = {key: braces for key, (_, (_, braces)) in results.items()}

    # every girder's forces under a sum of factored sources
    def combined(self, terms):
        parts = [(coefficient, self.forces(source)) for coefficient, source in terms]
        return {girder: sum_of(scaled(forces[girder], coefficient) for coefficient, forces in parts) for girder in parts[0][1]}

    # every brace member's axial force under the same sum
    def combined_braces(self, terms):
        return sum(coefficient * self.brace_forces(source) for coefficient, source in terms)


# the existing identity keys for traffic and content keys for ordinary load cases
def source_key(source):
    if isinstance(source, LiveArrangement):
        return ("live", id(source.critical), id(source.surface))
    if isinstance(source, LoadCase):
        # the load's content, held as its shapes and a SHA-256 digest rather than a copy of every node's load
        nodes, loads = source.nodal_arrays
        digest = hashlib.sha256(nodes.tobytes())
        digest.update(loads.tobytes())
        digest.update(repr(source.element_loads).encode())
        return ("load", nodes.shape, loads.shape, digest.digest())
    return None


# queue diagram sources in serial order while the parent replays the remaining combinations
def diagram_sources(analysis, values, seismic, braking_height_above_deck_m, terms_by_key):
    for key, critical in values.criticals.items():
        yield LiveArrangement(critical, values.surfaces[key])
    for (girder, response, adverse), station in values.stations.items():
        details = values.braking.get((girder, (response, station), adverse))
        if details is not None and details["selected"] is not None:  # none where a congested or crowd case governs (cl. 204.4)
            yield details["cases"][details["selected"]]
    yield from analysis.wind_forces.values()
    for girder, by_response in values.girders.items():
        for response, by_limit_state in by_response.items():
            for limit_state, by_adverse in by_limit_state.items():
                for adverse, value in by_adverse.items():
                    terms = replayed_terms(analysis, values, seismic, braking_height_above_deck_m, girder, response, adverse, value)
                    if terms_by_key is not None:
                        terms_by_key[girder, response, limit_state, adverse] = terms
                    yield from (source for _, source in terms)


# one load solved when asked for, here, with its brace forces from the same solve
class SolvedHere:
    def __init__(self, model, case):
        self.model, self.case, self.done = model, case, None

    def solve(self):
        if self.done is None:
            self.done = analyze_with_braces(self.model, self.case)
            self.case = None

    def result(self):
        self.solve()
        return self.done


# The replay's loads, solved in this process while it would otherwise wait for its workers (the girder results already fix them):
# solve_one() takes the next distinct load in source order. Every load is solved the same way wherever and whenever it is solved, so
# the diagrams are the same as a replay solved all at once.
# Nothing but the solved forces is kept: each value's terms are worked out again when the diagrams are put together, and its loads
# are found by their keys.
class ReplayInTheGaps:
    def __init__(self, analysis, values, seismic, braking_height_above_deck_m):
        self.model = analysis.model
        self.solver = LoadSolver(analysis.model, analysis.dead)
        self.latest = None
        self.solver.queue(diagram_sources(analysis, values, seismic, braking_height_above_deck_m, None), self)

    def load(self, case):
        self.latest = SolvedHere(self.model, case)
        return self.latest

    def solve_one(self):
        if not self.solver.queue_next():
            return False
        self.latest.solve()
        return True


# every governing girder design value replayed as forces along all girders, with the dead stages, live arrangements, braking and wind
# replay: a ReplayInTheGaps that has solved some of the loads already
def bridge_diagrams(analysis, values, seismic, braking_height_above_deck_m, replay=None):
    terms_by_key = {}
    if replay is not None:
        solver = replay.solver
        while replay.solve_one():  # one at a time, so no more than one load waits to be solved
            pass
        solver.collect()
    else:
        solver = LoadSolver(analysis.model, analysis.dead)
        if analysis.work is not None:
            solver.prepare(diagram_sources(analysis, values, seismic, braking_height_above_deck_m, terms_by_key), analysis.work)
    prepared = analysis.work is not None  # the terms were kept while the loads were queued
    live = {key: solver.forces(LiveArrangement(critical, values.surfaces[key])) for key, critical in values.criticals.items()}
    braking = {}
    for (girder, response, adverse), station in values.stations.items():
        details = values.braking.get((girder, (response, station), adverse))
        if details is not None and details["selected"] is not None:
            braking[girder, response, adverse] = solver.forces(details["cases"][details["selected"]])
    wind = {name: solver.forces(case) for name, case in analysis.wind_forces.items()}
    governing = {}
    if not prepared:  # solved one by one below, so count the governing values as they are replayed
        progress.start(sum(len(by_adverse) for by_response in values.girders.values() for by_limit_state in by_response.values() for by_adverse in by_limit_state.values()))
    for girder, by_response in values.girders.items():
        for response, by_limit_state in by_response.items():
            for limit_state, by_adverse in by_limit_state.items():
                for adverse, value in by_adverse.items():
                    terms = terms_by_key[girder, response, limit_state, adverse] if prepared else replayed_terms(analysis, values, seismic, braking_height_above_deck_m, girder, response, adverse, value)
                    governing[girder, response, limit_state, adverse] = GoverningDiagram(girder, response, limit_state, adverse, value, solver.combined(terms),
                                                                                         solver.combined_braces(terms))
                    if not prepared:
                        progress.step()
    return BridgeDiagrams(live, braking, wind, governing, *plan_positions(analysis.model), brace_members=analysis.model.brace_elements)


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
