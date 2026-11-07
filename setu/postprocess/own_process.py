import multiprocessing
import os
import signal
import traceback
from collections import deque
from contextlib import nullcontext

from setu.postprocess.brace_design_values import BridgeDesignValues, brace_values, member_values, search_member
from setu.postprocess.design_values import (MIDSPAN_DEFLECTION, MAX_MOMENT, girder_values, midspan_deck_node_over, search_deflection,
                                            search_place, search_stress, shared_analysis, stress_surface, surface_for, places_to_design)
from setu.postprocess import progress
from setu.postprocess.construction import construction_design_values
from setu.postprocess.governing_diagrams import bridge_diagrams
from setu.postprocess.special_vehicle import keep_worst, special_vehicle_combinations, special_vehicle_effects, special_vehicle_member, special_vehicle_values
from setu.loads.wind_loads import wind_load_cases
from setu.loads.seismic_loads import seismic_load_cases
from setu.utils.constants import BASIC, BIGGER_IS_WORSE

# BLAS threads do not survive a fork, and the workers already divide the work
ONE_BLAS_THREAD = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1", "MKL_NUM_THREADS": "1"}

shared = None  # what a worker holds: analysis, bridge, seismic site, braking height
with_special_vehicle = False  # workers also work out each place's and member's Class SV values from the surface sent to them


def search_args():
    bridge = shared[1]
    return bridge.cross_section, bridge.span_m, bridge.wearing_course_thickness_m


# the worker tasks: this process solves every surface and sends it; a worker searches its traffic, works out its Class SV values and
# combines, and never calls OpenSees. A solve writes into every element and node, so a forked worker that solved copied the whole
# model (about 1 GB of a wide deck's 1.45 GB per worker); the same surfaces give the same values wherever they are searched.
def place_task(girder, place, surface):
    analysis = shared[0]
    searched = search_place(surface, place, *search_args())
    special = special_vehicle_place(analysis, shared[1], surface, girder, place) if with_special_vehicle else None
    return (*searched, special)


def deflection_task(surface):
    return (search_deflection(surface, *search_args()),)


def stress_task(surface, station):
    return search_stress(surface, float(shared[0].model.mesh.length_mesh_m[station]), *search_args()[:2])


# Once braking has settled each direction's placement, the other arrangements' placements (hundreds per response on a wide deck) are
# never read again; only values leave this process, so they are let go rather than carried back and held.
def settled_only(criticals):
    for critical in criticals:
        if critical is None:
            continue
        critical.alternatives = []
        if critical.searched is not None:
            critical.searched.alternatives = []


def member_task(member, surface):
    analysis, bridge, seismic, braking_height_m = shared
    found = search_member(surface, *search_args())
    special = special_vehicle_member(analysis, bridge, member, surface) if with_special_vehicle else None
    values = member_values(analysis, seismic, braking_height_m, member, surface, found)
    settled_only(found.values())
    return (member, found, *values, special)


# one girder place's worst Class SV value per limit state and direction, and the placements behind them
def special_vehicle_place(analysis, bridge, surface, girder, place):
    from setu.postprocess.design_values import reader
    found = special_vehicle_effects(analysis, bridge, surface, reader({(girder, place): surface}), (girder, place), analysis.dead.stages)
    by_limit_state = {}
    keep_worst(by_limit_state, found, special_vehicle_combinations(), float(analysis.model.mesh.length_mesh_m[place[1]]))
    return by_limit_state, [placement for _, pair in found for placement in pair]


class Pending:
    def __init__(self, waiting):
        self.waiting = waiting

    def result(self):
        return self.waiting.get()


# a surface solved here with the rest of its results from a worker, in the order ParallelWork gives them
class Solved:
    def __init__(self, surface, waiting):
        self.surface, self.waiting = surface, waiting

    def result(self):
        return (self.surface, *self.waiting.get())


# ParallelWork's results: this process solves each surface on its factor and a worker searches it; a search needs only the deck
# ordinates, while a place or member also reads load cases by reciprocity and gets the whole surface
class ForkedWork:
    def __init__(self, pool, analysis, girders, places):
        self.pool, self.analysis = pool, analysis
        solver, model = analysis.solver, analysis.model
        self.ahead = 2 * pool._processes  # members solved ahead of the workers: enough to keep them busy, few surfaces held at once
        self.places, self.deflections, self.stresses = {}, {}, {}
        for girder in girders:
            for place in places:
                surface = self.solved(surface_for(solver, model, girder, place))
                self.places[girder, place] = Solved(surface, pool.apply_async(place_task, (girder, place, surface)))
            surface = self.solved(solver.for_deflection(f"girder {girder}, {MIDSPAN_DEFLECTION}", midspan_deck_node_over(model, girder)))
            self.deflections[girder] = Solved(surface, pool.apply_async(deflection_task, (surface.deck_only(),)))
        for girder in girders:
            for face, y_m in (("steel top", model.girders[girder].depth_m), ("steel bottom", 0.0)):
                for response, station in places:
                    if response == MAX_MOMENT:
                        surface = self.solved(stress_surface(solver, model, girder, face, y_m, station))
                        self.stresses[girder, face, station] = Pending(pool.apply_async(stress_task, (surface.deck_only(), station)))

    def solved(self, surface):
        self.analysis.solver.surfaces.clear()
        return surface

    def members(self, model):
        from setu.postprocess.brace_design_values import brace_surface
        waiting = deque()
        for member in model.brace_elements:
            surface = self.solved(brace_surface(self.analysis.solver, model, member))
            waiting.append(self.pool.apply_async(member_task, (member, surface)))
            if len(waiting) > self.ahead:
                yield waiting.popleft().get()
        while waiting:
            yield waiting.popleft().get()

    def special_vehicle_places(self, girders, places):
        return ((girder, place, *self.places[girder, place].result()[3]) for girder in girders for place in places)


# the raw wind and seismic forces behind a report's load tables
def site_forces(model, wind, seismic, girders):
    forces = {}
    if wind is not None:
        forces["wind_kn"] = wind_load_cases(model, wind).forces_kn
    if seismic is not None:
        governing, _ = girders.governing("maximum composite moment", BASIC, BIGGER_IS_WORSE)
        cases = seismic_load_cases(model, seismic, girders.criticals[governing, "maximum composite moment", BIGGER_IS_WORSE])
        forces["seismic_kn"] = {"longitudinal": cases.horizontal_coefficient * cases.dead_weight_kn,
                                "transverse": cases.horizontal_coefficient * (cases.dead_weight_kn + cases.live_weight_kn)}
    return forces


# only this process talks to the caller: a forked worker that counted would write on its pipe alongside it
def progress_stays_here():
    progress.report = None


# a spawned worker (no fork, as on Windows) builds its own model beside the parent's dead load stages for what its searches and
# combinations read; it never solves, so it never factors
def spawned_worker(bridge, wind, dead, seismic, braking_height_m, special_vehicle):
    global shared, with_special_vehicle
    progress_stays_here()
    with_special_vehicle = special_vehicle
    shared = (shared_analysis(bridge, wind, (), (), dead=dead), bridge, seismic, braking_height_m)


# workers forked after the factor exists, or spawned where the platform cannot fork
def worker_pool(workers, analysis, bridge, wind, seismic, braking_height_m):
    if "fork" in multiprocessing.get_all_start_methods():
        return multiprocessing.get_context("fork").Pool(workers, initializer=progress_stays_here)
    return multiprocessing.get_context("spawn").Pool(workers, initializer=spawned_worker,
                                                     initargs=(bridge, wind, analysis.dead, seismic, braking_height_m, with_special_vehicle))


# girders, braces and diagrams: in workers that each solve, search and combine (forked, or spawned where the platform cannot fork)
# special_vehicle: also design for Class SV; construction: a ConstructionLoads for the bare-steel stage (wind and construction_seismic,
# a site with importance factor 1, go with it)
def run_analysis(bridge, wind, seismic, temperature, braking_height_m, workers, phase, special_vehicle=False, construction=None, construction_seismic=None):
    global shared, with_special_vehicle
    with_special_vehicle = bool(special_vehicle)
    phase("building the model and solving the dead load stages")
    analysis = shared_analysis(bridge, wind, (), ())
    shared = (analysis, bridge, seismic, braking_height_m)
    girders_range = range(bridge.girders.count)
    places = places_to_design(analysis.model)
    phase("factorising the stiffness matrix")
    surface_for(analysis.solver, analysis.model, 0, places[0])
    analysis.solver.surfaces.clear()
    with worker_pool(workers, analysis, bridge, wind, seismic, braking_height_m) if workers > 1 else nullcontext() as pool:
        if pool is not None:
            analysis.work = ForkedWork(pool, analysis, girders_range, places)
        phase("solving and searching the girders")
        girder_results = girder_values(analysis, bridge, seismic, temperature, braking_height_m)
        phase("solving and searching the braces")
        brace_results = brace_values(analysis, bridge, seismic, braking_height_m, keep_surfaces=False, special_vehicle=bool(special_vehicle))
        if special_vehicle:
            phase("solving and searching the Class SV")
            special_vehicle = special_vehicle_values(analysis, bridge, girder_results.place_surfaces, brace_results.special_vehicle)
            special_vehicle.placements = {}
    # The workers are gone before the replay, which holds the most here (about 1.6 GB on a 52 m deck); it solves in this process, as
    # a run without workers does, with the same diagrams.
    analysis.work = None
    phase("replaying the governing load states")
    diagrams = bridge_diagrams(analysis, girder_results, seismic, braking_height_m)
    forces = site_forces(analysis.model, wind, seismic, girder_results)
    # Only values leave this process: influence surfaces stay behind and vanish with it.
    girder_results.surfaces = girder_results.place_surfaces = {}
    settled_only([*girder_results.criticals.values(), *girder_results.place_criticals.values(), *brace_results.criticals.values()])
    if construction is not None:
        phase("the construction stage on the bare steel")
        construction = construction_design_values(bridge, construction, wind, construction_seismic)
    return BridgeDesignValues(girder_results, brace_results, diagrams, special_vehicle or None, construction), forces


def own_process_main(connection, arguments, options):
    if hasattr(os, "setsid"):
        os.setsid()  # so a Stop can end this process and its forked workers together
    try:
        progress.report = lambda done, total: connection.send(("progress", (done, total)))
        connection.send(("done", run_analysis(*arguments, lambda text: connection.send(("phase", text)), **options)))
    except Exception:
        connection.send(("error", traceback.format_exc()))
    connection.close()


# run the whole analysis in a process of its own: no GUI to fork under, and every byte of it returns to the system when it ends.
# check() may raise to stop the run; phase(text) names each stage as it starts and progress(done, total) counts its items.
def solve_in_own_process(bridge, wind, seismic, temperature, braking_height_m, *, workers, phase=lambda text: None, check=lambda: None,
                         special_vehicle=False, construction=None, construction_seismic=None, progress=lambda done, total: None):
    context = multiprocessing.get_context("spawn")
    ours, theirs = context.Pipe()
    process = context.Process(target=own_process_main, args=(theirs, (bridge, wind, seismic, temperature, braking_height_m, workers),
                                                             dict(special_vehicle=special_vehicle, construction=construction, construction_seismic=construction_seismic)))
    before = {name: os.environ.get(name) for name in ONE_BLAS_THREAD}
    os.environ.update(ONE_BLAS_THREAD)
    try:
        process.start()
    finally:
        for name, value in before.items():
            if value is None:
                del os.environ[name]
            else:
                os.environ[name] = value
    theirs.close()
    try:
        while True:
            check()
            if not ours.poll(0.2):
                continue
            try:
                kind, payload = ours.recv()
            except EOFError:
                process.join()
                raise RuntimeError(f"the setu analysis process ended unexpectedly (exit code {process.exitcode})") from None
            if kind == "phase":
                phase(payload)
            elif kind == "progress":
                progress(*payload)
            elif kind == "error":
                raise RuntimeError(f"setu analysis failed:\n{payload}")
            else:
                process.join()
                return payload
    finally:
        if process.is_alive():
            if hasattr(os, "killpg"):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    process.kill()
            else:
                process.kill()
            process.join()
