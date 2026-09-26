"""setu end to end from one bridge file.

    python cli.py examples/bridge.toml            everything, written to analysis_results/
    python cli.py examples/bridge.toml --plot     the same, and pop up the plots
    python cli.py examples/bridge.toml --out DIR  write somewhere else

analysis_results/result.json holds every critical position (every girder, moment and shear,
both directions: vehicles, wheels with their loads, lanes, UDL and footway strips, and the
same load solved in OpenSees), the design values for every girder and limit state, the dead
loads by stage, and the wind, seismic and temperature numbers. Plots go to analysis_results/plots/.
analysis_results/critical_positions.csv lists where every vehicle stands for each girder's maximum
bending moment. analysis_results/girder_results.nc holds the girder
element forces and displacements of every dead load stage and critical live load, in OsdagBridge's
xarray layout.

To write the bridge file, open examples/form.html in a browser. Only setu's public API is used.
"""

import argparse
import csv
import inspect
import json
import os
import sys
import time
import tomllib
from pathlib import Path

import openseespy.opensees as ops

from setu import (
    AddedDeadLoads,
    Bracing,
    BridgeInput,
    DeckCrossSection,
    DeckSlab,
    Girders,
    MeshSettings,
    PlateGirderSection,
    build_mesh,
    build_bridge_model,
    live_load,
)
from setu.irc6.combinations import custom_combination
from setu.irc6.seismic import horizontal_seismic_coefficient, vertical_seismic_coefficient
from setu.loads.wind_loads import wind_load_cases
from setu.models.custom_load import CustomLoad
from setu.models.materials import Concrete, Steel
from setu.models.site import SeismicSite, TemperatureSite, WindSite
from setu.loads.load_builders import applied_live_loads
from setu.postprocess.design_values import girder_design_values
from setu.postprocess.result_dataset import merge_datasets, result_dataset
from setu.postprocess.girder_response import analyze_load_case
from setu.utils.constants import (
    BASIC,
    BIGGER_IS_WORSE,
    KPA_PER_MPA,
    BEARING_REACTION,
    MAX_MOMENT,
    MIDSPAN_DEFLECTION,
    RARE,
    RULE,
    SEISMIC_COMBINATION,
    SMALLER_IS_WORSE,
    SUPPORT,
    SUPPORT_SHEAR,
)

BAD_INPUT = 2
CRITICAL_POSITION_COLUMNS = ("girder", "section_x_m", "vehicle", "facing", "centre_z_m", "front_x_m_of_each_in_train", "impact_factor", "lane_reduction", "live_moment_kn_m")
BRIDGE_KEYS = {"span_m", "skew", "wearing_course_unit_weight_kn_m3"}
# the direction each response is printed and plotted in
WORSE_WAY = {MAX_MOMENT: BIGGER_IS_WORSE, SUPPORT_SHEAR: SMALLER_IS_WORSE, BEARING_REACTION: BIGGER_IS_WORSE, MIDSPAN_DEFLECTION: BIGGER_IS_WORSE}
UNIT = {MAX_MOMENT: "kN·m", SUPPORT_SHEAR: "kN", BEARING_REACTION: "kN", MIDSPAN_DEFLECTION: "m"}
# deflection is solved in m and printed in mm
PRINTED_SCALE = {MIDSPAN_DEFLECTION: 1000.0}
PRINTED_UNIT = {MIDSPAN_DEFLECTION: " (mm)"}
TABLE_CLASSES = {"deck": DeckSlab, "girders.section": PlateGirderSection, "bracing": Bracing, "mesh": MeshSettings,
                 "concrete": Concrete, "steel": Steel, "wind": WindSite, "seismic": SeismicSite, "temperature": TemperatureSite,
                 "added_dead_loads": AddedDeadLoads}
TABLES = {"bridge", "cross_section", "deck", "girders", "bracing", "mesh", "concrete", "steel", "added_dead_loads",
          "wind", "seismic", "temperature", "custom_loads", "combinations"}
DESIGN_COLUMNS = (
    ("ULS sagging", MAX_MOMENT, BASIC, BIGGER_IS_WORSE),
    ("ULS seismic", MAX_MOMENT, SEISMIC_COMBINATION, BIGGER_IS_WORSE),
    ("SLS rare", MAX_MOMENT, RARE, BIGGER_IS_WORSE),
    ("ULS shear", SUPPORT_SHEAR, BASIC, SMALLER_IS_WORSE),
    ("ULS reaction", BEARING_REACTION, BASIC, BIGGER_IS_WORSE),
)


class BadInput(Exception):
    pass


# ── reading the input ─────────────────────────────────────────────────────────

# the parameter names a class takes, split into the ones it must get and all of them
def keys_of(cls):
    parameters = [p for name, p in inspect.signature(cls.__init__).parameters.items() if name != "self"]
    return {p.name for p in parameters if p.default is p.empty}, {p.name for p in parameters}


# refuse a table with a key we don't know or a key it must have missing
def checked(table, values, required, allowed):
    unknown = set(values) - allowed
    if unknown:
        raise BadInput(f"[{table}] has unknown key(s) {sorted(unknown)}; valid keys are {sorted(allowed)}")
    missing = required - set(values)
    if missing:
        raise BadInput(f"[{table}] is missing {sorted(missing)}")
    return values


# the [table] out of the file, or a clear error when it isn't there
def table_of(data, table):
    node = data
    for part in table.split("."):
        if part not in node:
            raise BadInput(f"the input needs a [{table}] table")
        node = node[part]
    return node


# one model object from its table
def build(table, data):
    cls = TABLE_CLASSES[table]
    return cls(**checked(table, table_of(data, table), *keys_of(cls)))


# wind, seismic and temperature are left out of the analysis when their table is not in the file
def build_if_given(table, data):
    return build(table, data) if table in data else None


# the whole bridge file into a BridgeInput and the site loads
def read_input(path):
    try:
        data = tomllib.loads(Path(path).read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise BadInput(f"cannot read {path}: {error}") from error
    checked("top level", data, set(), TABLES)
    girders = {key: value for key, value in table_of(data, "girders").items() if key != "section"}
    bridge = BridgeInput(
        cross_section=DeckCrossSection.from_widths(table_of(data, "cross_section")),
        deck=build("deck", data),
        girders=Girders(section=build("girders.section", data), **checked("girders", girders, {"count"}, {"count"})),
        bracing=build("bracing", data), mesh=build("mesh", data),
        steel=build("steel", data), concrete=build("concrete", data),
        added_dead_loads=build("added_dead_loads", data),
        **checked("bridge", table_of(data, "bridge"), BRIDGE_KEYS, BRIDGE_KEYS),
    )
    loads = {
        "wind": build_if_given("wind", data),
        "seismic": build_if_given("seismic", data),
        "temperature": build_if_given("temperature", data),
        "custom_loads": [CustomLoad(**checked("custom_loads", load, *keys_of(CustomLoad))) for load in data.get("custom_loads", [])],
        "custom_combinations": [custom_combination(c["name"], c["factors"]) for c in data.get("combinations", [])],
    }
    return bridge, loads


# ── the analysis ──────────────────────────────────────────────────────────────

# solve every critical position's live load in OpenSees as a check
def checked_in_opensees(bridge, results, model):
    found = {}
    datasets = []
    for key, critical in results.criticals.items():
        girder, response, adverse = key
        surface = results.surfaces[key]
        forces = analyze_load_case(model, live_load(model, critical, surface), ops)[girder]
        datasets.append(result_dataset(model, ops, f"live, girder {girder}, {response}, {adverse}"))
        found[key] = (surface, critical, solved_at(forces, response, results.stations[key]))
    return found, datasets


# the response read straight off the solved girder, at the station the critical position was searched for
def solved_at(forces, response, station):
    if response == MAX_MOMENT:
        return float(forces.composite_moment_kn_m[station])
    if response == SUPPORT_SHEAR:
        return float(forces.shear_kn[station])
    if response == BEARING_REACTION:
        return forces.reaction_kn
    return float(forces.deflection_m[station])


# design values, the OpenSees check, wind and dead load for the bridge
def analyse(bridge, loads):
    results = girder_design_values(bridge, ops=ops, **loads)
    model = build_bridge_model(bridge, ops)
    found, live_datasets = checked_in_opensees(bridge, results, model)
    wind = wind_load_cases(model, loads["wind"]) if loads["wind"] else None
    return found, wind, results, merge_datasets([results.dead.dataset, *live_datasets])


# ── result.json ───────────────────────────────────────────────────────────────

# one critical position for result.json
def critical_to_dict(critical, solved):
    return {
        "live_load_response": critical.response,
        "solved_in_opensees": solved,
        "response_before_lane_reduction": critical.response_before_reduction,
        "lane_pattern": critical.lane_pattern,
        "design_lanes": critical.design_lanes,
        "lane_reduction": critical.lane_reduction,
        "footway_response": critical.footway_response,
        "residual_udl_strips_m": critical.residual_udl_strips,
        "footway_strips_m_kpa": critical.footway_strips,
        "vehicles": [{"vehicle": v.vehicle_name, "centre_z_m": v.z_centre_m, "front_x_m": v.x_front_m, "impact_factor": v.impact_factor,
                      "train_front_x_m": list(v.train_x_front_m)} for v in critical.vehicles],
    }


# everything for result.json
def result_to_dict(bridge, loads, found, wind, results):
    dead = results.dead
    midspan = len(dead.total[0].moment_kn_m) // 2
    critical = {}
    for (girder, response, adverse), (_, position, solved) in found.items():
        critical.setdefault(f"girder {girder}", {}).setdefault(response, {})[adverse] = {
            "at_m": float(dead.total[girder].stations_m[results.stations[girder, response, adverse]]),
            **critical_to_dict(position, solved)}
    design = {f"girder {girder}": {response: {limit: {adverse: value.to_dict() for adverse, value in by_direction.items()}
                                              for limit, by_direction in by_limit.items()}
                                   for response, by_limit in by_response.items()}
              for girder, by_response in results.girders.items()}
    governing = {}
    for title, response, limit, adverse in DESIGN_COLUMNS:
        girder, value = results.governing(response, limit, adverse)
        governing[title] = {"girder": girder, **value.to_dict()}
    dead_loads = {f"girder {girder}": {stage: {"midspan_composite_moment_kn_m": float(forces[girder].composite_moment_kn_m[midspan]),
                                               "support_shear_kn": float(forces[girder].shear_kn[SUPPORT]),
                                               "bearing_reaction_kn": forces[girder].reaction_kn,
                                               "midspan_deflection_m": float(forces[girder].deflection_m[midspan])}
                                       for stage, forces in dead.stages.items()}
                  for girder in range(bridge.girders.count)}
    fatigue = {f"girder {girder}": {response: {"range": found_range.range, "largest": found_range.largest, "smallest": found_range.smallest,
                                               "at_m": found_range.at_m, "truck_centre_z_m": found_range.z_centre_m, "impact_factor": found_range.impact_factor,
                                               "truck_front_x_m_at_largest": found_range.x_front_at_largest_m, "truck_front_x_m_at_smallest": found_range.x_front_at_smallest_m}
                                    for response, found_range in by_response.items()}
               for girder, by_response in results.fatigue.items()}
    result = {
        "bridge": {"span_m": bridge.span_m, "skew": bridge.skew, "girders": bridge.girders.count, "deck_width_m": bridge.width_m(),
                   "strips": [[s.name, s.width_m] for s in bridge.cross_section.strips]},
        "units": "moments kN·m, shears kN, distances m (x along the span from the first bearing, z across from the left edge)",
        "critical_positions": critical,
        "design_values": design,
        "governing": governing,
        "dead_loads_unfactored": dead_loads,
        "deflections_m": {f"girder {girder}": deflection for girder, deflection in results.deflections.items()},
        "deflection_limits_m": {"live_load_and_impact": bridge.span_m / 800, "total": bridge.span_m / 600},
        "fatigue_ranges": fatigue,
        "live_shear_range_kn": {f"girder {girder}": value for girder, value in results.live_shear_range_kn.items()},
    }
    if wind is not None:
        result["wind"] = {"forces_kn": wind.forces_kn, "wind_speed_at_deck_mps": wind.speed_at_deck_mps}
    if loads["seismic"]:
        result["seismic"] = {"horizontal_coefficient": horizontal_seismic_coefficient(loads["seismic"]),
                             "vertical_coefficient": vertical_seismic_coefficient(loads["seismic"]), "vertical_included": loads["seismic"].include_vertical}
    if results.thermal:
        result["temperature"] = {"effective_range_c": results.thermal["effective range c"], "free_bearing_movement_m": results.thermal["free bearing movement m"],
                                 "profiles_depth_m_and_c": results.thermal["profiles"],
                                 "primary_stress_kpa": {f"girder {girder}": {kind: {"slab_top": stresses.slab_top_kpa, "slab_bottom": stresses.slab_bottom_kpa,
                                                                                    "steel_top": stresses.steel_top_kpa, "steel_bottom": stresses.steel_bottom_kpa,
                                                                                    "effective_slab_width_m": stresses.slab_width_m}
                                                                             for kind, stresses in by_kind.items()}
                                                        for girder, by_kind in results.thermal["girders"].items()},
                                 "girder_forces": "simply supported with a free bearing: no girder force from temperature, only these primary stresses"}
    return result


# each girder's maximum-moment critical position, one row per vehicle: where every vehicle of the train stands
def write_critical_positions_csv(path, results):
    with open(path, "w", newline="") as file:
        rows = csv.writer(file)
        rows.writerow(CRITICAL_POSITION_COLUMNS)
        for (girder, response, adverse), critical in results.criticals.items():
            if response != MAX_MOMENT or adverse != BIGGER_IS_WORSE:
                continue
            at_m = float(results.dead.total[girder].stations_m[results.stations[girder, response, adverse]])
            for vehicle in critical.vehicles:
                facing = "reversed" if vehicle.vehicle_name.endswith("_reversed") else "forward"
                rows.writerow([girder, round(at_m, 3), vehicle.vehicle_name.removesuffix("_reversed"), facing, round(vehicle.z_centre_m, 4),
                               " ".join(f"{x_m:.4f}" for x_m in vehicle.train_x_front_m), round(vehicle.impact_factor, 4),
                               critical.lane_reduction, round(critical.response, 2)])


# ── what the screen shows ─────────────────────────────────────────────────────

# one line on the bridge and the loads being run
def print_summary(bridge, loads):
    print("setu · IRC:6-2017 · IRC:22-2015 · IRC:SP:114-2018")
    print(f"Bridge   {bridge.span_m:g} m span · {bridge.girders.count} girders · {bridge.width_m():g} m deck · skew {bridge.skew:g}")
    site = ["dead", "live + braking"]
    if loads["wind"]:
        site.append(f"wind {loads['wind'].basic_wind_speed_mps:g} m/s {loads['wind'].terrain}")
    if loads["seismic"]:
        site.append(f"seismic {loads['seismic'].zone}/{loads['seismic'].soil}")
    if loads["temperature"]:
        site.append("temperature")
    if loads["custom_loads"]:
        site.append(f"{len(loads['custom_loads'])} custom load(s)")
    print(f"Loads    {' · '.join(site)}")


# the critical positions and design values table
def print_results(bridge, found, results):
    print(RULE)
    print(f" {'girder':<7}{'response':<27}{'live load':>11}{'OpenSees':>11}   lanes                     vehicles (centre z, front x)")
    for (girder, response, adverse), (_, critical, solved) in found.items():
        if adverse != WORSE_WAY[response]:
            continue
        vehicles = "; ".join(f"{v.vehicle_name} ({v.z_centre_m:.2f}, {v.x_front_m:.2f})" for v in critical.vehicles)
        shown = PRINTED_SCALE.get(response, 1.0)
        print(f"   {girder:<5}{response + PRINTED_UNIT.get(response, ''):<27}{shown * critical.response:11.1f}{shown * solved:11.1f}   {critical.design_lanes}×{critical.lane_reduction:<4g}{critical.lane_pattern:<21} {vehicles}")
    print(RULE)
    print(f" {'girder':<7}" + "".join(f"{title:>15}" for title, *_ in DESIGN_COLUMNS) + "     design values (kN·m, kN)")
    for girder, by_response in results.girders.items():
        print(f"   {girder:<5}" + "".join(f"{by_response[r][limit][adverse].value:15.1f}" for _, r, limit, adverse in DESIGN_COLUMNS))
    print(RULE)
    for title, response, limit_state, adverse in DESIGN_COLUMNS:
        girder, governing = results.governing(response, limit_state, adverse)
        print(f" Governing {title:<12} girder {girder}  {governing.value:10.1f}   {governing.combination}")


# ── plots ─────────────────────────────────────────────────────────────────────

# where the girders sit across the deck
def girder_lines_m(bridge):
    return list(build_mesh(bridge).girder_lines_m)


# influence surface and critical vehicles for one girder
def plot_critical(bridge, found, girder):
    import matplotlib.pyplot as plt
    import numpy as np
    figure, axes = plt.subplots(2, 1, figsize=(13, 9), constrained_layout=True)
    for axis, response in zip(axes, (MAX_MOMENT, SUPPORT_SHEAR), strict=True):
        worst = max((found[girder, response, adverse] for adverse in (BIGGER_IS_WORSE, SMALLER_IS_WORSE)), key=lambda item: abs(item[1].response))
        surface, critical, solved = worst
        along, across = np.meshgrid(surface.length_mesh_m, surface.width_mesh_m, indexing="ij")
        filled = axis.contourf(along, across, surface.values, levels=30, cmap="RdBu_r")
        figure.colorbar(filled, ax=axis, label="influence ordinate")
        for strip in bridge.cross_section.strips:
            axis.axhline(strip.z_from_m, color="0.4", lw=0.6)
        wheels = [w for w in applied_live_loads(bridge, critical, surface)[0] if w["on_span"]]
        axis.scatter([w["x_m"] - bridge.skew * w["z_m"] for w in wheels], [w["z_m"] for w in wheels],
                     s=[8 + w["applied_kn"] for w in wheels], c="k", marker="s", label="wheel loads (size ∝ kN)")
        for k, (a, b) in enumerate(critical.residual_udl_strips):
            axis.axhspan(a, b, fill=False, hatch="//", edgecolor="darkorange", lw=0, label="residual UDL" if k == 0 else None)
        for k, (a, b, _) in enumerate(critical.footway_strips):
            axis.axhspan(a, b, fill=False, hatch="..", edgecolor="green", lw=0, label="footway load" if k == 0 else None)
        for line_m in girder_lines_m(bridge):
            axis.axhline(line_m, color="k", ls="--", lw=0.8)
        axis.axhline(girder_lines_m(bridge)[girder], color="k", ls="-", lw=2, label=f"girder {girder}")
        axis.set_xlim(surface.length_mesh_m[0], surface.length_mesh_m[-1])
        axis.set_ylim(surface.width_mesh_m[0], surface.width_mesh_m[-1])
        axis.set_xlabel("along the span (m)")
        axis.set_ylabel("across the deck from the left edge (m)")
        axis.set_title(f"Girder {girder} · {response}: {critical.response:.1f} {UNIT[response]} ({critical.lane_pattern}) · OpenSees {solved:.1f}")
        axis.legend(loc="upper right", fontsize=8)
    figure.suptitle("setu · critical vehicle position", fontweight="bold")
    return figure



# design values, dead load and temperature dashboard
def plot_design(bridge, results):
    import matplotlib.pyplot as plt
    import numpy as np
    figure, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    girders = list(results.girders)
    width = 0.8 / len(DESIGN_COLUMNS)
    for k, (title, response, limit, adverse) in enumerate(DESIGN_COLUMNS):
        values = [results.girders[g][response][limit][adverse].value for g in girders]
        axes[0, 0].bar(np.array(girders) + (k - (len(DESIGN_COLUMNS) - 1) / 2) * width, values, width, label=title)
    axes[0, 0].axhline(0, color="k", lw=0.6)
    axes[0, 0].set_xticks(girders)
    axes[0, 0].set_xlabel("girder")
    axes[0, 0].set_ylabel("kN·m / kN")
    axes[0, 0].set_title("Design values per girder")
    axes[0, 0].legend(fontsize=8)

    girder, governing = results.governing(MAX_MOMENT, BASIC, BIGGER_IS_WORSE)
    shares = {group: share for group, share in governing.shares.items() if share}
    axes[0, 1].barh(list(shares), list(shares.values()), color="tab:blue")
    axes[0, 1].set_title(f"Governing ULS sagging, girder {girder}: {governing.value:.1f} kN·m\n{governing.combination}")
    axes[0, 1].set_xlabel("factored share (kN·m)")

    dead = results.dead
    for stage, forces in dead.stages.items():
        axes[1, 0].plot(forces[girder].stations_m, forces[girder].composite_moment_kn_m, label=stage)
    axes[1, 0].plot(dead.total[girder].stations_m, dead.total[girder].composite_moment_kn_m, "k", lw=2, label="all dead load")
    axes[1, 0].set_title(f"Dead load moment along girder {girder} (unfactored)")
    axes[1, 0].set_xlabel("along the span (m)")
    axes[1, 0].set_ylabel("composite moment (kN·m)")
    axes[1, 0].legend(fontsize=8)

    if results.thermal:
        for kind, colour in (("positive difference", "tab:red"), ("reverse difference", "tab:blue")):
            stresses = results.thermal["girders"][girder][kind]
            depths = [depth for depth, _, _ in stresses.layers]
            axes[1, 1].plot([s / KPA_PER_MPA for s in stresses.stresses], depths, colour, label=f"{kind}: primary stress (MPa)")
            profile = results.thermal["profiles"][kind]
            axes[1, 1].plot([t for _, t in profile], [d for d, _ in profile], colour, ls="--", label=f"{kind}: temperature (°C)")
        axes[1, 1].axhline(bridge.deck.thickness_m, color="0.5", lw=0.6)
        axes[1, 1].invert_yaxis()
        axes[1, 1].set_ylabel("depth from slab top (m)")
        axes[1, 1].set_title(f"Temperature (Fig. 17b) through girder {girder}'s composite section")
        axes[1, 1].legend(fontsize=8)
    else:
        axes[1, 1].axis("off")
    figure.suptitle("setu · design values", fontweight="bold")
    return figure


# write every plot, and pop up the main ones if asked
def save_plots(bridge, found, results, out_dir, pop_up):
    import matplotlib
    if not pop_up:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plots = Path(out_dir) / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    governing_girder, _ = results.governing(MAX_MOMENT, BASIC, BIGGER_IS_WORSE)
    figures = {"design": plot_design(bridge, results)}
    for girder in range(bridge.girders.count):
        figures[f"critical_girder_{girder}"] = plot_critical(bridge, found, girder)
    for name, figure in figures.items():
        figure.savefig(plots / f"{name}.png", dpi=130, bbox_inches="tight")
        if not pop_up or name not in ("design", f"critical_girder_{governing_girder}"):
            plt.close(figure)
    if pop_up:
        plt.show()


# ── the one command ───────────────────────────────────────────────────────────

# read the bridge file, run everything, write analysis_results/
def main(argv=None):
    arguments = argparse.ArgumentParser(prog="cli.py", description="setu end to end: critical positions and IRC:6 design values for every girder.")
    arguments.add_argument("input", help="bridge file (TOML); write one with examples/form.html")
    arguments.add_argument("--out", default="analysis_results", help="folder for result.json and plots (default analysis_results)")
    arguments.add_argument("--plot", action="store_true", help="also pop up the design and governing critical-position plots")
    arguments = arguments.parse_args(argv)
    ops.logFile(os.devnull, "-noEcho")
    try:
        bridge, loads = read_input(arguments.input)
    except BadInput as problem:
        print(f"Input problem: {problem}", file=sys.stderr)
        return BAD_INPUT
    print_summary(bridge, loads)
    print("Analysing …", end=" ", flush=True)
    started = time.time()
    found, wind, results, dataset = analyse(bridge, loads)
    print(f"done in {time.time() - started:.1f} s")
    print_results(bridge, found, results)
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result_to_dict(bridge, loads, found, wind, results), indent=1, default=float))
    write_critical_positions_csv(out / "critical_positions.csv", results)
    dataset.to_netcdf(out / "girder_results.nc")
    save_plots(bridge, found, results, out, arguments.plot)
    print(f"Everything written to {out}/ (result.json, critical_positions.csv, girder_results.nc and plots/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
