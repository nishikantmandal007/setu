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
        "ULS-1": {"dead": 1.35, "live": 1.50},
        "ULS-2": {"dead": 1.35, "live": 1.50, "wind": 1.15},
        "ULS-3": {"dead": 1.35, "live": 1.50, "temperature": 0.90},
        "ULS-4": {"dead": 1.35, "temperature": 1.50},
        "ULS-5": {"dead": 1.35, "temperature": 1.50, "wind": 1.15},
        "ULS-6": {"dead": 1.00, "wind": 1.50},
        "ULS-7": {"dead": 1.35, "live": 1.50, "braking": 1.50},
        "ULS-8": {"dead": 1.35, "seismic": 1.50},
        "ULS-9": {"dead": 1.35, "live": 0.20, "seismic": 1.50},
        "ULS-10": {"dead": 1.00, "live": 1.00},
    }


def irc6_sls_recipes():
    return {
        "SLS-rare-1": {"dead": 1.00, "live": 1.00},
        "SLS-rare-2": {"dead": 1.00, "live": 1.00, "wind": 0.60},
        "SLS-rare-3": {"dead": 1.00, "live": 1.00, "temperature": 0.60},
        "SLS-rare-4": {"dead": 1.00, "temperature": 1.00},
        "SLS-rare-5": {"dead": 1.00, "wind": 1.00},
        "SLS-freq-1": {"dead": 1.00, "live": 0.75},
        "SLS-freq-2": {"dead": 1.00, "live": 0.75, "temperature": 0.50},
        "SLS-qp-1": {"dead": 1.00},
        "SLS-qp-2": {"dead": 1.00, "temperature": 0.50},
    }


def irc6_fatigue_recipe():
    return {"fatigue": {"dead": 1.00, "fatigue": 1.00}}


def irc6_construction_recipe():
    return {"construction": {"dead": 1.00, "construction": 1.20}}
