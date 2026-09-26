import numpy as np
from setu.errors import OtherLoadsStillActiveError
from setu.solver.backend import configure_linear_static
from setu.loads.load_cases import apply_load_case
from setu.helpers import import_opensees
from setu.loads.dead_loads import construction_stage_load, superimposed_dead_load, surfacing_load
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

    # internal forces along one girder
    def __init__(self, stations_m, moment_kn_m, shear_kn, torsion_kn_m, axial_kn, composite_lever_arm_m=0.0):
        self.stations_m = np.asarray(stations_m, float)
        self.moment_kn_m = np.asarray(moment_kn_m, float)
        self.shear_kn = np.asarray(shear_kn, float)
        self.torsion_kn_m = np.asarray(torsion_kn_m, float)
        self.axial_kn = np.asarray(axial_kn, float)
        self.composite_lever_arm_m = composite_lever_arm_m

    # steel moment plus the axial couple about the slab
    @property
    def composite_moment_kn_m(self):
        return self.moment_kn_m + self.composite_lever_arm_m * self.axial_kn


class GirderDeflections:

    # vertical deflection along one girder
    def __init__(self, stations_m, vertical_m):
        self.stations_m = np.asarray(stations_m, float)
        self.vertical_m = np.asarray(vertical_m, float)


# read one girder's internal forces off the solved model
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
    return GirderForces(stations_m, moment, shear, torsion, axial, composite_lever_arm_m=model.composite_lever_arm_m())


# read one girder's deflections off the solved model
def girder_deflections(model, girder_index, ops):
    n_stations = model.mesh.stations_along_span
    stations_m = np.array(model.mesh.length_mesh_m, float)
    vertical = np.zeros(n_stations)
    for i in range(n_stations):
        node = model.girder_nodes[girder_index, i]
        vertical[i] = ops.nodeDisp(node, 2)
    return GirderDeflections(stations_m, vertical)


# support reactions at both ends of every girder
def reactions(model, ops):
    ops.reactions()
    n_stations = model.mesh.stations_along_span
    result = {}
    for k in range(model.bridge.girders.count):
        for i in [0, n_stations - 1]:
            node = model.girder_nodes[k, i]
            result[node] = np.array(ops.nodeReaction(node))
    return result


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


STAGE_IS_FACTORED_AS = {"construction": DEAD, "superimposed": DEAD, "surfacing": SURFACING}


class DeadLoadForces:
    # girder forces from each dead load stage, and their total
    def __init__(self, stages):
        self.stages = stages
        self.total = self.factored({DEAD: 1.0, SURFACING: 1.0})

    # stages added up, each with its dead or surfacing factor
    def factored(self, factors):
        girders = next(iter(self.stages.values())).keys()
        return {girder: sum_of(scaled(forces[girder], factors[STAGE_IS_FACTORED_AS[name]]) for name, forces in self.stages.items()) for girder in girders}


# girder forces times a factor
def scaled(forces, factor):
    return GirderForces(forces.stations_m, factor * forces.moment_kn_m, factor * forces.shear_kn, factor * forces.torsion_kn_m, factor * forces.axial_kn, composite_lever_arm_m=forces.composite_lever_arm_m)


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
        composite_lever_arm_m=first.composite_lever_arm_m,
    )


# un-propped dead load: steel stage, then long term composite SIDL and surfacing
def dead_load_forces(bridge, ops=None):
    from setu.builder.assembly import build_bridge_model
    ops = import_opensees() if ops is None else ops
    steel = build_bridge_model(bridge, ops, composite=False)
    construction = analyze_load_case(steel, construction_stage_load(steel, ops), ops)
    composite = build_bridge_model(bridge, ops, load_duration=LONG_TERM)
    superimposed = analyze_load_case(composite, superimposed_dead_load(composite), ops)
    surfacing = analyze_load_case(composite, surfacing_load(composite), ops)
    return DeadLoadForces({"construction": construction, "superimposed": superimposed, "surfacing": surfacing})
