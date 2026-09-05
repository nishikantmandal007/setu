import numpy as np


class Envelope:

    def __init__(self, stations_m, moment_kn_m, shear_kn, deflection_m, governing_case):
        self.stations_m = np.asarray(stations_m, float)
        self.moment_kn_m = np.asarray(moment_kn_m, float)
        self.shear_kn = np.asarray(shear_kn, float)
        self.deflection_m = np.asarray(deflection_m, float)
        self.governing_case = list(governing_case)


def envelope(case_results, adverse="maximum"):
    pick = np.argmax if adverse == "maximum" else np.argmin
    names = list(case_results.keys())
    forces_list = list(case_results.values())
    stations_m = forces_list[0].stations_m
    n = len(stations_m)
    moment_stack = np.array([f.moment_kn_m for f in forces_list])
    shear_stack = np.array([f.shear_kn for f in forces_list])
    moment_idx = pick(moment_stack, axis=0)
    moment_kn_m = moment_stack[moment_idx, np.arange(n)]
    shear_kn = shear_stack[moment_idx, np.arange(n)]
    governing_case = [names[i] for i in moment_idx]
    deflection_m = np.zeros(n)
    return Envelope(stations_m, moment_kn_m, shear_kn, deflection_m, governing_case)


def envelope_with_deflections(case_results, deflection_results, adverse="maximum"):
    pick = np.argmax if adverse == "maximum" else np.argmin
    names = list(case_results.keys())
    forces_list = list(case_results.values())
    stations_m = forces_list[0].stations_m
    n = len(stations_m)
    moment_stack = np.array([f.moment_kn_m for f in forces_list])
    shear_stack = np.array([f.shear_kn for f in forces_list])
    defl_stack = np.array([deflection_results[name].vertical_m for name in names])
    moment_idx = pick(moment_stack, axis=0)
    moment_kn_m = moment_stack[moment_idx, np.arange(n)]
    shear_kn = shear_stack[moment_idx, np.arange(n)]
    deflection_m = defl_stack[moment_idx, np.arange(n)]
    governing_case = [names[i] for i in moment_idx]
    return Envelope(stations_m, moment_kn_m, shear_kn, deflection_m, governing_case)
