from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..deck_cross_section import (
    CRASH_BARRIER_PREFIX,
    KERB_PREFIX,
    MEDIAN_PREFIX,
)
from ..reporting import report
from .build_model import BridgeModel
from .model_tags import SolverCommands

DEAD_LOAD_PATTERN = 1
DEAD_LOAD_TIME_SERIES = 1

START_OF_THE_LOAD_STEP = 0.0
NOTHING_ON_TOP_KPA = 0.0


@dataclass(frozen=True)
class DeadLoadTotals:
    deck_and_surfacing_kn: float
    girders_kn: float
    bracing_kn: float

    @property
    def total_kn(self) -> float:
        return self.deck_and_surfacing_kn + self.girders_kn + self.bracing_kn


def downward_force(load_kn: float) -> tuple[float, ...]:
    force_x, force_y, force_z = 0.0, -load_kn, 0.0
    moment_x, moment_y, moment_z = 0.0, 0.0, 0.0
    return (force_x, force_y, force_z, moment_x, moment_y, moment_z)


def apply_dead_loads(
    model: BridgeModel, ops: SolverCommands | None = None, new_pattern: bool = True
) -> DeadLoadTotals:
    ops = load_opensees() if ops is None else ops

    if new_pattern:
        start_a_fresh_load_case(ops)

    deck_kn = apply_deck_and_surfacing(ops, model)
    girders_kn = apply_girder_weight(ops, model)
    bracing_kn = apply_bracing_weight(ops, model)

    totals = DeadLoadTotals(
        deck_and_surfacing_kn=deck_kn, girders_kn=girders_kn, bracing_kn=bracing_kn
    )
    report_dead_loads(model, totals)
    return totals


def start_a_fresh_load_case(ops: SolverCommands) -> None:
    # A Linear time series scales its load with the pseudo-time, so a model that has been
    # analysed once already would otherwise pick up twice its own weight.
    ops.remove("loadPattern", DEAD_LOAD_PATTERN)
    ops.remove("timeSeries", DEAD_LOAD_TIME_SERIES)
    ops.timeSeries("Linear", DEAD_LOAD_TIME_SERIES)
    ops.pattern("Plain", DEAD_LOAD_PATTERN, DEAD_LOAD_TIME_SERIES)
    ops.reset()
    ops.setTime(START_OF_THE_LOAD_STEP)


def apply_deck_and_surfacing(ops: SolverCommands, model: BridgeModel) -> float:
    # Each node takes the load standing on the patch of deck nearest to it.
    mesh = model.mesh
    bridge = model.bridge

    slab_kpa = bridge.concrete.unit_weight_kn_m3 * bridge.deck.thickness_m
    applied_kn = 0.0

    for i in range(mesh.stations_along_span):
        along_span_m = tributary_length_m(mesh.length_mesh_m, i)

        for j in range(mesh.stations_across_width):
            across_width_m = tributary_length_m(mesh.width_mesh_m, j)
            area_m2 = along_span_m * across_width_m
            z_m = float(mesh.width_mesh_m[j])

            load_kn = (slab_kpa + surfacing_pressure_at(model, z_m)) * area_m2
            ops.load(model.deck_nodes[(i, j)], *downward_force(load_kn))
            applied_kn += load_kn

    return applied_kn


def surfacing_pressure_at(model: BridgeModel, z_m: float) -> float:
    # A strip whose name matches no prefix carries nothing, so a misspelt name loads
    # nothing and says nothing.
    bridge = model.bridge
    added = bridge.added_dead_loads

    for strip in bridge.cross_section.strips:
        if not (strip.z_from_m <= z_m <= strip.z_to_m):
            continue

        if strip.carries_traffic:
            return bridge.wearing_course.pressure_kpa
        if strip.carries_pedestrians:
            return added.footpath.pressure_kpa
        if strip.name.startswith(KERB_PREFIX):
            return added.kerb.pressure_kpa
        if strip.name.startswith(MEDIAN_PREFIX):
            return added.median.pressure_kpa
        if strip.name.startswith(CRASH_BARRIER_PREFIX):
            return added.crash_barrier.pressure_kpa
        return NOTHING_ON_TOP_KPA

    return NOTHING_ON_TOP_KPA


def apply_girder_weight(ops: SolverCommands, model: BridgeModel) -> float:
    weight_kn_per_m = model.bridge.steel.unit_weight_kn_m3 * model.girder.area_m2

    # A beamUniform load is given in the element's local axes, and the girder's local y
    # axis is on global Y. Swapping these two points the weight sideways.
    down_the_local_y_axis = -weight_kn_per_m
    along_the_local_z_axis = 0.0

    for element in model.girder_elements.values():
        ops.eleLoad(
            "-ele",
            element,
            "-type",
            "-beamUniform",
            down_the_local_y_axis,
            along_the_local_z_axis,
        )

    return weight_kn_per_m * model.bridge.span_m * model.bridge.girders.count


def apply_bracing_weight(ops: SolverCommands, model: BridgeModel) -> float:
    unit_weight_kn_m3 = model.bridge.steel.unit_weight_kn_m3
    area_m2 = model.bridge.bracing.area_m2
    applied_kn = 0.0

    for element in model.brace_elements.values():
        start, end = ops.eleNodes(element)
        start_m = np.array(ops.nodeCoord(start))
        end_m = np.array(ops.nodeCoord(end))

        length_m = float(np.linalg.norm(end_m - start_m))
        weight_kn = area_m2 * unit_weight_kn_m3 * length_m
        half_of_it_kn = weight_kn / 2

        ops.load(start, *downward_force(half_of_it_kn))
        ops.load(end, *downward_force(half_of_it_kn))
        applied_kn += weight_kn

    return applied_kn


def tributary_length_m(stations_m: np.ndarray, station: int) -> float:
    # Halfway to the neighbour on each side, or at the ends, halfway to the only one.
    first_station = 0
    last_station = len(stations_m) - 1

    if station == first_station:
        return float(stations_m[1] - stations_m[0]) / 2
    if station == last_station:
        return float(stations_m[-1] - stations_m[-2]) / 2
    return float(stations_m[station + 1] - stations_m[station - 1]) / 2


def report_dead_loads(model: BridgeModel, totals: DeadLoadTotals) -> None:
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


def load_opensees() -> SolverCommands:
    from ..influence_surfaces.opensees_backend import import_opensees as load

    return load()
