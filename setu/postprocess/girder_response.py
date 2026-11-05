import numpy as np
from setu.solver import backend
from setu.postprocess.result_dataset import merge_datasets, result_dataset
from setu.builder.assembly import BEARING_VERTICAL_STIFFNESS_KN_PER_M, VERTICAL_DOF, build_bridge_model
from setu.loads.dead_loads import steel_self_weight_load, superimposed_dead_load, surfacing_load, wet_slab_load
from setu.utils.constants import (
    DEAD,
    SURFACING,
    END_I_FORCE_TO_INTERNAL_FORCE,
    LOAD_CASE_PATTERN_BASE,
    LONG_TERM,
    MY_I,
    MY_J,
    MZ_I,
    MZ_J,
    N_I,
    N_J,
    T_I,
    T_J,
    VY_I,
    VZ_I,
    VZ_J,
    VY_J,
)




class GirderForces:

    # one girder's internal forces and downward deflection along it, and the reactions on its bearings at x = 0 and at the far end
    def __init__(self, stations_m, moment_kn_m, shear_kn, torsion_kn_m, axial_kn, composite_lever_arm_m, deflection_m, reaction_kn, end_reaction_kn, *, weak_axis_shear_kn=None, weak_axis_moment_kn_m=None, displacements_m=None):
        self.stations_m = np.asarray(stations_m, float)
        self.moment_kn_m = np.asarray(moment_kn_m, float)
        self.shear_kn = np.asarray(shear_kn, float)
        self.torsion_kn_m = np.asarray(torsion_kn_m, float)
        self.axial_kn = np.asarray(axial_kn, float)
        self.composite_lever_arm_m = composite_lever_arm_m
        self.deflection_m = np.asarray(deflection_m, float)
        self.reaction_kn = float(reaction_kn)
        self.end_reaction_kn = float(end_reaction_kn)
        # for full result plots: shear and moment about the other axis, and the six displacements of each station
        self.weak_axis_shear_kn = None if weak_axis_shear_kn is None else np.asarray(weak_axis_shear_kn, float)
        self.weak_axis_moment_kn_m = None if weak_axis_moment_kn_m is None else np.asarray(weak_axis_moment_kn_m, float)
        self.displacements_m = None if displacements_m is None else np.asarray(displacements_m, float)

    # steel moment plus the axial couple about the slab
    @property
    def composite_moment_kn_m(self):
        return self.moment_kn_m + self.composite_lever_arm_m * self.axial_kn


# read one girder's forces, deflection and bearing reaction off the solved model
def girder_forces(model, girder_index):
    n_stations = model.mesh.stations_along_span
    n_elements = n_stations - 1
    stations_m = np.array(model.mesh.length_mesh_m, float)
    moment = np.zeros(n_stations)
    shear = np.zeros(n_stations)
    torsion = np.zeros(n_stations)
    axial = np.zeros(n_stations)
    weak_shear = np.zeros(n_stations)
    weak_moment = np.zeros(n_stations)
    for e in range(n_elements):
        f = backend.element_local_forces(model.girder_elements[girder_index, e])
        axial[e] = END_I_FORCE_TO_INTERNAL_FORCE * f[N_I]
        shear[e] = END_I_FORCE_TO_INTERNAL_FORCE * f[VY_I]
        torsion[e] = END_I_FORCE_TO_INTERNAL_FORCE * f[T_I]
        moment[e] = END_I_FORCE_TO_INTERNAL_FORCE * f[MZ_I]
        weak_shear[e] = END_I_FORCE_TO_INTERNAL_FORCE * f[VZ_I]
        weak_moment[e] = END_I_FORCE_TO_INTERNAL_FORCE * f[MY_I]
        if e == n_elements - 1:
            axial[e + 1] = f[N_J]
            shear[e + 1] = f[VY_J]
            torsion[e + 1] = f[T_J]
            moment[e + 1] = f[MZ_J]
            weak_shear[e + 1] = f[VZ_J]
            weak_moment[e + 1] = f[MY_J]
    deflection_m = [-backend.node_displacement(model.girder_nodes[girder_index, i], VERTICAL_DOF) for i in range(n_stations)]
    reaction_kn = -BEARING_VERTICAL_STIFFNESS_KN_PER_M * backend.node_displacement(model.bearings[girder_index, 0], VERTICAL_DOF)
    end_reaction_kn = -BEARING_VERTICAL_STIFFNESS_KN_PER_M * backend.node_displacement(model.bearings[girder_index, n_stations - 1], VERTICAL_DOF)
    return GirderForces(stations_m, moment, shear, torsion, axial, model.composite_lever_arm_m(girder_index), deflection_m, reaction_kn,
                        end_reaction_kn=end_reaction_kn, weak_axis_shear_kn=weak_shear, weak_axis_moment_kn_m=weak_moment,
                        displacements_m=[backend.node_displacements(model.girder_nodes[girder_index, i]) for i in range(n_stations)])

# Upward vertical spring reactions, keyed by (girder index, bearing station index).
def bearing_reactions(model):
    return {key: -BEARING_VERTICAL_STIFFNESS_KN_PER_M * backend.node_displacement(node, VERTICAL_DOF)
            for key, node in model.bearings.items()}


# Axial truss force in kN, tension positive, keyed by (girder pair index, station index, role).
def brace_forces(model):
    return {key: backend.truss_axial_force(element) for key, element in model.brace_elements.items()}


# every brace member's axial force (kN, tension positive) in the model's brace order, read off the load state solved now
def brace_force_array(model):
    return np.array([backend.truss_axial_force(element) for element in model.brace_elements.values()])


# solve one load case and read every girder's forces
def analyze_load_case(model, load_case, pattern_tag=None, *, on_solved=None):
    tag = pattern_tag if pattern_tag is not None else LOAD_CASE_PATTERN_BASE
    with backend.solved(load_case.nodal_loads, load_case.element_loads, pattern=tag):
        forces = {k: girder_forces(model, k) for k in range(model.bridge.girders.count)}
        if on_solved is not None:
            on_solved(forces)
        return forces


# a load case's girder forces, and its brace members' forces read off the same solve
def analyze_with_braces(model, load_case):
    braces = []
    forces = analyze_load_case(model, load_case, on_solved=lambda _: braces.append(brace_force_array(model)))
    return forces, braces[0]


STEEL_SELF_WEIGHT = "steel self weight"
WET_SLAB = "wet slab"
SUPERIMPOSED = "superimposed"
SURFACING_STAGE = "surfacing"
STAGE_IS_FACTORED_AS = {STEEL_SELF_WEIGHT: DEAD, WET_SLAB: DEAD, SUPERIMPOSED: DEAD, SURFACING_STAGE: SURFACING}


class DeadLoadForces:
    # girder and brace forces from each dead load stage, their total, and every stage's element forces and displacements for OsdagBridge
    def __init__(self, stages, dataset, brace_stages):
        self.stages = stages
        self.dataset = dataset
        self.brace_stages = brace_stages
        self.total = self.factored({DEAD: 1.0, SURFACING: 1.0})

    # stages added up, each with its dead or surfacing factor
    def factored(self, factors):
        girders = next(iter(self.stages.values())).keys()
        return {girder: sum_of(scaled(forces[girder], factors[STAGE_IS_FACTORED_AS[name]]) for name, forces in self.stages.items()) for girder in girders}


OPTIONAL_RESULTS = ("weak_axis_shear_kn", "weak_axis_moment_kn_m", "displacements_m")


# girder forces times a factor
def scaled(forces, factor):
    optional = {name: None if getattr(forces, name) is None else factor * getattr(forces, name) for name in OPTIONAL_RESULTS}
    return GirderForces(forces.stations_m, factor * forces.moment_kn_m, factor * forces.shear_kn, factor * forces.torsion_kn_m, factor * forces.axial_kn,
                        forces.composite_lever_arm_m, factor * forces.deflection_m, factor * forces.reaction_kn, factor * forces.end_reaction_kn, **optional)


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
        sum(forces.end_reaction_kn for forces in girder_forces),
        **{name: None if getattr(first, name) is None else sum(getattr(forces, name) for forces in girder_forces) for name in OPTIONAL_RESULTS},
    )


# un-propped dead load: girders and bracing, then the wet slab, on the bare steel; then SIDL and surfacing on the long-term composite deck
def dead_load_forces(bridge):
    stages = {}
    brace_stages = {}
    datasets = []
    steel = build_bridge_model(bridge, composite=False)
    for name, load_case in ((STEEL_SELF_WEIGHT, steel_self_weight_load(steel)), (WET_SLAB, wet_slab_load(steel))):
        stages[name] = analyze_load_case(steel, load_case)
        brace_stages[name] = brace_forces(steel)
        datasets.append(result_dataset(steel, f"dead, {name}"))
    composite = build_bridge_model(bridge, load_duration=LONG_TERM)
    for name, load_case in ((SUPERIMPOSED, superimposed_dead_load(composite)), (SURFACING_STAGE, surfacing_load(composite))):
        stages[name] = analyze_load_case(composite, load_case)
        brace_stages[name] = brace_forces(composite)
        datasets.append(result_dataset(composite, f"dead, {name}"))
    return DeadLoadForces(stages, merge_datasets(datasets), brace_stages=brace_stages)
