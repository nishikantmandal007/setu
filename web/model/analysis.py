import openseespy.opensees as ops

from setu import analyze_load_case, build_bridge_model, girder_design_values, live_load
from setu.loads.wind_loads import wind_load_cases
from setu.utils.constants import BEARING_REACTION, MAX_MOMENT, SUPPORT_SHEAR


# the design values, every critical position re-solved in OpenSees as a check, and the wind forces
def analyse(bridge, loads, tick):
    results = girder_design_values(bridge, ops=ops, **loads)
    model = build_bridge_model(bridge, ops)
    checks, live_forces = {}, []
    for key, critical in results.criticals.items():
        tick("Checking in OpenSees")
        forces = analyze_load_case(model, live_load(model, critical, results.surfaces[key]), ops)
        live_forces.append(forces)
        checks[key] = solved_at(forces[key[0]], key[1], results.stations[key])
    wind = wind_load_cases(model, loads["wind"]) if loads["wind"] else None
    return results, checks, wind, live_forces


# the response read straight off the solved girder, at the station the critical position was searched for
def solved_at(forces, response, station):
    if response == MAX_MOMENT:
        return float(forces.composite_moment_kn_m[station])
    if response == SUPPORT_SHEAR:
        return float(forces.shear_kn[station])
    if response == BEARING_REACTION:
        return forces.reaction_kn
    return float(forces.deflection_m[station])
