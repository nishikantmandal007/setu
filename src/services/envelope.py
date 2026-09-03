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


def irc6_uls_recipes():
    return {
        "ULS-1: 1.35DL + 1.50LL": {"dead": 1.35, "live": 1.50},
        "ULS-2: 1.35DL + 1.50LL + 1.15WL": {"dead": 1.35, "live": 1.50, "wind": 1.15},
        "ULS-3: 1.35DL + 1.50TL": {"dead": 1.35, "temperature": 1.50},
        "ULS-4: 1.00DL + 1.50WL": {"dead": 1.00, "wind": 1.50},
    }


def irc6_sls_recipes():
    return {
        "SLS-1: 1.00DL + 1.00LL": {"dead": 1.00, "live": 1.00},
        "SLS-2: 1.00DL + 0.75LL + 1.00TL": {"dead": 1.00, "live": 0.75, "temperature": 1.00},
        "SLS-3: 1.00DL + 1.00WL": {"dead": 1.00, "wind": 1.00},
    }
