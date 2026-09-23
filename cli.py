"""setu end to end from one bridge file - for testing the numbers and comparing with MIDAS.

    python cli.py examples/bridge.toml            everything, written to analysis_results/
    python cli.py examples/bridge.toml --plot     the same, and pop up the plots
    python cli.py examples/bridge.toml --out DIR  write somewhere else

analysis_results/result.json holds every critical position (every girder, moment and shear,
both directions: vehicles, wheels with their loads, lanes, UDL and footway strips, and the
same load solved in OpenSees), the design values for every girder and limit state, the dead
loads by stage, and the wind, seismic and temperature numbers. Plots go to analysis_results/plots/.

To write the bridge file, open examples/form.html in a browser. Only setu's public API is used.
"""

import argparse
import inspect
import json
import os
import sys
import time
import tomllib
from pathlib import Path

import openseespy.opensees as ops

from setu import (
    Bracing,
    BridgeInput,
    DeckCrossSection,
    DeckSlab,
    Girders,
    MeshSettings,
    PlateGirderSection,
    build_bridge_model,
    live_load,
)
from setu.helpers import DEFAULT_SAMPLING
from setu.irc6.combinations import custom_combination
from setu.irc6.seismic import horizontal_seismic_coefficient, vertical_seismic_coefficient
from setu.irc6.temperature import temperature_difference_profile
from setu.irc6.vehicles import find_vehicle_or_its_reverse
from setu.irc6.wheel_loads import wheel_load_offsets
from setu.loads.wind_loads import wind_load_cases
from setu.models.custom_load import CustomLoad
from setu.models.materials import Concrete, Steel
from setu.models.site import SeismicSite, TemperatureSite, WindSite
from setu.postprocess.design_values import girder_design_values
from setu.postprocess.girder_response import analyze_load_case, dead_load_forces
from setu.utils.constants import (
    BASIC,
    BIGGER_IS_WORSE,
    MIDSPAN_MOMENT,
    RARE,
    SEISMIC_COMBINATION,
    SMALLER_IS_WORSE,
    SUPPORT_SHEAR,
)

BAD_INPUT = 2
RULE = "─" * 86
SUPPORT = 0
RESPONSES = (MIDSPAN_MOMENT, SUPPORT_SHEAR)
DIRECTIONS = (BIGGER_IS_WORSE, SMALLER_IS_WORSE)
BRIDGE_KEYS = {"span_m", "skew", "construction", "shuttering_kpa", "wearing_course_unit_weight_kn_m3"}
READ_FROM_KWARGS = {Bracing: {"area_m2"}}
TABLE_CLASSES = {"deck": DeckSlab, "girders.section": PlateGirderSection, "bracing": Bracing, "mesh": MeshSettings,
                 "concrete": Concrete, "steel": Steel, "wind": WindSite, "seismic": SeismicSite, "temperature": TemperatureSite}
TABLES = {"bridge", "cross_section", "deck", "girders", "bracing", "mesh", "concrete", "steel", "wind", "seismic", "temperature", "custom_loads", "combinations"}
DESIGN_COLUMNS = (
    ("ULS sagging", MIDSPAN_MOMENT, BASIC, BIGGER_IS_WORSE),
    ("ULS seismic", MIDSPAN_MOMENT, SEISMIC_COMBINATION, BIGGER_IS_WORSE),
    ("SLS rare", MIDSPAN_MOMENT, RARE, BIGGER_IS_WORSE),
    ("ULS shear", SUPPORT_SHEAR, BASIC, SMALLER_IS_WORSE),
)


class BadInput(Exception):
    pass


# ── reading the input ─────────────────────────────────────────────────────────

def keys_of(cls):
    named = {name for name, parameter in inspect.signature(cls.__init__).parameters.items() if name != "self" and parameter.kind is not parameter.VAR_KEYWORD}
    return named | READ_FROM_KWARGS.get(cls, set())


def checked(table, values, allowed):
    unknown = set(values) - set(allowed)
    if unknown:
        raise BadInput(f"[{table}] has unknown key(s) {sorted(unknown)}; valid keys are {sorted(allowed)}")
    return values


def build(table, data, required=True):
    if table not in data and not required:
        return None
    if table not in data:
        raise BadInput(f"the input needs a [{table}] table")
    cls = TABLE_CLASSES[table]
    return cls(**checked(table, data[table], keys_of(cls)))


def read_input(path):
    try:
        data = tomllib.loads(Path(path).read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise BadInput(f"cannot read {path}: {error}") from error
    checked("top level", data, TABLES)
    girders = dict(data.get("girders", {}))
    section_values = girders.pop("section", None)
    if section_values is None:
        raise BadInput("the input needs a [girders.section] table")
    section = PlateGirderSection(**checked("girders.section", section_values, keys_of(PlateGirderSection)))
    if "cross_section" not in data:
        raise BadInput("the input needs a [cross_section] table of strip widths")
    bridge = BridgeInput(
        cross_section=DeckCrossSection.from_widths(data["cross_section"]),
        deck=build("deck", data), girders=Girders(section=section, **checked("girders", girders, keys_of(Girders) - {"section"})),
        bracing=build("bracing", data), mesh=build("mesh", data),
        concrete=build("concrete", data, required=False), steel=build("steel", data, required=False),
        **checked("bridge", data.get("bridge", {}), BRIDGE_KEYS),
    )
    loads = {
        "wind": build("wind", data, required=False),
        "seismic": build("seismic", data, required=False),
        "temperature": build("temperature", data, required=False),
        "custom_loads": [CustomLoad(**checked("custom_loads", load, keys_of(CustomLoad))) for load in data.get("custom_loads", [])],
        "custom_combinations": [custom_combination(c["name"], c["factors"]) for c in data.get("combinations", [])],
    }
    return bridge, loads


# ── the analysis ──────────────────────────────────────────────────────────────

def checked_in_opensees(bridge, results, model):
    midspan = model.mesh.stations_along_span // 2
    found = {}
    for (girder, response, adverse), critical in results.criticals.items():
        surface = results.surfaces[girder, response]
        forces = analyze_load_case(model, live_load(model, critical, surface), ops)[girder]
        solved = forces.composite_moment_kn_m[midspan] if response == MIDSPAN_MOMENT else forces.shear_kn[SUPPORT]
        found[girder, response, adverse] = (surface, critical, float(solved))
    return found


def analyse(bridge, loads):
    results = girder_design_values(bridge, ops=ops, **loads)
    model = build_bridge_model(bridge, ops)
    found = checked_in_opensees(bridge, results, model)
    wind = wind_load_cases(model, loads["wind"]) if loads["wind"] else None
    dead = dead_load_forces(bridge, ops)
    return found, wind, results, dead


# ── result.json ───────────────────────────────────────────────────────────────

def wheels_of(bridge, critical):
    wheels = []
    for placed in critical.vehicles:
        vehicle = find_vehicle_or_its_reverse(placed.vehicle_name)
        offsets = wheel_load_offsets(vehicle, bridge.wearing_course_thickness_m, DEFAULT_SAMPLING)
        for train, x_front_m in enumerate(placed.train_x_front_m):
            for dx_m, dz_m, load_kn in offsets:
                x_m, z_m = x_front_m + dx_m, placed.z_centre_m + dz_m
                on_span = bool(0.0 <= x_m - bridge.skew * z_m <= bridge.span_m)
                applied_kn = load_kn * placed.impact_factor * critical.lane_reduction
                wheels.append({"vehicle": placed.vehicle_name, "train": train, "x_m": round(x_m, 6), "z_m": round(z_m, 6),
                               "wheel_load_kn": round(float(load_kn), 6), "impact_factor": placed.impact_factor,
                               "lane_reduction": critical.lane_reduction, "applied_kn": round(float(applied_kn), 6), "on_span": on_span})
    return wheels



def critical_to_dict(bridge, critical, solved):
    return {
        "live_load_response": critical.response,
        "solved_in_opensees": solved,
        "response_before_lane_reduction": critical.response_before_reduction,
        "lane_pattern": critical.lane_pattern,
        "design_lanes": critical.design_lanes,
        "lane_reduction": critical.lane_reduction,
        "carriageways_read_as": critical.carriageways_read_as,
        "footway_response": critical.footway_response,
        "residual_udl_strips_m": critical.residual_udl_strips,
        "footway_strips_m_kpa": critical.footway_strips,
        "resultant_centred_response": critical.resultant_centred_response,
        "vehicles": [{"vehicle": v.vehicle_name, "centre_z_m": v.z_centre_m, "front_x_m": v.x_front_m, "impact_factor": v.impact_factor,
                      "train_front_x_m": list(v.train_x_front_m)} for v in critical.vehicles],
        "wheels": wheels_of(bridge, critical),
    }


def result_to_dict(bridge, loads, found, wind, results, dead):
    midspan = len(dead.total[0].moment_kn_m) // 2
    critical = {f"girder {girder}": {response: {adverse: critical_to_dict(bridge, found[girder, response, adverse][1], found[girder, response, adverse][2])
                                                for adverse in DIRECTIONS} for response in RESPONSES}
                for girder in range(bridge.girders.count)}
    design = {f"girder {girder}": {response: {limit: {adverse: value.to_dict() for adverse, value in by_direction.items()}
                                              for limit, by_direction in by_limit.items()}
                                   for response, by_limit in by_response.items()}
              for girder, by_response in results.girders.items()}
    governing = {}
    for title, response, limit, adverse in DESIGN_COLUMNS:
        girder, value = results.governing(response, limit, adverse)
        governing[title] = {"girder": girder, **value.to_dict()}
    dead_loads = {f"girder {girder}": {stage: {"midspan_composite_moment_kn_m": float(forces[girder].composite_moment_kn_m[midspan]),
                                               "support_shear_kn": float(forces[girder].shear_kn[SUPPORT])}
                                       for stage, forces in dead.stages.items()}
                  for girder in range(bridge.girders.count)}
    result = {
        "bridge": {"span_m": bridge.span_m, "skew": bridge.skew, "girders": bridge.girders.count, "deck_width_m": bridge.width_m(),
                   "construction": bridge.construction, "strips": [[s.name, s.width_m] for s in bridge.cross_section.strips]},
        "units": "moments kN·m, shears kN, distances m (x along the span from the first bearing, z across from the left edge)",
        "critical_positions": critical,
        "design_values": design,
        "governing": governing,
        "dead_loads_unfactored": dead_loads,
    }
    if wind is not None:
        result["wind"] = {"forces_kn": wind.forces_kn, "wind_speed_at_deck_mps": wind.speed_at_deck_mps}
    if loads["seismic"]:
        result["seismic"] = {"horizontal_coefficient": horizontal_seismic_coefficient(loads["seismic"]),
                             "vertical_coefficient": vertical_seismic_coefficient(loads["seismic"]), "vertical_included": loads["seismic"].include_vertical}
    if results.thermal:
        positive = results.thermal["positive difference"]
        result["temperature"] = {"girder_forces": positive.girder_forces_note, "effective_range_c": results.thermal["effective range c"],
                                 "free_bearing_movement_m": results.thermal["free bearing movement m"],
                                 "primary_stress_kpa": {"slab_top": positive.slab_top_kpa, "slab_bottom": positive.slab_bottom_kpa,
                                                        "steel_top": positive.steel_top_kpa, "steel_bottom": positive.steel_bottom_kpa}}
    return result


# ── what the screen shows ─────────────────────────────────────────────────────

def print_summary(bridge, loads):
    print("setu · IRC:6-2017 · IRC:22-2015 · IRC:SP:114-2018")
    print(f"Bridge   {bridge.span_m:g} m span · {bridge.girders.count} girders · {bridge.width_m():g} m deck · skew {bridge.skew:g} · {bridge.construction}")
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


def print_results(bridge, found, results):
    print(RULE)
    print(f" {'girder':<7}{'response':<27}{'live load':>11}{'OpenSees':>11}   lanes                     vehicles (centre z, front x)")
    for (girder, response, adverse), (_, critical, solved) in found.items():
        if adverse != (BIGGER_IS_WORSE if response == MIDSPAN_MOMENT else SMALLER_IS_WORSE):
            continue
        vehicles = "; ".join(f"{v.vehicle_name} ({v.z_centre_m:.2f}, {v.x_front_m:.2f})" for v in critical.vehicles)
        print(f"   {girder:<5}{response:<27}{critical.response:11.1f}{solved:11.1f}   {critical.design_lanes}×{critical.lane_reduction:<4g}{critical.lane_pattern:<21} {vehicles}")
    print(RULE)
    print(f" {'girder':<7}" + "".join(f"{title:>15}" for title, *_ in DESIGN_COLUMNS) + "     design values (kN·m, kN)")
    for girder, by_response in results.girders.items():
        print(f"   {girder:<5}" + "".join(f"{by_response[r][limit][adverse].value:15.1f}" for _, r, limit, adverse in DESIGN_COLUMNS))
    print(RULE)
    for title, response, limit_state, adverse in DESIGN_COLUMNS:
        girder, governing = results.governing(response, limit_state, adverse)
        print(f" Governing {title:<12} girder {girder}  {governing.value:10.1f}   {governing.combination}")


# ── plots ─────────────────────────────────────────────────────────────────────

def girder_lines_m(bridge):
    import numpy as np
    return list(np.linspace(bridge.deck.overhang_m, bridge.width_m() - bridge.deck.overhang_m, bridge.girders.count))


def plot_critical(bridge, found, girder):
    import matplotlib.pyplot as plt
    import numpy as np
    figure, axes = plt.subplots(2, 1, figsize=(13, 9), constrained_layout=True)
    for axis, response in zip(axes, (MIDSPAN_MOMENT, SUPPORT_SHEAR), strict=True):
        worst = max((found[girder, response, adverse] for adverse in (BIGGER_IS_WORSE, SMALLER_IS_WORSE)), key=lambda item: abs(item[1].response))
        surface, critical, solved = worst
        along, across = np.meshgrid(surface.length_mesh_m, surface.width_mesh_m, indexing="ij")
        filled = axis.contourf(along, across, surface.values, levels=30, cmap="RdBu_r")
        figure.colorbar(filled, ax=axis, label="influence ordinate")
        for strip in bridge.cross_section.strips:
            axis.axhline(strip.z_from_m, color="0.4", lw=0.6)
        wheels = [w for w in wheels_of(bridge, critical) if w["on_span"]]
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
        unit = "kN·m" if response == MIDSPAN_MOMENT else "kN"
        axis.set_title(f"Girder {girder} · {response}: {critical.response:.1f} {unit} ({critical.lane_pattern}) · OpenSees {solved:.1f}")
        axis.legend(loc="upper right", fontsize=8)
    figure.suptitle("setu · critical vehicle position", fontweight="bold")
    return figure



def plot_design(bridge, results):
    import matplotlib.pyplot as plt
    import numpy as np
    figure, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    girders = list(results.girders)
    width = 0.2
    for k, (title, response, limit, adverse) in enumerate(DESIGN_COLUMNS):
        values = [results.girders[g][response][limit][adverse].value for g in girders]
        axes[0, 0].bar(np.array(girders) + (k - 1.5) * width, values, width, label=title)
    axes[0, 0].axhline(0, color="k", lw=0.6)
    axes[0, 0].set_xticks(girders)
    axes[0, 0].set_xlabel("girder")
    axes[0, 0].set_ylabel("kN·m / kN")
    axes[0, 0].set_title("Design values per girder")
    axes[0, 0].legend(fontsize=8)

    girder, governing = results.governing(MIDSPAN_MOMENT, BASIC, BIGGER_IS_WORSE)
    shares = {group: share for group, share in governing.shares.items() if share}
    axes[0, 1].barh(list(shares), list(shares.values()), color="tab:blue")
    axes[0, 1].set_title(f"Governing ULS sagging, girder {girder}: {governing.value:.1f} kN·m\n{governing.combination}")
    axes[0, 1].set_xlabel("factored share (kN·m)")

    dead = dead_load_forces(bridge, ops)
    for stage, forces in dead.stages.items():
        axes[1, 0].plot(forces[girder].stations_m, forces[girder].composite_moment_kn_m, label=stage)
    axes[1, 0].plot(dead.total[girder].stations_m, dead.total[girder].composite_moment_kn_m, "k", lw=2, label="all dead load")
    axes[1, 0].set_title(f"Dead load moment along girder {girder} (unfactored)")
    axes[1, 0].set_xlabel("along the span (m)")
    axes[1, 0].set_ylabel("composite moment (kN·m)")
    axes[1, 0].legend(fontsize=8)

    if results.thermal:
        stresses = results.thermal["positive difference"]
        depths = [depth for depth, _, _ in stresses.layers]
        axes[1, 1].plot([s / 1000 for s in stresses.stresses], depths, "tab:red", label="primary stress (MPa)")
        profile = temperature_difference_profile(bridge.deck.thickness_m)
        axes[1, 1].plot([t for _, t in profile], [d for d, _ in profile], "tab:orange", ls="--", label="temperature difference (°C)")
        axes[1, 1].axhline(bridge.deck.thickness_m, color="0.5", lw=0.6)
        axes[1, 1].invert_yaxis()
        axes[1, 1].set_ylabel("depth from slab top (m)")
        axes[1, 1].set_title("Temperature (Fig. 16b, positive) through the composite section")
        axes[1, 1].legend(fontsize=8)
    else:
        axes[1, 1].axis("off")
    figure.suptitle("setu · design values", fontweight="bold")
    return figure


def save_plots(bridge, found, results, out_dir, pop_up):
    import matplotlib
    if not pop_up:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plots = Path(out_dir) / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    governing_girder, _ = results.governing(MIDSPAN_MOMENT, BASIC, BIGGER_IS_WORSE)
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
    found, wind, results, dead = analyse(bridge, loads)
    print(f"done in {time.time() - started:.1f} s")
    print_results(bridge, found, results)
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result_to_dict(bridge, loads, found, wind, results, dead), indent=1, default=float))
    save_plots(bridge, found, results, out, arguments.plot)
    print(f"Everything written to {out}/ (result.json and plots/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
