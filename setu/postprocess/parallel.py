import multiprocessing
import os
from math import isqrt
from concurrent.futures import Future, ProcessPoolExecutor
from contextlib import contextmanager

from setu.analysis.critical_position import find_critical_position, rank_all_positions
from setu.analysis.fatigue import fatigue_range
from setu.analysis.influence_surface import InfluenceSolver
from setu.builder.assembly import BridgeModel, build_bridge_model
from setu.helpers import DEFAULT_SAMPLING
from setu.postprocess.girder_response import analyze_load_case, dead_load_forces
from setu.utils.constants import BIGGER_IS_WORSE, MAX_MOMENT, MIDSPAN_DEFLECTION, SUPPORT_SHEAR

model: BridgeModel
solver: InfluenceSolver


# build the process's own composite model and retain it for subsequent tasks
def initialize(bridge):
    global model, solver
    model = build_bridge_model(bridge)
    solver = InfluenceSolver(model.as_deck_model())


# solve the construction stages and restore the worker's short-term model afterwards
def dead_task(bridge):
    dead = dead_load_forces(bridge)
    initialize(bridge)
    return dead


# dispatch one physical solve on this process's composite model
def solve(kind, args):
    from setu.postprocess.brace_design_values import brace_surface
    from setu.postprocess.design_values import midspan_deck_node_over, stress_surface, surface_for

    if kind == "place":
        return surface_for(solver, model, *args)
    if kind == "deflection":
        girder, = args
        return solver.for_deflection(f"girder {girder}, {MIDSPAN_DEFLECTION}", midspan_deck_node_over(model, girder))
    if kind == "stress":
        return stress_surface(solver, model, *args)
    if kind == "brace":
        return brace_surface(solver, model, *args)
    if kind == "load":
        return analyze_load_case(model, *args)
    raise ValueError(f"unknown solve {kind!r}")


# search both directions consecutively so they share their vehicle-response grids
def live_positions(surface):
    from setu.postprocess.design_values import BOTH_DIRECTIONS

    bridge = model.bridge
    return {adverse: find_critical_position(surface, bridge.cross_section, bridge.span_m, adverse, bridge.wearing_course_thickness_m)
            for adverse in BOTH_DIRECTIONS}


# search both directions and fatigue for one solved girder design place
def place_task(surface, girder, place):
    bridge = model.bridge
    criticals = live_positions(surface)
    fatigue = fatigue_range(surface, bridge.cross_section, bridge.span_m, DEFAULT_SAMPLING) if place[0] in (MAX_MOMENT, SUPPORT_SHEAR) else None
    return surface, criticals, fatigue


# rank all traffic arrangements for one girder's solved midspan deflection
def deflection_task(surface, girder):
    bridge = model.bridge
    return surface, rank_all_positions(surface, bridge.cross_section, bridge.span_m, BIGGER_IS_WORSE, bridge.wearing_course_thickness_m)


# search fatigue on one solved flange-stress surface
def stress_task(surface, girder, face, y_m, station):
    stress = fatigue_range(surface, model.bridge.cross_section, model.bridge.span_m, DEFAULT_SAMPLING)
    return stress.located_at(float(model.mesh.length_mesh_m[station]))


# search both directions on one solved brace surface
def brace_task(surface, member):
    return surface, live_positions(surface)


# forward a completed process result or its exception to the whole task's future
def copy_result(completed, result):
    error = completed.exception()
    if error is not None:
        result.set_exception(error)
    else:
        result.set_result(completed.result())


# start the traffic search as soon as its surface is ready, without blocking another process
def search_after(completed, pool, function, args, result):
    error = completed.exception()
    if error is not None:
        result.set_exception(error)
        return
    try:
        search = pool.submit(function, completed.result(), *args)
    except Exception as error:
        result.set_exception(error)
    else:
        search.add_done_callback(lambda done: copy_result(done, result))


# pending results indexed by serial keys, independent of their completion order
class ParallelWork:
    # dead stages run alongside native solves and traffic searches within the worker budget
    def __init__(self, native, searches, bridge, girders, braces):
        self.native = native
        self.searches = searches
        self.girders = girders
        self.include_braces = braces
        self.dead = searches.submit(dead_task, bridge)
        self.places = {}
        self.deflections = {}
        self.stresses = {}
        self.braces = {}

    # one task's surface and its searches share a future while occupying different processes
    def submit(self, kind, function, *args):
        result = Future()
        surface = self.native.submit(solve, kind, args)
        surface.add_done_callback(lambda done: search_after(done, self.searches, function, args, result))
        return result

    # ordinary diagram loads use the same native solvers and need no traffic search
    def load(self, load_case):
        return self.native.submit(solve, "load", (load_case,))

    # queue the two-direction traffic searches before the smaller flange-fatigue jobs
    def start(self, parent_model):
        from setu.postprocess.design_values import places_to_design

        places = places_to_design(parent_model)
        if self.girders:
            for girder in range(parent_model.bridge.girders.count):
                for place in places:
                    self.places[girder, place] = self.submit("place", place_task, girder, place)
                self.deflections[girder] = self.submit("deflection", deflection_task, girder)
        if self.include_braces:
            for member in parent_model.brace_elements:
                self.braces[member] = self.submit("brace", brace_task, member)
        if self.girders:
            for girder, section in enumerate(parent_model.girders):
                for face, y_m in (("steel top", section.depth_m), ("steel bottom", 0.0)):
                    for response, station in places:
                        if response == MAX_MOMENT:
                            self.stresses[girder, face, station] = self.submit("stress", stress_task, girder, face, y_m, station)


# split the worker budget so native factors fit in memory while other cores search traffic
@contextmanager
def analysis_for(bridge, wind, custom_loads, custom_combinations, workers, *, girders=False, braces=False):
    from setu.postprocess.design_values import shared_analysis

    if workers == 1:
        yield shared_analysis(bridge, wind, custom_loads, custom_combinations)
        return
    count = os.cpu_count() if workers is None else workers
    assert count is not None
    context = multiprocessing.get_context("spawn")
    # shortcut: sqrt(workers) bounds factor memory; retune for larger meshes or different hardware.
    native_count = isqrt(count)
    with ProcessPoolExecutor(max_workers=count - native_count, mp_context=context,
                             initializer=initialize, initargs=(bridge,)) as searches:
        with ProcessPoolExecutor(max_workers=native_count, mp_context=context,
                                 initializer=initialize, initargs=(bridge,)) as native:
            work = ParallelWork(native, searches, bridge, girders, braces)
            yield shared_analysis(bridge, wind, custom_loads, custom_combinations, work=work)
