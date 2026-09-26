"""cli.py: one command, the whole analysis, everything in analysis_results/ - for testing values and comparing with MIDAS."""

import json
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("openseespy.opensees", reason="needs a finite element solver")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import cli  # noqa: E402

EXAMPLE = REPO / "examples" / "bridge.toml"
FORM = REPO / "examples" / "form.html"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """The example bridge on a coarse mesh, run once through the one command."""
    folder = tmp_path_factory.mktemp("cli")
    small = folder / "bridge.toml"
    small.write_text(EXAMPLE.read_text().replace("panels_between_braces = 25", "panels_between_braces = 4").replace("target_size_across_width_m = 0.25", "target_size_across_width_m = 0.6"))
    out = folder / "analysis_results"
    assert cli.main([str(small), "--out", str(out)]) == 0
    return out, json.loads((out / "result.json").read_text())


def test_everything_lands_in_one_folder(run):
    out, result = run

    assert set(result) >= {"critical_positions", "design_values", "governing", "dead_loads_unfactored", "wind", "seismic", "temperature"}
    assert sorted(p.name for p in (out / "plots").iterdir()) == ["critical_girder_0.png", "critical_girder_1.png", "critical_girder_2.png", "critical_girder_3.png", "critical_girder_4.png", "design.png"]


def test_every_critical_position_gets_a_midas_csv_and_osdagbridge_gets_the_dataset(run):
    import xarray as xr

    out, result = run
    csvs = sorted((out / "midas").iterdir())
    dataset = xr.open_dataset(out / "girder_results.nc")

    assert len(csvs) == 5 * 2 * 2
    assert "wheel_load_kn" in csvs[0].read_text() and "pressure_kpa" in csvs[0].read_text()
    assert dataset["forces"].dims == ("Loadcase", "Element", "Component")
    assert len(dataset["Loadcase"]) == 3 + 5 * 2 * 2
    assert result["critical_positions"]["girder 0"]["midspan composite moment"]["maximum"]["udl_and_footway_patches"]


def test_every_critical_position_is_there_and_matches_opensees(run):
    _, result = run
    positions = result["critical_positions"]

    assert len(positions) == 5
    for by_response in positions.values():
        for by_direction in by_response.values():
            assert set(by_direction) == {"maximum", "minimum"}
            for position in by_direction.values():
                assert position["solved_in_opensees"] == pytest.approx(position["live_load_response"], rel=1e-5, abs=1e-3)
                assert position["vehicles"] and position["wheels"]


def test_each_wheel_carries_impact_and_lane_reduction(run):
    _, result = run
    for wheel in result["critical_positions"]["girder 1"]["midspan composite moment"]["maximum"]["wheels"]:
        assert wheel["applied_kn"] == pytest.approx(wheel["wheel_load_kn"] * wheel["impact_factor"] * wheel["lane_reduction"], rel=1e-5)
        assert isinstance(wheel["on_span"], bool)


def test_mirror_girders_match(run):
    _, result = run
    design = result["design_values"]

    assert design["girder 0"]["midspan composite moment"]["ultimate, basic"]["maximum"]["value"] == pytest.approx(
        design["girder 4"]["midspan composite moment"]["ultimate, basic"]["maximum"]["value"], rel=1e-6)


def test_a_typo_names_the_valid_keys(tmp_path, capsys):
    typo = tmp_path / "typo.toml"
    typo.write_text(EXAMPLE.read_text().replace("span_m = 35.0", "spna_m = 35.0"))

    assert cli.main([str(typo), "--out", str(tmp_path / "out")]) == cli.BAD_INPUT
    assert "unknown key(s) ['spna_m']" in capsys.readouterr().err


def _form_schema():
    return json.loads(re.search(r'<script type="application/json" id="schema">(.*?)</script>', FORM.read_text(), re.S).group(1))


def test_every_form_field_is_a_key_setu_accepts():
    for table in _form_schema()["tables"]:
        if table.get("strips"):
            continue
        allowed = cli.BRIDGE_KEYS if table["table"] == "bridge" else {"count"} if table["table"] == "girders" else cli.keys_of(cli.TABLE_CLASSES[table["table"]])[1]
        assert {field["key"] for field in table["fields"]} <= allowed, table["table"]


def test_the_form_defaults_make_a_valid_input(tmp_path):
    """Written the way the page's toml() writes it: one [table] per section, key = value lines."""
    lines = []
    for table in _form_schema()["tables"]:
        lines.append(f"[{table['table']}]")
        if table.get("strips"):
            lines += [f"{name} = {width}" for name, width in table["strips"]]
            continue
        for field in table["fields"]:
            value = field["value"]
            if value == "":
                continue
            lines.append(f"{field['key']} = {json.dumps(value) if isinstance(value, str) else str(value).lower() if isinstance(value, bool) else value}")
    path = tmp_path / "from_form.toml"
    path.write_text("\n".join(lines) + "\n")

    bridge, loads = cli.read_input(path)

    assert bridge.span_m == 35.0 and bridge.girders.count == 5
    assert loads["wind"] is not None and loads["seismic"] is not None


def test_a_misspelt_table_is_named(tmp_path, capsys):
    no_concrete = tmp_path / "no_concrete.toml"
    no_concrete.write_text(EXAMPLE.read_text().replace("[concrete]", "[concrete_gone]"))

    assert cli.main([str(no_concrete), "--out", str(tmp_path / "out")]) == cli.BAD_INPUT
    assert "unknown key(s) ['concrete_gone']" in capsys.readouterr().err


def test_a_missing_key_is_named(tmp_path, capsys):
    no_modulus = tmp_path / "no_modulus.toml"
    no_modulus.write_text(EXAMPLE.read_text().replace("elastic_modulus_mpa = 200000\n", ""))

    assert cli.main([str(no_modulus), "--out", str(tmp_path / "out")]) == cli.BAD_INPUT
    assert "[steel] is missing ['elastic_modulus_mpa']" in capsys.readouterr().err
