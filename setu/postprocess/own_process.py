import multiprocessing
import os
import signal
import traceback
from concurrent.futures import ProcessPoolExecutor

from setu.postprocess.brace_design_values import BridgeDesignValues, brace_values, member_values, search_member
from setu.postprocess.design_values import (MIDSPAN_DEFLECTION, MAX_MOMENT, girder_values, midspan_deck_node_over, search_deflection,
                                            search_place, search_stress, shared_analysis, stress_surface, surface_for, places_to_design)
from setu.postprocess import progress
from setu.postprocess.construction import construction_design_values
from setu.postprocess.governing_diagrams import bridge_diagrams
from setu.postprocess.special_vehicle import keep_worst, special_vehicle_combinations, special_vehicle_effects, special_vehicle_member, special_vehicle_values
from setu.postprocess.girder_response import analyze_load_case
from setu.loads.wind_loads import wind_load_cases
from setu.loads.seismic_loads import seismic_load_cases
from setu.utils.constants import BASIC, BIGGER_IS_WORSE

# BLAS threads do not survive a fork, and the workers already divide the work
ONE_BLAS_THREAD = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1", "MKL_NUM_THREADS": "1"}

shared = None  # what a forked worker inherits: analysis, bridge, seismic site, braking height
with_special_vehicle = False  # forked workers also work out each member's Class SV values from the surface they solved


def search_args():
    bridge = shared[1]
    return bridge.cross_section, bridge.span_m, bridge.wearing_course_thickness_m


# the worker tasks: each solves on the factor it inherited, read-only and shared with its siblings
def place_task(girder, place):
    analysis = shared[0]
    surface = surface_for(analysis.solver, analysis.model, girder, place)
    analysis.solver.surfaces.clear()
    return (surface, *search_place(surface, place, *search_args()))


def deflection_task(girder):
    analysis = shared[0]
    surface = analysis.solver.for_deflection(f"girder {girder}, {MIDSPAN_DEFLECTION}", midspan_deck_node_over(analysis.model, girder))
    analysis.solver.surfaces.clear()
    return surface, search_deflection(surface, *search_args())


def stress_task(girder, face, y_m, station):
    analysis = shared[0]
    surface = stress_surface(analysis.solver, analysis.model, girder, face, y_m, station)
    analysis.solver.surfaces.clear()
    return search_stress(surface, float(analysis.model.mesh.length_mesh_m[station]), *search_args()[:2])


# Once braking has settled each direction's placement, the other arrangements' placements (hundreds per response on a wide deck) are
# never read again; only values leave this process, so they are let go rather than carried back and held.
def settled_only(criticals):
    for critical in criticals:
        if critical is None:
            continue
        critical.alternatives = []
        if critical.searched is not None:
            critical.searched.alternatives = []


def member_task(member):
    from setu.postprocess.brace_design_values import brace_surface
    analysis, bridge, seismic, braking_height_m = shared
    surface = brace_surface(analysis.solver, analysis.model, member)
    analysis.solver.surfaces.clear()
    found = search_member(surface, *search_args())
    special = special_vehicle_member(analysis, bridge, member, surface) if with_special_vehicle else None
    values = member_values(analysis, seismic, braking_height_m, member, surface, found)
    settled_only(found.values())
    return (member, found, *values, special)


def special_vehicle_place_task(args):
    from setu.postprocess.design_values import reader
    girder, place = args
    analysis, bridge, _, _ = shared
    surface = surface_for(analysis.solver, analysis.model, girder, place)
    analysis.solver.surfaces.clear()
    found = special_vehicle_effects(analysis, bridge, surface, reader({(girder, place): surface}), (girder, place), analysis.dead.stages)
    by_limit_state = {}
    keep_worst(by_limit_state, found, special_vehicle_combinations(), float(analysis.model.mesh.length_mesh_m[place[1]]))
    return girder, place, by_limit_state, [placement for _, pair in found for placement in pair]


def special_vehicle_member_task(member):
    from setu.postprocess.brace_design_values import brace_reader, brace_surface
    analysis, bridge, _, _ = shared
    surface = brace_surface(analysis.solver, analysis.model, member)
    analysis.solver.surfaces.clear()
    found = special_vehicle_effects(analysis, bridge, surface, brace_reader({member: surface}), (member, None), analysis.dead.brace_stages, lane_reduction=False)
    by_limit_state = {}
    keep_worst(by_limit_state, found, special_vehicle_combinations(), None)
    return member, by_limit_state


def load_task(load_case):
    return analyze_load_case(shared[0].model, load_case)


class Pending:
    def __init__(self, waiting):
        self.waiting = waiting

    def result(self):
        return self.waiting.get()


# ParallelWork's results from workers forked after the factor exists, so every worker reads one copy of it
class ForkedWork:
    def __init__(self, pool, model, girders, places):
        self.pool = pool
        self.places = {(girder, place): Pending(pool.apply_async(place_task, (girder, place))) for girder in girders for place in places}
        self.deflections = {girder: Pending(pool.apply_async(deflection_task, (girder,))) for girder in girders}
        self.stresses = {(girder, face, station): Pending(pool.apply_async(stress_task, (girder, face, y_m, station)))
                         for girder in girders for face, y_m in (("steel top", model.girders[girder].depth_m), ("steel bottom", 0.0))
                         for response, station in places if response == MAX_MOMENT}

    def members(self, model):
        return self.pool.imap(member_task, list(model.brace_elements))

    def special_vehicle_places(self, girders, places):
        return self.pool.imap(special_vehicle_place_task, [(girder, place) for girder in girders for place in places])

    def special_vehicle_members(self, model):
        return self.pool.imap(special_vehicle_member_task, list(model.brace_elements))

    def load(self, load_case):
        return Pending(self.pool.apply_async(load_task, (load_case,)))


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


# girders, braces and diagrams: forked workers where the platform can fork, light search workers where it cannot
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
    if workers > 1 and "fork" in multiprocessing.get_all_start_methods():
        with multiprocessing.get_context("fork").Pool(workers, initializer=progress_stays_here) as pool:
            analysis.work = ForkedWork(pool, analysis.model, girders_range, places)
            phase("solving and searching the girders")
            girder_results = girder_values(analysis, bridge, seismic, temperature, braking_height_m)
            phase("solving and searching the braces")
            brace_results = brace_values(analysis, bridge, seismic, braking_height_m, keep_surfaces=False, special_vehicle=bool(special_vehicle))
            if special_vehicle:
                phase("solving and searching the Class SV")
                special_vehicle = special_vehicle_values(analysis, bridge, girder_results.place_surfaces, brace_results.special_vehicle)
                special_vehicle.placements = {}
            phase("replaying the governing load states")
            diagrams = bridge_diagrams(analysis, girder_results, seismic, braking_height_m)
    elif workers > 1:
        with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn")) as pool:
            phase("searching the girders")
            girder_results = girder_values(analysis, bridge, seismic, temperature, braking_height_m, search_pool=pool)
            phase("searching the braces")
            brace_results = brace_values(analysis, bridge, seismic, braking_height_m, keep_surfaces=False, search_pool=pool, special_vehicle=bool(special_vehicle))
        if special_vehicle:
            phase("solving and searching the Class SV")
            special_vehicle = special_vehicle_values(analysis, bridge, girder_results.place_surfaces, brace_results.special_vehicle)
            special_vehicle.placements = {}
        phase("replaying the governing load states")
        diagrams = bridge_diagrams(analysis, girder_results, seismic, braking_height_m)
    else:
        phase("solving and searching the girders")
        girder_results = girder_values(analysis, bridge, seismic, temperature, braking_height_m)
        phase("solving and searching the braces")
        brace_results = brace_values(analysis, bridge, seismic, braking_height_m, keep_surfaces=False, special_vehicle=bool(special_vehicle))
        if special_vehicle:
            phase("solving and searching the Class SV")
            special_vehicle = special_vehicle_values(analysis, bridge, girder_results.place_surfaces, brace_results.special_vehicle)
            special_vehicle.placements = {}
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
