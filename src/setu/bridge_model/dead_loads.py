"""The weight the bridge carries before any traffic arrives.

Five things, each worked out where it actually sits:

    the slab, everywhere,
    the wearing course, on the carriageways only,
    the footpath, kerb and median surfacing, each on its own strip,
    the girders, along their own length,
    and the bracing, shared between the nodes at its ends.

The slab and everything on it are lumped to the deck nodes by tributary area:
each node takes the load standing on the patch of deck that is nearer to it than
to any other node.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..reporting import report
from .build_model import BridgeModel

DEAD_LOAD_PATTERN = 1
DEAD_LOAD_TIME_SERIES = 1


@dataclass(frozen=True)
class DeadLoadTotals:
    """What was applied, so it can be checked against the support reactions."""

    deck_and_surfacing_kn: float
    girders_kn: float
    bracing_kn: float

    @property
    def total_kn(self) -> float:
        return self.deck_and_surfacing_kn + self.girders_kn + self.bracing_kn


def apply_dead_loads(model: BridgeModel, ops=None, new_pattern: bool = True) -> DeadLoadTotals:
    """Applies the bridge's own weight, and returns what was applied."""
    ops = _opensees() if ops is None else ops

    if new_pattern:
        # Starting a load case means starting from a known state. The load factor
        # of a Linear time series follows the pseudo-time, so a model that has
        # already been analysed once would otherwise pick up twice its own weight.
        ops.remove("loadPattern", DEAD_LOAD_PATTERN)
        ops.remove("timeSeries", DEAD_LOAD_TIME_SERIES)
        ops.timeSeries("Linear", DEAD_LOAD_TIME_SERIES)
        ops.pattern("Plain", DEAD_LOAD_PATTERN, DEAD_LOAD_TIME_SERIES)
        ops.reset()
        ops.setTime(0.0)

    deck_kn = _apply_deck_and_surfacing(ops, model)
    girders_kn = _apply_girder_weight(ops, model)
    bracing_kn = _apply_bracing_weight(ops, model)

    totals = DeadLoadTotals(
        deck_and_surfacing_kn=deck_kn, girders_kn=girders_kn, bracing_kn=bracing_kn
    )
    _report_dead_loads(model, totals)
    return totals


def _apply_deck_and_surfacing(ops, model: BridgeModel) -> float:
    """Lumps the slab and everything lying on it onto the deck nodes."""
    mesh = model.mesh
    bridge = model.bridge

    slab_kpa = bridge.concrete.unit_weight_kn_m3 * bridge.deck.thickness_m
    applied_kn = 0.0

    for i in range(mesh.stations_along_span):
        along_span_m = _tributary_length_m(mesh.length_mesh_m, i)

        for j in range(mesh.stations_across_width):
            across_width_m = _tributary_length_m(mesh.width_mesh_m, j)
            area_m2 = along_span_m * across_width_m
            z_m = float(mesh.width_mesh_m[j])

            load_kn = (slab_kpa + _surfacing_pressure_at(model, z_m)) * area_m2
            ops.load(model.deck_nodes[(i, j)], 0.0, -load_kn, 0.0, 0.0, 0.0, 0.0)
            applied_kn += load_kn

    return applied_kn


def _surfacing_pressure_at(model: BridgeModel, z_m: float) -> float:
    """Returns what is lying on the slab at this position across the deck.

    Read straight off the cross-section: whichever strip this position falls in
    decides what is on top of it. A carriageway carries the wearing course, a
    footpath its own surfacing, and so on.
    """
    bridge = model.bridge
    added = bridge.added_dead_loads

    for strip in bridge.cross_section.strips:
        if not (strip.z_from_m <= z_m <= strip.z_to_m):
            continue

        if strip.carries_traffic:
            return bridge.wearing_course.pressure_kpa
        if strip.carries_pedestrians:
            return added.footpath.pressure_kpa
        if strip.name.startswith("kerb"):
            return added.kerb.pressure_kpa
        if strip.name.startswith("median"):
            return added.median.pressure_kpa
        return 0.0

    return 0.0


def _apply_girder_weight(ops, model: BridgeModel) -> float:
    """Spreads each girder's own weight along its length.

    For a 3D beam, a uniform element load is given in the element's *local* axes.
    With the girder's local y axis on global Y, the vertical component is the
    first of the two. Putting the weight in the second component instead points
    it sideways, which once took 18 per cent of the dead load out of the vertical
    load path without any error being raised.
    """
    weight_kn_per_m = model.bridge.steel.unit_weight_kn_m3 * model.girder.area_m2

    for element in model.girder_elements.values():
        ops.eleLoad("-ele", element, "-type", "-beamUniform", -weight_kn_per_m, 0.0)

    return weight_kn_per_m * model.bridge.span_m * model.bridge.girders.count


def _apply_bracing_weight(ops, model: BridgeModel) -> float:
    """Hangs half of each brace's weight on each of the nodes it spans between."""
    unit_weight_kn_m3 = model.bridge.steel.unit_weight_kn_m3
    area_m2 = model.bridge.bracing.area_m2
    applied_kn = 0.0

    for element in model.brace_elements.values():
        start, end = ops.eleNodes(element)
        length_m = float(
            np.linalg.norm(np.array(ops.nodeCoord(end)) - np.array(ops.nodeCoord(start)))
        )
        weight_kn = area_m2 * unit_weight_kn_m3 * length_m

        ops.load(start, 0.0, -weight_kn / 2, 0.0, 0.0, 0.0, 0.0)
        ops.load(end, 0.0, -weight_kn / 2, 0.0, 0.0, 0.0, 0.0)
        applied_kn += weight_kn

    return applied_kn


def _tributary_length_m(stations_m: np.ndarray, station: int) -> float:
    """Returns how much length a station is responsible for.

    Halfway to its neighbour on each side; at the ends, halfway to the only
    neighbour there is.
    """
    if station == 0:
        return float(stations_m[1] - stations_m[0]) / 2
    if station == len(stations_m) - 1:
        return float(stations_m[-1] - stations_m[-2]) / 2
    return float(stations_m[station + 1] - stations_m[station - 1]) / 2


def _report_dead_loads(model: BridgeModel, totals: DeadLoadTotals) -> None:
    bridge = model.bridge
    added = bridge.added_dead_loads
    slab_kpa = bridge.concrete.unit_weight_kn_m3 * bridge.deck.thickness_m
    girder_kn_per_m = bridge.steel.unit_weight_kn_m3 * model.girder.area_m2

    report(
        "DEAD LOADS APPLIED",
        {
            "Deck slab": f"{slab_kpa:8.3f} kN/m2",
            "Wearing course": f"{bridge.wearing_course.pressure_kpa:8.3f} kN/m2",
            "Footpath": f"{added.footpath.pressure_kpa:8.3f} kN/m2",
            "Kerb": f"{added.kerb.pressure_kpa:8.3f} kN/m2",
            "Median": f"{added.median.pressure_kpa:8.3f} kN/m2",
            "Girder self weight": f"{girder_kn_per_m:8.3f} kN/m",
            "Deck and surfacing": f"{totals.deck_and_surfacing_kn:8.1f} kN",
            "Girders": f"{totals.girders_kn:8.1f} kN",
            "Bracing": f"{totals.bracing_kn:8.1f} kN",
            "Total dead load": f"{totals.total_kn:8.1f} kN",
        },
    )


def _opensees():
    from ..influence_surfaces.opensees_backend import _opensees as load

    return load()
