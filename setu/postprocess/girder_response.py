import numpy as np
from setu.errors import OtherLoadsStillActiveError
from setu.solver.backend import configure_linear_static
from setu.loads.load_cases import apply_load_case
from setu.helpers import import_opensees
from setu.postprocess.result_dataset import merge_datasets, result_dataset
from setu.builder.assembly import BEARING_VERTICAL_STIFFNESS_KN_PER_M, VERTICAL_DOF, build_bridge_model
from setu.loads.dead_loads import steel_self_weight_load, superimposed_dead_load, surfacing_load, wet_slab_load
from setu.utils.constants import (
    DEAD,
    SURFACING,
    END_I_FORCE_TO_INTERNAL_FORCE,
    LOAD_CASE_PATTERN_BASE,
    LONG_TERM,
    MZ_I,
    MZ_J,
    N_I,
    N_J,
    T_I,
    T_J,
    VY_I,
    VY_J,
)




class GirderForces:

    # one girder's internal forces and downward deflection along it, and the reaction on its bearing at x = 0
    def __init__(self, stations_m, moment_kn_m, shear_kn, torsion_kn_m, axial_kn, composite_lever_arm_m, deflection_m, reaction_kn):
        self.stations_m = np.asarray(stations_m, float)
        self.moment_kn_m = np.asarray(moment_kn_m, float)
        self.shear_kn = np.asarray(shear_kn, float)
        self.torsion_kn_m = np.asarray(torsion_kn_m, float)
        self.axial_kn = np.asarray(axial_kn, float)
        self.composite_lever_arm_m = composite_lever_arm_m
        self.deflection_m = np.asarray(deflection_m, float)
        self.reaction_kn = float(reaction_kn)

    # steel moment plus the axial couple about the slab
    @property
    def composite_moment_kn_m(self):
        return self.moment_kn_m + self.composite_lever_arm_m * self.axial_kn


# read one girder's forces, deflection and bearing reaction off the solved model
def girder_forces(model, girder_index, ops):
    n_stations = model.mesh.stations_along_span
    n_elements = n_stations - 1
    stations_m = np.array(model.mesh.length_mesh_m, float)
    moment = np.zeros(n_stations)
    shear = np.zeros(n_stations)
    torsion = np.zeros(n_stations)
    axial = np.zeros(n_stations)
    for e in range(n_elements):
        f = ops.eleResponse(model.girder_elements[girder_index, e], "localForce")
        axial[e] = END_I_FORCE_TO_INTERNAL_FORCE * f[N_I]
        shear[e] = END_I_FORCE_TO_INTERNAL_FORCE * f[VY_I]
        torsion[e] = END_I_FORCE_TO_INTERNAL_FORCE * f[T_I]
        moment[e] = END_I_FORCE_TO_INTERNAL_FORCE * f[MZ_I]
        if e == n_elements - 1:
            axial[e + 1] = f[N_J]
            shear[e + 1] = f[VY_J]
            torsion[e + 1] = f[T_J]
            moment[e + 1] = f[MZ_J]
    deflection_m = [-ops.nodeDisp(model.girder_nodes[girder_index, i], VERTICAL_DOF) for i in range(n_stations)]
    reaction_kn = -BEARING_VERTICAL_STIFFNESS_KN_PER_M * ops.nodeDisp(model.bearings[girder_index, 0], VERTICAL_DOF)
    return GirderForces(stations_m, moment, shear, torsion, axial, model.composite_lever_arm_m(), deflection_m, reaction_kn)


# solve one load case and read every girder's forces
def analyze_load_case(model, load_case, ops, pattern_tag=None):
    tag = pattern_tag if pattern_tag is not None else LOAD_CASE_PATTERN_BASE
    already_loading = ops.getPatterns()
    if already_loading:
        raise OtherLoadsStillActiveError(f"load patterns {already_loading} are still on the model, so they would be added into {load_case.name!r}. Remove them, or combine them into this load case, first.")
    ops.reset()
    ops.setTime(0.0)
    apply_load_case(load_case, ops, pattern_tag=tag)
    if not getattr(model, "analysis_is_set_up", False):
        configure_linear_static(ops)
        model.analysis_is_set_up = True
    ops.analyze(1)
    results = {}
    for k in range(model.bridge.girders.count):
        results[k] = girder_forces(model, k, ops)
    ops.remove("loadPattern", tag)
    ops.remove("timeSeries", tag)
    return results


STEEL_SELF_WEIGHT = "steel self weight"
WET_SLAB = "wet slab"
SUPERIMPOSED = "superimposed"
SURFACING_STAGE = "surfacing"
STAGE_IS_FACTORED_AS = {STEEL_SELF_WEIGHT: DEAD, WET_SLAB: DEAD, SUPERIMPOSED: DEAD, SURFACING_STAGE: SURFACING}


class DeadLoadForces:
    # girder forces from each dead load stage, their total, and every stage's element forces and displacements for OsdagBridge
    def __init__(self, stages, dataset):
        self.stages = stages
        self.dataset = dataset
        self.total = self.factored({DEAD: 1.0, SURFACING: 1.0})

    # stages added up, each with its dead or surfacing factor
    def factored(self, factors):
        girders = next(iter(self.stages.values())).keys()
        return {girder: sum_of(scaled(forces[girder], factors[STAGE_IS_FACTORED_AS[name]]) for name, forces in self.stages.items()) for girder in girders}


# girder forces times a factor
def scaled(forces, factor):
    return GirderForces(forces.stations_m, factor * forces.moment_kn_m, factor * forces.shear_kn, factor * forces.torsion_kn_m, factor * forces.axial_kn,
                        forces.composite_lever_arm_m, factor * forces.deflection_m, factor * forces.reaction_kn)


# girder forces added up
def sum_of(girder_forces):
    girder_forces = list(girder_forces)
    first = girder_forces[0]
    return GirderForces(
        first.stations_m,
        sum(forces.moment_kn_m for forces in girder_forces),
        sum(forces.shear_kn for forces in girder_forces),
        sum(forces.torsion_kn_m for forces in girder_forces),
        sum(forces.axial_kn for forces in girder_forces),
        first.composite_lever_arm_m,
        sum(forces.deflection_m for forces in girder_forces),
        sum(forces.reaction_kn for forces in girder_forces),
    )


# un-propped dead load: girders and bracing, then the wet slab, on the bare steel; then SIDL and surfacing on the long-term composite deck
def dead_load_forces(bridge, ops=None):
    ops = import_opensees() if ops is None else ops
    stages = {}
    datasets = []
    steel = build_bridge_model(bridge, ops, composite=False)
    for name, load_case in ((STEEL_SELF_WEIGHT, steel_self_weight_load(steel, ops)), (WET_SLAB, wet_slab_load(steel))):
        stages[name] = analyze_load_case(steel, load_case, ops)
        datasets.append(result_dataset(steel, ops, f"dead, {name}"))
    composite = build_bridge_model(bridge, ops, load_duration=LONG_TERM)
    for name, load_case in ((SUPERIMPOSED, superimposed_dead_load(composite)), (SURFACING_STAGE, surfacing_load(composite))):
        stages[name] = analyze_load_case(composite, load_case, ops)
        datasets.append(result_dataset(composite, ops, f"dead, {name}"))
    return DeadLoadForces(stages, merge_datasets(datasets))
