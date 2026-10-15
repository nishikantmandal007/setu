"""The form's verification inputs reach a real, JSON-serializable analysis report."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))

from model import analysis, inputs, report  # noqa: E402
from setu.utils.constants import BIGGER_IS_WORSE, MAX_MOMENT  # noqa: E402


def form():
    return {
        "tables": {t["table"]: {f["key"]: f["value"] for f in t["fields"]} for t in inputs.SCHEMA["tables"] if "fields" in t},
        "strips": next(t["strips"] for t in inputs.SCHEMA["tables"] if "strips" in t),
    }


def test_grade_labels_are_optional_and_kept_separate():
    given = form()
    given["tables"]["steel"]["grade"] = " E350 "
    given["tables"]["bracing"]["steel_grade"] = "E250"
    given["tables"]["bracing"]["end_diaphragm_steel_grade"] = "E410"
    given["tables"]["concrete"]["grade"] = "M35"
    bridge, _ = inputs.bridge_from_form(given)

    assert bridge.steel.grade == "E350"
    assert bridge.bracing.steel_grade == "E250"
    assert bridge.bracing.end_diaphragm_steel_grade == "E410"
    assert bridge.concrete.grade == "M35"

    for values in given["tables"].values():
        for key in ("grade", "steel_grade", "end_diaphragm_steel_grade"):
            values.pop(key, None)
    bridge, _ = inputs.bridge_from_form(given)
    assert bridge.steel.grade is None and bridge.concrete.grade is None
    assert bridge.bracing.steel_grade is None and bridge.bracing.end_diaphragm_steel_grade is None


@pytest.mark.parametrize("table,key", [("steel", "grade"), ("concrete", "grade"), ("bracing", "steel_grade"), ("bracing", "end_diaphragm_steel_grade")])
@pytest.mark.parametrize("invalid", [350, [], "E" * 81])
def test_bad_grade_labels_are_refused(table, key, invalid):
    given = form()
    given["tables"][table][key] = invalid
    with pytest.raises(inputs.InputError, match="grade label"):
        inputs.bridge_from_form(given)


def test_verification_report_from_a_real_analysis():
    given = form()
    given["tables"]["girders"]["count"] = 3
    given["tables"]["mesh"] = {"panels_between_braces": 2, "target_size_across_width_m": 1.0}
    given["tables"]["steel"]["grade"] = "E350"
    bridge, loads = inputs.bridge_from_form(given)
    results, checks, wind, live_forces = analysis.analyse(bridge, loads, lambda _: None)
    body = json.loads(json.dumps(report.build(bridge, loads, results, checks, wind, live_forces), allow_nan=False))

    assert body["bridge"]["deck_width_m"] == pytest.approx(13.5)
    assert body["bridge"]["girder_spacing_m"] == pytest.approx(5.5)
    assert body["bridge"]["effective_slab_widths_m"] == {"girder 0": 4.0, "girder 1": 5.5, "girder 2": 4.0}
    assert body["bridge"]["grades"] == {"girder": "E350", "cross bracing": None, "end diaphragm": None, "concrete": None}
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
