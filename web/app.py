"""setu in the browser: fill in the bridge, press Analyse, read the results.

    uv run --with flask python web/app.py        then open http://localhost:5000

Runs the same analysis as cli.py (cli.read_input and cli.analyse) and only uses setu's public API.
Progress is counted by wrapping setu's search functions in this process, so setu itself is untouched.
"""

import csv
import io
import json
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from flask import Flask, Response, jsonify, request, send_file

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cli  # noqa: E402
import openseespy.opensees as ops  # noqa: E402
import setu.postprocess.design_values as design_values  # noqa: E402
from setu import applied_live_loads, build_mesh  # noqa: E402
from setu.helpers import DEFAULT_SAMPLING  # noqa: E402
from setu.irc6.impact import impact_factor  # noqa: E402
from setu.irc6.irc_constants import (  # noqa: E402
    CLASS_A_KERB_CLEARANCE_M, CLASS_A_LANE_WIDTH_M, VEHICLE_70R_CLEARANCE_M, VEHICLE_70R_WIDTH_M, ZONE_70R_ALONE_M)
from setu.irc6.vehicles import (  # noqa: E402
    CLASS_70R_TRACKED, CLASS_70R_WHEELED, CLASS_A, TrackedVehicle, both_directions_of, find_vehicle_or_its_reverse)
from setu.irc6.wheel_loads import wheel_load_offsets  # noqa: E402
from setu.utils.constants import (  # noqa: E402
    BEARING_REACTION, BIGGER_IS_WORSE, MAX_MOMENT, MIDSPAN_DEFLECTION, SMALLER_IS_WORSE, SUPPORT_SHEAR)

app = Flask(__name__)
jobs = {}
ROLL_STEPS = 90
ARRANGEMENTS_REPLAYED = 6
# the design places shown in the web app: key, (response, adverse), label, unit, and the scale from setu's units to the unit shown
PLACES = {
    "moment": ((MAX_MOMENT, BIGGER_IS_WORSE), "Moment near midspan", "kN·m", 1.0),
    "shear": ((SUPPORT_SHEAR, SMALLER_IS_WORSE), "Shear at the support", "kN", 1.0),
    "reaction": ((BEARING_REACTION, BIGGER_IS_WORSE), "Reaction at the bearing", "kN", 1.0),
    "deflection": ((MIDSPAN_DEFLECTION, BIGGER_IS_WORSE), "Midspan deflection", "mm", 1000.0),
}
CRITICAL_LABEL = {(MAX_MOMENT, BIGGER_IS_WORSE): "largest moment", (MAX_MOMENT, SMALLER_IS_WORSE): "smallest moment",
                  (SUPPORT_SHEAR, BIGGER_IS_WORSE): "largest + shear", (SUPPORT_SHEAR, SMALLER_IS_WORSE): "largest − shear",
                  (BEARING_REACTION, BIGGER_IS_WORSE): "largest reaction", (BEARING_REACTION, SMALLER_IS_WORSE): "smallest reaction",
                  (MIDSPAN_DEFLECTION, BIGGER_IS_WORSE): "largest deflection"}
one_at_a_time = threading.Lock()  # OpenSees keeps one global model, so analyses queue behind each other
running = None


class Job:
    # one analysis: where it has got to, and what it found
    def __init__(self, bridge, loads):
        self.bridge, self.loads = bridge, loads
        girders = bridge.girders.count
        places = len(design_values.places_to_design(SimpleNamespace(mesh=build_mesh(bridge))))
        self.totals = {"Dead load stages": 1, "Influence surfaces": girders * places, "Searching traffic": girders * (2 * places + 1),
                       "Fatigue truck": girders * places, "Checking in OpenSees": girders * 7}
        self.done = {step: 0 for step in self.totals}
        self.step, self.result, self.error, self.results, self.started = "Starting", None, None, None, time.time()
        self.live_forces = []

    # a step has started one more call
    def tick(self, step):
        self.step = step
        self.done[step] = min(self.done[step] + 1, self.totals[step])

    # progress for the page
    def status(self):
        fraction = sum(self.done.values()) / sum(self.totals.values())
        return {"step": self.step, "count": self.done.get(self.step, 0), "of": self.totals.get(self.step, 0),
                "percent": 100 if self.result else round(99 * fraction), "seconds": round(time.time() - self.started),
                "finished": self.result is not None, "error": self.error}


# count every call of a setu function against a progress step, without changing setu; keep=True also keeps what it returned
def counted(module, name, step, keep=False):
    original = getattr(module, name)

    def wrapper(*args, **kwargs):
        job = running
        if job is not None:
            job.tick(step)
        answer = original(*args, **kwargs)
        if job is not None and keep:
            job.live_forces.append(answer)
        return answer
    setattr(module, name, wrapper)
    return original


counted(design_values, "dead_load_forces", "Dead load stages")
counted(design_values, "surface_for", "Influence surfaces")
search_quietly = counted(design_values, "rank_all_positions", "Searching traffic")
counted(design_values, "fatigue_range", "Fatigue truck")
counted(cli, "analyze_load_case", "Checking in OpenSees", keep=True)


# the analysis in the background, one job at a time
def run(job):
    global running
    with one_at_a_time:
        running = job
        try:
            found, wind, results, _ = cli.analyse(job.bridge, job.loads)
            job.results = results
            job.step = "Preparing the plots"
            job.result = {**cli.result_to_dict(job.bridge, job.loads, found, wind, results), "drawing": drawing(job.bridge, results),
                          "diagrams": diagrams(job.bridge, results, job.live_forces), "mesh": mesh_of(job.bridge),
                          "places": {key: {"label": label, "unit": unit} for key, (_, label, unit, _) in PLACES.items()},
                          "replay": {key: {girder: replay(job.bridge, results, girder, key) for girder in range(job.bridge.girders.count)} for key in PLACES}}
        except Exception as problem:  # the page shows whatever went wrong
            job.error = f"{type(problem).__name__}: {problem}"
        finally:
            running = None


# the loads of one girder's maximum-moment critical position, as setu applies them
def max_moment_loads(bridge, results, girder, response=MAX_MOMENT, adverse=BIGGER_IS_WORSE):
    key = (girder, response, adverse)
    critical = results.criticals[key]
    wheels, patches = applied_live_loads(bridge, critical, results.surfaces[key])
    return critical, float(results.dead.total[girder].stations_m[results.stations[key]]), wheels, patches


# a vehicle on the deck for drawing: its front axle at x, centre line at z, body and axles measured from the front axle
def body_of(name, x_front_m, z_m, impact):
    vehicle = find_vehicle_or_its_reverse(name)
    tracked = isinstance(vehicle, TrackedVehicle)
    body_m = (0.0, vehicle.length_m()) if tracked else (-vehicle.lead_clearance_m, sum(vehicle.axle_spacing_m) + vehicle.trail_clearance_m)
    heading = heading_of(name)
    return {"name": name.removesuffix("_reversed").replace("_", " "), "x_m": float(x_front_m), "z_m": float(z_m), "body_m": body_m,
            "from_m": float(x_front_m + body_m[0]), "to_m": float(x_front_m + body_m[1]), "heading": heading, "impact_factor": impact, "tracked": tracked,
            "width_m": CLASS_A_LANE_WIDTH_M if name.startswith("Class_A") else VEHICLE_70R_WIDTH_M, "gauge_m": vehicle.transverse_gauge_m,
            "axles_m": [] if tracked else list(vehicle.axle_positions_m()), "track_m": [vehicle.track_length_m, vehicle.track_width_m] if tracked else None,
            "axle_loads_t": [2 * vehicle.load_per_track_t] if tracked else list(vehicle.axle_loads_t)}


# what the deck view needs: strips, girder lines and each girder's maximum-moment trucks, wheels and patches
def drawing(bridge, results):
    places = {}
    for key, ((response, adverse), _, _, scale) in PLACES.items():
        places[key] = {}
        for girder in range(bridge.girders.count):
            critical, at_m, wheels, patches = max_moment_loads(bridge, results, girder, response, adverse)
            places[key][girder] = {"at_m": at_m, "value": scale * critical.response, "lane_reduction": critical.lane_reduction, "lane_pattern": critical.lane_pattern,
                                   "vehicles": [body_of(placed.vehicle_name, x_m, placed.z_centre_m, placed.impact_factor) for placed in critical.vehicles for x_m in placed.train_x_front_m],
                                   "wheels": [[w["x_m"], w["z_m"], w["applied_kn"]] for w in wheels if w["on_span"]],
                                   "patches": [{"kind": p["kind"], "kpa": p["pressure_kpa"], "corners": p["corners_x_z_m"]} for p in patches]}
    girders = places["moment"]
    dead = results.dead.total
    return {"span_m": bridge.span_m, "width_m": bridge.width_m(), "skew": bridge.skew, "girder_lines_m": [float(z) for z in build_mesh(bridge).girder_lines_m],
            "strips": [{"name": s.name, "from_m": s.z_from_m, "to_m": s.z_to_m} for s in bridge.cross_section.strips], "max_moment": girders, "places": places,
            "dead_moment": {girder: {"x_m": [float(x) for x in dead[girder].stations_m], "kn_m": [float(m) for m in dead[girder].composite_moment_kn_m]}
                            for girder in range(bridge.girders.count)}}


# one load case's forces along every girder, rounded for the page
def along_girders(forces):
    return {girder: {"m": np.round(f.composite_moment_kn_m, 2).tolist(), "v": np.round(f.shear_kn, 2).tolist(),
                     "d": np.round(1000 * f.deflection_m, 3).tolist(), "r": round(f.reaction_kn, 2)} for girder, f in forces.items()}


# moment, shear and deflection along every girder for each dead stage and each critical live load (the live ones solved in OpenSees)
def diagrams(bridge, results, live_forces):
    cases = {f"Dead · {stage}": along_girders(forces) for stage, forces in results.dead.stages.items()}
    cases["Dead · all stages"] = along_girders(results.dead.total)
    for (girder, response, adverse), forces in zip(results.criticals, live_forces, strict=True):
        cases[f"Live · {CRITICAL_LABEL[response, adverse]} in G{girder}"] = along_girders(forces)
    return {"x_m": results.dead.total[0].stations_m.tolist(), "cases": cases}


# the deck mesh, girder lines, brace lines and girder depth for the 3D view
def mesh_of(bridge):
    mesh = build_mesh(bridge)
    section = bridge.girders.section
    return {"x_m": mesh.length_mesh_m.tolist(), "z_m": mesh.width_mesh_m.tolist(), "girder_lines_m": mesh.girder_lines_m.tolist(),
            "brace_lines_m": mesh.brace_lines_m.tolist(), "skew": bridge.skew, "slab_m": bridge.deck.thickness_m,
            "depth_m": section.web_height_m + section.top_flange_thickness_m + section.bottom_flange_thickness_m}


# a layout of vehicles driven across the span, each the way it faces, all passing their given place at travel 0:
# the girder moment from their wheels at every travel distance, off the influence surface
def rolling(bridge, surface, layout, lane_reduction):
    points = np.array([(x_m + dx, z_m + dz, load * impact * lane_reduction, heading_of(name)) for name, x_m, z_m, impact in layout
                       for dx, dz, load in wheel_load_offsets(find_vehicle_or_its_reverse(name), bridge.wearing_course_thickness_m, DEFAULT_SAMPLING)])
    margin_m = 2.0 + abs(bridge.skew) * bridge.width_m()
    off_both_ends_m = max(np.max(bridge.span_m + margin_m - points[:, 0]), np.max(points[:, 0] + margin_m))
    travel_m = np.union1d(np.linspace(-off_both_ends_m, off_both_ends_m, ROLL_STEPS), [0.0])
    wheel_x_m = points[None, :, 0] + travel_m[:, None] * points[None, :, 3]
    moments = (points[:, 2] * surface.influence_at(wheel_x_m, points[None, :, 1])).sum(axis=1)
    return travel_m, moments


# which way a vehicle drives: its axles lie behind the front one in +x, so it drives towards -x; turned round, towards +x
def heading_of(name):
    return 1 if name.endswith("_reversed") else -1


# one rolled layout for the replay
# signed and scaled so the adverse direction plots upward (a support shear is negative, a deflection is shown in mm)
def trial(bridge, surface, label, kind, layout, lane_reduction, total=None, shown_as=1.0):
    shifts, moments = rolling(bridge, surface, layout, lane_reduction)
    moments = shown_as * moments
    peak = int(np.argmax(moments))
    return {"label": label, "kind": kind, "vehicles": [body_of(*vehicle) for vehicle in layout], "shifts": np.round(shifts, 3).tolist(),
            "moments": np.round(moments, 1).tolist(), "peak": float(moments[peak]), "peak_at": peak,
            "total": float(moments[peak]) if total is None else total}


# the search replayed for one girder and one design place: each vehicle alone rolled along each lane, then setu's best lane arrangements
def replay(bridge, results, girder, place):
    (response, adverse), _, _, scale = PLACES[place]
    key = (girder, response, adverse)
    surface = results.surfaces[key]
    shown_as = scale * (1.0 if adverse == BIGGER_IS_WORSE else -1.0)
    trials = []
    for lane, carriageway in enumerate(bridge.cross_section.carriageways(), start=1):
        kinds = [(CLASS_A, CLASS_A_LANE_WIDTH_M / 2 + CLASS_A_KERB_CLEARANCE_M)]
        if carriageway.width_m() >= ZONE_70R_ALONE_M:
            kinds += [(vehicle, VEHICLE_70R_WIDTH_M / 2 + VEHICLE_70R_CLEARANCE_M) for vehicle in (CLASS_70R_WHEELED, CLASS_70R_TRACKED)]
        for vehicle, from_edge_m in kinds:
            nearest, furthest = carriageway.left_m + from_edge_m, carriageway.right_m - from_edge_m
            for z_m in sorted({round(nearest, 3), round((nearest + furthest) / 2, 3), round(furthest, 3)}):
                both = [trial(bridge, surface, f"{way.name.replace('Class_', '').replace('_', ' ').replace(' reversed', ' ↺')} alone · c/w {lane} · z {z_m:.2f} m",
                              "single", [(way.name, bridge.span_m / 2, z_m, impact_factor(way.name, bridge.span_m))], 1.0, shown_as=shown_as) for way in both_directions_of(vehicle)]
                trials.append(max(both, key=lambda t: t["peak"]))
    ranked = search_quietly(surface, bridge.cross_section, bridge.span_m, adverse, bridge.wearing_course_thickness_m)
    # IRC:22 live deflection leaves the footway load out, so its arrangements are compared without it
    without_footway = response == MIDSPAN_DEFLECTION
    arrangements = []
    for rank in reversed(range(min(ARRANGEMENTS_REPLAYED, len(ranked)))):
        case = ranked[rank]
        layout = [(placed.vehicle_name, x_m, placed.z_centre_m, placed.impact_factor) for placed in case.vehicles for x_m in placed.train_x_front_m]
        value = case.response - (case.footway_response * case.lane_reduction if without_footway else 0.0)
        found = trial(bridge, surface, f"Arrangement #{rank + 1}: {case.lane_pattern.replace('_', ' ').replace('class', 'Class').replace('70r', '70R').replace('Class a', 'Class A')}", "arrangement",
                      layout, case.lane_reduction, total=shown_as * value, shown_as=shown_as)
        found["lane_reduction"] = case.lane_reduction
        arrangements.append(found)
    winner = max(arrangements, key=lambda found: found["total"])
    for found in arrangements:
        found["winner"] = found is winner
        if found is winner:
            found["label"] = "Critical: " + found["label"].split(": ", 1)[1]
    trials += arrangements
    return {"at_m": float(results.dead.total[girder].stations_m[results.stations[key]]), "trials": trials}


# the static load case for MIDAS: vehicles for reference, wheels as point loads, UDL and footway as area loads
def midas_csv(bridge, results, girders):
    out = io.StringIO()
    rows = csv.writer(out)
    out.write("# setu live load at each girder's maximum-moment critical position, for a static check in MIDAS\n"
              "# x along the span from the first bearing, z across from the left deck edge (m); loads act downward\n"
              "# point loads already include impact and lane reduction; area pressures include lane reduction; wheels off the span are left out\n")
    for girder in girders:
        critical, at_m, wheels, patches = max_moment_loads(bridge, results, girder)
        out.write(f"\n# girder {girder}: setu composite moment at x = {at_m:.3f} m is {critical.response:.2f} kN·m (IRC:6 live load with impact, lane reduction and footway)\n")
        rows.writerow(["vehicles", "girder", "vehicle", "facing", "train", "front_x_m", "centre_z_m", "impact_factor", "lane_reduction"])
        for placed in critical.vehicles:
            for train, x_m in enumerate(placed.train_x_front_m):
                facing = "reversed" if placed.vehicle_name.endswith("_reversed") else "forward"
                rows.writerow(["vehicle", girder, placed.vehicle_name.removesuffix("_reversed"), facing, train, round(x_m, 4), round(placed.z_centre_m, 4),
                               round(placed.impact_factor, 4), critical.lane_reduction])
        rows.writerow(["point loads", "girder", "vehicle", "train", "x_m", "z_m", "wheel_kn", "impact_factor", "lane_reduction", "load_kn"])
        for w in wheels:
            if w["on_span"]:
                rows.writerow(["point", girder, w["vehicle"], w["train"], round(w["x_m"], 4), round(w["z_m"], 4), round(w["wheel_load_kn"], 4),
                               round(w["impact_factor"], 4), w["lane_reduction"], round(w["applied_kn"], 4)])
        rows.writerow(["area loads", "girder", "kind", "pressure_kpa", "x1_m", "z1_m", "x2_m", "z2_m", "x3_m", "z3_m", "x4_m", "z4_m"])
        for p in patches:
            rows.writerow(["area", girder, p["kind"], round(p["pressure_kpa"], 4), *[round(v, 4) for corner in p["corners_x_z_m"] for v in corner]])
    return out.getvalue()


# the page
@app.get("/")
def page():
    return send_file(Path(__file__).with_name("index.html"))


# the logo files, shared with the docs
@app.get("/assets/<name>")
def assets(name):
    if name not in ("logo.svg", "logo-dark.svg", "mark.svg"):
        return Response(status=404)
    return send_file(ROOT / "docs" / "assets" / name, mimetype="image/svg+xml")


# the vehicle drawings, shared with the docs
@app.get("/vehicles.js")
def vehicles_js():
    return send_file(ROOT / "docs" / "javascripts" / "vehicles.js", mimetype="text/javascript")


# the input fields, read out of examples/form.html so there is one list of inputs
@app.get("/schema")
def schema():
    form = (ROOT / "examples" / "form.html").read_text()
    return Response(re.search(r'<script type="application/json" id="schema">(.*?)</script>', form, re.S).group(1), mimetype="application/json")


# check the bridge file the page wrote and start the analysis
@app.post("/analyse")
def analyse():
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as file:
        file.write(request.get_data(as_text=True))
    try:
        bridge, loads = cli.read_input(file.name)
    except cli.BadInput as problem:
        return jsonify(error=str(problem)), 400
    except Exception as problem:  # setu's own input checks raise their own errors
        return jsonify(error=f"{type(problem).__name__}: {problem}"), 400
    finally:
        os.unlink(file.name)
    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = Job(bridge, loads)
    threading.Thread(target=run, args=(jobs[job_id],), daemon=True).start()
    return jsonify(id=job_id)


# progress as server-sent events until the analysis finishes
@app.get("/progress/<job_id>")
def progress(job_id):
    job = jobs[job_id]

    def events():
        while True:
            status = job.status()
            yield f"data: {json.dumps(status)}\n\n"
            if status["finished"] or status["error"]:
                return
            time.sleep(0.4)
    return Response(events(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})


# the finished result
@app.get("/result/<job_id>")
def result(job_id):
    return Response(json.dumps(jobs[job_id].result, default=float), mimetype="application/json")


# the MIDAS check loads for one girder or all of them
@app.get("/midas/<job_id>.csv")
def midas(job_id):
    job = jobs[job_id]
    which = request.args.get("girder", "all")
    girders = range(job.bridge.girders.count) if which == "all" else [int(which)]
    name = f"setu_midas_loads_{'all_girders' if which == 'all' else 'girder_' + which}.csv"
    return Response(midas_csv(job.bridge, job.results, girders), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={name}"})


if __name__ == "__main__":
    ops.logFile(os.devnull, "-noEcho")
    app.run(port=int(os.environ.get("PORT", 5000)), threaded=True)
