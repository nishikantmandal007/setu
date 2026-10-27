"""The form's verification inputs reach a real, JSON-serializable analysis report."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))

from model import analysis, inputs, jobs, report  # noqa: E402
from setu import Bracing, Concrete, Steel  # noqa: E402
from setu.utils.constants import BIGGER_IS_WORSE, MAX_MOMENT  # noqa: E402


# the bridge's steel, bracing and concrete, checked to be what the form should have built
def materials(bridge):
    assert isinstance(bridge.steel, Steel) and isinstance(bridge.bracing, Bracing) and isinstance(bridge.concrete, Concrete)
    return bridge.steel, bridge.bracing, bridge.concrete


# one server-sent progress event as JSON
def event_json(chunk):
    return json.loads(chunk[len("data: "):])


def form():
    return {
        "tables": {t["table"]: {f["key"]: f["value"] for f in t["fields"]} for t in inputs.SCHEMA["tables"] if "fields" in t},
        "strips": next(t["strips"] for t in inputs.SCHEMA["tables"] if "strips" in t),
    }


def test_grades_are_optional_and_kept_separate():
    given = form()
    given["tables"]["steel"]["grade"] = "E 350A"
    given["tables"]["bracing"]["steel_grade"] = "E 250A"
    given["tables"]["bracing"]["end_diaphragm_steel_grade"] = "E 410C"
    given["tables"]["concrete"]["grade"] = "M35"
    steel, bracing, concrete = materials(inputs.bridge_from_form(given)[0])

    assert steel.grade == "E 350A"
    assert bracing.steel_grade == "E 250A"
    assert bracing.end_diaphragm_steel_grade == "E 410C"
    assert concrete.grade == "M35"

    for values in given["tables"].values():
        for key in ("grade", "steel_grade", "end_diaphragm_steel_grade"):
            values.pop(key, None)
    steel, bracing, concrete = materials(inputs.bridge_from_form(given)[0])
    assert steel.grade is None and concrete.grade is None
    assert bracing.steel_grade is None and bracing.end_diaphragm_steel_grade is None


@pytest.mark.parametrize("table,key", [("steel", "grade"), ("concrete", "grade"), ("bracing", "steel_grade"), ("bracing", "end_diaphragm_steel_grade")])
@pytest.mark.parametrize("invalid", [350, [], "E350", "M35 "])
def test_grades_outside_the_material_table_are_refused(table, key, invalid):
    given = form()
    given["tables"][table][key] = invalid
    with pytest.raises(inputs.InputError, match="must be one of"):
        inputs.bridge_from_form(given)


def test_verification_report_from_a_real_analysis():
    given = form()
    given["tables"]["girders"]["count"] = 3
    given["tables"]["mesh"] = {"panels_between_braces": 2, "target_size_across_width_m": 1.0}
    given["tables"]["steel"]["grade"] = "E 350A"
    given["tables"]["concrete"]["grade"] = None
    bridge, loads = inputs.bridge_from_form(given)
    results, checks, wind, live_forces = analysis.analyse(bridge, loads, lambda _: None)
    body = json.loads(json.dumps(report.build(bridge, loads, results, checks, wind, live_forces), allow_nan=False))

    assert body["bridge"]["deck_width_m"] == pytest.approx(13.5)
    assert body["bridge"]["girder_spacing_m"] == pytest.approx(5.5)
    assert body["bridge"]["effective_slab_widths_m"] == {"girder 0": 4.0, "girder 1": 5.5, "girder 2": 4.0}
    assert body["bridge"]["grades"] == {"girder": {"grade": "E 350A", "fy_mpa": 350, "fu_mpa": 490},
                                        "cross bracing": {"grade": "E 250A", "fy_mpa": 250, "fu_mpa": 410},
                                        "end diaphragm": {"grade": "E 250A", "fy_mpa": 250, "fu_mpa": 410}, "concrete": None}

    for girder in results.girders:
        key = f"girder {girder}"
        df = body["deflections_m"][key]
        assert sum(df["dead_m"].values()) + df["live_m"] == pytest.approx(df["total_m"])
        assert set(body["fatigue_stresses_mpa"][key]) == {"steel top", "steel bottom"}
        for stress in body["fatigue_stresses_mpa"][key].values():
            assert stress["range"] > 0
            assert stress["range"] == pytest.approx(stress["largest"] - stress["smallest"])
        for value in body["combinations"][key][MAX_MOMENT].values():
            largest = value[BIGGER_IS_WORSE]
            assert largest["value"] == pytest.approx(sum(largest["shares"].values()))
        for case in body["drawing"]["places"].values():
            assert all(v["impact_factor"] >= 1 and "z_m" in v and "x_m" in v for v in case[str(girder)]["vehicles"])
    assert "Dead · all stages" in body["diagrams"]["cases"]
    for check in body["checks"]:
        assert check["solved"] == pytest.approx(check["searched"], rel=1e-4, abs=1e-8)


def test_each_grade_fills_the_stiffness_it_stands_for():
    assert inputs.CONCRETE_FILLS["M40"] == {"elastic_modulus_mpa": 33000}
    assert inputs.STEEL_GRADES["E 450BR"] == {"fy_mpa": 450, "fu_mpa": 570}
    assert len(inputs.STEEL_GRADES) == 28 and len(inputs.CONCRETE_GRADES) == 16
    schema = {t["table"]: {f["key"]: f for f in t["fields"]} for t in inputs.SCHEMA["tables"] if "fields" in t}
    assert inputs.CONCRETE_FILLS[schema["concrete"]["grade"]["value"]]["elastic_modulus_mpa"] == schema["concrete"]["elastic_modulus_mpa"]["value"]

@pytest.mark.parametrize("individual", [False, True])
def test_http_submission_runs_a_real_job_and_returns_its_report(monkeypatch, individual):
    from flask import Flask
    import routes

    given = form()
    given["tables"]["girders"]["count"] = 3
    given["tables"]["mesh"] = {"panels_between_braces": 2, "target_size_across_width_m": 1.5}
    given["tables"]["bracing"]["station_count"] = 3
    if individual:
        section = given["tables"]["girders.section"]
        given["tables"]["girders"]["sections"] = [{**section, "web_height_m": 2.1 + 0.1 * k} for k in range(3)]
        given["tables"]["bridge"]["skew"] = 0.2
        given["tables"]["bracing"]["arrangement"] = "KT"
        given["tables"]["wind"].update(drag=2.2, exposed_area_m2=100., force_height_above_deck_m=-0.4)
        given["tables"]["seismic"].update(horizontal_coefficient=0.1, vertical_coefficient=0.05,
                                           dead_weight_kn=9000., live_weight_kn=600., include_vertical=True)
        given["tables"]["analysis"]["braking_height_above_deck_m"] = 1.8
        given["include"] = {"wind": True, "seismic": True}

    # Execute the real worker synchronously to make the HTTP test deterministic.
    class InlineThread:
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    previews = {}
    check_previews, loading_previews = [], []
    show = jobs.Job.show

    # retain published previews without changing the real worker
    def capture(job, stage, data):
        show(job, stage, data)
        json.dumps(job.status(), allow_nan=False)
        previews.setdefault(data["kind"], data)
        assert not {"frame", "frames", "verified_forces"} & data.keys()
        if data["kind"] == "check":
            check_previews.append(data)
        if data["kind"] == "loading":
            loading_previews.append(data)

    monkeypatch.setattr(jobs.Job, "show", capture)
    monkeypatch.setattr(jobs.threading, "Thread", InlineThread)
    app = Flask(__name__)
    app.config["TESTING"] = True
    routes.register(app)
    client = app.test_client()
    response = client.post("/analyse", json=given)
    assert response.status_code == 200
    job_id = response.get_json()["id"]
    try:
        job = jobs.get(job_id)
        assert job is not None and job.error is None
        results, result = job.results, job.result
        assert results is not None and result is not None
        assert job.status()["finished"]
        assert job.done == job.totals
        assert job.done["Dead load stages"] == 4
        assert all(v["count"] == v["of"] for v in job.traffic_work.values())
        brake = previews["braking"]
        assert brake["combined"] == pytest.approx(brake["live"] + brake["directions"][brake["selected"]]["response"])
        for direction, sign in (("forwards", 1), ("backwards", -1)):
            nodes = brake["directions"][direction]["nodes"]
            assert sum(n["fx_kn"] for n in nodes) == pytest.approx(sign*brake["force_kn"])
            height = job.bridge.deck.thickness_m/2 + (1.8 if individual else job.bridge.wearing_course_thickness_m+1.2)
            assert sum(n["mz_kn_m"] for n in nodes) == pytest.approx(-sign*brake["force_kn"]*height)
        from setu.analysis.along_span import along_the_mesh, positions_along_span, sum_over_wheels, with_every_train_spacing
        from setu.helpers import DEFAULT_SAMPLING
        from setu.irc6.vehicles import find_vehicle_or_its_reverse
        from setu.irc6.wheel_loads import wheel_load_offsets

        for place, ((response_name, adverse), _, _, _) in report.drawing.PLACES.items():
            for girder in range(3):
                key = (girder, response_name, adverse)
                source = results.surfaces[key]
                record, ranked = job.traces[(source.name, adverse)]
                if place == "deflection":
                    traffic = max(case.response - case.footway_response * case.lane_reduction for case in ranked)
                    assert traffic == results.criticals[key].response
                else:
                    assert ranked[0].response == results.criticals[key].response
                for vehicle in record["vehicles"]:
                    truck = find_vehicle_or_its_reverse(vehicle["key"])
                    offsets = along_the_mesh(wheel_load_offsets(truck, job.bridge.wearing_course_thickness_m, DEFAULT_SAMPLING), job.bridge.skew)
                    mesh_surface = source.along_the_mesh()
                    full_x = with_every_train_spacing(positions_along_span(mesh_surface, offsets), truck)
                    train = vehicle["train"]
                    for j in range(len(record["z_m"])):
                        assert train["response"][j] == pytest.approx(vehicle["impact_factor"] * sum(train["ordinates"][j]))
                    for j in (0, len(record["z_m"])//2, len(record["z_m"])-1):
                        # Brute force the full x grid independently of the recorded train.
                        column = sum_over_wheels(mesh_surface, offsets, full_x, [record["z_m"][j]])[:, 0]
                        alone = vehicle["impact_factor"] * (column.max() if adverse == BIGGER_IS_WORSE else column.min())
                        if len(train["x_front_m"][j]) == 1:
                            assert train["response"][j] == pytest.approx(alone, rel=1e-9)
                        else:
                            assert (train["response"][j] - alone) * (1 if adverse == BIGGER_IS_WORSE else -1) >= -1e-9
        for key, r in result["replay"].items():
            for g, view in r.items():
                assert (view["braking"] is None) == (key == "deflection")
                if view["braking"]:
                    assert view["braking"]["girder"] == int(g)
                    assert view["braking"]["station_m"] == view["at_m"]
        assert len(job.traces) == len({(results.surfaces[key].name, key[2]) for key in results.criticals})
        assert all("Completed " not in event["name"] for event in job.activity_log)
        assert {"Solved an influence field", "Searched traffic layouts", "Evaluated a fatigue range", "Solved construction loads"} <= {e["name"] for e in job.activity_log}
        search = previews["search"]
        assert 0 < len(search["ranking"]) <= 8
        assert search["searched"] == 1 and search["of"] == job.traffic_work["searches"]["of"]
        assert all(not row["vehicles"] for row in search["ranking"][1:])
        assert {e["girder"] for e in job.activity_log if e["name"] == "Solving a critical load case"} == set(range(3))
        assert len([e for e in job.activity_log if e["name"] == "Building a traffic replay"]) == len(report.drawing.PLACES)*3
        assert job.done["Preparing the plots"] == 2 + len(report.drawing.PLACES)*3
        assert job.status(after_event=len(job.activity_log))["activity_log"] == []
        assert set(previews) == {"loading", "dead", "surface", "search", "braking", "fatigue", "check", "results"}
        geometry = job.status()["geometry"]
        assert geometry["width_m"] == pytest.approx(job.bridge.width_m())
        assert sum(s["width_m"] for s in geometry["strips"]) == pytest.approx(geometry["width_m"])
        assert geometry["sections"] == [vars(job.bridge.girders.section_at(g)) for g in range(3)]
        assert previews["loading"]["stages"][0]["name"] == "steel self weight"
        assert previews["loading"]["stages"][0]["total_downward_kn"] > 0
        assert set(previews["loading"]["stages"][0]) == {"name", "total_downward_kn", "solved"}
        reactions = sum(f.reaction_kn + f.end_reaction_kn for f in results.dead.stages["steel self weight"].values())
        assert previews["loading"]["stages"][0]["total_downward_kn"] == pytest.approx(reactions, rel=1e-6)
        assert {row["name"] for row in previews["dead"]["stages"]} == set(results.dead.stages)
        assert previews["dead"]["construction_stages"] == list(results.dead.stages)
        assert previews["dead"]["forces"]["moment_kn_m"] == results.dead.total[0].composite_moment_kn_m.tolist()
        assert previews["dead"]["forces"]["far_reaction_kn"] == results.dead.total[0].end_reaction_kn
        surface = next(iter(results.surfaces.values()))
        first = previews["surface"]["surface"]
        # The first surface is retained as the governing surface on this coarse mesh.
        assert first["name"] == surface.name
        assert first["minimum"] == float(surface.values.min())
        assert first["maximum"] == float(surface.values.max())
        assert first["full_shape"] == list(surface.values.shape)
        fatigue = previews["fatigue"]
        assert fatigue["range"] == pytest.approx(fatigue["largest"] - fatigue["smallest"])
        assert previews["check"]["rows"][0]["solved"] == pytest.approx(previews["check"]["rows"][0]["searched"], rel=1e-4, abs=1e-8)
        assert [len(p["rows"]) for p in check_previews] == list(range(1, job.totals["Checking in OpenSees"] + 1))
        assert job.check_rows == check_previews[-1]["rows"]
        for row, check in zip(job.check_rows, result["checks"], strict=True):
            key = (check["girder"], check["response"], check["adverse"])
            solved = check["solved"]
            assert (row["girder"], row["response"], row["adverse"]) == key
            assert row["searched"] == results.criticals[key].response
            assert row["solved"] == solved
            if row["searched"]:
                assert row["difference_pct"] == pytest.approx(100 * abs(solved-row["searched"]) / abs(row["searched"]))
            else:
                assert row["difference_pct"] is None
        assert len(loading_previews) == 8
        for i, preview in enumerate(loading_previews):
            assert len(preview["stages"]) == i // 2 + 1
            assert preview["stages"][-1]["solved"] == bool(i % 2)
            assert all(row["solved"] for row in preview["stages"][:-1])
        assert all(row["solved"] for row in previews["dead"]["stages"])
        assert "steel_frame" not in geometry
        stream = client.get(f"/progress/{job_id}")
        status = json.loads(stream.data.decode().removeprefix("data: ").strip())
        assert status["geometry"] == geometry
        assert status["preview"]["kind"] == "results"

        assert status["progress_protocol"] == client.get("/schema").get_json()["progress_protocol"] == 10
        # Keep this stream open for two events, then let the finished job close it.
        saved_result = job.result
        job.result = None
        monkeypatch.setattr("controller.time.sleep", lambda _: None)
        stream = client.get(f"/progress/{job_id}", buffered=False)
        try:
            events = iter(stream.response)
            first = event_json(next(events))
            second = event_json(next(events))
            assert first["geometry"] == geometry
            assert "geometry" not in second
        finally:
            job.result = saved_result
            stream.close()

        response = client.get(f"/result/{job_id}")
        assert response.status_code == 200
        body = response.get_json()
        assert body["mesh"]["girder_depths_m"] == pytest.approx([2.165, 2.265, 2.365] if individual else [2.165] * 3)
        for check in body["checks"]:
            assert check["solved"] == pytest.approx(check["searched"], rel=1e-4, abs=1e-8)
        assert all("r_end" in force for force in body["diagrams"]["cases"]["Dead · all stages"].values())
        if individual:
            assert body["site"]["seismic"]["horizontal_coefficient"] == 0.1
    finally:
        jobs._jobs.pop(job_id, None)


def test_far_bearing_reader_preserves_both_reactions():
    from types import SimpleNamespace
    from setu.utils.constants import BEARING_REACTION

    forces = SimpleNamespace(reaction_kn=10., end_reaction_kn=25.)
    assert analysis.solved_at(forces, BEARING_REACTION, 0) == 10.
    assert analysis.solved_at(forces, BEARING_REACTION, 8) == 25.


@pytest.mark.parametrize("invalid", [-1., float("nan"), True, "high"])
def test_bad_braking_height_is_rejected_before_starting_a_job(invalid):
    given = form()
    given["tables"]["analysis"]["braking_height_above_deck_m"] = invalid
    with pytest.raises(inputs.InputError, match="finite and nonnegative"):
        inputs.bridge_from_form(given)


@pytest.mark.parametrize("sections", [[], [None] * 5, [{"bad": 1}] * 5])
def test_bad_individual_sections_are_rejected(sections):
    given = form()
    given["tables"]["girders"]["sections"] = sections
    with pytest.raises(inputs.InputError):
        inputs.bridge_from_form(given)


def test_unequal_depth_automatic_wind_is_an_actionable_http_input_error():
    from flask import Flask
    import routes

    given = form()
    section = given["tables"]["girders.section"]
    given["tables"]["girders"]["sections"] = [{**section, "web_height_m": 2.1 + 0.1 * k} for k in range(5)]
    given["include"] = {"wind": True}
    app = Flask(__name__)
    routes.register(app)
    response = app.test_client().post("/analyse", json=given)
    assert response.status_code == 400
    assert "engineer-supplied" in response.get_json()["error"]


@pytest.mark.parametrize("fails", [False, True])
def test_progress_counts_only_completed_operations_and_exposes_each_stage(monkeypatch, fails):
    from types import SimpleNamespace

    bridge, loads = inputs.bridge_from_form(form())
    job = jobs.Job(bridge, loads)
    monkeypatch.setattr(jobs, "_running", job)

    def operation():
        assert job.step == "Dead load stages"
        assert job.status()["stages"]["Dead load stages"] == {"count": 0, "of": 4}
        if fails:
            raise RuntimeError("solver failed")
        return "solved"

    module = SimpleNamespace(operation=operation)
    jobs.counted(module, "operation", "Dead load stages")
    if fails:
        with pytest.raises(RuntimeError, match="solver failed"):
            module.operation()
    else:
        assert module.operation() == "solved"
    status = job.status()
    assert status["stages"]["Dead load stages"]["count"] == (0 if fails else 1)
    assert status["stages"]["Preparing the plots"] == {"count": 0, "of": 2 + len(report.drawing.PLACES) * bridge.girders.count}
    assert status["stages"]["Searching traffic"]["count"] == 0


def test_progress_surface_displays_original_nodes_and_full_grid_extrema():
    import numpy as np
    from model import progress
    from setu.analysis.influence_surface import InfluenceSurface

    x, z = np.linspace(0, 35, 83), np.linspace(0, 13.5, 57)
    values = x[:, None] ** 2 - z[None, :] ** 3
    source = InfluenceSurface(values, x, z, "maximum composite moment", 0.2)
    shown = progress.surface(source)
    assert shown["full_shape"] == [83, 57]
    assert shown["minimum"] == float(values.min())
    assert shown["maximum"] == float(values.max())
    assert shown["unit"] == "kN·m / kN"
    assert len(shown["x_m"]) == 41 and len(shown["z_m"]) == 25
    for i, along in enumerate(shown["x_m"]):
        for j, across in enumerate(shown["z_m"]):
            assert shown["values"][i][j] == values[np.where(x == along)[0][0], np.where(z == across)[0][0]]




def test_activity_cursor_returns_each_event_once():
    bridge, loads = inputs.bridge_from_form(form())
    job = jobs.Job(bridge, loads)
    job.phase("Influence surfaces", "Solving field", girder=0, station_m=17.5)
    first = job.status()
    job.phase("Influence surfaces", "Solving field", girder=1, station_m=17.5)
    second = job.status(after_event=first["event_count"])
    assert [e["girder"] for e in first["activity_log"] + second["activity_log"]] == [0, 1]
    assert job.status(after_event=second["event_count"])["activity_log"] == []
