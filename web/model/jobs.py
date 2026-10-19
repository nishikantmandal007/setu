import threading
import time
import uuid
from types import SimpleNamespace

import setu.postprocess.design_values as design_values
import setu.postprocess.girder_response as girder_response
from setu import build_mesh
from setu.analysis.influence_surface import InfluenceSolver
import re
from setu.models.sections import girder_properties
from setu.utils.constants import MAX_MOMENT, SUPPORT_SHEAR

from model import analysis, drawing, progress, report, search_trace

PROGRESS_PROTOCOL = 10

_jobs = {}
_one_at_a_time = threading.Lock()  # OpenSees keeps one global model, so analyses queue behind each other
_running = None


# one analysis running in the background
class Job:
    # the bridge, its site loads, and the progress counters for each step
    def __init__(self, bridge, loads):
        self.bridge, self.loads = bridge, loads
        girders = bridge.girders.count
        mesh = build_mesh(bridge)
        self.geometry = progress.geometry(bridge, mesh)
        self.preview, self.preview_id = None, 0
        self.construction_loads = {}
        self.check_rows = []
        self.activity, self.activity_log = {}, []
        self.traces = {}
        design_places = design_values.places_to_design(SimpleNamespace(
            mesh=mesh, girders=[girder_properties(bridge.girders.section_at(g)) for g in range(girders)]))
        places = len(design_places)
        moments = sum(response == MAX_MOMENT for response, _ in design_places)
        shears = sum(response == SUPPORT_SHEAR for response, _ in design_places)
        self.totals = {"Dead load stages": 4, "Influence surfaces": girders * (places + 1), "Searching traffic": girders * (2 * places + 1),
                       "Fatigue truck": girders * (3 * moments + shears), "Checking in OpenSees": girders * 7,
                       "Preparing the plots": 2 + len(drawing.PLACES) * girders}
        self.traffic_work = {"searches": {"count": 0, "of": self.totals["Searching traffic"]},
                             "braking": {"count": 0, "of": girders*places*2},
                             "combinations": {"count": 0, "of": girders*places}}
        self.totals["Searching traffic"] = sum(v["of"] for v in self.traffic_work.values())
        self.done = {step: 0 for step in self.totals}
        self.step, self.result, self.results, self.error, self.started = "Starting", None, None, None, time.time()

    # one tracked operation has completed
    def tick(self, step):
        self.step = step
        self.done[step] = min(self.done[step] + 1, self.totals[step])

    # count a completed traffic operation
    def traffic_tick(self, kind):
        self.traffic_work[kind]["count"] += 1
        self.tick("Searching traffic")

    # publish the latest completed preview
    def show(self, stage, data):
        self.preview_id += 1
        self.preview = {"id": self.preview_id, "stage": stage, **data}

    # record the current calculation activity
    def phase(self, stage, name, **context):
        self.step = stage
        self.activity = {"id": len(self.activity_log) + 1, "stage": stage, "name": name,
                         "started_seconds": time.time()-self.started, **context}
        self.activity_log.append(self.activity)

    # retain every completed direct-solve comparison
    def checked(self, key, critical, solved):
        self.check_rows.append({"girder": key[0], "response": key[1], "adverse": key[2],
                                "unit": progress.response_unit(key[1]), "searched": critical.response, "solved": solved,
                                "difference_pct": 100 * abs(solved-critical.response) / abs(critical.response) if critical.response else None})
        self.show("Checking in OpenSees", {"kind": "check", "rows": self.check_rows[:]})

    # progress for the page
    def status(self, after_event=0, include_geometry=True):
        fraction = sum(self.done.values()) / sum(self.totals.values())
        events = self.activity_log[:]
        return {"progress_protocol": PROGRESS_PROTOCOL, "step": self.step, "count": self.done.get(self.step, 0), "of": self.totals.get(self.step, 0),
                "percent": 100 if self.result else round(99 * fraction), "seconds": round(time.time() - self.started),
                "finished": self.result is not None, "error": self.error,
                **({"geometry": self.geometry} if include_geometry else {}), "preview": self.preview,
                "traffic_work": {key: dict(value) for key, value in self.traffic_work.items()},
                "activity_seconds": round(time.time()-self.started-self.activity.get("started_seconds", 0)),
                "activity": self.activity, "activity_log": events[after_event:], "event_count": len(events),
                "stages": {step: {"count": self.done[step], "of": total} for step, total in self.totals.items()}}


# count every call of a setu function against a progress step, without changing setu
def counted(module, name, step):
    original = getattr(module, name)

    # the original call, counted for the running job
    def wrapper(*args, **kwargs):
        job = _running
        if job is not None:
            context = {}
            if name == "surface_for":
                context = {"girder": args[2], "response": args[3][0], "station_m": float(args[1].mesh.length_mesh_m[args[3][1]])}
            elif name in ("rank_all_positions", "fatigue_range"):
                context = {"target": args[0].name}
            job.phase(step, {"surface_for": "Solving an influence field", "rank_all_positions": "Evaluating traffic layouts",
                            "fatigue_range": "Evaluating a fatigue range", "dead_load_forces": "Solving construction loads"}.get(name, name), **context)
        if job is not None and name == "rank_all_positions":
            with search_trace.recording() as record:
                value = original(*args, **kwargs)
            job.traces[(args[0].name, args[3])] = (record, value)
            job.traffic_tick("searches")
            work = job.traffic_work["searches"]
            job.show(step, search_trace.preview(record, value, args[0].name, progress.response_unit(args[0].name),
                                               args[3], work["count"], work["of"]))
        else:
            value = original(*args, **kwargs)
            if job is not None:
                preview = progress.completed(name, value, args)
                if preview is not None:
                    if name == "dead_load_forces":
                        preview["stages"] = list(job.construction_loads.values())
                    job.show(step, preview)
                if name != "dead_load_forces":
                    job.tick(step)
        if job is not None:
            job.phase(step, {"surface_for": "Solved an influence field", "rank_all_positions": "Searched traffic layouts",
                             "fatigue_range": "Evaluated a fatigue range", "dead_load_forces": "Solved construction loads"}.get(name, name), **context)
        return value
    setattr(module, name, wrapper)


counted(design_values, "dead_load_forces", "Dead load stages")
counted(design_values, "surface_for", "Influence surfaces")
counted(design_values, "rank_all_positions", "Searching traffic")
counted(design_values, "fatigue_range", "Fatigue truck")


# Observe the exact construction loads before the existing solver applies them.
_solve_load_case = girder_response.analyze_load_case


# publish construction totals before and after each existing solve
def show_construction_loads(model, load_case, ops, *args, **kwargs):
    job = _running if _running is not None and _running.step == "Dead load stages" else None
    if job is not None:
        job.phase("Dead load stages", "Applying " + load_case.name)
        row = {"name": load_case.name, "total_downward_kn": progress.applied_loads(model, load_case, ops), "solved": False}
        job.construction_loads[load_case.name] = row
        job.show("Dead load stages", {"kind": "loading", "stages": list(job.construction_loads.values())})
    value = _solve_load_case(model, load_case, ops, *args, **kwargs)
    if job is not None:
        job.construction_loads[load_case.name] = {**row, "solved": True}
        job.tick("Dead load stages")
        job.phase("Dead load stages", "Solved " + load_case.name)
        job.show("Dead load stages", {"kind": "loading", "stages": list(job.construction_loads.values())})
    return value


girder_response.analyze_load_case = show_construction_loads


_deflection_field = InfluenceSolver.for_deflection
_stress_field = InfluenceSolver.for_girder_stress_mpa


# publish the completed deflection influence field
def observe_deflection_field(self, name, node):
    job = _running
    if job is not None:
        job.phase("Influence surfaces", "Solving a deflection influence field", target=name)
    value = _deflection_field(self, name, node)
    if job is not None:
        x, _, z = self.backend.node_coordinates(node)
        job.show("Influence surfaces", {"kind": "surface", "surface": progress.surface(value),
                 "girder": int(re.search(r"girder (\d+)", name).group(1)), "station_m": float(x-self.deck.skew*z)})
        job.tick("Influence surfaces")
    return value


# identify the fatigue stress field being solved
def observe_stress_field(self, name, *args, **kwargs):
    if _running is not None:
        _running.phase("Fatigue truck", "Solving a flange-stress influence field", target=name)
    return _stress_field(self, name, *args, **kwargs)


InfluenceSolver.for_deflection = observe_deflection_field
InfluenceSolver.for_girder_stress_mpa = observe_stress_field


# These operations explain the gaps between traffic counters and report completion.
def observe_operation(module, name, describe, report_tick=False):
    original = getattr(module, name)

    def wrapper(*args, **kwargs):
        job = _running
        if job is not None:
            label, context = describe(args)
            job.phase(job.step, label, **context)
        value = original(*args, **kwargs)
        if job is not None and report_tick:
            job.tick("Preparing the plots")
        return value
    setattr(module, name, wrapper)


_live_braking = design_values.live_with_braking
_combine = design_values.governing_by_limit_state


# publish both solved braking directions
def observe_braking(model, critical, read, girder, place, **kwargs):
    job = _running
    if job is not None:
        job.phase("Searching traffic", "Applying braking with traffic", girder=girder, response=place[0], adverse=critical.adverse)
    value = _live_braking(model, critical, read, girder, place, **kwargs)
    if job is not None:
        data = drawing.braking_view(model.bridge, kwargs["details"], girder, model.mesh.length_mesh_m[place[1]], place[0], critical)
        job.show("Searching traffic", data)
        job.traffic_tick("braking")
    return value


# count the completed load combination batch
def observe_combinations(effects, combinations, wind_forces, read, girder, place, at_m):
    job = _running
    if job is not None:
        job.phase("Searching traffic", "Combining load actions", girder=girder, response=place[0], station_m=float(at_m))
    value = _combine(effects, combinations, wind_forces, read, girder, place, at_m)
    if job is not None:
        job.traffic_tick("combinations")
    return value


design_values.live_with_braking = observe_braking
design_values.governing_by_limit_state = observe_combinations
observe_operation(drawing, "replay", lambda a: ("Building a traffic replay", {"girder": a[2], "response": a[3]}), report_tick=True)


# a new analysis in the background; returns its id
def start(bridge, loads):
    job_id = uuid.uuid4().hex[:8]
    _jobs[job_id] = Job(bridge, loads)
    threading.Thread(target=run, args=(_jobs[job_id],), daemon=True).start()
    return job_id


# the analysis and the report for the page, one job at a time
def run(job):
    global _running
    with _one_at_a_time:
        _running = job
        try:
            results, checks, wind, live_forces = analysis.analyse(job.bridge, job.loads, job.tick, on_check=job.checked, on_phase=job.phase)
            job.results = results
            job.phase("Preparing the plots", "Assembling solved results")
            job.show(job.step, {"kind": "results", "combinations": len(results.combinations[0][MAX_MOMENT])})
            job.tick("Preparing the plots")
            result = report.build(job.bridge, job.loads, results, checks, wind, live_forces)
            job.tick("Preparing the plots")
            job.phase("Preparing the plots", "Report ready")
            needed = {(results.surfaces[key].name, key[2]) for key in results.criticals}
            job.traces = {key: value for key, value in job.traces.items() if key in needed}
            job.result = result
        except Exception as problem:  # the page shows whatever went wrong
            job.error = f"{type(problem).__name__}: {problem}"
        finally:
            _running = None


# a job by its id, or None
def get(job_id):
    return _jobs.get(job_id)
