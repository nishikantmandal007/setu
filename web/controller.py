import json
import time
from pathlib import Path

from flask import Response, jsonify, request, send_file

from model import critical_loads, inputs, jobs

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
# files the page shares with the docs: the logo and the vehicle drawings
SHARED = {"logo.svg": ("docs/assets/logo.svg", "image/svg+xml"), "logo-dark.svg": ("docs/assets/logo-dark.svg", "image/svg+xml"),
          "mark.svg": ("docs/assets/mark.svg", "image/svg+xml"), "vehicles.js": ("docs/javascripts/vehicles.js", "text/javascript")}


# the page
def page():
    return send_file(WEB / "views" / "index.html")


# the input form's fields
def schema():
    return jsonify(inputs.SCHEMA)


# check the bridge the page sent and start its analysis
def analyse():
    try:
        bridge, loads = inputs.bridge_from_form(request.get_json(force=True))
    except Exception as problem:  # the form's and setu's own input checks both name what is wrong
        return jsonify(error=str(problem) if isinstance(problem, inputs.InputError) else f"{type(problem).__name__}: {problem}"), 400
    return jsonify(id=jobs.start(bridge, loads))


# progress as server-sent events until the analysis finishes
def progress(job_id):
    job = jobs.get(job_id)
    if job is None:
        return Response(status=404)

    # one status every 0.4 s until it is done
    def events():
        while True:
            status = job.status()
            yield f"data: {json.dumps(status)}\n\n"
            if status["finished"] or status["error"]:
                return
            time.sleep(0.4)
    return Response(events(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})


# the finished report
def result(job_id):
    job = jobs.get(job_id)
    if job is None or job.result is None:
        return Response(status=404)
    return Response(json.dumps(job.result, default=float), mimetype="application/json")


# the critical position's loads for one girder or all of them, as CSV
def critical_loads_file(job_id):
    job = jobs.get(job_id)
    if job is None or job.results is None:
        return Response(status=404)
    which = request.args.get("girder", "all")
    girders = range(job.bridge.girders.count) if which == "all" else [int(which)]
    name = f"setu_critical_loads_{'all_girders' if which == 'all' else 'girder_' + which}.csv"
    return Response(critical_loads.critical_loads_csv(job.bridge, job.results, girders), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={name}"})


# the logo and vehicle drawings, straight from the docs
def shared(name):
    if name not in SHARED:
        return Response(status=404)
    path, mimetype = SHARED[name]
    return send_file(ROOT / path, mimetype=mimetype)
