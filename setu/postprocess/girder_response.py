import numpy as np
from setu.errors import OtherLoadsStillActiveError
from setu.loads.load_cases import LOAD_CASE_PATTERN_BASE, apply_load_case


N_I = 0
VY_I = 1
T_I = 3
MZ_I = 5
N_J = 6
VY_J = 7
T_J = 9
MZ_J = 11


class GirderForces:

    def __init__(self, stations_m, moment_kn_m, shear_kn, torsion_kn_m, axial_kn):
        self.stations_m = np.asarray(stations_m, float)
        self.moment_kn_m = np.asarray(moment_kn_m, float)
        self.shear_kn = np.asarray(shear_kn, float)
        self.torsion_kn_m = np.asarray(torsion_kn_m, float)
        self.axial_kn = np.asarray(axial_kn, float)


class GirderDeflections:

    def __init__(self, stations_m, vertical_m):
        self.stations_m = np.asarray(stations_m, float)
        self.vertical_m = np.asarray(vertical_m, float)


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
        axial[e] = -f[N_I]
        shear[e] = -f[VY_I]
        torsion[e] = -f[T_I]
        moment[e] = -f[MZ_I]
        if e == n_elements - 1:
            axial[e + 1] = f[N_J]
            shear[e + 1] = f[VY_J]
            torsion[e + 1] = f[T_J]
            moment[e + 1] = f[MZ_J]
    return GirderForces(stations_m, moment, shear, torsion, axial)


def girder_deflections(model, girder_index, ops):
    n_stations = model.mesh.stations_along_span
    stations_m = np.array(model.mesh.length_mesh_m, float)
    vertical = np.zeros(n_stations)
    for i in range(n_stations):
        node = model.girder_nodes[girder_index, i]
        vertical[i] = ops.nodeDisp(node, 2)
    return GirderDeflections(stations_m, vertical)


def reactions(model, ops):
    ops.reactions()
    n_stations = model.mesh.stations_along_span
    result = {}
    for k in range(model.bridge.girders.count):
        for i in [0, n_stations - 1]:
            node = model.girder_nodes[k, i]
            result[node] = np.array(ops.nodeReaction(node))
    return result


def analyze_load_case(model, load_case, ops, pattern_tag=None):
    tag = pattern_tag if pattern_tag is not None else LOAD_CASE_PATTERN_BASE
    already_loading = ops.getPatterns()
    if already_loading:
        raise OtherLoadsStillActiveError(f"load patterns {already_loading} are still on the model, so they would be added into {load_case.name!r}. Remove them, or combine them into this load case, first.")
    ops.reset()
    ops.setTime(0.0)
    apply_load_case(load_case, ops, pattern_tag=tag)
    ops.system("UmfPack")
    ops.numberer("RCM")
    ops.constraints("Transformation")
    ops.integrator("LoadControl", 1.0)
    ops.algorithm("Linear")
    ops.analysis("Static")
    ops.analyze(1)
    results = {}
    for k in range(model.bridge.girders.count):
        results[k] = girder_forces(model, k, ops)
    ops.remove("loadPattern", tag)
    ops.remove("timeSeries", tag)
    ops.wipeAnalysis()
    return results
