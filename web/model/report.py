from setu.irc6.seismic import horizontal_seismic_coefficient, vertical_seismic_coefficient
from setu.utils.constants import (BASIC, BEARING_REACTION, BIGGER_IS_WORSE, MAX_MOMENT, RARE, SEISMIC_COMBINATION, SMALLER_IS_WORSE,
                                  SUPPORT, SUPPORT_SHEAR)

from model import drawing

# the headline design values: title, response, limit state, direction
GOVERNING = (
    ("ULS sagging", MAX_MOMENT, BASIC, BIGGER_IS_WORSE),
    ("ULS seismic", MAX_MOMENT, SEISMIC_COMBINATION, BIGGER_IS_WORSE),
    ("SLS rare", MAX_MOMENT, RARE, BIGGER_IS_WORSE),
    ("ULS shear", SUPPORT_SHEAR, BASIC, SMALLER_IS_WORSE),
    ("ULS reaction", BEARING_REACTION, BASIC, BIGGER_IS_WORSE),
)


# everything the page shows, as plain JSON-ready values
def build(bridge, loads, results, checks, wind, live_forces):
    girders = range(bridge.girders.count)
    return {
        "bridge": {"span_m": bridge.span_m, "skew": bridge.skew, "girders": bridge.girders.count, "deck_width_m": bridge.width_m()},
        "design_values": {f"girder {g}": {response: {limit: {adverse: value.to_dict() for adverse, value in by_direction.items()} for limit, by_direction in by_limit.items()}
                                          for response, by_limit in results.girders[g].items()} for g in girders},
        "governing": governing(results),
        "dead_loads_unfactored": dead_loads(bridge, results),
        "deflections_m": {f"girder {g}": results.deflections[g] for g in girders},
        "deflection_limits_m": {"live_load_and_impact": bridge.span_m / 800, "total": bridge.span_m / 600},
        "fatigue_ranges": {f"girder {g}": {response: {"range": r.range, "largest": r.largest, "smallest": r.smallest, "at_m": r.at_m}
                                           for response, r in results.fatigue[g].items()} for g in girders},
        "checks": [{"girder": g, "response": response, "adverse": adverse, "searched": results.criticals[g, response, adverse].response, "solved": solved}
                   for (g, response, adverse), solved in checks.items()],
        "site": site_loads(loads, results, wind),
        "drawing": drawing.deck_drawing(bridge, results),
        "diagrams": drawing.diagrams(results, live_forces),
        "mesh": drawing.mesh_of(bridge),
        "places": {key: {"label": label, "unit": unit} for key, (_, label, unit, _) in drawing.PLACES.items()},
        "replay": {key: {g: drawing.replay(bridge, results, g, key) for g in girders} for key in drawing.PLACES},
    }


# the worst girder for each headline design value, with its combination and each load group's share
def governing(results):
    found = {}
    for title, response, limit, adverse in GOVERNING:
        girder, value = results.governing(response, limit, adverse)
        found[title] = {"girder": girder, **value.to_dict()}
    return found


# each dead load stage at midspan and at the support, unfactored
def dead_loads(bridge, results):
    dead = results.dead
    midspan = len(dead.total[0].moment_kn_m) // 2
    return {f"girder {g}": {stage: {"midspan_moment_kn_m": float(forces[g].composite_moment_kn_m[midspan]), "support_shear_kn": float(forces[g].shear_kn[SUPPORT]),
                                    "bearing_reaction_kn": forces[g].reaction_kn, "midspan_deflection_m": float(forces[g].deflection_m[midspan])}
                            for stage, forces in dead.stages.items()} for g in range(bridge.girders.count)}


# wind, seismic and temperature: the numbers behind them and what they add; None for a load left out
def site_loads(loads, results, wind):
    site = {"wind": None, "seismic": None, "temperature": None}
    if wind is not None:
        site["wind"] = {"basic_speed_mps": loads["wind"].basic_wind_speed_mps, "speed_at_deck_mps": wind.speed_at_deck_mps, "forces_kn": wind.forces_kn}
    if loads["seismic"] is not None:
        s = loads["seismic"]
        site["seismic"] = {"zone": s.zone, "soil": s.soil, "importance_factor": s.importance_factor, "period_s": s.period_s, "response_reduction": s.response_reduction,
                           "horizontal_coefficient": horizontal_seismic_coefficient(s), "vertical_coefficient": vertical_seismic_coefficient(s), "vertical_included": s.include_vertical}
    if results.thermal:
        t = results.thermal
        site["temperature"] = {"shade_max_c": loads["temperature"].shade_max_c, "shade_min_c": loads["temperature"].shade_min_c,
                               "effective_range_c": t["effective range c"], "free_bearing_movement_m": t["free bearing movement m"], "profiles": t["profiles"],
                               "stresses_kpa": {f"girder {g}": {kind: {"slab_top": st.slab_top_kpa, "slab_bottom": st.slab_bottom_kpa, "steel_top": st.steel_top_kpa,
                                                                        "steel_bottom": st.steel_bottom_kpa, "effective_slab_width_m": st.slab_width_m}
                                                                 for kind, st in by_kind.items()} for g, by_kind in t["girders"].items()}}
    return site
