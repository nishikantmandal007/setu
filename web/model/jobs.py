import threading
import time
import uuid
from types import SimpleNamespace

import setu.postprocess.design_values as design_values
from setu import build_mesh

from model import analysis, report

_jobs = {}
_one_at_a_time = threading.Lock()  # OpenSees keeps one global model, so analyses queue behind each other
_running = None


# one analysis running in the background
class Job:
    # the bridge, its site loads, and the progress counters for each step
    def __init__(self, bridge, loads):
        self.bridge, self.loads = bridge, loads
        girders = bridge.girders.count
        places = len(design_values.places_to_design(SimpleNamespace(mesh=build_mesh(bridge))))
        self.totals = {"Dead load stages": 1, "Influence surfaces": girders * places, "Searching traffic": girders * (2 * places + 1),
                       "Fatigue truck": girders * places, "Checking in OpenSees": girders * 7}
        self.done = {step: 0 for step in self.totals}
        self.step, self.result, self.results, self.error, self.started = "Starting", None, None, None, time.time()

    # one more call of a step has started
    def tick(self, step):
        self.step = step
        self.done[step] = min(self.done[step] + 1, self.totals[step])

    # progress for the page
    def status(self):
        fraction = sum(self.done.values()) / sum(self.totals.values())
        return {"step": self.step, "count": self.done.get(self.step, 0), "of": self.totals.get(self.step, 0),
                "percent": 100 if self.result else round(99 * fraction), "seconds": round(time.time() - self.started),
                "finished": self.result is not None, "error": self.error}


# count every call of a setu function against a progress step, without changing setu
def counted(module, name, step):
    original = getattr(module, name)

    # the original call, counted for the running job
    def wrapper(*args, **kwargs):
        if _running is not None:
            _running.tick(step)
        return original(*args, **kwargs)
    setattr(module, name, wrapper)


counted(design_values, "dead_load_forces", "Dead load stages")
counted(design_values, "surface_for", "Influence surfaces")
counted(design_values, "rank_all_positions", "Searching traffic")
counted(design_values, "fatigue_range", "Fatigue truck")


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
            results, checks, wind, live_forces = analysis.analyse(job.bridge, job.loads, job.tick)
            job.results = results
            job.step = "Preparing the plots"
            job.result = report.build(job.bridge, job.loads, results, checks, wind, live_forces)
        except Exception as problem:  # the page shows whatever went wrong
            job.error = f"{type(problem).__name__}: {problem}"
        finally:
            _running = None


# a job by its id, or None
def get(job_id):
    return _jobs.get(job_id)
