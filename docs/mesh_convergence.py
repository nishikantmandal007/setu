"""Mesh convergence study for the example bridge (examples/bridge.toml, without wind and seismic).

    uv run python docs/mesh_convergence.py

Refines along the span (panels between braces) and across the deck (target element size) in turn,
and prints the design values and live-load results that depend most on the mesh, for the outer and
the middle girder. The findings are written up in docs/mesh_convergence.md.
"""

import os
import sys
import time
from pathlib import Path

import openseespy.opensees as ops

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cli  # noqa: E402
from setu import BridgeInput, MeshSettings, girder_design_values  # noqa: E402
from setu.utils.constants import BASIC, BEARING_REACTION, BIGGER_IS_WORSE, MAX_MOMENT, SMALLER_IS_WORSE, SUPPORT_SHEAR  # noqa: E402

ALONG_THE_SPAN = [(4, 0.25), (8, 0.25), (16, 0.25), (25, 0.25), (40, 0.25)]
ACROSS_THE_DECK = [(25, 0.6), (25, 0.4), (25, 0.25), (25, 0.15)]
GIRDERS = (0, 2)


# the example bridge on this mesh
def example_on(panels_between_braces, target_size_across_width_m):
    bridge, loads = cli.read_input(Path(__file__).resolve().parents[1] / "examples" / "bridge.toml")
    return BridgeInput(**{**bridge.__dict__, "mesh": MeshSettings(panels_between_braces, target_size_across_width_m)}), loads["temperature"]


# one row per girder: live responses, ULS design values, deflection and fatigue range
def run(panels_between_braces, target_size_across_width_m):
    bridge, temperature = example_on(panels_between_braces, target_size_across_width_m)
    started = time.time()
    results = girder_design_values(bridge, temperature=temperature, ops=ops)
    seconds = time.time() - started
    rows = []
    for girder in GIRDERS:
        rows.append((panels_between_braces, target_size_across_width_m, girder,
                     results.criticals[girder, MAX_MOMENT, BIGGER_IS_WORSE].response,
                     results.criticals[girder, SUPPORT_SHEAR, SMALLER_IS_WORSE].response,
                     results.criticals[girder, BEARING_REACTION, BIGGER_IS_WORSE].response,
                     results.girders[girder][MAX_MOMENT][BASIC][BIGGER_IS_WORSE].value,
                     results.girders[girder][SUPPORT_SHEAR][BASIC][SMALLER_IS_WORSE].value,
                     1000 * results.deflections[girder]["live_m"],
                     results.fatigue[girder][MAX_MOMENT].range, seconds))
    return rows


# the table, one series at a time
def main():
    ops.logFile(os.devnull, "-noEcho")
    header = f"{'panels':>6} {'size m':>7} {'girder':>6} {'live M':>9} {'live V':>9} {'live R':>9} {'ULS M':>9} {'ULS V':>9} {'LL defl mm':>10} {'fatigue M':>9} {'s':>6}"
    for title, series in (("along the span", ALONG_THE_SPAN), ("across the deck", ACROSS_THE_DECK)):
        print(f"\nrefining {title}\n{header}")
        for mesh in series:
            for row in run(*mesh):
                print(f"{row[0]:>6} {row[1]:>7.2f} {row[2]:>6} " + " ".join(f"{value:>9.1f}" for value in row[3:8]) + f" {row[8]:>10.2f} {row[9]:>9.1f} {row[10]:>6.0f}")


if __name__ == "__main__":
    main()
