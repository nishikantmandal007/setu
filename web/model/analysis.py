from setu import analyze_load_case, build_bridge_model, girder_design_values, live_load
from setu.loads.wind_loads import wind_load_cases
from setu.utils.constants import BEARING_REACTION, MAX_MOMENT, SUPPORT_SHEAR


# the design values, every critical position re-solved in OpenSees as a check, and the wind forces
def analyse(bridge, loads, tick, *, on_check=None, on_phase=None):
    results = girder_design_values(bridge, **loads)
    if on_phase is not None:
        on_phase("Checking in OpenSees", "Building the verification model")
    model = build_bridge_model(bridge)
    checks, live_forces = {}, []
    for key, critical in results.criticals.items():
        if on_phase is not None:
            on_phase("Checking in OpenSees", "Solving a critical load case", girder=key[0], response=key[1],
                     station_m=float(model.mesh.length_mesh_m[results.stations[key]]), adverse=key[2])
        forces = analyze_load_case(model, live_load(model, critical, results.surfaces[key]))
        live_forces.append(forces)
        checks[key] = solved_at(forces[key[0]], key[1], results.stations[key])
        if on_check is not None:
            on_check(key, critical, checks[key])
        tick("Checking in OpenSees")
    wind = wind_load_cases(model, loads["wind"]) if loads["wind"] else None
    return results, checks, wind, live_forces


# the response read straight off the solved girder, at the station the critical position was searched for
def solved_at(forces, response, station):
    if response == MAX_MOMENT:
        return float(forces.composite_moment_kn_m[station])
    if response == SUPPORT_SHEAR:
        return float(forces.shear_kn[station])
    if response == BEARING_REACTION:
        return forces.reaction_kn if station == 0 else forces.end_reaction_kn
    return float(forces.deflection_m[station])
